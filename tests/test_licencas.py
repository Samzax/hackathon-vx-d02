"""Licenças e condicionantes: o trecho literal conferido, a aprovação da dona e a renovação.

A regra do catálogo vale aqui: sem trecho conferido, não entra. Quem aprova é a própria empresa.
"""

from __future__ import annotations

import json

import pytest

from mitra import db, instanciacao as inst, licencas, pessoal
from mitra.ia import Roteador

POR = "Paulo Ribeiro (Regulatório)"
EMPRESA = "Mineradora Nova (fictícia)"

TEXTO_LICENCA = """GOVERNO DO ESTADO DE MINAS GERAIS
SECRETARIA DE ESTADO DE MEIO AMBIENTE (fictícia, para teste)

LICENÇA DE OPERAÇÃO LO Nº 123/2026
Validade: 15/03/2032

O empreendimento Mina Nova, da Mineradora Nova S.A., fica licenciado para operação, observadas as
condicionantes abaixo.

Condicionante 1. Monitorar trimestralmente a qualidade das águas superficiais a montante e a jusante
do empreendimento, apresentando laudo de laboratório acreditado até 30 dias após o fim do trimestre.

Condicionante 2. Executar o Programa de Recuperação de Áreas Degradadas (PRAD) e apresentar relatório
anual de execução.

Condicionante 3. Comunicar ao órgão ambiental, em até 24 horas, qualquer acidente ou incidente
ambiental ocorrido na unidade.
"""


class IAFalsa:
    """Provedor que devolve uma resposta roteirizada, sem rede."""

    def __init__(self, resposta: dict):
        self.resposta = resposta
        self.chamadas: list[str] = []

    def chamar(self, modelo, sistema, usuario, max_tokens, sessao):
        self.chamadas.append(usuario)
        return json.dumps(self.resposta, ensure_ascii=False), 2000, 400


RESPOSTA = {
    "numero_licenca": "123/2026",
    "orgao": "Secretaria de Estado de Meio Ambiente (fictícia, para teste)",
    "validade": "2032-03-15",
    "condicionantes": [
        {"titulo": "Monitorar a qualidade das águas superficiais", "periodicidade": "Trimestral",
         "prazo": "Até 30 dias após o fim do trimestre", "evidencia": "Laudo de laboratório acreditado",
         "aplica_a": "unidade", "alvo": "Mina Nova", "numero": "1",
         "trecho": "Monitorar trimestralmente a qualidade das águas superficiais a montante e a jusante"},
        {"titulo": "Executar o PRAD e apresentar relatório", "periodicidade": "Anual",
         "prazo": "Anual", "evidencia": "Relatório de execução do PRAD", "aplica_a": "empresa",
         "alvo": None, "numero": "2",
         "trecho": "Executar o Programa de Recuperação de Áreas Degradadas (PRAD)"},
        {"titulo": "Comunicar acidente ou incidente ambiental", "periodicidade": "Por evento",
         "prazo": "Até 24 horas", "evidencia": "Protocolo da comunicação", "aplica_a": "empresa",
         "alvo": None, "numero": "3",
         "trecho": "Comunicar ao órgão ambiental, em até 24 horas, qualquer acidente ou incidente"},
        # esta a IA inventou: o trecho não está na licença
        {"titulo": "Plantar 10 mil mudas por ano", "periodicidade": "Anual", "prazo": "Anual",
         "evidencia": "Relatório de plantio", "aplica_a": "empresa", "alvo": None, "numero": "4",
         "trecho": "Plantar, anualmente, 10.000 (dez mil) mudas de espécies nativas"},
        # e esta aponta para uma unidade que a empresa não tem
        {"titulo": "Monitorar a pilha de estéril", "periodicidade": "Mensal", "prazo": "Mensal",
         "evidencia": "Relatório", "aplica_a": "unidade", "alvo": "Mina Fantasma", "numero": "5",
         "trecho": "observadas as condicionantes abaixo"},
    ],
}


@pytest.fixture
def empresa():
    conn = db.conectar(":memory:")
    eid = inst.criar(conn, nome=EMPRESA, razao_social="Mineradora Nova S.A.", cnpj=None, ufs=["MG"],
                     por="Curadoria Mitra")
    inst.criar_unidade(conn, eid, "Mina Nova", "Curadoria Mitra", uf="MG")
    inst.criar_ativo(conn, eid, tipo="licenca", codigo="L1", nome="LO da Mina Nova", por="Curadoria Mitra")
    yield conn, eid
    conn.close()


