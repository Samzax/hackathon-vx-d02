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
    legendas = [c.value for c in at.caption]
    assert any(c.startswith("Conferido pelo Python") for c in legendas)      # o roteiro aponta para esta linha
    assert any(c.startswith("Por quê:") for c in legendas)
    escopo = " ".join(m.value for m in at.markdown)
    assert "**Muda 1 obrigação (OB-01).** As outras 23 da Res. ANM 220/2025 ficam iguais." in escopo  # o roteiro diz isso
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
    assert "Versão 2" in texto and "Resolução ANM nº 245, de 31 de julho de 2026" in texto and "26/12/2029" in texto
    versoes = [m.value for m in at.markdown if m.value.startswith("**Versão")]
    assert versoes and not [v for v in versoes if "UTC" in v]
    assert "sem fim" not in texto and "vale a partir de 02/08/2027" in texto
    custos = " ".join(c.value for c in at.caption if "custo" in c.value)
    assert r"US\$ 0," in custos and r"US\$ 0." not in custos
    assert "confiança 0," in custos and "confiança 0." not in custos


def test_viagem_no_tempo_para_a_res_220(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    next(b for b in at.button if b.label == "Res. 220").click().run()
    assert not at.exception
    assert str(at.date_input[0].value) == "2027-08-02"
    assert next(m for m in at.metric if m.label == "Dias até a Res. ANM 220/2025").value == "0"
    next(b for b in at.button if b.label == "Demo").click().run()
    assert str(at.date_input[0].value) == "2026-11-07"


def test_todas_as_visoes_em_todas_as_datas_da_viagem(banco_temporario):
    """Cada gestor, no dia da demo, na troca para a Res. 220 e depois do prazo da ZAS: nenhuma tela quebra."""
    from datetime import date

    at = AppTest.from_file(APP, default_timeout=120).run()
    visoes = at.sidebar.selectbox[0].options
    assert len(visoes) >= 8
    for v in visoes:
        for d in (date(2026, 11, 7), date(2027, 8, 2), date(2029, 12, 27)):
            at.sidebar.selectbox[0].select(v)
            at.sidebar.date_input[0].set_value(d)
            at.run()
            assert not at.exception, (v, d, [e.value for e in at.exception])


def test_ato_ficticio_vira_mudanca_pendente(banco_temporario, monkeypatch):
    """O ato de exemplo da aba Radar roda do cache da demo (sem chave) e vira mudança para aprovar."""
    from regulaia import ia

    monkeypatch.setattr(ia, "load_dotenv", lambda *a, **k: None)
    for chave in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "OPENCODE_API_KEY"):
        monkeypatch.delenv(chave, raising=False)
    at = AppTest.from_file(APP, default_timeout=120).run()
    next(b for b in at.button if b.label == "Usar um ato fictício de exemplo").click().run()
    next(b for b in at.button if b.label == "Analisar ato").click().run()
    assert not at.exception
    texto = " ".join(m.value for m in at.markdown)
    assert "R95-01" in texto and "Semanal" in texto and "conferida pelo Python" in texto
    next(b for b in at.button if b.label.startswith("Enviar para aprovação")).click().run()
    assert not at.exception
    assert len([b for b in at.button if b.label == "Aprovar"]) == 2       # Res. 245 e o ato de teste
    tabela = " ".join(m.value for m in at.markdown)
    assert "| Agenda | quinzenal, até o fim de cada quinzena | **semanal, até o fim de cada semana** |" in tabela  # por regra
    # o cartão do ato colado tem o mesmo porquê e a mesma conferência que o da Res. 245
    assert "**Muda 1 obrigação (R95-01).** As outras 20 da Res. ANM 95/2022 ficam iguais." in tabela
    conferidos = [c.value for c in at.caption if c.value.startswith("Conferido pelo Python")]
    assert len(conferidos) == 2
    assert sum("as datas propostas aparecem no trecho" in c for c in conferidos) == 1   # só a Res. 245 muda data


