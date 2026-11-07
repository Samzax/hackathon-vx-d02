"""Personalização da empresa: prazo interno, normas internas e responsável padrão por área.

A norma não muda: o prazo legal continua o da norma, e o interno é meta da empresa — a torre mostra os
dois e cobra pelo interno.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from api.config import Config
from api.main import criar_app
from mitra import agenda, db, demo, personalizacao as pers, torre, usuarios
from tests.test_api import CURADORIA, SENHA, _banco_da_demo, _url, como

HOJE = date(2026, 11, 7)
DESDE = date(2026, 5, 1)
POR = "Paulo Ribeiro (Regulatório)"


# ------------------------------------------------------------------ domínio


@pytest.fixture
def serra():
    conn = db.conectar(":memory:")
    ids = demo.montar(conn)
    yield conn, ids
    conn.close()


def _linha(conn, ativo: str, codigo: str, hoje: date = HOJE):
    return {l.codigo: l for l in torre.painel(conn, 1, hoje, DESDE, ativo=ativo)}[codigo]


def test_prazo_interno_mostra_os_dois_e_cobra_pelo_interno(serra):
    conn, _ = serra
    antes = _linha(conn, "B3", "R95-03")        # DCE/RISR: datas fixas, em dia hoje
    assert antes.status == agenda.EM_DIA and antes.vence_interno is None
    legal = date.fromisoformat(antes.vence)
    # a empresa decide entregar 15 dias antes
    pers.definir_prazo_interno(conn, 1, "R95-03", 15, POR)
    com_meta = _linha(conn, "B3", "R95-03")
    assert com_meta.vence == antes.vence                    # o prazo legal não mudou
    assert com_meta.vence_interno == (legal - timedelta(days=15)).isoformat()
    assert com_meta.dias_antes == 15 and "eta interna da empresa" in com_meta.nota
    # no dia seguinte à meta, a torre já cobra, mesmo com o prazo legal em aberto
    depois = _linha(conn, "B3", "R95-03", hoje=date.fromisoformat(com_meta.vence_interno) +
                    timedelta(days=1))
    assert depois.status == agenda.ATRASADA and depois.vence > depois.vence_interno


def test_prazo_interno_nao_muda_o_que_ja_estava_atrasado_nem_o_cumprido(serra):
    conn, _ = serra
    atrasada = _linha(conn, "B3", "R95-01")
    assert atrasada.status == agenda.ATRASADA
    pers.definir_prazo_interno(conn, 1, "R95-01", 10, POR)
    com_meta = _linha(conn, "B3", "R95-01")
    assert com_meta.status == agenda.ATRASADA and com_meta.dias_antes == 10


def test_prazo_interno_zero_tira_a_meta_e_codigo_alheio_e_recusado(serra):
    conn, _ = serra
    pers.definir_prazo_interno(conn, 1, "R95-03", 15, POR)
    assert "R95-03" in pers.prazos_internos(conn, 1)
    pers.definir_prazo_interno(conn, 1, "R95-03", 0, POR)
    assert pers.prazos_internos(conn, 1) == {}
    with pytest.raises(pers.ErroPersonalizacao, match="não existe"):
        pers.definir_prazo_interno(conn, 1, "NAO-EXISTE", 5, POR)
    with pytest.raises(pers.ErroPersonalizacao, match="use de 0 a"):
        pers.definir_prazo_interno(conn, 1, "R95-03", 500, POR)


def test_norma_interna_nasce_vigente_e_entra_na_torre(serra):
    conn, ids = serra
    pers.definir_responsavel_padrao(conn, 1, "barragem", "Gerência de Geotecnia", POR)
    codigo = pers.nova_norma_interna(
        conn, 1, titulo="Inspeção interna mensal da crista", por=POR, tipo_ativo="barragem",
        area="barragem", agenda="mensal+5d", periodicidade="Mensal",
        prazo="Até 5 dias após o fim do mês", evidencia="Relatório interno assinado",
        vigencia_desde="2026-01-01")
    assert codigo == "INT-01"
    v = db.versao(conn, codigo, empresa="Mineradora Serra Azul")
    assert v["titulo"] == "Inspeção interna mensal da crista" and v["status"] == "vigente"
    assert v["responsavel"] == "Gerência de Geotecnia"      # veio do responsável padrão da área
    assert v["decidida_por"] == POR                         # a empresa aprovando o que é dela
    assert codigo in {o.codigo for o in db.obrigacoes_do_ativo(conn, ids["B1"])}
    assert codigo in {l.codigo for l in torre.painel(conn, 1, HOJE, DESDE, ativo="B1")}
    assert [n["codigo"] for n in pers.normas_internas(conn, 1)] == [codigo]
    assert pers.nova_norma_interna(conn, 1, titulo="Outra", por=POR) == "INT-02"


def test_norma_interna_recusa_regra_e_agenda_invalidas(serra):
    conn, _ = serra
    with pytest.raises(pers.ErroPersonalizacao, match="precisa de um título"):
        pers.nova_norma_interna(conn, 1, titulo="  ", por=POR)
    with pytest.raises(pers.ErroPersonalizacao, match="agenda"):
        pers.nova_norma_interna(conn, 1, titulo="X", por=POR, agenda="de vez em quando")
    with pytest.raises(pers.ErroPersonalizacao, match="condição inválida"):
        pers.nova_norma_interna(conn, 1, titulo="X", por=POR, regra="dpa >>> alto")
    with pytest.raises(pers.ErroPersonalizacao, match="área desconhecida"):
        pers.nova_norma_interna(conn, 1, titulo="X", por=POR, area="inventada")


def test_norma_interna_de_uma_empresa_nao_vale_para_outra(serra):
    conn, _ = serra
    outra = db.criar_empresa(conn, "Vizinha (fictícia)")
    b1_outra = db.criar_ativo(conn, outra, "barragem", "B1", "Barragem da vizinha",
                              {"uf": "MG", "dpa": "alto", "cri": "alto", "inserida_pnsb": True})
    codigo = pers.nova_norma_interna(conn, 1, titulo="Padrão só da Serra Azul", por=POR,
                                     tipo_ativo="barragem", area="barragem", agenda="anual+30d")
    assert codigo not in {o.codigo for o in db.obrigacoes_do_ativo(conn, b1_outra)}
    assert pers.normas_internas(conn, outra) == []


# ------------------------------------------------------------------ API


@pytest.fixture
def cfg(tmp_path):
    banco, cache = _banco_da_demo(tmp_path)
    return Config(banco=banco, banco_cache=cache, armazenamento=str(tmp_path / "uploads"),
                  token_servico="token-de-teste-do-agente")


@pytest.fixture
def cliente(cfg):
    with TestClient(criar_app(cfg)) as c:
        yield c


def test_api_a_empresa_personaliza_e_a_plataforma_so_le(cliente, cfg):
    como(cliente, CURADORIA)
    emp = cliente.get(_url("/empresas")).json()[0]["id"]
    r = cliente.put(_url(f"/empresas/{emp}/prazos-internos"), json={"codigo": "R95-03", "dias_antes": 15})
    assert r.status_code == 403 and "só lê" in r.json()["detail"]
    como(cliente, "regulatorio@serraazul.demo")
    assert cliente.put(_url(f"/empresas/{emp}/prazos-internos"),
                       json={"codigo": "R95-03", "dias_antes": 15}).status_code == 200
    linhas = cliente.get(_url(f"/empresas/{emp}/painel")).json()["linhas"]
    linha = next(l for l in linhas if l["codigo"] == "R95-03" and l["ativo"] == "B3")
    assert linha["dias_antes"] == 15 and linha["vence_interno"] < linha["vence"]
    p = cliente.get(_url(f"/empresas/{emp}/personalizacao")).json()
    assert p["prazos_internos"][0]["codigo"] == "R95-03" and p["areas"]
    assert any(t["acao"] == "prazo_interno" for t in cliente.get(_url("/auditoria")).json())


def test_api_norma_interna_e_responsavel_padrao(cliente, cfg):
    como(cliente, "regulatorio@serraazul.demo")
    emp = cliente.get(_url("/empresas")).json()[0]["id"]
    assert cliente.put(_url(f"/empresas/{emp}/responsaveis-padrao"),
                       json={"area": "barragem", "responsavel": "Gerência de Geotecnia"}).status_code == 200
    r = cliente.post(_url(f"/empresas/{emp}/normas-internas"), json={
        "titulo": "Inspeção interna mensal da crista", "tipo_ativo": "barragem", "area": "barragem",
        "agenda": "mensal+5d", "periodicidade": "Mensal", "evidencia": "Relatório interno"})
    assert r.status_code == 201 and r.json()["codigo"] == "INT-01"
    linhas = cliente.get(_url(f"/empresas/{emp}/painel")).json()["linhas"]
    interna = next(l for l in linhas if l["codigo"] == "INT-01")
    assert interna["responsavel"] == "Gerência de Geotecnia" and interna["norma"] == "Padrão interno"
    p = cliente.get(_url(f"/empresas/{emp}/personalizacao")).json()
    assert p["responsaveis_padrao"]["barragem"] == "Gerência de Geotecnia"
    assert p["normas_internas"][0]["titulo"] == "Inspeção interna mensal da crista"
    r = cliente.post(_url(f"/empresas/{emp}/normas-internas"),
                     json={"titulo": "Com agenda ruim", "agenda": "de vez em quando"})
    assert r.status_code == 422


def test_api_gestor_nao_define_as_regras_da_empresa(cliente, cfg):
    como(cliente, "geotecnia@serraazul.demo")
    emp = cliente.get(_url("/empresas")).json()[0]["id"]
    r = cliente.put(_url(f"/empresas/{emp}/prazos-internos"), json={"codigo": "R95-03", "dias_antes": 15})
    assert r.status_code == 403 and "Regulatório ou da Diretoria" in r.json()["detail"]
    r = cliente.post(_url(f"/empresas/{emp}/normas-internas"), json={"titulo": "Minha regra"})
    assert r.status_code == 403


def test_api_personalizacao_de_outra_cliente_e_404(cliente, cfg):
    como(cliente, "regulatorio@serraazul.demo")
    conn = db.conectar(cfg.banco)
    outra = db.criar_empresa(conn, "Vizinha (fictícia)")
    usuarios.criar(conn, "dir@vizinha.demo", "Dir Vizinha", usuarios.DIRETORIA, senha=SENHA,
                   empresa="Vizinha (fictícia)")
    conn.close()
    assert cliente.get(_url(f"/empresas/{outra}/personalizacao")).status_code == 404
    assert cliente.put(_url(f"/empresas/{outra}/prazos-internos"),
                       json={"codigo": "R95-03", "dias_antes": 5}).status_code == 404
    assert cliente.post(_url(f"/empresas/{outra}/normas-internas"),
                        json={"titulo": "Na empresa alheia"}).status_code == 404
