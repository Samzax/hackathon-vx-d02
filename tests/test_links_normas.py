"""O link oficial de cada norma do cadastro e o da página do DOU de cada ato (para reabrir o texto)."""

import csv
from pathlib import Path

from mitra import db, fontes

RAIZ = Path(__file__).resolve().parent.parent
SEM_FONTE_PUBLICA = {"LO 000/2023 (fictícia)"}      # licença da demo: o original é o PDF que a empresa enviou


def _normas_do_cadastro() -> set[str]:
    normas = {"Res. ANM 220/2025"}      # seed_obligations.csv não tem a coluna: é toda dessa resolução
    for f in (RAIZ / "cadastro").glob("*.csv"):
        with f.open(encoding="utf-8") as arq:
            normas |= {r["norma"] for r in csv.DictReader(arq) if r.get("norma")}
    return normas - SEM_FONTE_PUBLICA


def test_toda_norma_do_cadastro_tem_link_oficial():
    sem = sorted(n for n in _normas_do_cadastro() if not fontes.link_da_norma(n))
    assert not sem, f"normas do cadastro sem link em mitra/fontes.py OFICIAL: {sem}"
    assert all(u.startswith("https://") for u in fontes.OFICIAL.values())


def test_nome_da_norma_com_complemento_acha_o_link():
    assert fontes.link_da_norma("Lei 12.334/2010 (PNSB)") == fontes.OFICIAL["Lei 12.334/2010"]
    assert fontes.link_da_norma("Decreto MG 48.078/2020 (PAE)") == fontes.OFICIAL["Decreto MG 48.078/2020"]
    assert fontes.link_da_norma("Padrão interno") is None and fontes.link_da_norma(None) is None


def test_norma_que_entrou_pela_descoberta_usa_o_link_da_fonte():
    conn = db.conectar(":memory:")
    with conn:
        conn.execute("INSERT INTO norma_candidata (chave, jurisdicao, fonte, tipo, numero, ano, titulo, url) "
                     "VALUES ('MG:LEI:99999/2024', 'MG', 'almg', 'LEI', '99999', 2024, 'Lei 99999', "
                     "'https://www.almg.gov.br/legislacao-mineira/texto/LEI/99999/2024/')")
    assert fontes.link_da_norma("Lei MG 99.999/2024", conn).endswith("/LEI/99999/2024/")
    assert fontes.link_da_norma("Lei MG 99.999/2024") is None       # sem banco, só o cadastro


def test_link_do_dou_vem_em_https():
    assert fontes.link_do_dou("http://pesquisa.in.gov.br/imprensa/jsp/visualiza/index.jsp?data=04/08/2026"
                              "&jornal=515&pagina=68").startswith("https://pesquisa.in.gov.br/")
    assert fontes.link_do_dou("") is None and fontes.link_do_dou("javascript:alert(1)") is None


def test_ato_ganha_o_link_quando_faltava():
    """A página do DOU de ponta a ponta (radar -> mudança -> histórico) está em test_api.py."""
    conn = db.conectar(":memory:")
    aid = db.registrar_ato(conn, "dou", "x-1", "ATO X", texto="texto")
    assert conn.execute("SELECT url FROM ato WHERE id = ?", (aid,)).fetchone()["url"] is None
    assert db.registrar_ato(conn, "dou", "x-1", "ATO X", url="https://exemplo.gov.br/x") == aid
    assert conn.execute("SELECT url FROM ato WHERE id = ?", (aid,)).fetchone()["url"] == "https://exemplo.gov.br/x"