@pytest.fixture
def com_licenca(empresa):
    conn, eid = empresa
    lid = licencas.guardar_licenca(conn, eid, tipo="LO", numero="123/2026", por=POR,
                                   orgao="SEMAD (fictícia)", emitida_em="2026-03-15", validade="2032-03-15",
                                   unidade="Mina Nova", arquivo="LO_123_2026.pdf", texto=TEXTO_LICENCA)
    return conn, eid, lid


# ------------------------------------------------------------------ a conferência do trecho


def test_proposta_sem_trecho_na_licenca_nao_entra(com_licenca):
    conn, eid, lid = com_licenca
    ia = IAFalsa(RESPOSTA)
    le = licencas.ler(conn, Roteador(conn, provedores={"anthropic": ia}), eid, TEXTO_LICENCA)
    assert len(le.propostas) == 5 and len(le.aprovadas) == 3
    por_titulo = {p.titulo: p for p in le.propostas}
    assert por_titulo["Plantar 10 mil mudas por ano"].reprovada == "o trecho citado não existe no texto da licença"
    assert "não tem a unidade 'Mina Fantasma'" in por_titulo["Monitorar a pilha de estéril"].reprovada
    assert le.validade == "2032-03-15" and le.numero_licenca == "123/2026"

    ids = licencas.propor(conn, eid, lid, le, POR)
    assert len(ids) == 3                                  # só as conferidas
    pendentes = licencas.condicionantes(conn, eid, status=licencas.PENDENTE)
    assert {c["titulo"] for c in pendentes} == {
        "Monitorar a qualidade das águas superficiais (cond. 1)",
        "Executar o PRAD e apresentar relatório (cond. 2)",
        "Comunicar acidente ou incidente ambiental (cond. 3)"}
    aguas = next(c for c in pendentes if "águas" in c["titulo"])
    assert aguas["agenda"] == "trimestral+30d"            # da periodicidade e do prazo, por regra
    assert aguas["aplica_a"] == "unidade" and aguas["alvo"] == "Mina Nova"
    assert aguas["trecho"] in TEXTO_LICENCA               # literal, palavra por palavra
    evento = next(c for c in pendentes if "Comunicar" in c["titulo"])
    assert evento["agenda"] == "evento"                   # "Por evento": gatilho, sem prazo inventado


def test_dado_pessoal_nunca_vai_para_a_ia(com_licenca):
    """O texto da licença pode trazer o CPF do responsável técnico: a IA recebe com marcador."""
    conn, eid, _ = com_licenca
    cpf = "123.456.789" + "-09"
    texto = TEXTO_LICENCA + f"\nResponsável técnico: Ana Souza, CPF {cpf}, CREA MG-123456.\n"
    ia = IAFalsa(RESPOSTA)
    licencas.ler(conn, Roteador(conn, provedores={"anthropic": ia}), eid, texto)
    [enviado] = ia.chamadas
    assert cpf not in enviado and pessoal.MARCADOR in enviado
    assert "Ana Souza" in enviado                        # o nome fica: o que sai é o CPF


def test_pagina_do_trecho_vem_das_paginas_do_pdf(com_licenca):
    conn, eid, _ = com_licenca
    paginas = ["capa sem condicionante", TEXTO_LICENCA]
    ia = IAFalsa(RESPOSTA)
    le = licencas.ler(conn, Roteador(conn, provedores={"anthropic": ia}), eid, TEXTO_LICENCA, paginas)
    assert all(p.pagina == 2 for p in le.aprovadas)


def test_pdf_sem_texto_nao_vai_para_a_ia(com_licenca):
    conn, eid, _ = com_licenca
    ia = IAFalsa(RESPOSTA)
    le = licencas.ler(conn, Roteador(conn, provedores={"anthropic": ia}), eid, "duas palavras")
    assert not le.propostas and "escaneado" in le.problemas[0] and ia.chamadas == []


def test_ia_indisponivel_diz_o_problema_e_nao_inventa(com_licenca):
    conn, eid, _ = com_licenca
    le = licencas.ler(conn, Roteador(conn, env={}, provedores={}), eid, TEXTO_LICENCA)
    assert not le.propostas and "leitura indisponível" in le.problemas[0]


# ------------------------------------------------------------------ a licença


