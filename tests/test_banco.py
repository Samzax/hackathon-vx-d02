"""SQLite e Postgres com o mesmo esquema e a mesma interface."""

from __future__ import annotations

import re

import pytest

from mitra import banco, db

RAIZ = db.ROOT


def _colunas_pg() -> dict[str, set[str]]:
    return _colunas((RAIZ / "mitra" / "schema_pg.sql").read_text(encoding="utf-8"))


def _colunas(sql: str) -> dict[str, set[str]]:
    """{tabela: colunas} dos CREATE TABLE de um script."""
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


def test_as_migracoes_somadas_dao_o_esquema_do_postgres():
    """A 0001 é o schema_pg.sql congelado no primeiro deploy; as seguintes acrescentam colunas
    (ALTER TABLE ... ADD COLUMN IF NOT EXISTS) ou tabelas. Somadas, têm de dar as tabelas e colunas
    do schema_pg.sql de hoje. Mudou o esquema? Nova migração, e o schema_pg.sql acompanha."""
    pasta = RAIZ / "migrations" / "versions"
    versoes = sorted(pasta.glob("0*.sql"))
    assert [v.name[:4] for v in versoes] == [f"{i:04d}" for i in range(1, len(versoes) + 1)]
    assert {p.stem for p in pasta.glob("0*.py")} == {v.stem for v in versoes}    # cada .sql tem a sua revisão
    soma: dict[str, set[str]] = {}
    for v in versoes:
        sql = re.sub(r"--[^\n]*", "", v.read_text(encoding="utf-8"))
        for tabela, cols in _colunas(sql).items():
            soma.setdefault(tabela, set()).update(cols)
        for tabela, coluna in re.findall(r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)", sql):
            soma[tabela].add(coluna)
    assert soma == _colunas_pg()


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
    assert not banco.eh_url_postgres("data/mitra.db") and not banco.eh_url_postgres(RAIZ / "x.db")
