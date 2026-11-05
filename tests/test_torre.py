from datetime import date

import pytest

from regulaia import agenda, db, demo, torre

HOJE = date(2026, 11, 7)
DESDE = date(2026, 5, 1)
TRECHO_245 = "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º."


@pytest.fixture
def serra():
    conn = db.conectar(":memory:")
    ids = demo.montar(conn)
    return conn, ids


def _status(conn, ativo, codigo, hoje=HOJE):
    linhas = {l.codigo: l for l in torre.painel(conn, 1, hoje, DESDE, ativo=ativo)}
    return linhas[codigo]


def test_licenca_renovacao_vence_em_breve_e_efluente_atrasado(serra):
    conn, _ = serra
    assert _status(conn, "L1", "LO-06").status == agenda.VENCE_LOGO
    lo02 = _status(conn, "L1", "LO-02")
    assert lo02.status == agenda.ATRASADA and lo02.faltando == ["2026-09"]
    assert _status(conn, "L1", "LO-01").status == agenda.EM_DIA


def test_viagem_no_tempo_a_renovacao_vira_atrasada(serra):
    conn, _ = serra
    assert _status(conn, "L1", "LO-06", hoje=date(2026, 11, 20)).status == agenda.ATRASADA


def test_obrigacoes_da_res_220_nao_aparecem_hoje(serra):
    conn, _ = serra
    hoje = {l.codigo for l in torre.painel(conn, 1, HOJE, DESDE)}
    assert not any(c.startswith("OB-") for c in hoje)
    depois = {l.codigo for l in torre.painel(conn, 1, date(2027, 8, 2), DESDE)}
    assert "OB-02" in depois


def test_transicao_lista_o_que_entra_em_2027(serra):
    conn, _ = serra
    trocas = {t.ativo: t for t in torre.transicao(conn, 1, date(2027, 8, 2))}
    assert "OB-01" in {o["codigo"] for o in trocas["B2"].entram}       # gente na ZAS
    assert "OB-01" not in {o["codigo"] for o in trocas["B1"].entram}
    assert "U1" not in trocas and "L1" not in trocas


def test_res_245_aprovada_tira_a_ob01_da_transicao_de_2027(serra):
    conn, _ = serra
    ato = db.registrar_ato(conn, "dou", "res-245", "Resolução ANM Nº 245", texto=TRECHO_245)
    vid = db.propor_versao(conn, "OB-01", {"prazo": "2029-12-26", "vigencia_desde": "2029-12-26"},
                           ato_id=ato, trecho=TRECHO_245)
    [m] = torre.mudancas(conn, 1)
    assert m.codigo == "OB-01" and m.ativos == ["B2"] and m.trecho == TRECHO_245
    db.decidir(conn, vid, aprovar=True, por="teste")
    trocas = {t.ativo: t for t in torre.transicao(conn, 1, date(2027, 8, 2))}
    assert "OB-01" not in {o["codigo"] for o in trocas["B2"].entram}
    assert torre.mudancas(conn, 1) == []


def test_unidade_tem_obrigacoes_da_nr22(serra):
    conn, _ = serra
    codigos = {l.codigo for l in torre.painel(conn, 1, HOJE, DESDE, ativo="U1")}
    assert {"N22-07", "N22-08", "N22-09"} <= codigos


def test_vaso_categoria_iii_com_exame_externo_vencido(serra):
    conn, _ = serra
    assert _status(conn, "E1", "N13-03").status == agenda.ATRASADA      # 30/10/2023 + 3 anos
    assert _status(conn, "E1", "N13-04").status == agenda.EM_DIA
    e2 = {l.codigo for l in torre.painel(conn, 1, HOJE, DESDE, ativo="E2")}
    assert {"N13-05", "N13-06"} <= e2 and "N13-03" not in e2
