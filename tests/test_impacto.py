import json
from pathlib import Path

import pytest

from collector.xml_dou import load_month
from regulaia import db, demo, impacto, triagem
from regulaia.ia import RespostaInvalida, Roteador, extrair_json

AMOSTRA = Path(__file__).parent / "fixtures" / "dou" / "S01_amostra.zip"
TRECHO = "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º."


@pytest.fixture(scope="module")
def atos():
    return {a.identifica.split(",")[0]: a for a in load_month(AMOSTRA) if a.is_anm and a.is_normative}


@pytest.fixture
def serra():
    conn = db.conectar(":memory:")
    return conn, demo.montar(conn)


class Falso:
    """Provedor que devolve respostas roteirizadas por esforço (camada 2 = high, 3 = max)."""

    def __init__(self, respostas: dict):
        self.respostas = respostas
        self.chamadas = []

    def chamar(self, modelo, sistema, usuario, max_tokens, sessao):
        self.chamadas.append(modelo.rotulo)
        r = self.respostas[modelo.esforco]
        return (r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)), 1000, 200


def _roteador(conn, respostas):
    falso = Falso(respostas)
    return Roteador(conn, provedores={"opencode": falso}), falso


CERTA_245 = {
    "mudancas": [
        {"obrigacao": "OB-01", "campo": "prazo", "valor_atual": "2027-08-02",
         "valor_novo": "2029-12-26", "trecho": TRECHO, "justificativa": "novo inciso III"},
        {"obrigacao": "OB-01", "campo": "vigencia_desde", "valor_atual": "2027-08-02",
         "valor_novo": "2029-12-26", "trecho": TRECHO, "justificativa": "novo inciso III"},
    ],
    "motivo": "Adia só o art. 7 §1.",
    "confianca": 0.95,
}


def test_triagem_poe_a_ob01_em_primeiro_na_res_245(serra, atos):
    conn, _ = serra
    obs = [db.versao(conn, f"OB-{i:02d}") for i in range(1, 16)]
    cands = triagem.candidatas(atos["Resolução ANM Nº 245"].text, obs)
    assert cands[0].codigo == "OB-01"
    assert date_in(triagem.datas(TRECHO))


def date_in(ds):
    from datetime import date
    return date(2029, 12, 26) in ds


def test_res_245_resposta_certa_vira_pendente_so_na_b2(serra, atos):
    conn, ids = serra
    rot, falso = _roteador(conn, {"high": CERTA_245, "max": CERTA_245})
    ato = atos["Resolução ANM Nº 245"]
    an = impacto.analisar(conn, rot, ato.identifica, ato.text)
    assert falso.chamadas == ["opencode:deepseek-v4.1-flash@high"]     # nem subiu para a camada 3
    assert [(m.obrigacao, m.campo) for m in an.aprovadas] == [("OB-01", "prazo"), ("OB-01", "vigencia_desde")]
    assert not an.revisao_humana

    ato_id = db.registrar_ato(conn, "dou", "245", ato.identifica, texto=ato.text)
    assert len(impacto.aplicar(conn, an, ato_id)) == 1
    pend = db.versao(conn, "OB-01", "pendente")
    assert pend["prazo"] == "2029-12-26" and pend["vigencia_desde"] == "2029-12-26"
    afetadas = {c for c, a in ids.items() if any(o.pendente for o in db.obrigacoes_do_ativo(conn, a))}
    assert afetadas == {"B2"}


def test_trecho_inventado_e_reprovado_e_sobe_para_a_camada_3(serra, atos):
    conn, _ = serra
    inventada = json.loads(json.dumps(CERTA_245))
    inventada["mudancas"][0]["trecho"] = "o prazo fica prorrogado para 26 de dezembro de 2029"
    rot, falso = _roteador(conn, {"high": inventada, "max": CERTA_245})
    ato = atos["Resolução ANM Nº 245"]
    an = impacto.analisar(conn, rot, ato.identifica, ato.text)
    assert falso.chamadas == ["opencode:deepseek-v4.1-flash@high", "opencode:deepseek-v4.1-flash@max"]
    assert not an.reprovadas and not an.revisao_humana


