from datetime import date

import pytest

from regulaia import agenda, db, demo, evidencias as ev, torre

HOJE = date(2026, 11, 7)
DESDE = date(2026, 5, 1)


@pytest.fixture
def conn():
    c = db.conectar(":memory:")
    demo.montar(c)
    return c


def _linha(conn, ativo, codigo):
    return {l.codigo: l for l in torre.painel(conn, 1, HOJE, DESDE, ativo=ativo)}[codigo]


def _pdf(nome):
    caminho = ev.exemplo(nome)
    if not caminho.exists():
        pytest.importorskip("reportlab")
        from regulaia import exemplos
        exemplos.gerar()
    return ev.texto_pdf(caminho)


def test_fir_da_b3_baixa_a_quinzena_atrasada(conn):
    antes = _linha(conn, "B3", "R95-01")
    assert antes.status == agenda.ATRASADA and "2026-10-1Q" in antes.faltando

    le = ev.ler(conn, _pdf("FIR_B3_2026-10-1Q.pdf"), 1, HOJE)
    assert (le.ativo, le.obrigacao, le.periodo, le.data) == ("B3", "R95-01", "2026-10-1Q", "2026-10-09")
    assert le.completa and le.metodo == "regra" and not le.gatilhos

    ev.registrar(conn, le, "FIR_B3_2026-10-1Q.pdf")
    depois = _linha(conn, "B3", "R95-01")
    assert depois.status != agenda.ATRASADA and "2026-10-1Q" not in depois.faltando


def test_fir_com_pontuacao_10_dispara_ise(conn):
    le = ev.ler(conn, _pdf("FIR_B2_2026-11-1Q_anomalia.pdf"), 1, HOJE)
    assert le.ativo == "B2"                       # "Serra I" não pode casar com "Serra II"
    assert le.pontuacao_maxima == 10
    assert le.gatilhos and "Especial" in le.gatilhos[0]


def test_boletim_de_efluentes_vai_para_a_licenca(conn):
    le = ev.ler(conn, _pdf("Boletim_efluentes_2026-09.pdf"), 1, HOJE)
    assert (le.ativo, le.obrigacao, le.periodo) == ("L1", "LO-02", "2026-09")
    ev.registrar(conn, le, "Boletim_efluentes_2026-09.pdf")
    assert _linha(conn, "L1", "LO-02").status != agenda.ATRASADA


def test_nome_parecido_nao_confunde_ativos(conn):
    ativos = db.ativos(conn, 1)
    nomes = {a["codigo"]: a["nome"] for a in ativos}
    texto = ev.normalizar(f"vistoria na {nomes['B2']}")
    assert ev._ativos_citados(texto, ativos) == ["B2"]


def test_sem_ativo_a_leitura_fica_incompleta_e_nao_registra(conn):
    le = ev.ler(conn, "Ficha de Inspeção Regular\nData da inspeção: 01/11/2026", 1, HOJE)
    assert le.ativo is None and not le.completa
    with pytest.raises(ValueError):
        ev.registrar(conn, le, "x.pdf")


def test_data_no_futuro_e_problema(conn):
    le = ev.ler(conn, "Ficha de Inspeção Regular (B3)\nData da inspeção: 20/12/2026", 1, HOJE)
    assert "data de execução no futuro" in le.problemas and le.periodo is None


class _IA:
    def __init__(self, dados):
        self.dados = dados

    def pedir_json(self, *a, **k):
        return self


def test_ia_nao_pode_inventar_data(conn):
    texto = "Ficha de Inspeção Regular (B3)\nvistoria feita sem data legível"
    le = ev.ler(conn, texto, 1, HOJE, roteador=_IA({"ativo": "B3", "data": "2026-10-09"}))
    assert le.metodo == "ia" and le.periodo is None
    assert any("não está no documento" in p for p in le.problemas)


def test_ia_completa_o_ativo_quando_a_regra_nao_acha(conn):
    texto = "Ficha de Inspeção Regular\nData da inspeção: 09/10/2026\nbarramento do córrego"
    le = ev.ler(conn, texto, 1, HOJE, roteador=_IA({"ativo": "B3", "data": None}))
    assert (le.ativo, le.periodo, le.metodo) == ("B3", "2026-10-1Q", "ia")
    assert le.completa