def test_fir_no_modelo_da_res220_dispara_ise_na_viagem_no_tempo(banco_temporario):
    """No primeiro dia da Res. 220 a FIR traz as colunas EC do Quadro I.8; EC3 = 5 obriga ISE (art. 42)."""
    at = AppTest.from_file(APP, default_timeout=120).run()
    next(b for b in at.button if b.label == "Res. 220").click().run()
    exemplo = next(s for s in at.selectbox if s.label.endswith("documento de exemplo"))
    exemplo.select("FIR_B2_2027-08-1Q_Res220_EC3.pdf").run()
    next(b for b in at.button if b.label == "Ler documento").click().run()
    assert not at.exception
    assert any("Res. ANM 220/2025, art. 42" in e.value for e in at.error)
    registrar = next(b for b in at.button if b.label.startswith("Registrar evidência"))
    assert "B2 · OB-02 · 2027-08-1Q" in registrar.label


def test_anomalia_registrada_fica_na_torre_ate_o_relatorio_da_ise(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    antes = _atrasadas(at)

    def ler_e_registrar(nome, aviso=None):
        next(s for s in at.selectbox if s.label.endswith("documento de exemplo")).select(nome).run()
        next(b for b in at.button if b.label == "Ler documento").click().run()
        if aviso:
            assert any(aviso in c.value for c in at.caption)
        next(b for b in at.button if b.label.startswith("Registrar evidência")).click().run()
        assert not at.exception

    ler_e_registrar("FIR_B2_2026-11-1Q_anomalia.pdf", aviso="Ao registrar, a torre abre em B2, com prazo de 24 h: **R95-04 · Realizar ISE")
    assert _atrasadas(at) == antes + 1                 # a ISE da B2 fica aberta e passou do prazo de 24 h
    assert any(m.value.startswith("Acionada em 04/11/2026 por FIR_B2_2026-11-1Q_anomalia.pdf") for m in at.markdown)
    ler_e_registrar("Relatorio_ISE_B2_2026-11-06.pdf")
    assert _atrasadas(at) == antes


def test_detalhe_do_ativo_sem_codigo_cru(banco_temporario):
    """O vaso E1 diz quando foi o último exame, não repete a data; o dado faltando da B4 vem em português."""
    at = AppTest.from_file(APP, default_timeout=120).run()
    texto = " ".join(m.value for m in at.markdown)
    assert "Última evidência em 30/10/2023." in texto and "Períodos sem evidência: 30/10/2026" not in texto
    assert "**se passou por modificação estrutural** (`modificacao_estrutural`)" in texto


def test_aviso_de_atraso_comeca_com_maiuscula(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    next(s for s in at.selectbox if s.label.endswith("documento de exemplo")).select("EIR_B3_2026-10-1Q_recibo_SIGBM.pdf").run()
    next(b for b in at.button if b.label == "Ler documento").click().run()
    assert any(i.value.lstrip("⏰ ").startswith("Enviado em 06/11/2026, 7 dias depois do prazo") for i in at.info)


def test_por_norma_explica_a_ausencia_da_res220(banco_temporario):
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert any(c.value.startswith("A Res. ANM 220/2025 ainda não aparece: entra em 02/08/2027") for c in at.caption)
    next(b for b in at.button if b.label == "Res. 220").click().run()
    assert not any(c.value.startswith("A Res. ANM 220/2025 ainda não aparece") for c in at.caption)


def test_viagem_no_tempo_explica_os_atrasos(banco_temporario):
    """Na data da Res. 220 os atrasos sobem porque o histórico da demo para em 07/11/2026: a tela diz isso."""
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not [i for i in at.info if i.value.startswith("Viagem no tempo")]
    next(b for b in at.button if b.label == "Res. 220").click().run()
    assert [i for i in at.info if i.value.startswith("Viagem no tempo: 02/08/2027. As entregas da demo vão até 07/11/2026")]
