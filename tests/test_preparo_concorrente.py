"""Dois workers da API sobem ao mesmo tempo no mesmo Postgres: o preparo do banco roda um de cada vez.

Regressão do deploy de 7/11/2026: com --workers 2, os dois viam "a conta da demo não existe", os dois
inseriam e o segundo caía em UniqueViolation (usuario_email_key), derrubando o container.
"""

from __future__ import annotations

import os
import threading
import uuid

import pytest

from api import main
from api.config import Config
from mitra import usuarios

URL_PG = os.environ.get("MITRA_TESTE_PG")
pytestmark = pytest.mark.skipif(not URL_PG, reason="a trava é do Postgres (MITRA_TESTE_PG)")


@pytest.fixture
def url_esquema_novo():
    """URL do Postgres de teste apontando para um schema vazio só deste teste."""
    import psycopg

    esquema = f"t_preparo_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(URL_PG, autocommit=True) as c:
        c.execute(f'CREATE SCHEMA "{esquema}"')
    sep = "&" if "?" in URL_PG else "?"
    yield f"{URL_PG}{sep}options=-csearch_path%3D{esquema}"
    with psycopg.connect(URL_PG, autocommit=True) as c:
        c.execute("SET lock_timeout = '30s'")
        c.execute(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE')


def _corrida(cfg: Config, monkeypatch) -> list[BaseException]:
    """Os dois workers param depois de olhar se a conta existe e antes de inserir: sem trava, os dois
    passam pela barreira juntos e inserem; com trava, o segundo nem chega a olhar até o primeiro acabar
    (a barreira estoura por tempo e cada um segue sozinho)."""
    barreira = threading.Barrier(2)
    original = usuarios.por_email
    ja_parou: set[int] = set()

    def por_email(conn, email):
        achado = original(conn, email)
        eu = threading.get_ident()
        if eu not in ja_parou:
            ja_parou.add(eu)
            try:
                barreira.wait(timeout=3)
            except threading.BrokenBarrierError:
                pass
        return achado

    monkeypatch.setattr(usuarios, "por_email", por_email)
    erros: list[BaseException] = []

    def worker():
        try:
            main._preparar_banco(cfg)
        except BaseException as e:      # noqa: BLE001 - o teste quer ver qualquer falha do worker
            erros.append(e)

    ts = [threading.Thread(target=worker) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=60)
    return erros


def test_dois_workers_preparam_o_banco_sem_conflito(url_esquema_novo, monkeypatch):
    cfg = Config(banco=url_esquema_novo, montar_demo=False)
    assert _corrida(cfg, monkeypatch) == []

    from mitra import db
    conn = db.conectar(url_esquema_novo)
    try:
        emails = [r[0] for r in conn.execute("SELECT email FROM usuario")]
    finally:
        conn.close()
    assert emails and len(emails) == len(set(emails))       # cada conta da demo uma vez só


def test_sem_a_trava_a_corrida_acontece(url_esquema_novo, monkeypatch):
    """Prova que o teste de cima mede a trava: tirando-a, a mesma corrida quebra."""
    from contextlib import nullcontext

    monkeypatch.setattr(main, "_um_processo_por_vez", lambda cfg: nullcontext())
    cfg = Config(banco=url_esquema_novo, montar_demo=False)
    erros = _corrida(cfg, monkeypatch)
    assert any("usuario_email_key" in str(e) or "UNIQUE" in str(e).upper() for e in erros)
