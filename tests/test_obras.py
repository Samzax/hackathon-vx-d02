"""Vertical obras (fase B, 7/11/2026): o catálogo NR-18/NR-35 entra pelo motor que já existe.
A torre calcula status para uma construtora, a evidência dá baixa pela regra e a CAT de acidente
fatal abre o isolamento do local por gatilho (NR-18, 18.16.23) — tudo sem código novo de torre."""

from datetime import date

from mitra import agenda, db, demo, evidencias, torre

HOJE = date(2026, 11, 7)


def _construtora(conn) -> tuple[int, int]:
    emp = db.criar_empresa(conn, "Construtora Horizonte (fictícia)", ficticia=True, setor="construcao")
    aid = db.criar_ativo(conn, emp, "obra", "OB-01", "Obra Edifício Horizonte",
                         {"categoria_obra": "edificacao", "fase_obra": "execucao", "trabalhadores": 80,
                          "trabalho_altura": True, "uf": "PR", "municipio": "Curitiba"},
                         "Engenharia da Obra")
    return emp, aid


def test_torre_cobra_a_obra_com_o_mesmo_motor():
    conn = db.conectar(":memory:")
    demo.montar(conn)                    # o catálogo público (cadastro/*.csv) já traz NR-18 e NR-35
    emp, _ = _construtora(conn)
    linhas = torre.painel(conn, emp, HOJE, date(2026, 1, 1))
    por = {l.codigo: l for l in linhas}
    assert {"N18-01", "N18-05", "N35-01", "N35-02", "N35-06"} <= set(por)
    assert all(l.ativo == "OB-01" for l in linhas)
    assert por["N18-05"].status == agenda.ATRASADA          # inspeção semanal das redes, sem evidência
    # a demolição só vale para obra de demolição: nesta edificação a regra tira a obrigação da torre
    assert "N18-13" not in por


def test_regra_sem_atributo_vira_dado_faltando_nao_presuncao():
    conn = db.conectar(":memory:")
    demo.montar(conn)
    emp = db.criar_empresa(conn, "Construtora Sem Cadastro (fictícia)", ficticia=True, setor="construcao")
    db.criar_ativo(conn, emp, "obra", "OB-02", "Obra Galpão", {"uf": "PR"}, "Engenharia")
    linhas = torre.painel(conn, emp, HOJE, date(2026, 1, 1))
    n35 = [l for l in linhas if l.codigo.startswith("N35-")]
    assert n35 and all(l.status == torre.DADO_FALTANDO for l in n35)   # ninguém disse se há trabalho em altura


def test_evidencia_de_obra_da_baixa_pela_regra():
    conn = db.conectar(":memory:")
    demo.montar(conn)
    emp, _ = _construtora(conn)
    texto = ("Relatório de Inspeção Periódica do SPIQ\n"
             "Ativo: OB-01\nObra Edifício Horizonte\n"
             "Data da inspeção: 05/11/2026\nTodos os elementos aprovados.")
    le = evidencias.ler(conn, texto, emp, HOJE)
    assert le.completa, le.problemas
    assert le.documento == "Inspeção do SPIQ" and le.ativo == "OB-01" and le.obrigacao == "N35-06"
    assert le.metodo == "regra" and le.data == "2026-11-05"
    evidencias.registrar(conn, le, "spiq.pdf")
    linhas = torre.painel(conn, emp, HOJE, date(2026, 1, 1))
    assert next(l for l in linhas if l.codigo == "N35-06").status in (agenda.EM_DIA, agenda.CUMPRIDA)


def test_cat_de_acidente_fatal_abre_o_isolamento_por_gatilho():
    conn = db.conectar(":memory:")
    demo.montar(conn)
    emp, aid = _construtora(conn)
    texto = ("Comunicação de Acidente de Trabalho - CAT\n"
             "Ativo: OB-01\nData do acidente: 05/11/2026\n"
             "Descrição: queda de altura com óbito do trabalhador (acidente fatal).")
    le = evidencias.ler(conn, texto, emp, HOJE)
    assert le.completa, le.problemas
    assert le.documento == "CAT" and le.obrigacao == "N18-11"      # a CAT comprova a comunicação
    assert le.acionar == ["N18-12"] and "acidente fatal" in le.gatilhos[0].lower()
    evidencias.registrar(conn, le, "cat.pdf")
    abertos = db.acionamentos_abertos(conn, HOJE.isoformat())
    assert (aid, "N18-12") in abertos                              # isolar o local, aberto por gatilho
