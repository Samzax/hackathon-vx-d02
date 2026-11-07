"""A API das licenças: o PDF vira condicionantes propostas com trecho conferido, e só a dona decide."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.config import Config
from api.main import criar_app
from regulaia import db, instanciacao as inst, pdf, usuarios
from tests.test_api import CURADORIA, SENHA, _banco_da_demo, _url, como

NOVA = "Mineradora Nova (fictícia)"

TEXTO = """GOVERNO DO ESTADO DE MINAS GERAIS
SECRETARIA DE MEIO AMBIENTE (documento fictício, para teste)

LICENÇA DE OPERAÇÃO LO Nº 123/2026
Validade: 15/03/2032

Condicionante 1. Monitorar trimestralmente a qualidade das águas superficiais a montante e a jusante,
apresentando laudo de laboratório acreditado até 30 dias após o fim do trimestre.

Condicionante 2. Executar o Programa de Recuperação de Áreas Degradadas (PRAD) e apresentar relatório
anual de execução.
"""

RESPOSTA_IA = {
    "numero_licenca": "123/2026",
    "orgao": "Secretaria de Meio Ambiente (fictícia)",
    "validade": "2032-03-15",
    "condicionantes": [
        {"titulo": "Monitorar a qualidade das águas superficiais", "periodicidade": "Trimestral",
         "prazo": "Até 30 dias após o fim do trimestre", "evidencia": "Laudo de laboratório acreditado",
         "aplica_a": "unidade", "alvo": "Mina Nova", "numero": "1",
         "trecho": "Monitorar trimestralmente a qualidade das águas superficiais a montante e a jusante"},
        {"titulo": "Executar o PRAD e apresentar relatório", "periodicidade": "Anual", "prazo": "Anual",
         "evidencia": "Relatório de execução do PRAD", "aplica_a": "empresa", "alvo": None,
         "numero": "2",
         "trecho": "Executar o Programa de Recuperação de Áreas Degradadas (PRAD)"},
        # a IA inventou esta: o trecho não está na licença, então o Python recusa
        {"titulo": "Plantar 10 mil mudas por ano", "periodicidade": "Anual", "prazo": "Anual",
         "evidencia": "Relatório de plantio", "aplica_a": "empresa", "alvo": None, "numero": "3",
         "trecho": "Plantar, anualmente, 10.000 (dez mil) mudas de espécies nativas"},
    ],
}


class IAFalsa:
    def __init__(self, resposta: dict):
        self.resposta, self.chamadas = resposta, []

    def chamar(self, modelo, sistema, usuario, max_tokens, sessao):
        self.chamadas.append(usuario)
        return json.dumps(self.resposta, ensure_ascii=False), 2000, 400


@pytest.fixture
def ia(monkeypatch):
    """Troca o provedor de IA por um roteiro, sem rede (como nos outros testes de IA)."""
    falsa = IAFalsa(RESPOSTA_IA)
    from regulaia import ia as modulo

    original = modulo.Roteador.__init__

    def init(self, conn=None, config=modulo.CONFIG, env=None, provedores=None, timeout=180.0):
        original(self, conn, config, env or {}, {"opencode": falsa}, timeout)

    monkeypatch.setattr(modulo.Roteador, "__init__", init)
    return falsa


@pytest.fixture
def cfg(tmp_path):
    banco, cache = _banco_da_demo(tmp_path)
    return Config(banco=banco, banco_cache=cache, armazenamento=str(tmp_path / "uploads"),
                  token_servico="token-de-teste-do-agente")


@pytest.fixture
def cliente(cfg):
    with TestClient(criar_app(cfg)) as c:
        yield c


@pytest.fixture
def empresa(cliente, cfg) -> int:
    """Uma cliente instanciada, com uma unidade e contas de Diretoria e de gestor."""
    como(cliente, CURADORIA)
    eid = cliente.post(_url("/instanciacoes"), json={
        "nome": NOVA, "razao_social": "Mineradora Nova S.A.", "cnpj": None, "ufs": ["MG"],
        "ficticia": True}).json()["empresa_id"]
    conn = db.conectar(cfg.banco)
    inst.criar_unidade(conn, eid, "Mina Nova", "teste", uf="MG")
    inst.criar_ativo(conn, eid, tipo="unidade", codigo="U1", nome="Mina Nova", por="teste",
                     unidade="Mina Nova", atributos={"uf": "MG"})
    usuarios.criar(conn, "diretoria@nova.demo", "Diretoria Nova", usuarios.DIRETORIA, senha=SENHA,
                   empresa=NOVA)
    usuarios.criar(conn, "geo@nova.demo", "Geo Nova", usuarios.GESTOR, area="Geotecnia", senha=SENHA,
                   empresa=NOVA)
    conn.close()
    return eid


def _pdf() -> bytes:
    return pdf.de_markdown(TEXTO, "LO 123/2026 (fictícia)")


def _enviar(cliente, eid: int, **extra):
    params = {"tipo": "LO", "numero": "123/2026", "orgao": "SEMAD (fictícia)",
              "emitida_em": "2026-03-15", "validade": "2032-03-15", "unidade": "Mina Nova", **extra}
    return cliente.post(_url(f"/empresas/{eid}/licencas"), params=params,
                        files={"arquivo": ("LO_123_2026.pdf", _pdf(), "application/pdf")})


def test_licenca_enviada_pela_empresa_e_a_plataforma_so_le(cliente, empresa):
    r = _enviar(cliente, empresa)       # a sessão é a curadoria
    assert r.status_code == 403 and "só lê" in r.json()["detail"]
    como(cliente, "diretoria@nova.demo")
    r = _enviar(cliente, empresa)
    assert r.status_code == 201, r.text
    lic = r.json()
    assert (lic["tipo"], lic["numero"], lic["validade"]) == ("LO", "123/2026", "2032-03-15")
    assert lic["renovar_dias"] == 120 and lic["sha256"] and "guardado_em" not in lic
    assert cliente.get(_url(f"/empresas/{empresa}/licencas")).json()[0]["id"] == lic["id"]
    assert any(t["acao"] == "licenca_enviada" for t in cliente.get(_url("/auditoria")).json())
    r = _enviar(cliente, empresa)       # a mesma licença duas vezes, não
    assert r.status_code == 422 and "já tem a LO" in r.json()["detail"]


def test_leitura_propoe_com_trecho_conferido_e_recusa_o_que_a_ia_inventou(cliente, empresa, ia):
    como(cliente, "diretoria@nova.demo")
    lid = _enviar(cliente, empresa).json()["id"]
    r = cliente.post(_url(f"/licencas/{lid}/leitura"), params={"empresa_id": empresa})
    assert r.status_code == 200, r.text
    le = r.json()
    assert len(le["propostas"]) == 2 and len(le["reprovadas"]) == 1
    assert le["reprovadas"][0]["motivo"] == "o trecho citado não existe no texto da licença"
    assert le["validade_lida"] == "2032-03-15" and le["numero_lido"] == "123/2026"
    aguas = next(c for c in le["propostas"] if "águas" in c["titulo"])
    assert aguas["status"] == "pendente" and aguas["decide"] and "Diretoria da" in aguas["quem_decide"]
    assert aguas["agenda"] == "trimestral+30d" and aguas["aplica_a"] == "unidade"
    assert aguas["trecho"] in TEXTO.replace("\n", " ") or aguas["trecho"] in TEXTO
    # o texto que foi à IA não leva CPF (aqui não há, mas o caminho é o mesmo do domínio)
    assert ia.chamadas and "Condicionante 1" in ia.chamadas[0]


def test_so_a_dona_decide_a_condicionante(cliente, empresa, ia):
    como(cliente, "diretoria@nova.demo")
    lid = _enviar(cliente, empresa).json()["id"]
    cliente.post(_url(f"/licencas/{lid}/leitura"), params={"empresa_id": empresa})
    pendentes = cliente.get(_url(f"/empresas/{empresa}/condicionantes"),
                            params={"status_": "pendente"}).json()
    cid = next(c["id"] for c in pendentes if "águas" in c["titulo"])
    como(cliente, CURADORIA)        # a plataforma não aprova obrigação da cliente
    r = cliente.post(_url(f"/condicionantes/{cid}/decisao"), params={"empresa_id": empresa},
                     json={"aprovar": True})
    assert r.status_code == 403 and "só lê" in r.json()["detail"]
    como(cliente, "geo@nova.demo")  # gestor também não
    r = cliente.post(_url(f"/condicionantes/{cid}/decisao"), params={"empresa_id": empresa},
                     json={"aprovar": True})
    assert r.status_code == 403 and "Regulatório ou a Diretoria" in r.json()["detail"]
    como(cliente, "diretoria@serraazul.demo")       # outra cliente: nem existe
    assert cliente.post(_url(f"/condicionantes/{cid}/decisao"), params={"empresa_id": empresa},
                        json={"aprovar": True}).status_code == 404


def test_aprovada_vira_obrigacao_da_empresa_e_entra_na_torre(cliente, empresa, ia):
    como(cliente, "diretoria@nova.demo")
    lid = _enviar(cliente, empresa).json()["id"]
    cliente.post(_url(f"/licencas/{lid}/leitura"), params={"empresa_id": empresa})
    pendentes = cliente.get(_url(f"/empresas/{empresa}/condicionantes"),
                            params={"status_": "pendente"}).json()
    cid = next(c["id"] for c in pendentes if "águas" in c["titulo"])
    r = cliente.post(_url(f"/condicionantes/{cid}/decisao"), params={"empresa_id": empresa},
                     json={"aprovar": True, "correcoes": {"evidencia": "Laudo com ART"}})
    assert r.status_code == 200 and r.json() == {"status": "aprovada", "codigo": "LO-01"}
    linhas = cliente.get(_url(f"/empresas/{empresa}/painel")).json()["linhas"]
    aguas = next(l for l in linhas if l["codigo"] == "LO-01")
    assert aguas["ativo"] == "U1" and aguas["evidencia"] == "Laudo com ART"
    assert aguas["trecho"] and aguas["norma"] == "LO 123/2026"
    h = cliente.get(_url("/obrigacoes/LO-01/historico"), params={"empresa_id": empresa}).json()
    assert h[-1]["status"] == "vigente" and h[-1]["decidida_por"]
    assert any(t["acao"] == "condicionante_decisao" for t in cliente.get(_url("/auditoria")).json())
    # decidir de novo, não
    assert cliente.post(_url(f"/condicionantes/{cid}/decisao"), params={"empresa_id": empresa},
                        json={"aprovar": False}).status_code == 422


def test_rejeitada_nao_vira_obrigacao(cliente, empresa, ia):
    como(cliente, "diretoria@nova.demo")
    lid = _enviar(cliente, empresa).json()["id"]
    cliente.post(_url(f"/licencas/{lid}/leitura"), params={"empresa_id": empresa})
    cid = cliente.get(_url(f"/empresas/{empresa}/condicionantes"),
                      params={"status_": "pendente"}).json()[0]["id"]
    r = cliente.post(_url(f"/condicionantes/{cid}/decisao"), params={"empresa_id": empresa},
                     json={"aprovar": False, "nota": "já está no PAEBM"})
    assert r.status_code == 200 and r.json() == {"status": "rejeitada", "codigo": None}
    assert not [l for l in cliente.get(_url(f"/empresas/{empresa}/painel")).json()["linhas"]
                if l["codigo"].startswith("LO-")]


def test_validade_vira_obrigacao_de_renovacao(cliente, empresa):
    como(cliente, "diretoria@nova.demo")
    lid = _enviar(cliente, empresa).json()["id"]
    r = cliente.post(_url(f"/licencas/{lid}/renovacao"), params={"empresa_id": empresa})
    assert r.status_code == 200 and r.json()["codigo"] == "LO-01"
    linhas = cliente.get(_url(f"/empresas/{empresa}/painel")).json()["linhas"]
    renovar = next(l for l in linhas if l["codigo"] == "LO-01")
    assert "Requerer a renovação" in renovar["titulo"] and renovar["vence"] == "2031-11-16"
    assert cliente.post(_url(f"/licencas/{lid}/renovacao"),
                        params={"empresa_id": empresa}).json()["codigo"] is None   # não duplica


def test_licenca_de_outra_cliente_nao_existe(cliente, empresa, ia):
    como(cliente, "diretoria@nova.demo")
    lid = _enviar(cliente, empresa).json()["id"]
    como(cliente, "diretoria@serraazul.demo")
    assert cliente.get(_url(f"/empresas/{empresa}/licencas")).status_code == 404
    assert cliente.get(_url(f"/empresas/{empresa}/condicionantes")).status_code == 404
    assert cliente.post(_url(f"/licencas/{lid}/leitura"),
                        params={"empresa_id": empresa}).status_code == 404
    assert cliente.post(_url(f"/licencas/{lid}/renovacao"),
                        params={"empresa_id": empresa}).status_code == 404


def test_pdf_que_nao_abre_e_arquivo_vazio(cliente, empresa):
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{empresa}/licencas"),
                     params={"tipo": "LO", "numero": "9/2026"},
                     files={"arquivo": ("x.pdf", b"nao sou um pdf", "application/pdf")})
    assert r.status_code == 422 and "PDF" in r.json()["detail"]
    r = cliente.post(_url(f"/empresas/{empresa}/licencas"),
                     params={"tipo": "LO", "numero": "9/2026"},
                     files={"arquivo": ("x.pdf", b"", "application/pdf")})
    assert r.status_code == 422


def test_etapa_de_licencas_na_instanciacao_acompanha(cliente, empresa, ia):
    como(cliente, "diretoria@nova.demo")
    etapas = {e["etapa"]: e for e in
              cliente.get(_url(f"/empresas/{empresa}/instanciacao")).json()["etapas"]}
    assert etapas["licencas"]["estado"] == "pendente"
    lid = _enviar(cliente, empresa).json()["id"]
    cliente.post(_url(f"/licencas/{lid}/leitura"), params={"empresa_id": empresa})
    etapas = {e["etapa"]: e for e in
              cliente.get(_url(f"/empresas/{empresa}/instanciacao")).json()["etapas"]}
    assert etapas["licencas"]["estado"] == "em_andamento"
    assert etapas["licencas"]["numeros"]["propostas"] == 2
    for c in cliente.get(_url(f"/empresas/{empresa}/condicionantes"), params={"status_": "pendente"}).json():
        cliente.post(_url(f"/condicionantes/{c['id']}/decisao"), params={"empresa_id": empresa},
                     json={"aprovar": True})
    etapas = {e["etapa"]: e for e in
              cliente.get(_url(f"/empresas/{empresa}/instanciacao")).json()["etapas"]}
    assert etapas["licencas"]["estado"] == "pronta" and etapas["licencas"]["numeros"]["aprovadas"] == 2
