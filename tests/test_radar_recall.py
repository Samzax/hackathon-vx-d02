"""Gabarito do radar do DOU (camada 0, sem IA): o que TEM de entrar e o que fica fora.

Caso real que motivou a ampliação (7/11/2026): a Portaria MTE 105/2026, que altera a NR-22 — uma NR
que está no catálogo —, passava no DOU e era descartada quando o filtro era só "é da ANM?". O mesmo
valia para lei federal alterando a Lei 12.334 e para resolução da ANA. Falso negativo aqui é
estrutural: o ato nunca chegaria a ninguém. As categorias abaixo são as reais do XML da Imprensa
Nacional (amostra de agosto/2026)."""

from __future__ import annotations

from datetime import date

from api.jobs import motivo_interesse
from collector.dou import ORGAOS_RADAR, orgao_de_interesse
from collector.xml_dou import XmlAct
from mitra import descoberta

CFG = descoberta.temas()


def ato(category: str, art_type: str, identifica: str = "", ementa: str = "") -> XmlAct:
    return XmlAct("1", "n.xml", "DO1", art_type, date(2026, 8, 3), category,
                  "1", "", "", identifica, ementa, "")


DEVEM_ENTRAR = [
    (ato("Ministério de Minas e Energia/Agência Nacional de Mineração/Gabinete do Diretor-Geral",
         "Resolução", "RESOLUÇÃO ANM Nº 245, DE 31 DE JULHO DE 2026",
         "Altera o art. 87 da Resolução ANM nº 220, de 16 de outubro de 2025."), "ANM"),
    (ato("Ministério do Trabalho e Emprego/Gabinete do Ministro",
         "Portaria", "PORTARIA MTE Nº 105, DE 11 DE FEVEREIRO DE 2026",
         "Altera a Norma Regulamentadora nº 22 e aprova o Anexo V - Poeiras Minerais."), "MTE"),
    (ato("Atos do Poder Legislativo", "Lei", "LEI Nº 15.355, DE 26 DE JUNHO DE 2026",
         "Altera a Lei nº 12.334, de 20 de setembro de 2010, que estabelece a PNSB."), "lei federal"),
    (ato("Atos do Poder Executivo", "Decreto", "DECRETO Nº 12.345, DE 3 DE AGOSTO DE 2026",
         "Regulamenta dispositivos da Lei nº 12.334, de 20 de setembro de 2010."), "decreto"),
    (ato("Ministério da Integração e do Desenvolvimento Regional/Agência Nacional de Águas e "
         "Saneamento Básico", "Resolução", "RESOLUÇÃO ANA Nº 999, DE 3 DE AGOSTO DE 2026",
         "Dispõe sobre a segurança de barragens fiscalizadas pela ANA."), "ANA"),
    (ato("Ministério do Meio Ambiente e Mudança do Clima/Instituto Chico Mendes de Conservação da "
         "Biodiversidade", "Portaria", "PORTARIA ICMBIO Nº 10, DE 3 DE AGOSTO DE 2026",
         "Aprova plano de manejo."), "meio ambiente"),
    # órgão fora da lista, mas a ementa cita termo da carteira: entra pelo paraquedas dos temas
    (ato("Ministério de Minas e Energia/Gabinete do Ministro", "Portaria",
         "PORTARIA MME Nº 700, DE 3 DE AGOSTO DE 2026",
         "Dispõe sobre diretrizes para pilhas de estéril e disposição de rejeitos."), "termos:"),
]

FICAM_FORA = [
    # despacho da ANM: ato individual (um processo, uma empresa), não normativo
    ato("Ministério de Minas e Energia/Agência Nacional de Mineração/Superintendência de Outorga",
        "Despacho", "DESPACHO DE 3 DE AGOSTO DE 2026", "Defere o requerimento de lavra."),
    # órgão fora da lista, sem termo nenhum da carteira
    ato("Ministério da Fazenda/Secretaria Especial da Receita Federal", "Portaria",
        "PORTARIA RFB Nº 1, DE 3 DE AGOSTO DE 2026", "Dispõe sobre o horário de atendimento."),
    # "Alvará" de conselho profissional: tipo de ato que não cria obrigação geral
    ato("Entidades de Fiscalização do Exercício das Profissões Liberais/Conselho Regional",
        "Alvará", "ALVARÁ Nº 208, DE 3 DE AGOSTO DE 2026", "Concede registro profissional."),
    # ANP é do MME, mas não é órgão de interesse nem cita termos da carteira
    ato("Ministério de Minas e Energia/Agência Nacional do Petróleo, Gás Natural e Biocombustíveis",
        "Resolução", "RESOLUÇÃO ANP Nº 1, DE 3 DE AGOSTO DE 2026",
        "Dispõe sobre a comercialização de biocombustíveis."),
]


def test_todo_ato_do_gabarito_entra_com_o_motivo_certo():
    for a, comeco in DEVEM_ENTRAR:
        motivo = motivo_interesse(a, CFG)
        assert motivo and motivo.lower().startswith(comeco.lower()[:4]), (a.identifica, motivo)


def test_o_que_nao_interessa_fica_fora():
    for a in FICAM_FORA:
        assert motivo_interesse(a, CFG) is None, a.identifica


def test_orgaos_do_radar_incluem_quem_publica_o_que_o_catalogo_usa():
    """ANM (resoluções), MTE (NRs), leis e decretos federais: as fontes do próprio catálogo."""
    rotulos = " ".join(ORGAOS_RADAR)
    for orgao in ("Agência Nacional de Mineração", "Ministério do Trabalho e Emprego",
                  "Atos do Poder Legislativo", "Atos do Poder Executivo"):
        assert orgao in rotulos
    assert orgao_de_interesse("Ministério da Fazenda/Receita Federal") is None


def test_recall_da_descoberta_contra_o_gabarito():
    """Camada 0 da descoberta: toda norma rotulada como candidata tem de passar (recall 1,0), e as
    sintéticas de crédito/homenagem/concessão têm de ficar fora. Roda sem IA e sem rede."""
    r = descoberta.avaliar()
    assert r["camada0"]["recall"] == 1.0, r["camada0"]["falsos_negativos"]
    assert not r["camada0"]["falsos_negativos"]
    assert not r["camada0"]["passaram_sem_rotulo"]
    assert r["camada0"]["casos"] >= 15
