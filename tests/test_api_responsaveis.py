"""Responsáveis técnicos, dado pessoal e escopo por unidade.

O CPF é guardado cifrado, lido mascarado, e ver o inteiro fica na auditoria. A conta restrita a uma
unidade não vê, não entrega e não comenta nada da outra — como no isolamento entre empresas.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.config import Config
from api.main import criar_app
from regulaia import db, instanciacao as inst, pessoal, usuarios
from tests.test_api import CURADORIA, SENHA, _banco_da_demo, _url, como

CHAVE = "chave-de-teste-" + "a" * 48
CPF = "123.456.789" + "-09"          # fictício, montado em pedaços (nada com cara de CPF versionado)
OUTRO_CPF = "987.654.321" + "-00"
NOVA = "Mineradora Nova (fictícia)"


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setenv(pessoal.VARIAVEL, CHAVE)


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
def empresa(cliente, cfg) -> dict:
    """Uma cliente instanciada com duas unidades, um ativo em cada e contas: Diretoria, TI e um gestor
    restrito à Mina A."""
    como(cliente, CURADORIA)
    eid = cliente.post(_url("/instanciacoes"), json={
        "nome": NOVA, "razao_social": "Mineradora Nova S.A.", "cnpj": None, "ufs": ["MG"],
        "ficticia": True}).json()["empresa_id"]
    conn = db.conectar(cfg.banco)
    inst.criar_unidade(conn, eid, "Mina A", "teste", uf="MG")
    inst.criar_unidade(conn, eid, "Mina B", "teste", uf="MG")
    ids = {
        "A1": inst.criar_ativo(conn, eid, tipo="barragem", codigo="A1", nome="Barragem da Mina A",
                               por="teste", unidade="Mina A", responsavel="Geotecnia",
                               atributos={"uf": "MG", "dpa": "alto", "cri": "alto"}),
        "B1": inst.criar_ativo(conn, eid, tipo="barragem", codigo="B1", nome="Barragem da Mina B",
                               por="teste", unidade="Mina B", responsavel="Geotecnia",
                               atributos={"uf": "MG", "dpa": "alto", "cri": "alto"}),
    }
    usuarios.criar(conn, "diretoria@nova.demo", "Diretoria Nova", usuarios.DIRETORIA, senha=SENHA,
                   empresa=NOVA)
    usuarios.criar(conn, "ti@nova.demo", "TI Nova", usuarios.ADMIN, senha=SENHA, empresa=NOVA)
    usuarios.criar(conn, "geo.a@nova.demo", "Geo da Mina A", usuarios.GESTOR, area="Geotecnia",
                   senha=SENHA, empresa=NOVA, unidades=["Mina A"])
    usuarios.criar(conn, "geo.todas@nova.demo", "Geo de todas", usuarios.GESTOR, area="Geotecnia",
                   senha=SENHA, empresa=NOVA)
    conn.close()
    return {"id": eid, "ativos": ids}


# ------------------------------------------------------------------ o CPF


def test_cpf_entra_cifrado_sai_mascarado_e_ver_fica_na_auditoria(cliente, empresa, cfg):
    eid = empresa["id"]
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "Ana Souza", "cpf": CPF, "registro": "CREA MG-123456",
        "art_numero": "ART-2026-1", "art_vigencia_ate": "2027-03-31", "unidade": "Mina A"})
    assert r.status_code == 201, r.text
    rid = r.json()["responsavel_id"]
    assert r.json()["obrigacao_art"] == "ART-01"        # a ART vencendo virou obrigação
    [resp] = cliente.get(_url(f"/empresas/{eid}/responsaveis")).json()
    assert resp["cpf_mascarado"] == "***.456." + "789-**" and "cpf" not in resp
    assert resp["papel_rotulo"] == "Responsável técnico" and resp["nome"] == "Ana Souza"
    # no banco não há CPF em claro
    conn = db.conectar(cfg.banco)
    guardado = conn.execute("SELECT cpf_cifrado FROM responsavel_tecnico WHERE id = ?", (rid,)).fetchone()[0]
    conn.close()
    assert pessoal.digitos(CPF) not in guardado and CPF not in guardado
    # ver o CPF inteiro é do Regulatório, da Diretoria e da TI, e fica na trilha
    r = cliente.get(_url(f"/responsaveis/{rid}/cpf"), params={"empresa_id": eid})
    assert r.status_code == 200 and r.json()["cpf"] == CPF
    trilha = cliente.get(_url("/auditoria")).json()
    visto = next(t for t in trilha if t["acao"] == "cpf_visto")
    assert visto["alvo"] == "Ana Souza" and visto["usuario"] == "diretoria@nova.demo"
    criado = next(t for t in trilha if t["acao"] == "responsavel_criado")
    assert criado["detalhe"]["com_cpf"] is True and "cpf" not in criado["detalhe"]


def test_quem_nao_pode_nao_ve_o_cpf(cliente, empresa):
    eid = empresa["id"]
    como(cliente, "diretoria@nova.demo")
    rid = cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "Ana Souza", "cpf": CPF,
        "unidade": "Mina A"}).json()["responsavel_id"]
    como(cliente, "geo.todas@nova.demo")        # gestor vê a lista mascarada, não o CPF
    assert cliente.get(_url(f"/empresas/{eid}/responsaveis")).json()[0]["cpf_mascarado"].startswith("***")
    r = cliente.get(_url(f"/responsaveis/{rid}/cpf"), params={"empresa_id": eid})
    assert r.status_code == 403 and "Regulatório" in r.json()["detail"]
    como(cliente, "ti@nova.demo")               # a TI da própria empresa pode
    assert cliente.get(_url(f"/responsaveis/{rid}/cpf"), params={"empresa_id": eid}).status_code == 200
    como(cliente, CURADORIA)                    # a plataforma, não: acompanha a empresa sem ver pessoa
    r = cliente.get(_url(f"/responsaveis/{rid}/cpf"), params={"empresa_id": eid})
    assert r.status_code == 403 and "não vê o CPF" in r.json()["detail"]
    assert cliente.get(_url(f"/empresas/{eid}/responsaveis")).status_code == 200     # mascarado, sim


def test_cpf_invalido_e_empresa_de_outra_cliente(cliente, empresa):
    eid = empresa["id"]
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "Fulano", "cpf": "111.111.111" + "-11",
        "unidade": "Mina A"})
    assert r.status_code == 422 and "não é um CPF válido" in r.json()["detail"]
    r = cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "Fulano", "unidade": "Mina Fantasma"})
    assert r.status_code == 422 and "não tem a unidade" in r.json()["detail"]
    r = cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "Fulano"})
    assert r.status_code == 422 and "qual unidade ou ativo" in r.json()["detail"]
    como(cliente, "diretoria@serraazul.demo")       # de outra cliente: 404
    assert cliente.get(_url(f"/empresas/{eid}/responsaveis")).status_code == 404
    assert cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "Fulano", "unidade": "Mina A"}).status_code == 404


def test_sem_a_chave_guardar_cpf_responde_503_e_a_api_segue_de_pe(cliente, empresa, monkeypatch):
    eid = empresa["id"]
    monkeypatch.delenv(pessoal.VARIAVEL, raising=False)
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "Ana Souza", "cpf": CPF, "unidade": "Mina A"})
    assert r.status_code == 503 and pessoal.VARIAVEL in r.json()["detail"]
    # sem CPF, o cadastro entra: a chave só faz falta para dado pessoal
    r = cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "coordenador_paebm", "nome": "Bruno Lima", "unidade": "Mina A"})
    assert r.status_code == 201
    assert cliente.get(_url(f"/empresas/{eid}/responsaveis")).json()[0]["cpf_mascarado"] == "não informado"
    assert cliente.get(_url(f"/empresas/{eid}/painel")).status_code == 200


# ------------------------------------------------------------------ LGPD


def test_exportar_e_apagar_dados_pessoais_sao_da_ti_da_empresa(cliente, empresa):
    eid = empresa["id"]
    como(cliente, "diretoria@nova.demo")
    cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "Ana Souza", "cpf": CPF, "unidade": "Mina A"})
    r = cliente.get(_url(f"/empresas/{eid}/dados-pessoais"))     # Diretoria não é TI
    assert r.status_code == 403
    como(cliente, "ti@nova.demo")
    r = cliente.get(_url(f"/empresas/{eid}/dados-pessoais"))
    assert r.status_code == 200 and r.json()["empresa"] == NOVA
    [pessoa] = r.json()["pessoas"]
    assert pessoa["cpf"] == CPF and pessoa["nome"] == "Ana Souza"      # direito de acesso do titular
    r = cliente.delete(_url(f"/empresas/{eid}/dados-pessoais"))
    assert r.status_code == 200 and r.json()["removidos"] == 1
    assert cliente.get(_url(f"/empresas/{eid}/dados-pessoais")).json()["pessoas"] == []
    trilha = cliente.get(_url("/auditoria")).json()
    assert {"dados_pessoais_exportados", "dados_pessoais_apagados"} <= {t["acao"] for t in trilha}
    como(cliente, CURADORIA)        # a plataforma não exporta nem apaga dado pessoal da cliente
    assert cliente.get(_url(f"/empresas/{eid}/dados-pessoais")).status_code == 403


def test_consentimento_do_empreendedor_pessoa_fisica_fica_registrado(cliente, empresa, cfg):
    eid = empresa["id"]
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
        "papel": "responsavel_tecnico", "nome": "João da Silva", "cpf": OUTRO_CPF, "unidade": "Mina A",
        "consentimento_para": "cadastrar o próprio CPF como empreendedor pessoa física"})
    assert r.status_code == 201
    conn = db.conectar(cfg.banco)
    from regulaia import responsaveis as dominio
    [pessoa] = dominio.responsaveis(conn, eid)
    conn.close()
    assert pessoa.consentimento["para_que"].startswith("cadastrar o próprio CPF")
    assert pessoa.consentimento["quem"] and pessoa.consentimento["em"]


# ------------------------------------------------------------------ escopo por unidade


def test_conta_restrita_a_uma_unidade_nao_ve_nada_da_outra(cliente, empresa):
    eid, a1, b1 = empresa["id"], empresa["ativos"]["A1"], empresa["ativos"]["B1"]
    eu = como(cliente, "geo.a@nova.demo")
    assert "Mina A" in eu["visao"]
    assert {a["codigo"] for a in cliente.get(_url(f"/empresas/{eid}/ativos")).json()} == {"A1"}
    linhas = cliente.get(_url(f"/empresas/{eid}/painel")).json()["linhas"]
    assert linhas and {l["ativo"] for l in linhas} == {"A1"}
    assert cliente.get(_url(f"/ativos/{a1}")).status_code == 200
    assert cliente.get(_url(f"/ativos/{b1}")).status_code == 403     # da Mina B: de outra unidade
    # não entrega, não comenta e não atribui nada da outra unidade
    escritas = [
        cliente.post(_url("/entregas"), json={"ativo_id": b1, "codigo": "R95-01"}),
        cliente.post(_url("/comentarios"), json={"ativo_id": b1, "texto": "não é minha unidade"}),
        cliente.post(_url("/atribuicoes"), json={"ativo_id": b1, "codigo": "R95-01",
                                                 "responsavel": "Geotecnia"}),
        cliente.patch(_url(f"/ativos/{b1}/atributos"), json={"atributos": {"dpa2": 9}}),
    ]
    assert [r.status_code for r in escritas] == [403] * len(escritas)
    # e o boletim, o calendário e a planilha só falam da unidade dele
    assert "B1" not in cliente.get(_url(f"/empresas/{eid}/boletim")).text
    assert "A1" in cliente.get(_url(f"/empresas/{eid}/boletim")).text
    ics = cliente.get(_url(f"/empresas/{eid}/calendario.ics")).text
    assert "A1" in ics and "B1" not in ics
    venc = cliente.get(_url(f"/empresas/{eid}/calendario"), params={"ano": 2026, "mes": 11}).json()
    assert all(v["ativo"] == "A1" for v in venc)
    assert all(d["ativo"] == "A1" for d in cliente.get(_url(f"/empresas/{eid}/dados-faltando")).json())


def test_gestor_sem_restricao_ve_as_duas_unidades(cliente, empresa):
    eid = empresa["id"]
    como(cliente, "geo.todas@nova.demo")
    assert {a["codigo"] for a in cliente.get(_url(f"/empresas/{eid}/ativos")).json()} == {"A1", "B1"}
    como(cliente, "diretoria@nova.demo")        # e a Diretoria também
    assert {a["codigo"] for a in cliente.get(_url(f"/empresas/{eid}/ativos")).json()} == {"A1", "B1"}


def test_responsaveis_da_outra_unidade_ficam_fora_da_lista_do_gestor_restrito(cliente, empresa):
    eid = empresa["id"]
    como(cliente, "diretoria@nova.demo")
    for unidade, nome in (("Mina A", "Ana da A"), ("Mina B", "Bruno da B")):
        cliente.post(_url(f"/empresas/{eid}/responsaveis"), json={
            "papel": "responsavel_tecnico", "nome": nome, "unidade": unidade})
    assert len(cliente.get(_url(f"/empresas/{eid}/responsaveis")).json()) == 2
    como(cliente, "geo.a@nova.demo")
    [visto] = cliente.get(_url(f"/empresas/{eid}/responsaveis")).json()
    assert visto["nome"] == "Ana da A" and visto["unidade"] == "Mina A"


def test_escopo_por_unidade_e_de_gestor_nao_de_diretoria(cliente, cfg, empresa):
    """Diretoria e Regulatório da empresa veem tudo: gravar unidades nessas contas é erro de cadastro."""
    conn = db.conectar(cfg.banco)
    with pytest.raises(usuarios.ErroConta, match="escopo por unidade é de gestor"):
        usuarios.criar(conn, "dir.restrita@nova.demo", "Diretoria restrita", usuarios.DIRETORIA,
                       senha=SENHA, empresa=NOVA, unidades=["Mina A"])
    conn.close()
