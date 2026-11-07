"""A API da instanciação: quem cria a cliente, quem cadastra, quem entra em operação.

A curadoria da plataforma leva a cliente nova para dentro (criar a empresa, escolher as barragens do
SIGBM); nos dados operacionais ela só lê, então quem cadastra unidade e ativo e quem entra em operação
é a própria empresa. Cliente nenhuma vê a instanciação de outra.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.config import Config
from api.main import criar_app
from regulaia import db, usuarios
from tests.test_api import CURADORIA, SENHA, _banco_da_demo, _url, como, entrar

NOVA = "Mineradora Nova (fictícia)"


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
def nova(cliente) -> dict:
    """Uma empresa instanciada pela curadoria, ainda sem ativo e sem conta."""
    como(cliente, CURADORIA)
    r = cliente.post(_url("/instanciacoes"), json={
        "nome": NOVA, "razao_social": "Mineradora Nova S.A.", "cnpj": "11.222.333/0001-81",
        "ufs": ["mg"], "ficticia": True})
    assert r.status_code == 201, r.text
    return r.json()


def _conta(cfg, email: str, papel: str, area: str | None = None, empresa: str = NOVA) -> None:
    conn = db.conectar(cfg.banco)
    usuarios.criar(conn, email, email.split("@")[0].title(), papel, area=area, senha=SENHA, empresa=empresa)
    conn.close()


# ------------------------------------------------------------------ etapa 1: cadastro


def test_so_a_curadoria_instancia_uma_cliente_nova(cliente, nova):
    e = nova["estado"]
    assert e["razao_social"] == "Mineradora Nova S.A." and e["cnpj"] == "11222333000181"
    assert e["ufs"] == ["MG"] and e["percentual"] == 12 and not e["em_operacao"]
    etapas = {x["etapa"]: x for x in e["etapas"]}
    assert etapas["cadastro"]["estado"] == "pronta" and etapas["cadastro"]["por"]
    assert etapas["ativos"]["estado"] == "pendente" and etapas["ativos"]["falta"]
    assert any(t["acao"] == "instanciacao_criar" for t in cliente.get(_url("/auditoria")).json())
    como(cliente, "diretoria@serraazul.demo")       # a cliente não instancia ninguém
    r = cliente.post(_url("/instanciacoes"), json={"nome": "Minha própria (fictícia)",
                                                   "razao_social": "X", "cnpj": None, "ufs": []})
    assert r.status_code == 403


def test_cadastro_repetido_e_cnpj_invalido_sao_recusados_e_auditados(cliente, nova):
    como(cliente, CURADORIA)
    r = cliente.post(_url("/instanciacoes"), json={"nome": NOVA, "razao_social": "Outra",
                                                   "cnpj": None, "ufs": []})
    assert r.status_code == 422 and "já existe uma empresa" in r.json()["detail"]
    r = cliente.post(_url("/instanciacoes"), json={"nome": "Outra (fictícia)", "razao_social": "Outra S.A.",
                                                   "cnpj": "123", "ufs": []})
    assert r.status_code == 422 and "14 dígitos" in r.json()["detail"]
    trilha = cliente.get(_url("/auditoria")).json()
    assert any(t["acao"] == "instanciacao_criar" and t["resultado"] == "recusado" for t in trilha)


def test_cliente_nao_ve_a_instanciacao_de_outra(cliente, nova):
    eid = nova["empresa_id"]
    como(cliente, "diretoria@serraazul.demo")
    for caminho in ("instanciacao", "unidades", "dados-faltando"):
        assert cliente.get(_url(f"/empresas/{eid}/{caminho}")).status_code == 404, caminho
    assert cliente.post(_url(f"/empresas/{eid}/unidades"), json={"nome": "Mina de outra"}).status_code == 404
    assert eid not in [i["empresa_id"] for i in cliente.get(_url("/instanciacoes")).json()]
    como(cliente, CURADORIA)                        # a plataforma vê todas
    assert eid in [i["empresa_id"] for i in cliente.get(_url("/instanciacoes")).json()]


def test_empresa_que_entrou_por_outro_caminho_nao_tem_instanciacao(cliente):
    """A Serra Azul da demo é montada direto: a rota diz isso em vez de inventar etapas."""
    entrar(cliente, "diretoria@serraazul.demo")
    emp = cliente.get(_url("/empresas")).json()[0]["id"]
    r = cliente.get(_url(f"/empresas/{emp}/instanciacao"))
    assert r.status_code == 404 and "não passou pela instanciação" in r.json()["detail"]


# ------------------------------------------------------------------ etapa 2: unidades e ativos


def test_a_empresa_cadastra_unidade_e_ativo_e_a_plataforma_so_le(cliente, nova, cfg):
    eid = nova["empresa_id"]
    _conta(cfg, "diretoria@nova.demo", "diretoria")
    r = cliente.post(_url(f"/empresas/{eid}/unidades"), json={"nome": "Mina Nova", "uf": "MG"})
    assert r.status_code == 403 and "só lê" in r.json()["detail"]
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{eid}/unidades"),
                     json={"nome": "Mina Nova", "uf": "mg", "municipio": "Itabirito"})
    assert r.status_code == 201 and r.json()["nome"] == "Mina Nova" and r.json()["uf"] == "MG"
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/ativos"), json={
        "tipo": "barragem", "codigo": "B1", "nome": "Barragem Nova", "unidade": "Mina Nova",
        "atributos": {"uf": "mg", "altura_m": "25", "dpa": "alto", "inserida_pnsb": "sim"}})
    assert r.status_code == 201, r.text
    [u] = cliente.get(_url(f"/empresas/{eid}/unidades")).json()
    assert u["ativos"] == ["B1"]
    ativo = cliente.get(_url(f"/ativos/{r.json()['ativo_id']}")).json()["ativo"]
    assert ativo["atributos"] == {"uf": "MG", "altura_m": 25, "dpa": "alto", "inserida_pnsb": True}
    ruim = cliente.post(_url(f"/empresas/{eid}/instanciacao/ativos"), json={
        "tipo": "barragem", "codigo": "B2", "nome": "B2", "unidade": "Mina Fantasma"})
    assert ruim.status_code == 422 and "não tem a unidade" in ruim.json()["detail"]
    etapas = {x["etapa"]: x for x in cliente.get(_url(f"/empresas/{eid}/instanciacao")).json()["etapas"]}
    assert etapas["ativos"]["estado"] == "pronta" and etapas["cobertura"]["estado"] == "pronta"
    assert etapas["ativos"]["numeros"] == {"ativos": 1, "unidades": 1}


def test_unidade_repetida_e_ativo_com_valor_errado_sao_recusados(cliente, nova, cfg):
    eid = nova["empresa_id"]
    _conta(cfg, "diretoria@nova.demo", "diretoria")
    como(cliente, "diretoria@nova.demo")
    cliente.post(_url(f"/empresas/{eid}/unidades"), json={"nome": "Mina Nova"})
    r = cliente.post(_url(f"/empresas/{eid}/unidades"), json={"nome": "Mina Nova"})
    assert r.status_code == 422 and "já tem uma unidade" in r.json()["detail"]
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/ativos"), json={
        "tipo": "barragem", "codigo": "B1", "nome": "B1", "atributos": {"altura_m": "alta"}})
    assert r.status_code == 422 and "não é número" in r.json()["detail"]
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/ativos"), json={
        "tipo": "mina", "codigo": "M1", "nome": "M1"})
    assert r.status_code == 422 and "tipo de ativo desconhecido" in r.json()["detail"]


# ------------------------------------------------- a planilha (modelo e erro na linha)


def test_modelo_csv_e_planilha_com_o_erro_na_linha(cliente, nova, cfg):
    eid = nova["empresa_id"]
    modelo = cliente.get(_url("/instanciacoes/modelo.csv"))
    assert modelo.status_code == 200 and modelo.text.splitlines()[0].startswith("tipo,codigo,nome")
    assert "attachment" in modelo.headers["content-disposition"]
    assert "classe" in cliente.get(_url("/instanciacoes/modelo.csv"),
                                   params={"tipo": "equipamento"}).text.splitlines()[0]
    _conta(cfg, "diretoria@nova.demo", "diretoria")
    como(cliente, "diretoria@nova.demo")
    ruim = "tipo,codigo,nome,uf\nbarragem,B1,Um,MG\nbarragem,,Sem código,MG\n"
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/planilha"),
                     files={"arquivo": ("ativos.csv", ruim.encode(), "text/csv")})
    corpo = r.json()
    assert r.status_code == 200 and corpo["importados"] == 0 and corpo["erros"] == 1
    assert corpo["linhas"][1]["linha"] == 3 and "código vazio" in corpo["linhas"][1]["erro"]
    assert cliente.get(_url(f"/empresas/{eid}/ativos")).json() == []       # tudo ou nada
    boa = "tipo,codigo,nome,uf\nbarragem,B1,Um,MG\nbarragem,B2,Dois,MG\n"
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/planilha"),
                     files={"arquivo": ("ativos.csv", boa.encode(), "text/csv")})
    assert r.json()["importados"] == 2 and r.json()["erros"] == 0
    assert {a["codigo"] for a in cliente.get(_url(f"/empresas/{eid}/ativos")).json()} == {"B1", "B2"}
    assert any(t["acao"] == "ativos_planilha" for t in cliente.get(_url("/auditoria")).json())


def test_planilha_so_conferir_nao_grava(cliente, nova, cfg):
    eid = nova["empresa_id"]
    _conta(cfg, "diretoria@nova.demo", "diretoria")
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/planilha"), params={"conferir": True},
                     files={"arquivo": ("ativos.csv", b"tipo,codigo,nome\nbarragem,B9,Nove\n", "text/csv")})
    assert r.json()["erros"] == 0 and r.json()["importados"] == 0
    assert cliente.get(_url(f"/empresas/{eid}/ativos")).json() == []


def test_planilha_vazia_e_grande_demais(cliente, nova, cfg):
    eid = nova["empresa_id"]
    _conta(cfg, "diretoria@nova.demo", "diretoria")
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/planilha"),
                     files={"arquivo": ("vazia.csv", b"", "text/csv")})
    assert r.status_code == 422
    grande = b"tipo,codigo,nome\n" + b"barragem,B1,Um\n" * 400_000
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/planilha"),
                     files={"arquivo": ("grande.csv", grande, "text/csv")})
    assert r.status_code == 413


# ------------------------------------------------------------------ etapas 3 e 8


def test_dados_que_faltam_e_entrada_em_operacao_com_pendencia(cliente, nova, cfg):
    eid = nova["empresa_id"]
    _conta(cfg, "diretoria@nova.demo", "diretoria")
    _conta(cfg, "geo@nova.demo", "gestor", area="Geotecnia")
    como(cliente, "diretoria@nova.demo")
    cliente.post(_url(f"/empresas/{eid}/instanciacao/ativos"), json={
        "tipo": "barragem", "codigo": "B1", "nome": "Barragem Nova", "responsavel": "Geotecnia",
        "atributos": {"uf": "MG", "inserida_pnsb": "sim", "dpa": "alto", "cri": "alto"}})
    faltam = cliente.get(_url(f"/empresas/{eid}/dados-faltando")).json()
    assert faltam and all(d["obrigacoes"] and d["pergunta"] for d in faltam)
    assert "B1" in {d["ativo"] for d in faltam}
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/operacao"), json={"desde": "2026-11-07"})
    assert r.status_code == 200, r.text
    assert r.json()["monitorado_desde"] == "2026-11-07" and r.json()["pendencias"]
    assert cliente.get(_url(f"/empresas/{eid}/instanciacao")).json()["em_operacao"]
    assert cliente.post(_url(f"/empresas/{eid}/instanciacao/operacao"), json={}).status_code == 422
    como(cliente, "geo@nova.demo")      # gestor não decide a entrada em operação
    assert cliente.post(_url(f"/empresas/{eid}/instanciacao/operacao"), json={}).status_code == 403
    faltam = cliente.get(_url(f"/empresas/{eid}/dados-faltando")).json()
    assert all(d["ativo"] == "B1" for d in faltam)       # o gestor vê só os ativos da área dele


def test_entrar_em_operacao_sem_ativo_e_recusado(cliente, nova, cfg):
    eid = nova["empresa_id"]
    _conta(cfg, "diretoria@nova.demo", "diretoria")
    como(cliente, "diretoria@nova.demo")
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/operacao"), json={})
    assert r.status_code == 422 and "nenhum ativo" in r.json()["detail"]


# ------------------------------------------------------------------ as barragens do SIGBM


def test_barragens_do_sigbm_entram_as_escolhidas(cliente):
    """A curadoria vê todas as barragens do CNPJ (não só as da PNSB) e escolhe quais entram."""
    como(cliente, CURADORIA)
    achada = cliente.get(_url("/sigbm/busca"), params={"termo": "MINERACAO"}).json()["achadas"][0]
    r = cliente.post(_url("/instanciacoes"), json={
        "nome": "Instanciada do SIGBM (teste)", "razao_social": achada["nome"],
        "cnpj": achada["cnpj"], "ufs": achada["ufs"][:2], "ficticia": True})
    assert r.status_code == 201, r.text
    eid = r.json()["empresa_id"]
    assert r.json()["estado"]["no_sigbm"]
    doc = cliente.get(_url("/instanciacoes/sigbm"), params={"cnpj": achada["cnpj"]}).json()
    assert len(doc["barragens"]) == achada["barragens"] >= achada["na_pnsb"]
    escolhidas = [b["codigo"] for b in doc["barragens"][:2]]
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/sigbm"), json={"codigos": escolhidas})
    assert r.status_code == 201, r.text
    codigos = {a["codigo"] for a in cliente.get(_url(f"/empresas/{eid}/ativos")).json()}
    assert codigos == {f"SIGBM-{c}" for c in escolhidas}
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/sigbm"), json={"codigos": ["nao-existe"]})
    assert r.status_code == 422 and "não tem a barragem" in r.json()["detail"]


def test_sigbm_sem_cnpj_nao_tem_o_que_buscar(cliente):
    como(cliente, CURADORIA)
    r = cliente.post(_url("/instanciacoes"), json={"nome": "Pessoa física (fictícia)",
                                                   "razao_social": "João da Silva", "cnpj": None,
                                                   "ufs": ["MG"], "ficticia": True})
    eid = r.json()["empresa_id"]
    r = cliente.post(_url(f"/empresas/{eid}/instanciacao/sigbm"), json={"codigos": ["1"]})
    assert r.status_code == 422 and "não tem CNPJ" in r.json()["detail"]
    assert cliente.get(_url("/instanciacoes/sigbm"),
                   params={"cnpj": "00000000000000"}).status_code == 404
