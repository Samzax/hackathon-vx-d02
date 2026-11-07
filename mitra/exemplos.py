"""Gera os documentos fictícios usados na demo do leitor de evidências.

Uso: uv run python -m mitra.exemplos   (escreve em data/exemplos/)

Todos os nomes, números de ART e responsáveis são inventados.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from .evidencias import exemplo

AVISO = "Documento fictício gerado para demonstração (Hackathon VX). Não é um documento real."

DOCS = {
    "FIR_B3_2026-10-1Q.pdf": [
        "FICHA DE INSPEÇÃO REGULAR (FIR)",
        "Res. ANM nº 95/2022, art. 19, I",
        "",
        "Empreendedor: Mineradora Serra Azul (fictícia)",
        "Barragem: Barragem Córrego Fundo (B3)",
        "Quinzena: 1ª quinzena de outubro de 2026",
        "Data da inspeção: 09/10/2026",
        "Responsável pela inspeção: Eng. Ana Ribeiro (fictícia) - ART nº 0000000000",
        "",
        "Item inspecionado                     Situação                 Pontuação",
        "Crista                                Sem anomalia             0",
        "Talude de jusante                     Erosão superficial       1",
        "Vertedouro                            Sem anomalia             0",
        "Instrumentação (piezômetros)          Leituras normais         0",
        "",
        "Pontuação máxima de anomalia: 1",
        "Nível de emergência: sem emergência",
    ],
    "FIR_B2_2026-11-1Q_anomalia.pdf": [
        "FICHA DE INSPEÇÃO REGULAR (FIR)",
        "Res. ANM nº 95/2022, art. 19, I",
        "",
        "Empreendedor: Mineradora Serra Azul (fictícia)",
        "Barragem: Barragem Serra II (B2)",
        "Quinzena: 1ª quinzena de novembro de 2026",
        "Data da inspeção: 04/11/2026",
        "Responsável pela inspeção: Eng. Bruno Lima (fictício) - ART nº 0000000001",
        "",
        "Item inspecionado                     Situação                 Pontuação",
        "Crista                                Trinca longitudinal      10",
        "Talude de jusante                     Surgência com carreamento 10",
        "Vertedouro                            Sem anomalia             0",
        "",
        "Pontuação máxima de anomalia: 10",
        "Providência: comunicar a ANM e iniciar inspeção especial.",
    ],
    "FIR_B2_2027-08-1Q_Res220_EC3.pdf": [
        "FICHA DE INSPEÇÃO REGULAR (FIR)",
        "Res. ANM nº 220/2025, art. 38, I · Quadro I.8 (Estado de Conservação)",
        "",
        "Empreendedor: Mineradora Serra Azul (fictícia)",
        "Barragem: Barragem Serra II (B2)",
        "Quinzena: 1ª quinzena de agosto de 2027",
        "Data da inspeção: 02/08/2027",
        "Responsável pela inspeção: Eng. Bruno Lima (fictício) - ART nº 0000000003",
        "",
        "Coluna do Quadro I.8                  Situação                  Pontuação",
        "EC1 = 0   Confiabilidade das estruturas extravasoras            0",
        "EC2 = 5   Confiabilidade das estruturas de adução               5",
        "EC3 = 5   Percolação: surgência com carreamento de material     5",
        "EC4 = 0   Deformações e recalques                               0",
        "EC5 = 0   Deterioração dos taludes / paramentos                 0",
        "",
        "Providência: reportar no SIGBM e iniciar inspeção especial.",
    ],
    "Relatorio_ISE_B2_2026-11-06.pdf": [
        "RELATÓRIO DE INSPEÇÃO DE SEGURANÇA ESPECIAL (ISE)",
        "Res. ANM nº 95/2022, art. 27 · acionada pela FIR de 04/11/2026",
        "",
        "Empreendedor: Mineradora Serra Azul (fictícia)",
        "Barragem: Barragem Serra II (B2)",
        "Data da inspeção: 06/11/2026",
        "Equipe: Eng. Bruno Lima e Eng. Ana Ribeiro (fictícios) - ART nº 0000000004",
        "",
        "Anomalia                              Medida tomada             Situação",
        "Trinca longitudinal na crista         Selagem e marco de recalque  Controlada",
        "Surgência com carreamento             Filtro invertido          Sem carreamento",
        "",
        "Conclusão: anomalias controladas; registro no SIGBM feito em 05/11/2026.",
    ],
    "EIE_B2_2027-08-02_recibo_SIGBM.pdf": [
        "EXTRATO DE INSPEÇÃO ESPECIAL (EIE) - RECIBO DE ENVIO",
        "Res. ANM nº 220/2025, art. 38 §4 e art. 42 §2 · simulação do comprovante do SIGBM",
        "",
        "Empreendedor: Mineradora Serra Azul (fictícia)",
        "Barragem: Barragem Serra II (B2)",
        "Data da inspeção: 02/08/2027",
        "Data do envio: 02/08/2027",
        "Protocolo: 0000.000001/2027-00 (fictício)",
        "",
        "Anomalia reportada: EC3 - percolação com carreamento de material",
        "Situação: recebido",
    ],
    "EIR_B3_2026-10-1Q_recibo_SIGBM.pdf": [
        "EXTRATO DE INSPEÇÃO REGULAR (EIR) - RECIBO DE ENVIO",
        "Res. ANM nº 95/2022, art. 21 · simulação do comprovante do SIGBM",
        "",
        "Empreendedor: Mineradora Serra Azul (fictícia)",
        "Barragem: Barragem Córrego Fundo (B3)",
        "Data da inspeção: 09/10/2026",
        "Data do envio: 06/11/2026",
        "Protocolo: 0000.000000/2026-00 (fictício)",
        "",
        "Pontuação máxima de anomalia: 1",
        "Situação: recebido",
    ],
    "Relatorio_NR13_VP-101_exame_externo.pdf": [
        "RELATÓRIO DE INSPEÇÃO DE SEGURANÇA DO VASO DE PRESSÃO",
        "NR-13, item 13.5.4 · exame externo periódico",
        "",
        "Estabelecimento: Mineradora Serra Azul (fictícia) - usina de beneficiamento",
        "Equipamento: VP-101 Reservatório de ar comprimido da usina",
        "Categoria do vaso: III · Serviço Próprio de Inspeção (SPIE): não",
        "Tipo de exame: externo",
        "Data da inspeção: 03/11/2026",
        "Profissional habilitado: Eng. Carla Souza (fictícia) - ART nº 0000000002",
        "",
        "Item verificado                       Resultado",
        "Placa de identificação                Legível",
        "Válvula de segurança                  Calibrada (certificado vigente)",
        "Manômetro                             Aferido",
        "Costado e soldas (visual)             Sem corrosão ou deformação",
        "",
        "Conclusão: vaso apto para operação.",
    ],
    "Boletim_efluentes_2026-09.pdf": [
        "BOLETIM DE ANÁLISE DE EFLUENTES",
        "Licença de Operação nº 000/2023 (fictícia) - condicionante 2",
        "",
        "Empreendimento: Complexo Minerário Serra Azul (fictício)",
        "Ponto de coleta: saída da estação de tratamento",
        "Data da coleta: 22/09/2026",
        "Laboratório: Laboratório Exemplo Ltda. (fictício)",
        "",
        "pH 7,1 · Sólidos suspensos 18 mg/L · Óleos e graxas < 5 mg/L",
        "Resultado: dentro dos limites da licença",
    ],
}


def gerar() -> list[str]:
    destino = exemplo("x").parent
    destino.mkdir(parents=True, exist_ok=True)
    feitos = []
    for nome, linhas in DOCS.items():
        c = canvas.Canvas(str(destino / nome), pagesize=A4, invariant=True)   # mesmo PDF a cada geração
        c.setTitle(nome)
        y = A4[1] - 2.5 * cm
        for i, linha in enumerate(linhas):
            c.setFont("Helvetica-Bold" if i == 0 else "Courier" if "   " in linha else "Helvetica", 11)
            c.drawString(2 * cm, y, linha)
            y -= 0.6 * cm
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(2 * cm, 1.5 * cm, AVISO)
        c.save()
        feitos.append(nome)
    for nome, original in ESCANEADOS.items():
        (destino / nome).write_bytes(pdf_escaneado(DOCS[original]))
        feitos.append(nome)
    return feitos


# cópia "escaneada" (a página é uma imagem, sem texto selecionável) para mostrar o caminho do OCR
ESCANEADOS = {"FIR_B3_2026-10-1Q_escaneada.pdf": "FIR_B3_2026-10-1Q.pdf"}


def pdf_escaneado(linhas: list[str]) -> bytes:
    """Desenha as linhas numa imagem e põe a imagem numa página A4: o PDF não tem texto,
    como o de uma ficha impressa, assinada e escaneada."""
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader

    largura, altura = 1240, 1754                       # A4 a 150 dpi
    img = Image.new("L", (largura, altura), 255)
    d = ImageDraw.Draw(img)
    import reportlab

    # Vera vem com o reportlab (tem acentos; a fonte padrão do Pillow não tem) e existe também no Linux do Docker
    fonte = ImageFont.truetype(str(Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"), 22)
    y = 120
    for linha in [*linhas, "", AVISO]:
        d.text((110, y), linha, fill=0, font=fonte)
        y += 36
    png = BytesIO()
    img.save(png, format="PNG")
    saida = BytesIO()
    c = canvas.Canvas(saida, pagesize=A4, invariant=True)
    c.drawImage(ImageReader(BytesIO(png.getvalue())), 0, 0, width=A4[0], height=A4[1])
    c.save()
    return saida.getvalue()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(gerar()))
