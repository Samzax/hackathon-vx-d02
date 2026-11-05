from datetime import date
from pathlib import Path

import pytest

from collector.xml_dou import _ordem, funil_por_dia, load_month

FIXTURES = Path(__file__).parent / "fixtures" / "dou"
AMOSTRA = FIXTURES / "S01_amostra.zip"
AGOSTO = Path(__file__).resolve().parent.parent / "data" / "raw" / "dou" / "S01082026.zip"


@pytest.fixture(scope="module")
def amostra():
    return {a.id_materia: a for a in load_month(AMOSTRA)}


def test_partes_do_mesmo_ato_viram_um_ato_so(amostra):
    # 24187862 vem em 5 arquivos (-1 a -5) no ZIP
    res = amostra["24187862"]
    assert res.art_type == "Resolução"
    assert len(res.texto_html) > 5 * 1000
    assert sum(1 for a in amostra.values() if a.id_materia == "24187862") == 1


def test_ordem_numerica_das_partes():
    nomes = ["a-10.xml", "a-2.xml", "a-1.xml", "b.xml"]
    assert sorted(nomes, key=_ordem) == ["a-1.xml", "a-2.xml", "a-10.xml", "b.xml"]


def test_res_245_no_xml(amostra):
    res = next(a for a in amostra.values() if "Nº 245" in a.identifica)
    assert res.is_anm and res.is_normative
    assert res.pub_date == date(2026, 8, 4)
    assert res.page == "66" and res.edition == "145"
    assert any("26 de dezembro de 2029" in p for p in res.paragraphs)


def test_res_246_exclui_sigbm_da_prorrogacao(amostra):
    """Segundo caso de ouro: prorroga prazos, mas não os de barragem."""
    res = next(a for a in amostra.values() if "Nº 246" in a.identifica)
    assert res.is_anm and res.is_normative
    texto = res.text
    assert "Sistema Integrado de Gestão de Barragens de Mineração (SIGBM)" in texto
    assert "não se aplica a obrigações cujo descumprimento possa trazer risco" in texto


def test_edicao_extra_entra_no_funil(amostra):
    assert {a.pub_name for a in amostra.values()} >= {"DO1", "DO1E"}


@pytest.mark.skipif(not AGOSTO.exists(), reason="ZIP de agosto não baixado (data/raw/dou)")
def test_funil_real_de_agosto():
    funis = {f.dia: f for f in funil_por_dia(load_month(AGOSTO))}
    d4 = funis[date(2026, 8, 4)]
    assert d4.por_edicao == {"DO1": 339, "DO1E": 9}   # bate com a listagem do site
    assert d4.anm == 23
    assert [a.identifica for a in d4.normativos] == ["Resolução ANM Nº 245, DE 31 DE julho DE 2026"]
    assert sum(len(f.normativos) for f in funis.values()) == 2


@pytest.mark.skipif(not AGOSTO.exists(), reason="ZIP de agosto/2026 fora do Git (data/raw/dou)")
def test_numeros_do_funil_na_tela_e_nos_documentos():
    """7.884 → 825 → 2: a tela e os documentos citam o mês medido, não um número de memória."""
    funis = funil_por_dia(load_month(AGOSTO))
    total = f"{sum(f.total for f in funis):,}".replace(",", ".")
    anm = str(sum(f.anm for f in funis))
    raiz = AGOSTO.parent.parent.parent.parent
    app = (raiz / "app.py").read_text(encoding="utf-8")
    assert f'"Atos no DOU (ago/2026)", "{total}"' in app and f'"Da ANM", "{anm}"' in app
    assert f"{total} atos/mês" in app and f"{anm} da ANM" in app
    for doc in ("README.md", "docs/ROTEIRO_DEMO.md", "docs/ARQUITETURA.md"):
        texto = (raiz / doc).read_text(encoding="utf-8")
        assert total in texto and anm in texto, doc
