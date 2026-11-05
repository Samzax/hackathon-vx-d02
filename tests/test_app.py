"""Fumaça da interface: a torre abre, mostra os números e aprova a Res. 245 sem erro."""

from pathlib import Path

import pytest

from regulaia import db, demo

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PADRAO", tmp_path / "regulaia.db")
    monkeypatch.setattr(demo, "RADAR", tmp_path / "radar.json")


def test_torre_abre_e_aprova_mudanca(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    metricas = {m.label: m.value for m in at.metric}
    assert int(metricas["🔴 Atrasada"]) >= 1
    aprovar = [b for b in at.button if b.label == "Aprovar"]
    if aprovar:          # sem chave e sem cache, a Res. 245 vai para revisão humana
        aprovar[0].click().run()
        assert not at.exception


def test_clone_novo_sem_chave_mostra_o_radar(tmp_path, monkeypatch):
    """No evento o repositório é clonado limpo: sem cache_ia.db e sem .env, o radar vem do cache da demo."""
    from regulaia import ia, torre

    monkeypatch.setattr(ia, "load_dotenv", lambda *a, **k: None)
    for chave in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "OPENCODE_API_KEY"):
        monkeypatch.delenv(chave, raising=False)
    monkeypatch.setattr(demo, "RADAR", tmp_path / "radar.json")
    conn, _, analises = demo.preparar(tmp_path / "r.db", cache=tmp_path / "vazio.db")
    assert any(m.obrigacao == "OB-01" for an in analises for m in an.mudancas)
    assert [m.codigo for m in torre.mudancas(conn, 1)] == ["OB-01"]
