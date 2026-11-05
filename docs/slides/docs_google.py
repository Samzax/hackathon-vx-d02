"""Converte a análise de mercado e o roteiro do pitch em .docx, para importar no Google Docs.

Uso (fora das dependências do projeto):
    uv run --no-project --with pypandoc_binary --with python-docx python docs/slides/docs_google.py
Saída em docs/slides/saida/ (fora do Git). O Markdown do repositório continua sendo a fonte:
os testes conferem os números lá, não no Google Docs.
"""
from pathlib import Path

import pypandoc
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = Path(__file__).resolve().parent / "saida"
DOCS = {
    "ANALISE_MERCADO.md": "RegulaIA_analise_de_mercado.docx",
    "PITCH.md": "RegulaIA_roteiro_do_pitch.docx",
}


def bordas(tabela, cor="BFC6CC"):
    """O pandoc gera tabela sem borda; no Google Docs ela fica ilegível."""
    props = tabela._tbl.tblPr
    caixa = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{lado}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:color"), cor)
        caixa.append(b)
    props.append(caixa)
    for celula in tabela.rows[0].cells:          # cabeçalho em negrito
        for p in celula.paragraphs:
            for r in p.runs:
                r.bold = True


def main():
    SAIDA.mkdir(exist_ok=True)
    for md, docx in DOCS.items():
        destino = SAIDA / docx
        pypandoc.convert_file(str(RAIZ / "docs" / md), "docx", format="gfm", outputfile=str(destino))
        doc = Document(destino)
        for t in doc.tables:
            bordas(t)
        doc.save(destino)
        print(destino)


if __name__ == "__main__":
    main()
