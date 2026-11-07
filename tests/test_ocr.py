"""PDF escaneado: a torre percebe que a página é imagem, manda para o OCR (se ligado) e não inventa."""

from datetime import date
from io import BytesIO

import pytest

from mitra import db, demo, evidencias as ev, exemplos, ocr

pytest.importorskip("PIL")
HOJE = date(2026, 11, 7)
FIR_B3 = "FIR_B3_2026-10-1Q.pdf"


@pytest.fixture(scope="module")
def escaneada() -> bytes:
    return exemplos.pdf_escaneado(exemplos.DOCS[FIR_B3])


class OCRFalso:
    """Faz o papel do Textract: devolve o texto da ficha, e guarda o que recebeu."""
    nome = "OCR de teste"

    def __init__(self, texto="", erro=None):
        self.texto_fixo, self.erro, self.recebidos = texto, erro, []

    def texto(self, pagina_pdf: bytes) -> str:
        self.recebidos.append(pagina_pdf)
        if self.erro:
            raise self.erro
        return self.texto_fixo


def _imagem(pdf: bytes) -> tuple:
    """A imagem da página, descomprimida. Os bytes do PDF mudam com o zlib do Python (zlib-ng no
    Python 3.14 e em builds do Linux, zlib 1.3 no Windows) mesmo com os mesmos pixels."""
    from pypdf import PdfReader

    xobjetos = PdfReader(BytesIO(pdf)).pages[0]["/Resources"]["/XObject"]
    (img,) = [xobjetos[nome].get_object() for nome in xobjetos]
    return img["/Width"], img["/Height"], img.get_data()


def test_exemplo_escaneado_esta_nos_exemplos_e_e_igual_ao_gerado(escaneada):
    """O PDF guardado é o que o gerador faz hoje. No Windows, onde o exemplo é gerado, pixel a pixel. Em
    outro sistema o FreeType do Pillow desenha a mesma fonte (Vera.ttf) com hinting diferente e as letras
    andam alguns pixels: lá, mesma página, as mesmas linhas de texto e a mesma tinta em cada linha (±5%)."""
    import sys

    caminho = ev.exemplo("FIR_B3_2026-10-1Q_escaneada.pdf")
    assert caminho.exists()
    (w, h, a), (w2, h2, b) = _imagem(caminho.read_bytes()), _imagem(escaneada)
    assert (w, h) == (w2, h2) and len(a) == len(b) == w * h
    if sys.platform == "win32":
        assert a == b
        return

    def tinta_por_linha(px: bytes) -> list[int]:
        # o gerador escreve uma linha a cada 36 px a partir de y = 120
        return [sum(1 for v in px[y * w:(y + 36) * w] if v < 128) for y in range(120, h - 36, 36)]

    ta, tb = tinta_por_linha(a), tinta_por_linha(b)
    assert [t > 0 for t in ta] == [t > 0 for t in tb], "linhas de texto diferentes"
    assert all(abs(x - y) <= 0.05 * max(x, y) for x, y in zip(ta, tb, strict=True)), list(zip(ta, tb, strict=True))


def test_escaneado_sem_ocr_avisa_e_nao_inventa(escaneada):
    r = ocr.ler(escaneada, ocr=None)
    assert (r.paginas, r.escaneadas, r.ocr) == (1, 1, None)
    assert not "".join(r.texto.split())
    assert r.aviso == ocr.SEM_OCR


def test_pdf_digital_nao_chama_o_ocr():
    falso = OCRFalso("não deveria ser usado")
    r = ocr.ler(ev.exemplo(FIR_B3).read_bytes(), ocr=falso)
    assert not r.escaneado and r.aviso is None and r.ocr is None and not falso.recebidos
    assert "FICHA DE INSPEÇÃO REGULAR" in r.texto


def test_texto_do_ocr_passa_pelas_mesmas_regras(escaneada):
    falso = OCRFalso("\n".join(exemplos.DOCS[FIR_B3]))
    r = ocr.ler(escaneada, ocr=falso)
    assert r.ocr == "OCR de teste" and r.aviso is None
    assert len(falso.recebidos) == 1 and falso.recebidos[0].startswith(b"%PDF")
    conn = db.conectar(":memory:")
    demo.montar(conn)
    le = ev.ler(conn, r.texto, 1, HOJE)
    assert (le.ativo, le.obrigacao, le.periodo) == ("B3", "R95-01", "2026-10-1Q") and le.completa


def test_ocr_fora_do_ar_vira_aviso_sem_traceback(escaneada):
    r = ocr.ler(escaneada, ocr=OCRFalso(erro=ConnectionError("sem rede")))
    assert r.escaneado and not "".join(r.texto.split())
    assert r.aviso.startswith("o OCR (OCR de teste) não respondeu: ConnectionError")


def test_textract_manda_uma_pagina_por_chamada_e_junta_as_linhas():
    from pypdf import PdfReader, PdfWriter

    class ClienteTextract:
        def __init__(self):
            self.chamadas = []

        def detect_document_text(self, Document):
            self.chamadas.append(len(PdfReader(BytesIO(Document["Bytes"])).pages))
            return {"Blocks": [{"BlockType": "PAGE"},
                               {"BlockType": "LINE", "Text": "FICHA DE INSPEÇÃO REGULAR (FIR)"},
                               {"BlockType": "WORD", "Text": "FICHA"},
                               {"BlockType": "LINE", "Text": "Barragem: Barragem Córrego Fundo (B3)"}]}

    # duas páginas escaneadas no mesmo PDF
    w = PdfWriter()
    for _ in range(2):
        w.add_page(PdfReader(BytesIO(exemplos.pdf_escaneado(["x"]))).pages[0])
    duas = BytesIO()
    w.write(duas)
    cliente = ClienteTextract()
    r = ocr.ler(duas.getvalue(), ocr=ocr.Textract(cliente=cliente))
    assert cliente.chamadas == [1, 1]                  # a API síncrona só aceita uma página
    assert r.escaneadas == 2 and r.ocr == "Amazon Textract"
    assert r.texto.count("FICHA DE INSPEÇÃO REGULAR (FIR)\nBarragem: Barragem Córrego Fundo (B3)") == 2
    assert "FICHA\n" not in r.texto                     # WORD não duplica a LINE


def test_ocr_do_ambiente(monkeypatch):
    monkeypatch.delenv("MITRA_OCR", raising=False)
    assert ocr.ocr_configurado() is None
    pytest.importorskip("boto3")
    monkeypatch.setenv("MITRA_OCR", "textract")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    assert isinstance(ocr.ocr_configurado(), ocr.Textract)       # cria o cliente sem chamar a AWS