def test_data_que_nao_esta_no_trecho_e_reprovada(serra, atos):
    conn, _ = serra
    errada = json.loads(json.dumps(CERTA_245))
    for m in errada["mudancas"]:
        m["valor_novo"] = "2029-12-31"          # a data da notícia, não a do ato
    rot, _ = _roteador(conn, {"high": errada, "max": errada})
    ato = atos["Resolução ANM Nº 245"]
    an = impacto.analisar(conn, rot, ato.identifica, ato.text)
    assert an.aprovadas == []
    assert all("não aparece no trecho" in m.reprovada for m in an.reprovadas)
    assert an.revisao_humana


def test_res_246_nao_muda_nada(serra, atos):
    conn, _ = serra
    nada = {"mudancas": [], "motivo": "Prorrogação exclui prazos do SIGBM (§2º II).", "confianca": 0.9}
    rot, falso = _roteador(conn, {"high": nada, "max": nada})
    ato = atos["Resolução ANM Nº 246"]
    an = impacto.analisar(conn, rot, ato.identifica, ato.text)
    assert an.candidatas, "a triagem deveria mandar as obrigações do SIGBM para a IA"
    assert an.mudancas == [] and not an.revisao_humana
    assert len(falso.chamadas) == 1


def test_ato_sem_relacao_nao_chama_a_ia(serra):
    conn, _ = serra
    rot, falso = _roteador(conn, {"high": CERTA_245, "max": CERTA_245})
    an = impacto.analisar(conn, rot, "Portaria X", "Nomeia servidor para cargo em comissão no órgão.")
    assert an.candidatas == [] and falso.chamadas == []


def test_mesma_entrada_vem_do_cache(serra, atos):
    conn, _ = serra
    rot, falso = _roteador(conn, {"high": CERTA_245, "max": CERTA_245})
    ato = atos["Resolução ANM Nº 245"]
    impacto.analisar(conn, rot, ato.identifica, ato.text)
    an = impacto.analisar(conn, rot, ato.identifica, ato.text)
    assert len(falso.chamadas) == 1
    assert an.modelos == ["opencode:deepseek-v4.1-flash@high (cache)"] and an.custo_usd == 0
    assert rot.custo_total() == pytest.approx((1000 * 0.15 + 200 * 0.60) / 1e6)


def test_cache_vale_mesmo_sem_chave(serra, atos):
    """A demo roda sem internet: o que já foi analisado vem do cache, sem provedor."""
    conn, _ = serra
    rot, _ = _roteador(conn, {"high": CERTA_245, "max": CERTA_245})
    ato = atos["Resolução ANM Nº 245"]
    impacto.analisar(conn, rot, ato.identifica, ato.text)
    an = impacto.analisar(conn, Roteador(conn, env={}), ato.identifica, ato.text)
    assert an.modelos[0].endswith("(cache)") and an.aprovadas and not an.revisao_humana


def test_sem_chave_nenhuma_pede_revisao_humana(serra, atos):
    conn, _ = serra
    rot = Roteador(conn, env={})
    ato = atos["Resolução ANM Nº 245"]
    an = impacto.analisar(conn, rot, ato.identifica, ato.text)
    # sem IA não dá para dizer "não muda nada": vai para uma pessoa
    assert an.mudancas == [] and an.revisao_humana is True and "camada 2" in an.modelos[0]


@pytest.mark.parametrize("texto", ['{"a": 1}', '```json\n{"a": 1}\n```', 'Segue:\n{"a": 1}\nFim.'])
def test_extrair_json(texto):
    assert extrair_json(texto) == {"a": 1}


@pytest.mark.parametrize("texto", ["", "sem json", "[1, 2]", "{quebrado"])
def test_extrair_json_recusa(texto):
    with pytest.raises(RespostaInvalida):
        extrair_json(texto)