def test_licenca_confere_o_que_recebe(empresa):
    conn, eid = empresa
    with pytest.raises(licencas.ErroLicenca, match="tipo de licença desconhecido"):
        licencas.guardar_licenca(conn, eid, tipo="LX", numero="1", por=POR)
    with pytest.raises(licencas.ErroLicenca, match="número da licença"):
        licencas.guardar_licenca(conn, eid, tipo="LO", numero="  ", por=POR)
    with pytest.raises(licencas.ErroLicenca, match="não é data"):
        licencas.guardar_licenca(conn, eid, tipo="LO", numero="1", por=POR, validade="15/03/2032")
    with pytest.raises(licencas.ErroLicenca, match="não tem a unidade"):
        licencas.guardar_licenca(conn, eid, tipo="LO", numero="1", por=POR, unidade="Mina Fantasma")
    with pytest.raises(licencas.ErroLicenca, match="não tem o ativo"):
        licencas.guardar_licenca(conn, eid, tipo="LO", numero="1", por=POR, ativo_codigo="B9")
    licencas.guardar_licenca(conn, eid, tipo="LO", numero="1", por=POR)
    with pytest.raises(licencas.ErroLicenca, match="já tem a LO 1"):
        licencas.guardar_licenca(conn, eid, tipo="LO", numero="1", por=POR)


def test_licenca_de_outra_cliente_nao_existe_para_esta(com_licenca):
    conn, eid, lid = com_licenca
    outra = inst.criar(conn, nome="Vizinha (fictícia)", razao_social="V", cnpj=None, ufs=[], por=POR)
    assert licencas.licenca(conn, eid, lid)["numero"] == "123/2026"
    assert licencas.licenca(conn, outra, lid) is None
    assert licencas.condicionantes(conn, outra) == []
    with pytest.raises(licencas.ErroLicenca, match="não é desta empresa"):
        licencas.propor(conn, outra, lid, licencas.Leitura(), POR)


# ------------------------------------------------------------------ a decisão da dona


def _propostas(conn, eid, lid):
    ia = IAFalsa(RESPOSTA)
    le = licencas.ler(conn, Roteador(conn, provedores={"anthropic": ia}), eid, TEXTO_LICENCA)
    licencas.propor(conn, eid, lid, le, POR)
    return licencas.condicionantes(conn, eid, status=licencas.PENDENTE)


def test_aprovada_vira_obrigacao_propria_vigente_da_empresa(com_licenca):
    conn, eid, lid = com_licenca
    aguas = next(c for c in _propostas(conn, eid, lid) if "águas" in c["titulo"])
    codigo = licencas.aprovar(conn, eid, aguas["id"], POR)
    assert codigo == "LO-01"
    v = db.versao(conn, codigo, empresa=EMPRESA)
    assert v["titulo"] == "Monitorar a qualidade das águas superficiais (cond. 1)"
    assert v["agenda"] == "trimestral+30d" and v["status"] == "vigente" and v["decidida_por"] == POR
    assert v["trecho"] in TEXTO_LICENCA and v["vigencia_ate"] == "2032-03-15"
    assert v["aplica_se_a"] == "a unidade Mina Nova"
    ob = db.obrigacao_por_codigo(conn, codigo, EMPRESA)
    assert ob["empresa"] == EMPRESA and ob["norma"] == "LO 123/2026" and ob["tipo_ativo"] == "unidade"
    c = licencas.condicionante(conn, eid, aguas["id"])
    assert c["status"] == "aprovada" and c["codigo"] == codigo and c["decidida_por"] == POR
    # a segunda aprovada ganha o código seguinte
    prad = next(c for c in licencas.condicionantes(conn, eid, status=licencas.PENDENTE) if "PRAD" in c["titulo"])
    assert licencas.aprovar(conn, eid, prad["id"], POR) == "LO-02"


def test_quem_aprova_pode_corrigir_antes(com_licenca):
    conn, eid, lid = com_licenca
    prad = next(c for c in _propostas(conn, eid, lid) if "PRAD" in c["titulo"])
    codigo = licencas.aprovar(conn, eid, prad["id"], POR,
                              correcoes={"agenda": "anual+60d", "evidencia": "Relatório do PRAD com ART"},
                              nota="prazo combinado com o órgão")
    v = db.versao(conn, codigo, empresa=EMPRESA)
    assert v["agenda"] == "anual+60d" and v["evidencia"] == "Relatório do PRAD com ART"
    nota = json.loads(licencas.condicionante(conn, eid, prad["id"])["nota"])
    assert nota["correcoes"]["agenda"] == "anual+60d" and nota["nota"] == "prazo combinado com o órgão"


