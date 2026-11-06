"""Roda a suíte inteira também no Postgres.

Sem variável, os testes usam SQLite (rápido, sem servidor). Com
REGULAIA_TESTE_PG=postgresql://... cada `db.conectar(":memory:")` vira um schema novo e
isolado no Postgres, e cada arquivo vira um schema próprio (duas conexões no mesmo
arquivo veem os mesmos dados, como no SQLite). O mesmo domínio, os mesmos testes, os dois
bancos. Testes que medem algo só do SQLite (PRAGMA, arquivo antigo) levam a marca `sqlite`.
"""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest

URL_PG = os.environ.get("REGULAIA_TESTE_PG")


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
    from regulaia import banco, db

    rodada = uuid.uuid4().hex[:8]
    criados: list[str] = []
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
        return banco.ConexaoPostgres(URL_PG, esquema=esquema)

    monkeypatch.setattr(db, "conectar", conectar)
    yield
    import psycopg

    with psycopg.connect(URL_PG, autocommit=True) as c:
        for e in criados:
            c.execute(f'DROP SCHEMA IF EXISTS "{e}" CASCADE')
