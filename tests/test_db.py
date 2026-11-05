from pathlib import Path

import pytest

from regulaia import db

SEED = Path(__file__).resolve().parent.parent / "seed_obligations.csv"
TRECHO_245 = "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º."


@pytest.fixture
def conn():
    c = db.conectar(":memory:")
    assert db.carregar_obrigacoes_csv(c, SEED) == 15
    return c


@pytest.fixture
def serra_azul(conn):
    emp = db.criar_empresa(conn, "Mineradora Serra Azul (fictícia)")
    ids = {
        "B1": db.criar_ativo(conn, emp, "barragem", "B1", "Barragem B1",
                             {"dpa": "alto", "dpa2": 6, "trabalhadores_zas": False}),
        "B2": db.criar_ativo(conn, emp, "barragem", "B2", "Barragem B2",
                             {"dpa": "alto", "dpa2": 6, "trabalhadores_zas": True}),
        "B3": db.criar_ativo(conn, emp, "barragem", "B3", "Barragem B3",
                             {"dpa": "baixo", "dpa2": 2, "trabalhadores_zas": False}),
    }
    return ids


def _res_245(conn):
    return db.registrar_ato(
        conn, "dou", "resolucao-anm-n-245-de-31-de-julho-de-2026-723029571",
        "Resolução ANM Nº 245, DE 31 DE julho DE 2026",
        publicado_em="2026-08-04", texto=TRECHO_245,
    )


def test_cadastro_comeca_no_estado_anterior_a_res_245(conn):
    ob01 = db.versao(conn, "OB-01")
    assert ob01["prazo"] == "2027-08-02"
    assert ob01["versao"] == 1


def test_res_245_muda_so_a_ob01_e_so_depois_de_aprovada(conn):
    antes = {f"OB-{i:02d}": db.versao(conn, f"OB-{i:02d}") for i in range(1, 16)}
    ato = _res_245(conn)

    vid = db.propor_versao(
        conn, "OB-01", {"prazo": "2029-12-26", "vigencia_desde": "2029-12-26"},
        ato_id=ato, trecho=TRECHO_245, fonte="Res. ANM 245/2026 art. 1",
    )
    # pendente: a vigente ainda é a antiga
    assert db.versao(conn, "OB-01")["prazo"] == "2027-08-02"

    db.decidir(conn, vid, aprovar=True, por="Gerente de Geotecnia")
    depois = {c: db.versao(conn, c) for c in antes}

    mudou = {c for c in antes if antes[c]["prazo"] != depois[c]["prazo"]}
    assert mudou == {"OB-01"}
    assert depois["OB-01"]["prazo"] == "2029-12-26"
    assert depois["OB-01"]["trecho"] == TRECHO_245
    assert db.diferencas(antes["OB-01"], depois["OB-01"]) == {
        "prazo": ("2027-08-02", "2029-12-26"),
        "vigencia_desde": ("2027-08-02", "2029-12-26"),
    }
    assert [v["status"] for v in db.historico(conn, "OB-01")] == ["substituida", "vigente"]


def test_rejeitar_mantem_a_versao_vigente(conn):
    vid = db.propor_versao(conn, "OB-01", {"prazo": "2030-01-01"}, ato_id=None, trecho=None)
    db.decidir(conn, vid, aprovar=False, por="Gerente de Geotecnia")
    assert db.versao(conn, "OB-01")["prazo"] == "2027-08-02"
    assert [v["status"] for v in db.historico(conn, "OB-01")] == ["vigente", "rejeitada"]


def test_nao_aceita_duas_mudancas_pendentes_nem_mudanca_vazia(conn):
    db.propor_versao(conn, "OB-01", {"prazo": "2029-12-26"}, ato_id=None, trecho=None)
    with pytest.raises(db.ErroCadastro):
        db.propor_versao(conn, "OB-01", {"prazo": "2030-01-01"}, ato_id=None, trecho=None)
    with pytest.raises(db.ErroCadastro):
        db.propor_versao(conn, "OB-02", {"prazo": db.versao(conn, "OB-02")["prazo"]},
                         ato_id=None, trecho=None)


def test_campo_desconhecido_nao_entra(conn):
    with pytest.raises(db.ErroCadastro):
        db.propor_versao(conn, "OB-01", {"status": "vigente"}, ato_id=None, trecho=None)


def test_ato_registrado_duas_vezes_e_o_mesmo(conn):
    assert _res_245(conn) == _res_245(conn)


def test_mudanca_na_ob01_aparece_so_na_barragem_com_gente_na_zas(conn, serra_azul):
    ato = _res_245(conn)
    db.propor_versao(conn, "OB-01", {"prazo": "2029-12-26"}, ato_id=ato, trecho=TRECHO_245)

    def pendentes(codigo):
        return {o.codigo for o in db.obrigacoes_do_ativo(conn, serra_azul[codigo]) if o.pendente}

    assert pendentes("B2") == {"OB-01"}
    assert pendentes("B1") == set()
    assert pendentes("B3") == set()


def test_obrigacoes_seguem_o_perfil_da_barragem(conn, serra_azul):
    def codigos(b):
        return {o.codigo for o in db.obrigacoes_do_ativo(conn, serra_azul[b])}

    b1, b3 = codigos("B1"), codigos("B3")
    assert {"OB-02", "OB-03", "OB-04", "OB-06", "OB-15"} <= b1   # DPA alto
    assert "OB-05" not in b1 and "OB-12" not in b1
    assert {"OB-02", "OB-03", "OB-05", "OB-08", "OB-12"} <= b3   # DPA baixo
    assert "OB-04" not in b3 and "OB-06" not in b3


def test_dado_faltando_aparece_em_vez_de_sumir(conn, serra_azul):
    obs = {o.codigo: o for o in db.obrigacoes_do_ativo(conn, serra_azul["B1"])}
    # alteamento_continuo não foi informado para a B1
    assert obs["OB-10"].dados_faltando == ["alteamento_continuo"]


def test_janela_de_vigencia(conn, serra_azul):
    # OB-02 (FIR quinzenal pela Res. 220) só vale a partir de 2027-08-02
    hoje = {o.codigo for o in db.obrigacoes_do_ativo(conn, serra_azul["B1"], em="2026-11-05")}
    depois = {o.codigo for o in db.obrigacoes_do_ativo(conn, serra_azul["B1"], em="2027-08-02")}
    assert "OB-02" not in hoje and "OB-02" in depois
    assert db.vale_em({"vigencia_desde": "2022-02-07", "vigencia_ate": "2027-08-01"}, "2027-08-01")
    assert not db.vale_em({"vigencia_desde": "2022-02-07", "vigencia_ate": "2027-08-01"}, "2027-08-02")
    assert db.vale_em({"vigencia_desde": None, "vigencia_ate": None}, "1999-01-01")
