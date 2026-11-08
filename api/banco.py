"""A conexão de cada requisição.

- Postgres (API, AWS RDS): um pool de conexões (psycopg_pool) aberto no início do app (`abrir_pool`,
  no lifespan) e fechado no fim. Cada requisição pega uma conexão emprestada, com a mesma cara do
  sqlite3 que o domínio espera (`mitra/banco.py`), e devolve no fim. Transação que ficou aberta
  (erro no meio, leitura sem commit) volta desfeita antes da devolução: a próxima requisição que
  pegar essa conexão começa limpa, sem ver nada pela metade.
- SQLite (testes, demo): uma conexão por requisição, aberta e fechada aqui.

Uma requisição usa uma conexão só: a sessão (`seguranca.escopo`), a rota e o roteador de IA pedem
`conexao` e o FastAPI entrega a mesma.
"""

from __future__ import annotations

from contextlib import contextmanager

from fastapi import Depends, HTTPException, Request, status

from mitra import banco, db
from mitra.ia import Roteador

from .config import Config
from .observabilidade import log


def abrir_pool(cfg: Config):
    """O pool do Postgres, já com as `pool_min` conexões abertas. No SQLite, None."""
    if not cfg.postgres:
        return None
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        banco.url_psycopg(cfg.banco), min_size=cfg.pool_min, max_size=max(cfg.pool_max, cfg.pool_min),
        kwargs={"autocommit": False}, max_idle=cfg.pool_ociosa_s, timeout=cfg.pool_espera_s,
        # confere a conexão ao emprestar: depois de um failover do RDS, a quebrada é trocada, não vira 500
        check=ConnectionPool.check_connection, name="mitra-api", open=False)
    pool.open(wait=True, timeout=cfg.pool_espera_s)
    return pool


def _devolver(pool, pg) -> None:
    from psycopg import Error
    from psycopg.pq import TransactionStatus

    try:
        if not pg.closed and pg.info.transaction_status != TransactionStatus.IDLE:
            pg.rollback()
    except Error as erro:       # conexão quebrada no meio: o pool descarta e abre outra
        log.warning("rollback na devolução falhou", extra={"extra_json": {"erro": str(erro)}})
    finally:
        pool.putconn(pg)


@contextmanager
def emprestar(app):
    """Uma conexão por um instante, fora das dependências da rota: para quem não pode segurar uma
    conexão a requisição inteira (o Assistente Mitra, que faz requisições internas enquanto o modelo
    pensa, e cada uma delas pega a sua)."""
    pool = getattr(app.state, "pool", None)
    if pool is None:
        conn = db.conectar(app.state.cfg.banco)
        try:
            yield conn
        finally:
            conn.close()
        return
    from psycopg_pool import PoolTimeout

    try:
        pg = pool.getconn()
    except PoolTimeout:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "o banco está ocupado agora: tente de novo em instantes") from None
    try:
        yield banco.ConexaoPostgres.sobre(pg)
    finally:
        _devolver(pool, pg)


def conexao(request: Request):
    with emprestar(request.app) as conn:
        yield conn


def _roteador(cache) -> Roteador:
    try:
        return Roteador(cache)
    except Exception:
        return Roteador(cache, env={}, provedores={})


@contextmanager
def roteador_avulso(app):
    """O roteador de IA (custo do dia, teto) com conexão emprestada só pelo bloco `with`."""
    cfg: Config = app.state.cfg
    with emprestar(app) as conn:
        if cfg.cache == cfg.banco:
            yield _roteador(conn)
            return
        cache = db.conectar(cfg.cache)
        try:
            yield _roteador(cache)
        finally:
            cache.close()


def roteador(request: Request, conn=Depends(conexao)):
    """IA só para o que a regra não resolve. Sem chave, só a regra e as respostas em cache.

    O cache das respostas fica no mesmo banco no Postgres: usa a conexão da própria requisição (nunca
    duas do pool por requisição, que esgotariam o pool esperando umas pelas outras). Quem grava no cache
    faz commit dessa conexão, então chame a IA antes de escrever, não no meio de uma escrita. No SQLite
    o cache é outro arquivo: conexão aberta e fechada aqui."""
    cfg: Config = request.app.state.cfg
    if cfg.cache == cfg.banco:
        yield _roteador(conn)
        return
    cache = db.conectar(cfg.cache)
    try:
        yield _roteador(cache)
    finally:
        cache.close()
