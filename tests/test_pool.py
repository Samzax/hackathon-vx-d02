"""O pool de conexões da API no Postgres (api/banco.py).

No Postgres a API empresta conexões de um psycopg_pool; no SQLite abre uma por requisição. Os testes
do pool só rodam com REGULAIA_TESTE_PG: cada um num schema próprio, com as conexões marcadas por
`application_name` para contar no `pg_stat_activity` o que ficou aberto no servidor."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient

from api.banco import conexao
from api.config import Config
from api.main import PREFIXO, criar_app
from tests.conftest import URL_PG

TOKEN = "token-do-teste-do-pool"
so_postgres = pytest.mark.skipif(not URL_PG, reason="o pool é só do Postgres: rode com REGULAIA_TESTE_PG")


@pytest.fixture
def pg_isolado():
    """Um schema só deste teste e uma URL cujas conexões caem nele e se identificam no servidor."""
    import psycopg

    nome = f"t_pool_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(URL_PG, autocommit=True) as c:
        c.execute(f'CREATE SCHEMA "{nome}"')
    sep = "&" if "?" in URL_PG else "?"
    yield f"{URL_PG}{sep}options=-csearch_path%3D{nome}&application_name={nome}", nome
    with psycopg.connect(URL_PG, autocommit=True) as c:
        c.execute("SET lock_timeout = '30s'")
        c.execute(f'DROP SCHEMA IF EXISTS "{nome}" CASCADE')


def _cfg(url: str, tmp_path, **pool) -> Config:
    return Config(banco=url, banco_cache=None, montar_demo=False, token_servico=TOKEN,
                  armazenamento=str(tmp_path / "uploads"), front=str(tmp_path / "sem-front"), **pool)


def _app(cfg: Config):
    """A API de verdade com três rotas a mais: uma que segura a conexão, uma que cai no meio de uma
    escrita (erro inesperado e recusa) e uma que lê o que a anterior tentou gravar."""
    app = criar_app(cfg)

    @app.get("/teste/lenta")
    def lenta(conn=Depends(conexao)):
        conn.execute("SELECT pg_sleep(0.3)").fetchone()
        return {"ok": True}

    @app.post("/teste/cai-no-meio")
    def cai(recusa: bool = False, conn=Depends(conexao)):
        conn.execute("INSERT INTO empresa (nome, ficticia) VALUES (?, 1)", ("gravada pela metade",))
        if recusa:
            raise HTTPException(403, "recusada depois de escrever")
        raise RuntimeError("caiu no meio da requisição")

    @app.get("/teste/empresas")
    def empresas(conn=Depends(conexao)):
        return [r["nome"] for r in conn.execute("SELECT nome FROM empresa")]

    return app


def _no_servidor(nome: str) -> list[str]:
    """O estado de cada conexão aberta no servidor por este teste (idle, idle in transaction...)."""
    import psycopg

    with psycopg.connect(URL_PG, autocommit=True) as c:
        return sorted(r[0] for r in c.execute(
            "SELECT state FROM pg_stat_activity WHERE application_name = %s", (nome,)))


def _ate(condicao, segundos: float = 10.0) -> bool:
    """Fechar conexão e encolher o pool não são instantâneos no servidor: espera um pouco."""
    fim = time.monotonic() + segundos
    while not condicao():
        if time.monotonic() > fim:
            return False
        time.sleep(0.05)
    return True


def test_no_sqlite_e_uma_conexao_por_requisicao(tmp_path):
    cfg = Config(banco=str(tmp_path / "api.db"), banco_cache=str(tmp_path / "cache.db"), montar_demo=False,
                 armazenamento=str(tmp_path / "uploads"), front=str(tmp_path / "sem-front"))
    app = criar_app(cfg)
    with TestClient(app) as c:
        assert app.state.pool is None
        assert c.get("/health").json()["status"] == "ok"


@so_postgres
def test_pool_empresta_e_devolve_em_sequencia_e_em_paralelo_sem_vazar(pg_isolado, tmp_path):
    url, nome = pg_isolado
    app = _app(_cfg(url, tmp_path, pool_min=1, pool_max=4, pool_ociosa_s=0.2))
    with TestClient(app) as c:
        pool = app.state.pool
        assert pool is not None and pool.get_stats()["pool_size"] == 1
        h = {"Authorization": f"Bearer {TOKEN}"}
        for _ in range(15):         # em sequência: a mesma conexão, devolvida a cada requisição
            assert c.get("/health").json()["banco"] == "postgres"
            assert c.get(PREFIXO + "/empresas", headers=h).status_code == 200
            assert c.get(PREFIXO + "/empresas", headers={"Authorization": "Bearer errado"}).status_code == 401
        st = pool.get_stats()
        assert (st["pool_size"], st["pool_available"], st["connections_num"]) == (1, 1, 1)
        assert _no_servidor(nome) == ["idle"]

        with ThreadPoolExecutor(8) as ex:   # em paralelo: o pool cresce até o máximo e todas voltam
            rs = list(ex.map(lambda _: c.get("/teste/lenta"), range(8)))
        assert [r.status_code for r in rs] == [200] * 8
        st = pool.get_stats()
        assert st["connections_num"] > 1 and st["pool_size"] <= 4
        assert st["pool_available"] == st["pool_size"] and not st.get("requests_errors")

        # parada, a conexão que sobra acima do mínimo fecha: o pool volta a 1, no servidor também
        assert _ate(lambda: pool.get_stats()["pool_size"] == 1), pool.get_stats()
        assert _ate(lambda: _no_servidor(nome) == ["idle"]), _no_servidor(nome)
    assert app.state.pool is None
    assert _ate(lambda: _no_servidor(nome) == []), _no_servidor(nome)     # app parou: nenhuma ficou aberta


@so_postgres
def test_requisicao_que_cai_no_meio_nao_deixa_transacao_para_a_proxima(pg_isolado, tmp_path):
    url, nome = pg_isolado
    app = _app(_cfg(url, tmp_path, pool_min=1, pool_max=1))     # uma conexão só: a próxima pega a mesma
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/teste/cai-no-meio")
        assert r.status_code == 500 and r.json()["detail"] == "erro inesperado"
        assert _no_servidor(nome) == ["idle"]           # nada de "idle in transaction"
        assert c.get("/teste/empresas").json() == []    # a mesma conexão não vê o INSERT pela metade
        r = c.post("/teste/cai-no-meio", params={"recusa": True})
        assert r.status_code == 403 and r.json()["detail"] == "recusada depois de escrever"
        assert _no_servidor(nome) == ["idle"]
        assert c.get("/teste/empresas").json() == []
        st = app.state.pool.get_stats()
        assert (st["connections_num"], st["pool_size"]) == (1, 1) and not st.get("returns_bad")


@so_postgres
def test_pool_esgotado_responde_503_em_vez_de_travar(pg_isolado, tmp_path):
    url, nome = pg_isolado
    app = _app(_cfg(url, tmp_path, pool_min=1, pool_max=1, pool_espera_s=0.1))
    with TestClient(app) as c, ThreadPoolExecutor(1) as ex:
        segura = ex.submit(c.get, "/teste/lenta")
        assert _ate(lambda: app.state.pool.get_stats()["pool_available"] == 0, 5)
        r = c.get("/health")
        assert r.status_code == 503 and "ocupado" in r.json()["detail"]
        assert segura.result().status_code == 200
        assert c.get("/health").status_code == 200
