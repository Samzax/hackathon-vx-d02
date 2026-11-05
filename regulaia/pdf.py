"""Boletim e plano de transição em PDF, para o gestor abrir sem saber o que é Markdown.

Converte só o Markdown que a torre gera: `# título`, `## seção`, `- item`, `  - subitem`,
`**negrito**` e parágrafos. As fontes padrão do PDF não têm emoji: cada emoji de status vira
palavra ou some, para não aparecer quadrado preto no lugar.
"""

from __future__ import annotations

import re
from io import BytesIO
from xml.sax.saxutils import escape

# emoji que carrega informação vira palavra; o resto (decoração) sai
_EMOJI_TEXTO = {
    " 🟡": " (já em amarelo na torre)",
    "🔁": "",
    "🆕": "",
    "❌": "",
}
_SIMBOLOS = {"→": "->", "≥": ">=", "≤": "<=", "✓": "ok"}
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]")


def limpar(texto: str) -> str:
    """Só o que as fontes padrão do PDF (WinAnsi, a cp1252) conseguem desenhar: o travessão fica."""
    for k, v in {**_EMOJI_TEXTO, **_SIMBOLOS}.items():
        texto = texto.replace(k, v)
    texto = _EMOJI.sub("", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto).replace("— ,", "—,").strip()
    return texto.encode("cp1252", "replace").decode("cp1252")


def _inline(texto: str) -> str:
    """Escapa para o Paragraph do reportlab e converte **negrito**."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(limpar(texto)))


def de_markdown(md: str, titulo_documento: str = "RegulaIA") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    base = getSampleStyleSheet()
    estilo = {
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=16, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=4),
        "p": ParagraphStyle("p", parent=base["BodyText"], fontSize=9.5, leading=12.5),
        "li": ParagraphStyle("li", parent=base["BodyText"], fontSize=9.5, leading=12.5, leftIndent=12,
                             bulletIndent=2, spaceAfter=2),
        "li2": ParagraphStyle("li2", parent=base["BodyText"], fontSize=9, leading=11.5, leftIndent=26,
                              bulletIndent=16, textColor="#444444"),
        "rodape": ParagraphStyle("rodape", parent=base["BodyText"], fontSize=8, textColor="#666666"),
    }
    corpo = []
    for linha in md.splitlines():
        if not linha.strip():
            corpo.append(Spacer(1, 4))
        elif linha.startswith("# "):
            corpo.append(Paragraph(_inline(linha[2:]), estilo["h1"]))
        elif linha.startswith("## "):
            corpo.append(Paragraph(_inline(linha[3:]), estilo["h2"]))
        elif linha.startswith("  - "):
            corpo.append(Paragraph(_inline(linha[4:]), estilo["li2"], bulletText="–"))
        elif linha.startswith("- "):
            corpo.append(Paragraph(_inline(linha[2:]), estilo["li"], bulletText="•"))
        elif linha.startswith("Gerado pela RegulaIA"):
            corpo.append(Paragraph(_inline(linha), estilo["rodape"]))
        else:
            corpo.append(Paragraph(_inline(linha), estilo["p"]))
    rodape = limpar(titulo_documento)

    def numerar(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillGray(0.45)
        canvas.drawString(2 * cm, 1.1 * cm, f"RegulaIA · {rodape}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"página {doc.page}")
        canvas.restoreState()

    saida = BytesIO()
    SimpleDocTemplate(saida, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.8 * cm, title=rodape, author="RegulaIA").build(
        corpo, onFirstPage=numerar, onLaterPages=numerar)
    return saida.getvalue()
