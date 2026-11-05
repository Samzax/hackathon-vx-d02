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


def test_b3_com_fir_e_eir_atrasados(serra):
    conn, _ = serra
    fir, eir = _status(conn, "B3", "R95-01"), _status(conn, "B3", "R95-02")
    assert fir.status == eir.status == agenda.ATRASADA
    assert fir.faltando == ["2026-10-1Q"] and fir.norma == "Res. ANM 95/2022"


def test_b4_dado_faltando_e_rpsb_vencendo(serra):
    conn, _ = serra
    assert _status(conn, "B4", "R95-08").status == torre.DADO_FALTANDO
    rpsb = _status(conn, "B4", "R95-05")
    assert rpsb.status == agenda.VENCE_LOGO and rpsb.vence == "2026-11-20"
    assert "R95-15" in {l.codigo for l in torre.painel(conn, 1, HOJE, DESDE, ativo="B4")}   # NE1


def test_res_95_sai_na_troca_de_norma(serra):
    conn, _ = serra
    trocas = {t.ativo: t for t in torre.transicao(conn, 1, date(2027, 8, 2))}
    assert "R95-01" in {o["codigo"] for o in trocas["B1"].saem}
    assert "OB-02" in {o["codigo"] for o in trocas["B1"].entram}
    assert not any(l.codigo.startswith("R95") for l in torre.painel(conn, 1, date(2027, 8, 2), DESDE))


def test_zas_mte_e_anm_na_mesma_data(serra):
    """NR-22 (Portaria MTE 105/2026) e Res. ANM 245/2026: ZAS em 26/12/2029 para não montante."""
    conn, _ = serra
    agora = {l.codigo for l in torre.painel(conn, 1, HOJE, DESDE, ativo="B1")}
    assert "N22-ZAS1" in agora                       # B1 é a montante: vale já
    linha = [f for f in torre.futuras(conn, 1, HOJE) if f.ativo == "B2"]
    zas = {(f.codigo, f.dia, f.proposta) for f in linha if f.codigo in ("N22-ZAS2", "OB-01")}
    assert ("N22-ZAS2", "2029-12-26", False) in zas
    assert ("OB-01", "2027-08-02", False) in zas     # antes da Res. 245
    ato = db.registrar_ato(conn, "dou", "res-245", "Resolução ANM Nº 245", texto=TRECHO_245)
    db.propor_versao(conn, "OB-01", {"prazo": "2029-12-26", "vigencia_desde": "2029-12-26"},
                     ato_id=ato, trecho=TRECHO_245)
    linha = [f for f in torre.futuras(conn, 1, HOJE) if f.ativo == "B2" and f.codigo == "OB-01"]
    assert {(f.dia, f.proposta) for f in linha} == {("2027-08-02", False), ("2029-12-26", True)}


def test_boletim_da_diretoria_tem_tudo(serra):
    conn, _ = serra
    ato = db.registrar_ato(conn, "dou", "res-245", "Resolução ANM Nº 245", texto=TRECHO_245)
    db.propor_versao(conn, "OB-01", {"prazo": "2029-12-26", "vigencia_desde": "2029-12-26"},
                     ato_id=ato, trecho=TRECHO_245)
    b = torre.boletim(conn, 1, HOJE, DESDE)
    assert "## 🔴 Atrasadas (4)" in b
    assert "1ª quinzena de outubro/2026" in b and "2026-10-1Q" not in b
    assert "Requerer a renovação da licença" in b                  # L1 vence em 15/11
    assert "⚪ Falta dado no cadastro" in b and "modificacao_estrutural" in b
    assert "OB-01" in b and "26/12/2029" in b and "começa a valer em" in b


def test_boletim_do_gestor_so_tem_os_ativos_dele(serra):
    conn, _ = serra
    b = torre.boletim(conn, 1, HOJE, DESDE, responsavel="Manutenção da Usina")
    assert "1 ativo ·" in b and "**E1**" in b
    assert "**B3**" not in b and "**L1**" not in b
    assert "Mudanças de norma" not in b


def test_calendario_ics_do_gestor(serra):
    conn, _ = serra
    ics = torre.calendario(conn, 1, HOJE, DESDE, responsavel="Gerência de Meio Ambiente")
    linhas = ics.split("\r\n")
    assert linhas[0] == "BEGIN:VCALENDAR" and ics.endswith("END:VCALENDAR\r\n")
    assert all(len(l.encode("utf-8")) <= 75 for l in linhas)
    assert ics.count("BEGIN:VEVENT") == ics.count("END:VEVENT") > 0
    desdobrado = ics.replace("\r\n ", "")
    assert "SUMMARY:ATRASADA · L1 · Monitorar os efluentes" in desdobrado
    assert "DTSTART;VALUE=DATE:20261115" in desdobrado                        # renovação da LO
    assert "B3" not in desdobrado                                             # só os ativos dele


