"""Boletim e plano de transição em PDF, para o gestor abrir sem saber o que é Markdown.

Converte só o Markdown que a torre e os documentos do repositório usam: `# título`, `## seção`,
`### subseção`, `- item`, `  - subitem`, `1. item numerado`, tabela `| a | b |`, `**negrito**`,
`código` e parágrafos. Também gera o PDF de um documento do repositório:

    uv run python -m regulaia.pdf docs/ANALISE_MERCADO.md analise_de_mercado.pdf "Análise de mercado"

As fontes padrão do PDF não têm emoji: cada emoji de status vira palavra ou some, para não aparecer
quadrado preto no lugar.
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
    """Escapa para o Paragraph do reportlab e converte **negrito** e `código`."""
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(limpar(texto)))
    return re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', t)


def _celulas(linha: str) -> list[str]:
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def _tabela(linhas: list[str], estilo_celula, estilo_cabecalho, largura: float):
    """Tabela de markdown (| a | b |) com o cabeçalho repetido a cada página; a linha |---| é ignorada.
    Largura das colunas proporcional ao texto mais longo de cada uma, com mínimo para não espremer números."""
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    linhas = [l for l in linhas if not re.fullmatch(r"\|?[\s:|-]+\|?", l.strip())]
    dados = [_celulas(l) for l in linhas]
    n = max(len(d) for d in dados)
    dados = [d + [""] * (n - len(d)) for d in dados]
    # nenhuma coluna mais estreita que a palavra mais longa dela ("Barragens" não quebra em "Barragen s")
    pesos = [max(max(len(p) for d in dados for p in limpar(d[i]).split() or [""]) + 4,
                 min(60, max(len(limpar(d[i])) for d in dados))) for i in range(n)]
    larguras = [largura * p / sum(pesos) for p in pesos]
    celulas = [[Paragraph(_inline(c), estilo_cabecalho if i == 0 else estilo_celula) for c in d]
               for i, d in enumerate(dados)]
    t = Table(celulas, colWidths=larguras, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c2cc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


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
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=10.5, spaceBefore=6, spaceAfter=3),
        "num": ParagraphStyle("num", parent=base["BodyText"], fontSize=9.5, leading=12.5, leftIndent=16,
                              bulletIndent=2, spaceAfter=2),
        "td": ParagraphStyle("td", parent=base["BodyText"], fontSize=8, leading=10),
        "th": ParagraphStyle("th", parent=base["BodyText"], fontSize=8, leading=10, fontName="Helvetica-Bold"),
    }
    corpo = []
    linhas = md.splitlines()
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        i += 1
        if linha.lstrip().startswith("|"):
            bloco = [linha]
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                bloco.append(linhas[i])
                i += 1
            corpo.append(_tabela(bloco, estilo["td"], estilo["th"], A4[0] - 4 * cm))
            corpo.append(Spacer(1, 4))
        elif not linha.strip():
            corpo.append(Spacer(1, 4))
        elif linha.startswith("### "):
            corpo.append(Paragraph(_inline(linha[4:]), estilo["h3"]))
        elif m := re.match(r"(\d{1,2})\. (.+)", linha):
            corpo.append(Paragraph(_inline(m.group(2)), estilo["num"], bulletText=f"{m.group(1)}."))
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


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 3:
        sys.exit("uso: python -m regulaia.pdf entrada.md saida.pdf [título do rodapé]")
    entrada, saida = Path(sys.argv[1]), Path(sys.argv[2])
    saida.write_bytes(de_markdown(entrada.read_text(encoding="utf-8"),
                                  sys.argv[3] if len(sys.argv) > 3 else entrada.stem))
    print(f"{saida} ({saida.stat().st_size // 1024} KB)")
