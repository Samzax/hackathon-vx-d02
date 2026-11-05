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
    assert aprovar, "a Res. 245 deveria estar aguardando aprovação (cache da demo no Git)"
    aprovar[0].click().run()
    assert not at.exception
    assert not [b for b in at.button if b.label == "Aprovar"]


def _atrasadas(at) -> int:
    return int({m.label: m.value for m in at.metric}["🔴 Atrasada"])


def test_envio_de_fir_tira_a_b3_do_atraso(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    antes = _atrasadas(at)
    exemplo = next(s for s in at.selectbox if s.label.endswith("documento de exemplo"))
    exemplo.select("FIR_B3_2026-10-1Q.pdf").run()
    next(b for b in at.button if b.label == "Ler documento").click().run()
    assert not at.exception and not at.error          # FIR comum: sem alerta de ISE
    registrar = next(b for b in at.button if b.label.startswith("Registrar evidência"))
    assert "B3 · R95-01 · 2026-10-1Q" in registrar.label
    registrar.click().run()
    assert not at.exception
    assert _atrasadas(at) == antes - 1                # a FIR sai das atrasadas; o EIR da B3 continua
    tabela = next(d.value for d in at.dataframe if "Ativo" in d.value.columns and "Responsável" in d.value.columns)
    b3 = tabela[tabela["Ativo"].str.startswith("B3")].iloc[0]
    assert b3["🔴"] == 1


def test_fir_com_anomalia_mostra_alerta(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    exemplo = next(s for s in at.selectbox if s.label.endswith("documento de exemplo"))
    exemplo.select("FIR_B2_2026-11-1Q_anomalia.pdf").run()
    next(b for b in at.button if b.label == "Ler documento").click().run()
    assert any("Inspeção de Segurança Especial" in e.value for e in at.error)


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


def test_mercado_faz_a_conta_com_as_premissas(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    valores = {m.label: m.value for m in at.metric}
    assert valores["Barragens na PNSB"] == "461"
    # 461 barragens × (R$ 1.500 + 5 × R$ 150) × 12 = R$ 12,4 mi; 10% = R$ 1,2 mi
    assert valores["Receita anual se todas as barragens da PNSB usassem"] == "R$ 12,4 mi"
    assert valores["Receita anual com 10% de adoção"] == "R$ 1,2 mi"
    next(s for s in at.slider if s.label.startswith("Adoção")).set_value(100).run()
    assert {m.label: m.value for m in at.metric}["Receita anual com 100% de adoção"] == "R$ 12,4 mi"


def test_historico_mostra_a_versao_nova_depois_de_aprovar(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    next(b for b in at.button if b.label == "Aprovar").click().run()
    hist = next(s for s in at.selectbox if s.label == "Obrigação")
    assert hist.value == "OB-01"                       # a que já mudou aparece primeiro
    texto = " ".join(m.value for m in at.markdown)
    assert "Versão 2" in texto and "Resolução ANM Nº 245" in texto and "26/12/2029" in texto


def test_viagem_no_tempo_para_a_res_220(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    next(b for b in at.button if b.label == "Res. 220").click().run()
    assert not at.exception
    assert str(at.date_input[0].value) == "2027-08-02"
    assert next(m for m in at.metric if m.label == "Dias até a Res. ANM 220/2025").value == "0"
    next(b for b in at.button if b.label == "Demo").click().run()
    assert str(at.date_input[0].value) == "2026-11-07"