def test_calendario_lembra_quando_fica_amarela_e_nao_ocupa_a_agenda(serra):
    conn, _ = serra
    ics = torre.calendario(conn, 1, HOJE, DESDE).replace("\r\n ", "")
    eventos = ics.split("BEGIN:VEVENT")[1:]
    assert all("TRANSP:TRANSPARENT" in e for e in eventos)
    atrasadas = [e for e in eventos if "SUMMARY:ATRASADA" in e]
    assert atrasadas and not any("VALARM" in e for e in atrasadas)        # lembrete no passado não serve
    fir = next(e for e in eventos if "B1 · Preencher as FIR" in e and "ATRASADA" not in e)
    assert "TRIGGER:-P5D" in fir                       # quinzenal: amarela 5 dias antes
    assert any("TRIGGER:-P30D" in e for e in eventos)  # anual/plurianual: 30 dias antes
    assert ics.count("BEGIN:VALARM") == ics.count("END:VALARM")


def test_calendario_mostra_quando_a_res_220_comeca(serra):
    conn, _ = serra
    ics = torre.calendario(conn, 1, HOJE, DESDE, dias=365 * 4).replace("\r\n ", "")
    assert "DTSTART;VALUE=DATE:20270802" in ics and "Começa a valer: B" in ics


def test_plano_de_transicao(serra):
    conn, _ = serra
    p = torre.plano_transicao(conn, 1, date(2027, 8, 2), HOJE)
    assert "faltam 268 dias" in p and "## B1 · Barragem Serra I" in p
    assert "**Revisão Periódica (RPSB)** — 🔁 continua" in p
    assert "deixa de existir" not in p                     # cadastro da 220 é parcial: não afirmar o que não sabe
    so_usina = torre.plano_transicao(conn, 1, date(2027, 8, 2), HOJE, responsavel="Manutenção da Usina")
    assert "Nenhum dos ativos muda" in so_usina


def test_plano_explica_o_que_deixa_de_valer_por_ativo(serra):
    """B3 (DPA2 = 2) perde os treinamentos semestrais e as sirenes: a Res. 220 só cobra de DPA2 ≥ 4.
    B1 (DPA2 = 4, no limite) não perde nada: o "≥" do texto foi conferido."""
    conn, _ = serra
    p = torre.plano_transicao(conn, 1, date(2027, 8, 2), HOJE)
    b1 = p.split("## B1")[1].split("## B2")[0]
    b3 = p.split("## B3")[1].split("## B4")[0]
    assert "➖" not in b1
    assert "**Treinamento do PAEBM** — ➖ deixa de valer para este ativo" in b3
    assert "(Res. ANM 220/2025 art. 54), só para Barragens com DPA2 ≥ 4" in b3
    assert "**Sirenes e alerta** — ➖ deixa de valer" in b3
    assert "sem equivalente no cadastro" not in p


def test_rpsb_da_220_conta_a_ultima_rpsb_feita_pela_95(serra):
    """Na troca de norma a RPSB não 'zera': a última feita pela Res. 95 continua valendo."""
    conn, _ = serra
    dia = date(2027, 8, 2)
    b2 = {l.codigo: l for l in torre.painel(conn, 1, dia, DESDE, ativo="B2")}["OB-06"]
    assert b2.status == agenda.EM_DIA and b2.vence == "2028-02-14"          # RPSB de 14/02/2025 + 3 anos
    assert "R95-05" in b2.nota
    b4 = {l.codigo: l for l in torre.painel(conn, 1, dia, DESDE, ativo="B4")}["OB-06"]
    assert b4.status == agenda.ATRASADA and b4.vence == "2026-11-20"        # já vencia pela 95


def test_evidencia_propria_vale_mais_que_a_herdada(serra):
    conn, _ = serra
    b2 = next(a for a in db.ativos(conn, 1) if a["codigo"] == "B2")
    db.registrar_evidencia(conn, b2["id"], "OB-06", "2027-09-01")
    l = {l.codigo: l for l in torre.painel(conn, 1, date(2027, 10, 1), DESDE, ativo="B2")}["OB-06"]
    assert l.vence == "2030-09-01" and "R95-05" not in l.nota


def test_condicionantes_da_licenca_nao_somem_depois_da_validade(serra):
    """LC 140/2011 art. 14 §4: renovação pedida a tempo prorroga a licença; as condicionantes seguem."""
    conn, _ = serra
    depois = {l.codigo for l in torre.painel(conn, 1, date(2027, 8, 2), DESDE, ativo="L1")}
    assert {"LO-01", "LO-02", "LO-05"} <= depois
    assert "LO-06" not in depois                    # o pedido de renovação é que tem data para acabar


def test_boletim_nao_repete_a_data_quando_falta_uma_entrega_so(serra):
    """'venceu em 30/10/2026; falta: 30/10/2026' não diz nada; períodos de verdade continuam listados."""
    conn, _ = serra
    b = torre.boletim(conn, 1, HOJE, DESDE)
    assert "venceu em 30/10/2026; última evidência em 30/10/2023" in b         # exame externo do vaso E1 (a cada 3 anos)
    assert "venceu em 15/10/2026; falta: 1ª quinzena de outubro/2026" in b      # FIR da B3
    depois = torre.boletim(conn, 1, date(2027, 8, 10), DESDE)
    assert "falta: entrega única" not in depois and "falta: 10/03/2027" not in depois


