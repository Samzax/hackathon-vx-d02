from datetime import date

import pytest

from mitra import agenda as ag

HOJE = date(2026, 11, 5)
DESDE = date(2026, 9, 1)


def test_quinzenal_em_dia_e_atrasada():
    feitos = ["2026-09-1Q", "2026-09-2Q", "2026-10-1Q"]
    s = ag.situacao("quinzenal+15d", feitos, HOJE, DESDE)
    # 2026-10-2Q vence em 15/11: ainda não venceu, mas está a 10 dias
    assert s.status == ag.EM_DIA and s.proximo.rotulo == "2026-10-2Q"
    s = ag.situacao("quinzenal+15d", ["2026-09-1Q", "2026-10-1Q"], HOJE, DESDE)
    assert s.status == ag.ATRASADA and [p.rotulo for p in s.faltando] == ["2026-09-2Q"]


def test_quinzenal_vence_logo():
    feitos = ["2026-09-1Q", "2026-09-2Q", "2026-10-1Q"]
    s = ag.situacao("quinzenal+15d", feitos, date(2026, 11, 12), DESDE)
    assert s.status == ag.VENCE_LOGO and s.proximo.vence == date(2026, 11, 15)


def test_datas_fixas_campanha_da_dce():
    s = ag.situacao("datas:03-31,09-30", [], HOJE, date(2026, 6, 1))
    assert s.status == ag.ATRASADA and s.faltando[0].rotulo == "2026-09-30"
    s = ag.situacao("datas:03-31,09-30", ["2026-09-30"], HOJE, date(2026, 6, 1))
    assert s.status == ag.EM_DIA and s.proximo.rotulo == "2027-03-31"


def test_a_cada_n_anos_conta_da_ultima_execucao():
    s = ag.situacao("anos:3", ["2023-12-01"], HOJE, DESDE)
    assert s.status == ag.VENCE_LOGO and s.proximo.vence == date(2026, 12, 1)
    s = ag.situacao("anos:3", ["2023-06-01"], HOJE, DESDE)
    assert s.status == ag.ATRASADA
    assert ag.situacao("anos:3", [], HOJE, DESDE).status == ag.ATRASADA


def test_data_unica_e_evento():
    assert ag.situacao("data:2027-08-02", [], HOJE, DESDE).status == ag.EM_DIA
    assert ag.situacao("data:2026-11-20", [], HOJE, DESDE).status == ag.VENCE_LOGO
    assert ag.situacao("data:2026-10-01", [], HOJE, DESDE).status == ag.ATRASADA
    assert ag.situacao("data:2026-10-01", ["2026-09-20"], HOJE, DESDE).status == ag.CUMPRIDA
    assert ag.situacao("evento", [], HOJE, DESDE).status == ag.GATILHO


def test_agenda_invalida():
    for ruim in ("diaria+1d", "semanal", "datas:3-31", "anos:x", "data:2026-13-01", ""):
        with pytest.raises((ag.AgendaInvalida, ValueError)):
            ag.validar(ruim)


def test_unica_le_o_prazo_da_obrigacao():
    assert ag.situacao("unica", [], HOJE, DESDE, prazo="2026-11-20").status == ag.VENCE_LOGO
    assert ag.situacao("unica", [], HOJE, DESDE, prazo="2029-12-26").status == ag.EM_DIA


def test_trimestral():
    s = ag.situacao("trimestral+30d", ["2026-T3"], HOJE, date(2026, 7, 1))
    assert s.status == ag.EM_DIA and s.proximo.rotulo == "2026-T4"
    s = ag.situacao("trimestral+30d", [], HOJE, date(2026, 7, 1))
    assert s.status == ag.ATRASADA and [p.rotulo for p in s.faltando] == ["2026-T3"]


def test_periodo_de_uma_execucao():
    assert ag.periodo_de("quinzenal+0d", date(2026, 10, 9)) == "2026-10-1Q"
    assert ag.periodo_de("quinzenal+15d", date(2026, 10, 16)) == "2026-10-2Q"
    assert ag.periodo_de("mensal+15d", date(2026, 9, 30)) == "2026-09"
    assert ag.periodo_de("trimestral+30d", date(2026, 8, 1)) == "2026-T3"
    assert ag.periodo_de("datas:03-31,09-30", date(2026, 9, 12)) == "2026-09-30"
    assert ag.periodo_de("datas:03-31,09-30", date(2026, 10, 2)) == "2027-03-31"
    assert ag.periodo_de("anos:3", date(2026, 11, 6)) == "2026-11-06"


@pytest.mark.parametrize("periodo, esperado", [
    ("2026-10-1Q", "1ª quinzena de outubro/2026"),
    ("2026-09", "setembro/2026"),
    ("2026-T3", "3º trimestre/2026"),
    ("2026-S2", "2º semestre/2026"),
    ("2026-10-30", "30/10/2026"),
    ("2026", "2026"),
])
def test_rotulo_humano(periodo, esperado):
    assert ag.rotulo_humano(periodo) == esperado


def test_semanal_comeca_na_segunda_e_vence_depois_do_domingo():
    ps = ag.periodos("semanal+3d", date(2027, 4, 1), date(2027, 4, 12))
    assert [(p.rotulo, p.fim, p.vence) for p in ps][:2] == [
        ("2027-W13", date(2027, 4, 4), date(2027, 4, 7)), ("2027-W14", date(2027, 4, 11), date(2027, 4, 14))]
    assert ag.periodo_de("semanal+3d", date(2027, 4, 7)) == "2027-W14"
    assert ag.rotulo_humano("2027-W14") == "semana de 05/04/2027"


@pytest.mark.parametrize("texto, atual, esperado", [
    ("Semanal", "quinzenal+0d", "semanal+0d"),
    ("Mensalmente, até o dia 10", "trimestral+30d", "mensal+30d"),
    ("Quinzenal", "quinzenal+15d", None),              # não mudou
    ("Semanal ou mensal", "quinzenal+0d", None),       # ambíguo: deixa para a pessoa
    ("Semanal", "anos:3", None),                        # agenda por execução: não mexe
])
def test_agenda_acompanha_a_periodicidade(texto, atual, esperado):
    assert ag.agenda_para(texto, atual) == esperado


@pytest.mark.parametrize("agenda, texto", [
    ("quinzenal+0d", "quinzenal, até o fim de cada quinzena"),
    ("quinzenal+15d", "quinzenal, até 15 dias depois de cada quinzena"),
    ("anos:3", "a cada 3 anos, contados da última execução"),
    ("anos:1", "a cada ano, contado da última execução"),
    ("datas:03-31,09-30", "todo ano em 31/03, 30/09"),
    ("data:2027-08-02", "uma vez, até 02/08/2027"),
    ("evento", "quando houver o gatilho"),
])
def test_descrever_agenda(agenda, texto):
    assert ag.descrever(agenda) == texto
