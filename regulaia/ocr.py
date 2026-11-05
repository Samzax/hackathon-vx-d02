"""Texto de um PDF, inclusive escaneado.

PDF com texto selecionável: pypdf, sem custo e sem rede (é o caso dos exemplos da demo).
PDF escaneado (a página é uma foto, sem camada de texto): precisa de OCR. O OCR é configuração:

    REGULAIA_OCR=textract    Amazon Textract (DetectDocumentText), uma chamada por página,
                             na região do AWS_REGION (us-east-1 no evento). Credenciais pelo
                             perfil AWS do ambiente (AWS_PROFILE), nunca chave no código.

Sem OCR configurado, a torre não inventa: diz que o PDF é escaneado e o que fazer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO

# página com menos que isto de texto (sem espaços) é tratada como imagem
MIN_CARACTERES_POR_PAGINA = 20

SEM_OCR = ("o PDF é escaneado (as páginas são imagem, sem texto selecionável) e o OCR não está ligado "
           "nesta instalação: mande a versão digital do documento, ou ligue o OCR (REGULAIA_OCR=textract)")


@dataclass
class TextoPDF:
    texto: str
    paginas: int
    escaneadas: int = 0             # páginas sem camada de texto
    ocr: str | None = None          # nome do OCR quando parte do texto veio dele
    aviso: str | None = None        # o que dizer ao operador (OCR desligado, OCR falhou)

    @property
    def escaneado(self) -> bool:
        return self.escaneadas > 0


class Textract:
    """Amazon Textract síncrono. A API síncrona aceita PDF de uma página: o PDF é partido em páginas."""

    nome = "Amazon Textract"

    def __init__(self, cliente=None, regiao: str | None = None):
        if cliente is None:
            from . import aws

            cliente = aws.cliente("textract", regiao)
        self.cliente = cliente

    def texto(self, pagina_pdf: bytes) -> str:
        r = self.cliente.detect_document_text(Document={"Bytes": pagina_pdf})
        return "\n".join(b["Text"] for b in r.get("Blocks", []) if b.get("BlockType") == "LINE")


def ocr_configurado():
    """O OCR que o ambiente pede (REGULAIA_OCR), ou None."""
    return Textract() if os.environ.get("REGULAIA_OCR", "").strip().lower() == "textract" else None


def _pagina_sozinha(pagina) -> bytes:
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_page(pagina)
    saida = BytesIO()
    w.write(saida)
    return saida.getvalue()


def ler(conteudo: bytes, ocr="ambiente") -> TextoPDF:
    """Texto do PDF página a página; as páginas sem texto vão para o OCR, se houver.
    `ocr`: objeto com .nome e .texto(pdf_de_uma_pagina) -> str; None desliga; padrão: o do ambiente."""
    from pypdf import PdfReader

    if ocr == "ambiente":
        ocr = ocr_configurado()
    paginas = PdfReader(BytesIO(conteudo)).pages
    textos, escaneadas, aviso, usou = [], 0, None, False
    for p in paginas:
        t = p.extract_text() or ""
        if len("".join(t.split())) < MIN_CARACTERES_POR_PAGINA:
            escaneadas += 1
            if ocr is not None and aviso is None:
                try:
                    t = ocr.texto(_pagina_sozinha(p))
                    usou = True
                except Exception as e:      # rede, credencial, cota: o operador precisa saber, sem traceback
                    aviso = f"o OCR ({ocr.nome}) não respondeu: {type(e).__name__}. Tente de novo ou mande a versão digital"
        textos.append(t)
    if escaneadas and ocr is None:
        aviso = SEM_OCR
    return TextoPDF("\n".join(textos), len(paginas), escaneadas, ocr.nome if usou else None, aviso)
