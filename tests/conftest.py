"""Roda a suíte inteira também no Postgres.

Sem variável, os testes usam SQLite (rápido, sem servidor). Com
MITRA_TESTE_PG=postgresql://... cada `db.conectar(":memory:")` vira um schema novo e
isolado no Postgres, e cada arquivo vira um schema próprio (duas conexões no mesmo
arquivo veem os mesmos dados, como no SQLite). O mesmo domínio, os mesmos testes, os dois
bancos. Testes que medem algo só do SQLite (PRAGMA, arquivo antigo) levam a marca `sqlite`.
"""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest

URL_PG = os.environ.get("MITRA_TESTE_PG")


def pytest_configure(config):
    config.addinivalue_line("markers", "sqlite: o teste mede algo que só existe no SQLite")


def pytest_collection_modifyitems(config, items):
    if not URL_PG:
        return
    pula = pytest.mark.skip(reason="só faz sentido no SQLite")
    for item in items:
        if "sqlite" in item.keywords:
            item.add_marker(pula)


@pytest.fixture(autouse=True)
def _postgres_no_lugar_do_sqlite(monkeypatch):
    if not URL_PG:
        yield
        return
    from mitra import banco, db

    rodada = uuid.uuid4().hex[:8]
    criados: list[str] = []
    abertas: list = []
    original = db.conectar

    def conectar(caminho=db.DB_PADRAO):
        if banco.eh_url_postgres(caminho):
            return original(caminho)
        if str(caminho) == ":memory:":
            esquema = f"t_{rodada}_{len(criados)}"
        else:
            esquema = f"t_{rodada}_{hashlib.sha1(str(caminho).encode()).hexdigest()[:10]}"
        if esquema not in criados:
            criados.append(esquema)
        conn = banco.ConexaoPostgres(URL_PG, esquema=esquema)
        abertas.append(conn)
        return conn

    monkeypatch.setattr(db, "conectar", conectar)
    yield
    # Conexão que ficou aberta por um teste que falhou e ficou presa no traceback segura a transação
    # e o lock das tabelas: o DROP SCHEMA esperaria
    # para sempre. Fecha todas antes; e o lock_timeout faz falhar com erro em vez de travar o CI.
    for conn in abertas:
        try:
            conn.close()
        except Exception:
            pass
    import psycopg

    with psycopg.connect(URL_PG, autocommit=True) as c:
        c.execute("SET lock_timeout = '30s'")
        for e in criados:
            c.execute(f'DROP SCHEMA IF EXISTS "{e}" CASCADE')


@pytest.fixture(autouse=True)
def _modelos_sem_recusa_de_outro_teste():
    """A memória de modelos recusados é do processo: cada teste começa sem ela."""
    from mitra.ia import DISPONIBILIDADE

    DISPONIBILIDADE.esquecer()
    yield
    DISPONIBILIDADE.esquecer()


@pytest.fixture(autouse=True)
def _sem_extracao_automatica(monkeypatch):
    """Aprovar uma candidata dispara a extração em segundo plano (IA de verdade): nos testes vira
    no-op, para a suíte não depender de rede nem encher data/extraido/. O teste da fiação
    (test_aprovar_dispara_a_extracao_automatica) troca o no-op por um gravador."""
    from api.rotas import descoberta as rota_descoberta

    monkeypatch.setattr(rota_descoberta, "_extrair_aprovada", lambda app, chave: None)
