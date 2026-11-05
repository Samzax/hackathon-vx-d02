import json

from regulaia import extrator, normas
from regulaia.ia import Roteador

PARAGRAFOS = [
    "RESOLUÇÃO DE TESTE",
    "Art. 1º Esta Resolução trata de barragens.",
    "Art. 2º O empreendedor deverá preencher a Ficha de Inspeção Regular quinzenalmente.",
    "§ 1º Para barragens com DPA alto, a ficha será enviada pelo SIGBM até o quinto dia.",
    "Art. 3º (Revogado pela Resolução X)",
    "Art. 4º A ANM poderá fiscalizar.",
    "ANEXO I",
    "Art. 99 Texto de anexo que não é artigo.",
]


def test_artigos_ignora_revogado_e_anexo():
    arts = normas.artigos(normas.paragrafos_anmlegis_de(PARAGRAFOS))
    assert [a.numero for a in arts] == [1, 2, 4]
    assert "quinto dia" in arts[1].texto


def test_maior_ou_igual_sublinhado_do_anmlegis():
    """Na Res. 220 o ANMlegis escreve "≥" como ">" sublinhado; perder o sublinhado troca a regra."""
    html = ("<p>Art. 54. Para barragens classificadas com DPA2 <u>&gt;</u> 4, semestralmente.</p>"
            "<p>Art. 55. Para barragens classificadas com DPA2 &lt; 4, anualmente.</p>")
    arts = normas.artigos(normas.paragrafos_anmlegis_html(html))
    assert "DPA2 ≥ 4" in arts[0].texto and "DPA2 < 4" in arts[1].texto


def test_blocos_nao_partem_artigo():
    arts = [normas.Artigo(str(i), "x" * 600) for i in range(1, 6)]
    assert [[a.numero for a in b] for b in normas.blocos(arts, max_chars=1300)] == [[1, 2], [3, 4], [5]]


class Falso:
    def __init__(self, resposta):
        self.resposta = resposta

    def chamar(self, modelo, sistema, usuario, max_tokens, sessao):
        return json.dumps(self.resposta, ensure_ascii=False), 500, 300


def _extrair(obrigacoes):
    rot = Roteador(None, provedores={"opencode": Falso({"obrigacoes": obrigacoes})})
    unidades = normas.artigos(normas.paragrafos_anmlegis_de(PARAGRAFOS))
    return extrator.extrair(rot, "Res. Teste", unidades, "barragem")


BOA = {
    "artigo": "art. 2 §1", "titulo": "Enviar a FIR pelo SIGBM", "aplica_se_a": "Barragens com DPA alto",
    "regra": "dpa = alto", "periodicidade": "Quinzenal", "prazo": "Até o quinto dia",
    "evidencia": "FIR no SIGBM", "area": "barragem",
    "trecho": "Para barragens com DPA alto, a ficha será enviada pelo SIGBM até o quinto dia.",
}


def test_proposta_boa_passa():
    res = _extrair([BOA])
    assert [p.titulo for p in res.aprovadas] == ["Enviar a FIR pelo SIGBM"]


def test_conferencias_reprovam():
    casos = {
        "trecho": BOA | {"trecho": "a ficha será enviada em até 48 horas"},
        "artigo": BOA | {"artigo": "art. 40"},
        "atributo": BOA | {"regra": "porte = grande"},
        "regra": BOA | {"regra": "dpa = alto ou cri = alto"},
    }
    res = _extrair(list(casos.values()))
    motivos = [p.reprovada for p in res.propostas]
    assert "não existe no bloco" in motivos[0]
    assert "não está no bloco" in motivos[1]
    assert "atributo desconhecido" in motivos[2]
    assert "regra inválida" in motivos[3]
    assert res.aprovadas == []


def test_duplicada_e_marcada():
    res = _extrair([BOA, BOA | {"evidencia": "outra"}])
    assert [p.reprovada for p in res.propostas] == [None, "duplicada"]


# ------------------------------------------------------------------ NRs

LINHAS_NR = [
    "NR 13 - CALDEIRAS E VASOS DE PRESSÃO", "SUMÁRIO", "13.1 Objetivo", "13.2 Campo de aplicação",
    "ANEXO I - Capacitação",
    "13.1 Objetivo",
    "13.1.1 Esta Norma estabelece requisitos mínimos",
    "para a gestão da integridade estrutural.",
    "13.5.4 Inspeção de segurança de vasos de pressão",
    "13.5.4.1 Os vasos de pressão devem ser submetidos a inspeções de segurança inicial,",
    "periódica e extraordinária.",
    "a) antes de entrar em funcionamento;",
    "13.5.4.2 (Excluído pela Portaria X)",
    "13.5.5 Outro item.",
    "ANEXO I - Capacitação",
    "13.9.9 item de anexo",
]


def test_itens_nr_pula_sumario_juntam_linhas_e_param_no_anexo():
    ps = normas.paragrafos_de_linhas(LINHAS_NR)
    assert "13.1.1 Esta Norma estabelece requisitos mínimos para a gestão da integridade estrutural." in ps
    assert not any("Excluído" in p for p in ps)
    itens = {u.id: u.texto for u in normas.itens_nr(ps)}
    assert list(itens) == ["13.1", "13.1.1", "13.5.4", "13.5.5"]
    assert "a) antes de entrar em funcionamento;" in itens["13.5.4"]


def test_conferir_aceita_item_de_nr_dentro_do_bloco():
    texto = "13.5.4.1 Os vasos de pressão devem ser submetidos a inspeções de segurança inicial."
    p = extrator.Proposta(
        artigo="13.5.4.1", titulo="Inspecionar o vaso", aplica_se_a="Vasos de pressão",
        regra="classe = vaso_pressao", periodicidade="Por evento", prazo="Antes de operar",
        evidencia="Relatório de inspeção", area="equipamento",
        trecho="devem ser submetidos a inspeções de segurança inicial",
    )
    assert extrator.conferir(p, texto, {"13.5.4"}, "equipamento") is None
    p.artigo = "13.6.1"
    assert "não está no bloco" in extrator.conferir(p, texto, {"13.5.4"}, "equipamento")


def test_bloco_que_falha_e_dividido_ao_meio():
    class FalhaSeLongo:
        def chamar(self, modelo, sistema, usuario, max_tokens, sessao):
            if usuario.count("Art.") > 1:
                return "não é JSON", 10, 10
            return json.dumps({"obrigacoes": []}), 10, 10

    rot = Roteador(None, provedores={"opencode": FalhaSeLongo()})
    unidades = normas.artigos(normas.paragrafos_anmlegis_de(PARAGRAFOS))
    res = extrator.extrair(rot, "Res. Teste", unidades, "barragem")
    assert res.blocos_sem_resposta == []
    assert any("dividido" in m for m in res.modelos)
