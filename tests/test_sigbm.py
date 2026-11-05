"""Importar uma mineradora real do SIGBM e operar o dia a dia (entregar, responsável, histórico)."""

import csv
import re
from datetime import date

import pytest

from regulaia import agenda, db, demo, sigbm, torre

HOJE = date(2026, 11, 7)


@pytest.fixture
def conn():
    c = db.conectar(":memory:")
    demo.carregar_cadastro(c)
    return c


def test_arquivo_versionado_so_tem_empresa_e_nenhuma_coluna_pessoal():
    with open(sigbm.ARQUIVO, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert len(linhas) > 700
    assert set(linhas[0]) == set(sigbm.COLUNAS.values())
    assert all(re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", l["cnpj"]) for l in linhas)
    assert not {"latitude", "longitude", "cpf"} & set(linhas[0])


def test_busca_por_nome_sem_acento_e_por_cnpj():
    por_nome = sigbm.buscar("vale s.a")
    assert por_nome[0].nome == "VALE S.A." and len(por_nome[0].na_pnsb) > 50
    assert sigbm.buscar("33592510")[0].cnpj == por_nome[0].cnpj
    assert sigbm.buscar("33.592.510/0001-54")[0].cnpj == por_nome[0].cnpj
    assert sigbm.buscar("mineracao")    # sem acento acha "MINERAÇÃO"
    assert sigbm.buscar("xx") == []


def test_atributos_so_o_que_o_sigbm_diz():
    b = {"uf": "MG", "altura_m": "68,00", "volume_m3": "2.980.000,00", "pnsb": "Sim",
         "metodo": "10 - Alteamento a montante", "cri": "Médio", "dpa": "Alto",
         "situacao": "Em descaracterização (projeto/obras/monitoramento)",
         "nivel_emergencia": "Nível de Emergência 2", "embargo": "Embargada",
         "dce": "2º Campanha 2026 - Não Atestado", "dco": "-"}
    a = sigbm.atributos(b)
    assert a == {"uf": "MG", "altura_m": 68.0, "volume_m3": 2980000.0, "inserida_pnsb": True,
                 "metodo_construtivo": "montante", "cri": "medio", "dpa": "alto",
                 "situacao_operacional": "em_descaracterizacao", "nivel_emergencia": 2}
    assert not set(sigbm.FALTAM_NO_SIGBM) & set(a)
    assert sigbm.atributos(b | {"metodo": "Indefinido"}).get("metodo_construtivo") is None
    al = sigbm.alertas(b)
    assert "embargada no SIGBM" in al and any(x.startswith("DCE não atestada") for x in al)


def test_importar_monta_a_torre_sem_atraso_inventado(conn):
    emp = sigbm.buscar("33.592.510/0001-54")[0]
    eid = sigbm.importar(conn, emp, HOJE)
    assert sigbm.importar(conn, emp, HOJE) == eid          # de novo: a mesma empresa
    assert len(db.ativos(conn, eid)) == len(emp.na_pnsb)
    linhas = torre.painel(conn, eid, HOJE, date(2020, 1, 1))  # `desde` da demo não vale aqui
    assert linhas and not [l for l in linhas if l.status == agenda.ATRASADA]
    faltando = {c for l in linhas for c in l.dados_faltando}
    assert {"modificacao_estrutural", torre.ULTIMA_EXECUCAO} <= faltando
    assert db.empresas(conn)[-1]["origem"].startswith("SIGBM")


def test_preencher_dado_faltando_tira_do_dado_faltando(conn):
    eid = sigbm.importar(conn, sigbm.buscar("33.592.510/0001-54")[0], HOJE)
    a = db.ativos(conn, eid)[0]

    def faltando():
        return {c for l in torre.painel(conn, eid, HOJE, HOJE, ativo=a["codigo"]) for c in l.dados_faltando}

    assert "modificacao_estrutural" in faltando()
    db.atualizar_atributos(conn, a["id"], {"modificacao_estrutural": False, "alteamento_continuo": False,
                                          "mapa_inundacao_validado": True}, por="Geotecnia")
    assert not {"modificacao_estrutural", "alteamento_continuo", "mapa_inundacao_validado"} & faltando()
    ev = db.eventos(conn, a["id"])
    assert ev[0]["tipo"] == "cadastro" and "modificacao_estrutural = não" in ev[0]["texto"]


def test_entregar_da_baixa_e_desfazer_volta(conn):
    eid = sigbm.importar(conn, sigbm.buscar("33.592.510/0001-54")[0], HOJE)
    a = db.ativos(conn, eid)[0]
    rpsb = next(l for l in torre.painel(conn, eid, HOJE, HOJE, ativo=a["codigo"])
                if torre.ULTIMA_EXECUCAO in l.dados_faltando)
    db.entregar(conn, a["id"], rpsb.codigo, "2025-03-10", dia="2025-03-10", por="Geotecnia", obs="RPSB 2025")
    depois = next(l for l in torre.painel(conn, eid, HOJE, HOJE, ativo=a["codigo"]) if l.codigo == rpsb.codigo)
    assert depois.status in (agenda.EM_DIA, agenda.VENCE_LOGO) and depois.ultima == "2025-03-10"
    assert db.eventos(conn, a["id"], rpsb.codigo)[0]["texto"].startswith("entregue 2025-03-10")
    assert db.desfazer_entrega(conn, a["id"], rpsb.codigo, "2025-03-10")
    volta = next(l for l in torre.painel(conn, eid, HOJE, HOJE, ativo=a["codigo"]) if l.codigo == rpsb.codigo)
    assert volta.status == torre.DADO_FALTANDO


def test_responsavel_da_obrigacao_vale_no_painel_e_no_boletim():
    conn = db.conectar(":memory:")
    ids = demo.montar(conn)
    spec_desde = date(2026, 5, 1)
    l = next(l for l in torre.painel(conn, 1, HOJE, spec_desde) if l.ativo == "B2")
    db.atribuir(conn, ids["B2"], l.codigo, "Ana (consultoria)", por="Diretoria")
    l2 = next(x for x in torre.painel(conn, 1, HOJE, spec_desde) if x.ativo == "B2" and x.codigo == l.codigo)
    assert l2.responsavel == "Ana (consultoria)" and l2.responsavel_proprio
    assert db.eventos(conn, ids["B2"], l.codigo)[0]["texto"] == "responsável: Ana (consultoria)"
    assert l.titulo in torre.boletim(conn, 1, HOJE, spec_desde, responsavel="Ana (consultoria)")
    db.atribuir(conn, ids["B2"], l.codigo, "")
    l3 = next(x for x in torre.painel(conn, 1, HOJE, spec_desde) if x.ativo == "B2" and x.codigo == l.codigo)
    assert not l3.responsavel_proprio


def test_calendario_do_mes_e_planilha():
    import io
    import openpyxl
    from regulaia import operacao

    conn = db.conectar(":memory:")
    ids = demo.montar(conn)
    linhas = torre.painel(conn, 1, HOJE, date(2026, 5, 1))
    venc = operacao.vencimentos_no_mes(conn, linhas, 2026, 11)
    fir_b1 = [v for v in venc if v.linha.ativo == "B1" and "FIR" in v.linha.titulo]
    assert {v.dia for v in fir_b1} == {"2026-11-15", "2026-11-30"}       # período a período, não só o próximo
    outubro = operacao.vencimentos_no_mes(conn, linhas, 2026, 10)
    assert any(v.entregue for v in outubro) and any(not v.entregue for v in outubro)   # B3 deixou de entregar
    l = next(l for l in linhas if l.ativo == "B3" and l.status == agenda.ATRASADA and l.faltando)
    assert operacao.periodo_para_entrega(l, HOJE) == l.faltando[0]
    wb = openpyxl.load_workbook(io.BytesIO(operacao.planilha(linhas, "teste")))
    ws = wb["Obrigações"]
    assert ws.max_row == len(linhas) + 1 and ws.freeze_panes == "A2"
    assert "Resumo por ativo" in wb.sheetnames
    assert ids
