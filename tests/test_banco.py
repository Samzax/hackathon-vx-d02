"""SQLite e Postgres com o mesmo esquema e a mesma interface."""

from __future__ import annotations

import re

import pytest

from regulaia import banco, db

RAIZ = db.ROOT


def _colunas_pg() -> dict[str, set[str]]:
    sql = (RAIZ / "regulaia" / "schema_pg.sql").read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", sql)
    out = {}
    for nome, corpo in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", sql, re.S):
        cols = set()
        for linha in corpo.split("\n"):
            linha = linha.strip()
            if m := re.match(r"(\w+)\s+(BIGINT|INTEGER|TEXT|DOUBLE)", linha):
                cols.add(m.group(1))
        out[nome] = cols
    return out


@pytest.mark.sqlite
def test_sqlite_e_postgres_tem_as_mesmas_tabelas_e_colunas():
    c = db.conectar(":memory:")          # aplica schema.sql e as colunas acrescentadas depois
    tabelas = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    sqlite = {t: {r[1] for r in c.execute(f"PRAGMA table_info({t})")} for t in tabelas}
    assert sqlite == _colunas_pg()


def test_migracao_inicial_e_o_esquema_do_postgres():
    """Enquanto só houver a 0001, ela é o schema_pg.sql. Mudou o esquema? Nova migração (0002)
    e o schema_pg.sql acompanha; este teste então passa a comparar com a soma das migrações."""
    versoes = sorted((RAIZ / "migrations" / "versions").glob("0*.sql"))
    assert [v.name for v in versoes] == ["0001_esquema_inicial.sql"]
    assert versoes[0].read_text(encoding="utf-8") == (RAIZ / "regulaia" / "schema_pg.sql").read_text(encoding="utf-8")


def test_traduz_interrogacao_e_porcento_fora_das_aspas():
    assert banco.traduzir("SELECT * FROM t WHERE a = ? AND b LIKE '%?%'") == \
        "SELECT * FROM t WHERE a = %s AND b LIKE '%%?%%'"
    assert banco.traduzir("SELECT 'it''s ?' , ?") == "SELECT 'it''s ?' , %s"


def test_linha_le_por_nome_e_por_posicao_como_sqlite_row():
    linha = banco.Linha(["id", "nome"], (7, "B1"))
    assert linha[0] == 7 and linha["nome"] == "B1" and dict(linha) == {"id": 7, "nome": "B1"}
    assert list(linha) == [7, "B1"] and linha.keys() == ["id", "nome"]
    with pytest.raises(IndexError):
        linha["nao_existe"]


def test_url_postgres_e_reconhecida():
    assert banco.eh_url_postgres("postgresql://u:s@h:5432/b")
    assert banco.eh_url_postgres("postgresql+psycopg://u:s@h/b")
    assert not banco.eh_url_postgres("data/regulaia.db") and not banco.eh_url_postgres(RAIZ / "x.db")
