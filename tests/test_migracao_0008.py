"""Migração 0008: apaga a conta da demo do nome antigo (curadoria@regulaia.demo) e as sessões dela,
e só ela: conta com outro e-mail, ou criada por alguém que não o seed, fica."""

from __future__ import annotations

import importlib.util
import os
import uuid
from pathlib import Path

import pytest

URL_PG = os.environ.get("MITRA_TESTE_PG")
pytestmark = pytest.mark.skipif(not URL_PG, reason="migração do Postgres (MITRA_TESTE_PG)")

ARQUIVO = Path(__file__).resolve().parent.parent / "migrations" / "versions" / "0008_remove_conta_demo_legada.py"


def _migracao():
    spec = importlib.util.spec_from_file_location("migracao_0008", ARQUIVO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def conn():
    from mitra import banco

    esquema = f"t_m0008_{uuid.uuid4().hex[:8]}"
    c = banco.ConexaoPostgres(URL_PG, esquema=esquema)
    yield c
    c.close()
    import psycopg

    with psycopg.connect(URL_PG, autocommit=True) as pg:
        pg.execute("SET lock_timeout = '30s'")
        pg.execute(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE')


def _conta(conn, email: str, por: str) -> int:
    with conn:
        cur = conn.execute("INSERT INTO usuario (email, nome, papel, criado_por, plataforma) VALUES (?, ?, ?, ?, 1)",
                           (email, "Curadoria", "admin", por))
    return cur.lastrowid


def _sessao(conn, uid: int) -> None:
    with conn:
        conn.execute("INSERT INTO sessao (token_hash, usuario_id, expira_em) VALUES (?, ?, ?)",
                     (uuid.uuid4().hex, uid, "2099-01-01 00:00:00"))


def _emails(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT email FROM usuario")}


def test_apaga_a_conta_legada_e_as_sessoes_dela(conn):
    velha = _conta(conn, "curadoria@regulaia.demo", "demo")
    nova = _conta(conn, "curadoria@mitra.demo", "demo")
    _sessao(conn, velha)
    _sessao(conn, nova)

    with conn:
        conn.executescript(_migracao().SQL.read_text(encoding="utf-8"))

    assert _emails(conn) == {"curadoria@mitra.demo"}
    assert [r[0] for r in conn.execute("SELECT usuario_id FROM sessao")] == [nova]


def test_conta_com_o_mesmo_email_criada_pela_ti_fica(conn):
    """Guarda do criado_por: se alguém recriou o e-mail à mão, não é a conta do seed."""
    _conta(conn, "curadoria@regulaia.demo", "ti@serraazul.demo")
    with conn:
        conn.executescript(_migracao().SQL.read_text(encoding="utf-8"))
    assert _emails(conn) == {"curadoria@regulaia.demo"}


def test_rodar_de_novo_nao_quebra(conn):
    with conn:
        for _ in range(2):
            conn.executescript(_migracao().SQL.read_text(encoding="utf-8"))
    assert _emails(conn) == set()