def test_plano_de_transicao_cita_a_norma_dos_dois_lados(serra):
    """O plano é um arquivo solto: 'antes' e 'depois' dizem de que norma é cada artigo, sem repetir."""
    conn, _ = serra
    p = torre.plano_transicao(conn, 1, date(2027, 8, 2), HOJE)
    assert "(Res. ANM 95/2022, art. 19 I)" in p and "(Res. ANM 220/2025 art. 38 I)" in p
    assert "(art. 19 I)" not in p and "Res. ANM 220/2025, Res. ANM 220/2025" not in p
    assert torre.artigo_curto("Res. ANM 220/2025", "Res. ANM 220/2025 art. 38 I") == "art. 38 I"
    assert torre.artigo_curto("Res. ANM 95/2022", "art. 19 I") == "art. 19 I"


def test_rpsb_alteamento_continuo_tem_periodicidade_legivel():
    import csv
    from pathlib import Path

    with open(Path(__file__).parent.parent / "cadastro" / "res95_2022.csv", encoding="utf-8") as f:
        assert not [r["id"] for r in csv.DictReader(f) if " N " in r["periodicidade"]]


def test_nome_do_ato_sem_as_maiusculas_do_dou():
    assert torre.nome_ato("Resolução ANM Nº 245, DE 31 DE julho DE 2026") == "Resolução ANM nº 245, de 31 de julho de 2026"
    assert torre.nome_ato("PORTARIA MTE Nº 105, DE 5 DE MAIO DE 2026") == "Portaria MTE nº 105, de 5 de maio de 2026"
    assert torre.nome_ato("Ato colado na tela") == "Ato colado na tela" and torre.nome_ato(None) is None


def test_dado_faltando_em_portugues(serra):
    conn, _ = serra
    assert torre.campo_legivel("modificacao_estrutural") == "se passou por modificação estrutural"
    assert torre.campo_legivel("dpa2") == "pontuação de perda de vidas humanas do DPA (número)"
    assert torre.campo_legivel("inventado") == "inventado"
    b = torre.boletim(conn, 1, HOJE, DESDE)
    assert "informar se passou por modificação estrutural (modificacao_estrutural)" in b


def test_muitos_periodos_viram_um_intervalo(serra):
    conn, _ = serra
    b = torre.boletim(conn, 1, date(2027, 8, 10), DESDE)
    assert "falta: 10 períodos entre setembro/2026 e junho/2027" in b
    assert "falta: 4º trimestre/2026, 1º trimestre/2027, 2º trimestre/2027" in b      # até 3, por extenso


def test_zas_aprovada_vence_junto_com_a_nr22_no_painel(serra):
    """Aprovada a Res. 245, a OB-01 da B2 vence no mesmo dia da NR-22 (26/12/2029); no dia seguinte, as duas atrasam.
    Sem aprovação, a OB-01 continua cobrada desde 02/08/2027: nada muda sozinho."""
    conn, _ = serra
    assert _status(conn, "B2", "OB-01", date(2029, 12, 27)).vence == "2027-08-02"
    ato = db.registrar_ato(conn, "dou", "res-245", "Resolução ANM Nº 245", texto=TRECHO_245)
    vid = db.propor_versao(conn, "OB-01", {"prazo": "2029-12-26", "vigencia_desde": "2029-12-26"},
                           ato_id=ato, trecho=TRECHO_245)
    db.decidir(conn, vid, aprovar=True, por="teste")
    for codigo in ("OB-01", "N22-ZAS2"):
        assert _status(conn, "B2", codigo, date(2029, 12, 26)).status == agenda.VENCE_LOGO
        depois = _status(conn, "B2", codigo, date(2029, 12, 27))
        assert depois.status == agenda.ATRASADA and depois.vence == "2029-12-26"


def test_boletim_bate_com_o_amarelo_da_torre(serra):
    """O boletim olha 30 dias à frente, mas não pode contradizer o 'Vence em breve' da tela."""
    from collections import Counter

    conn, _ = serra
    amarelas = Counter(l.status for l in torre.painel(conn, 1, HOJE, DESDE))[agenda.VENCE_LOGO]
    b = torre.boletim(conn, 1, HOJE, DESDE)
    assert f", {amarelas} já em amarelo na torre)" in b
    secao = b.split("## 📅")[1].split("##")[0]
    marcadas = [l for l in secao.splitlines() if l.endswith(" 🟡")]
    assert sum(len(l.split("**")[1].split(", ")) for l in marcadas) == amarelas     # linha agrupada conta cada ativo
    assert "## 🟡" not in b                    # o título não promete amarelo para tudo


def test_boletim_junta_a_mesma_obrigacao_de_varios_ativos(serra):
    conn, _ = serra
    b = torre.boletim(conn, 1, HOJE, DESDE)
    assert "- **B1, B2, B4** · Preencher as FIR quinzenalmente" in b
    assert b.count("Preencher as FIR quinzenalmente") == 2          # a atrasada da B3 e a linha das três
    assert "(9, 3 já em amarelo na torre)" in b                      # a contagem continua por ativo
