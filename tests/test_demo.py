import pytest

from mitra import db, demo

TRECHO_245 = "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º."


@pytest.fixture
def serra():
    conn = db.conectar(":memory:")
    return conn, demo.montar(conn)


def _codigos(conn, ativo_id):
    return {o.codigo for o in db.obrigacoes_do_ativo(conn, ativo_id)}


def test_dpa2_igual_a_4_entra_no_art_39_i(serra):
    """Na Res. 220 o sinal é '≥' (> sublinhado). Com '>' a B1 ficaria sem RISR."""
    conn, ids = serra
    b1 = _codigos(conn, ids["B1"])
    assert "OB-04" in b1 and "OB-05" not in b1
    assert {"OB-11", "OB-14", "OB-15"} <= b1


def test_toda_barragem_tem_risr_por_um_dos_incisos_do_art_39(serra):
    conn, ids = serra
    for codigo, ativo_id in ids.items():
        if not codigo.startswith("B"):
            continue
        obs = _codigos(conn, ativo_id)
        assert len(obs & {"OB-04", "OB-05"}) == 1, codigo


def test_res_245_atinge_so_a_b2(serra):
    conn, ids = serra
    ato = db.registrar_ato(conn, "dou", "res-245", "Resolução ANM Nº 245", texto=TRECHO_245)
    db.propor_versao(conn, "OB-01", {"prazo": "2029-12-26", "vigencia_desde": "2029-12-26"},
                     ato_id=ato, trecho=TRECHO_245)
    afetadas = {
        codigo for codigo, ativo_id in ids.items()
        if any(o.pendente for o in db.obrigacoes_do_ativo(conn, ativo_id))
    }
    assert afetadas == {"B2"}


def test_b4_mostra_o_dado_que_falta(serra):
    conn, ids = serra
    obs = {o.codigo: o for o in db.obrigacoes_do_ativo(conn, ids["B4"])}
    assert obs["OB-09"].dados_faltando == ["modificacao_estrutural"]
