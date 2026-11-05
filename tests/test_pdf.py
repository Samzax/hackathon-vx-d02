from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

from regulaia import db, demo, pdf, torre

HOJE, DESDE = date(2026, 11, 7), date(2026, 5, 1)


@pytest.fixture(scope="module")
def conn():
    c = db.conectar(":memory:")
    demo.montar(c)
    return c


def _texto(conteudo: bytes) -> tuple[int, str]:
    r = PdfReader(BytesIO(conteudo))
    return len(r.pages), "\n".join(p.extract_text() for p in r.pages)


def test_limpar_tira_emoji_e_mantem_acento_e_travessao():
    assert pdf.limpar("## 🔴 Atrasadas (4)") == "## Atrasadas (4)"
    assert pdf.limpar("**OB-01** — prazo: 02/08/2027 → 26/12/2029") == "**OB-01** — prazo: 02/08/2027 -> 26/12/2029"
    assert pdf.limpar("até 15/11/2026 🟡") == "até 15/11/2026 (já em amarelo na torre)"
    assert pdf.limpar("Inspeção · 1ª quinzena · §1 · ⚠️ ok") == "Inspeção · 1ª quinzena · §1 · ok"


def test_boletim_em_pdf_le_como_o_markdown(conn):
    md = torre.boletim(conn, 1, HOJE, DESDE)
    paginas, texto = _texto(pdf.de_markdown(md, "Boletim · Diretoria"))
    assert paginas == 1
    for trecho in ("Boletim regulatório — Diretoria", "Atrasadas (4)", "1ª quinzena de outubro/2026",
                   "3 já em amarelo na torre", "página 1"):
        assert trecho in texto, trecho
    assert "**" not in texto and "?" not in texto      # sem marcação crua nem caractere que a fonte não tem


def test_plano_de_transicao_em_pdf_tem_todas_as_barragens(conn):
    md = torre.plano_transicao(conn, 1, date(2027, 8, 2), HOJE)
    paginas, texto = _texto(pdf.de_markdown(md, "Plano de transição · Diretoria"))
    assert paginas > 1 and f"página {paginas}" in texto
    assert "4 ativos afetados · 1 obrigação sem equivalente" in texto     # singular certo
    for barragem in ("B1 · Barragem Serra I", "B2 · Barragem Serra II", "B3 · Barragem Córrego Fundo",
                     "B4 · Barragem Vale do Cedro"):
        assert barragem in texto
    assert "?" not in texto
