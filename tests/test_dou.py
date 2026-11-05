from datetime import date
from pathlib import Path

import pytest

from collector.dou import NotCached, collect_day, load_act, parse_listing

FIXTURES = Path(__file__).parent / "fixtures"
RES_245 = "resolucao-anm-n-245-de-31-de-julho-de-2026-723029571"


@pytest.fixture
def cache(tmp_path):
    """Monta um cache/ temporário com as páginas reduzidas de 4 ago. 2026."""
    (tmp_path / "listing").mkdir()
    (tmp_path / "acts").mkdir()
    src = FIXTURES / "dou"
    (tmp_path / "listing" / "do1_2026-08-04.html").write_text(
        (src / "do1_2026-08-04.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "acts" / f"{RES_245}.html").write_text(
        (src / f"{RES_245}.html").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def test_funil_de_4_de_agosto(cache):
    day = collect_day(date(2026, 8, 4), cache=cache)
    assert day.total == 339
    assert len(day.anm) == 23
    assert [a.identifica for a in day.normative] == [
        "Resolução ANM Nº 245, DE 31 DE julho DE 2026"
    ]
    assert day.missing == []


def test_res_245_traz_o_novo_prazo(cache):
    act = load_act(RES_245, cache)
    assert act.published == "04/08/2026"
    assert act.edition == "145"
    assert act.page == "66"
    assert "Agência Nacional de Mineração" in act.organ
    assert any("26 de dezembro de 2029" in p and "§ 1º do art. 7º" in p for p in act.paragraphs)


def test_ato_fora_do_cache_nao_vai_para_a_rede(tmp_path):
    with pytest.raises(NotCached):
        load_act("qualquer-ato-123", tmp_path)


def test_listagem_sem_params_vem_vazia():
    assert parse_listing("<html><body>manutenção</body></html>", "do1") == []