def test_correcao_invalida_e_recusada(com_licenca):
    conn, eid, lid = com_licenca
    prad = next(c for c in _propostas(conn, eid, lid) if "PRAD" in c["titulo"])
    with pytest.raises(licencas.ErroLicenca, match="não podem ser corrigidos"):
        licencas.aprovar(conn, eid, prad["id"], POR, correcoes={"trecho": "outro texto"})
    from mitra.agenda import AgendaInvalida
    with pytest.raises(AgendaInvalida):
        licencas.aprovar(conn, eid, prad["id"], POR, correcoes={"agenda": "de vez em quando"})
    assert licencas.condicionante(conn, eid, prad["id"])["status"] == "pendente"


def test_rejeitada_nao_vira_obrigacao_e_nao_decide_duas_vezes(com_licenca):
    conn, eid, lid = com_licenca
    evento = next(c for c in _propostas(conn, eid, lid) if "Comunicar" in c["titulo"])
    licencas.rejeitar(conn, eid, evento["id"], POR, nota="já está no PAEBM")
    c = licencas.condicionante(conn, eid, evento["id"])
    assert c["status"] == "rejeitada" and c["codigo"] is None
    assert db.versao(conn, "LO-01", empresa=EMPRESA) is None
    with pytest.raises(licencas.ErroLicenca, match="já foi rejeitada"):
        licencas.aprovar(conn, eid, evento["id"], POR)


def test_condicionante_aprovada_entra_na_torre_do_ativo(com_licenca):
    """A obrigação própria passa a valer para a unidade da empresa, como qualquer norma do catálogo."""
    conn, eid, lid = com_licenca
    u1 = inst.criar_ativo(conn, eid, tipo="unidade", codigo="U1", nome="Mina Nova", por=POR,
                          unidade="Mina Nova", atributos={"uf": "MG"})
    aguas = next(c for c in _propostas(conn, eid, lid) if "águas" in c["titulo"])
    codigo = licencas.aprovar(conn, eid, aguas["id"], POR)
    assert codigo in {o.codigo for o in db.obrigacoes_do_ativo(conn, u1)}


# ------------------------------------------------------------------ a renovação


def test_validade_da_licenca_vira_obrigacao_de_renovacao(com_licenca):
    conn, eid, lid = com_licenca
    codigo = licencas.obrigacao_de_renovacao(conn, eid, lid, POR)
    v = db.versao(conn, codigo, empresa=EMPRESA)
    assert v["titulo"] == "Requerer a renovação da LO 123/2026"
    assert v["agenda"] == "data:2031-11-16"      # 120 dias antes de 15/03/2032
    assert "120 dias antes do vencimento" in v["prazo"] and v["vigencia_ate"] == "2032-03-15"
    assert licencas.obrigacao_de_renovacao(conn, eid, lid, POR) is None      # não duplica


def test_renovacao_respeita_o_prazo_da_propria_licenca(empresa):
    conn, eid = empresa
    lid = licencas.guardar_licenca(conn, eid, tipo="LI", numero="9/2026", por=POR, validade="2030-06-30",
                                   renovar_dias=180)
    codigo = licencas.obrigacao_de_renovacao(conn, eid, lid, POR)
    assert db.versao(conn, codigo, empresa=EMPRESA)["agenda"] == "data:2030-01-01"


def test_licenca_sem_validade_nao_inventa_renovacao(empresa):
    conn, eid = empresa
    lid = licencas.guardar_licenca(conn, eid, tipo="outorga", numero="7/2026", por=POR)
    assert licencas.obrigacao_de_renovacao(conn, eid, lid, POR) is None


# ------------------------------------------------- a etapa da instanciação acompanha


def test_a_etapa_de_licencas_segue_os_dados(com_licenca):
    conn, eid, lid = com_licenca
    etapas = {e.etapa: e for e in inst.estado(conn, eid).etapas}
    assert etapas[inst.LICENCAS].estado == inst.PRONTA        # licença sem proposta pendente
    _propostas(conn, eid, lid)
    etapas = {e.etapa: e for e in inst.estado(conn, eid).etapas}
    assert etapas[inst.LICENCAS].estado == inst.EM_ANDAMENTO  # com proposta esperando a dona
    assert etapas[inst.LICENCAS].numeros == {"licencas": 1, "propostas": 3, "aprovadas": 0, "rejeitadas": 0}
    for c in licencas.condicionantes(conn, eid, status=licencas.PENDENTE):
        licencas.aprovar(conn, eid, c["id"], POR)
    etapas = {e.etapa: e for e in inst.estado(conn, eid).etapas}
    assert etapas[inst.LICENCAS].estado == inst.PRONTA and etapas[inst.LICENCAS].numeros["aprovadas"] == 3
