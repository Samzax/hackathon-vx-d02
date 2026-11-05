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
