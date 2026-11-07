"""Fumaça da interface: a torre abre, mostra os números e aprova a Res. 245 sem erro."""

from pathlib import Path

import pytest

from regulaia import db, demo

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(Path(__file__).resolve().parent.parent / "app.py")
DEMO = "demo@serraazul.demo"        # conta de teste da demo: troca de visão pela barra lateral


def _abrir(conta: str | None = DEMO):
    """A torre já com alguém dentro (a conta de teste, por padrão); None: a tela de entrar."""
    at = AppTest.from_file(APP, default_timeout=120)
    if conta:
        at.session_state["usuario"] = conta
    return at


@pytest.fixture
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PADRAO", tmp_path / "regulaia.db")
    monkeypatch.setattr(demo, "RADAR", tmp_path / "radar.json")
    # como num clone novo (e no CI): só as respostas de IA que estão no Git (data/cache_ia_demo.json),
    # nunca o data/cache_ia.db local de quem desenvolve
    from regulaia import impacto
    monkeypatch.setattr(impacto, "CACHE_IA", tmp_path / "cache_ia.db")
    # cada teste com conexões novas: o st.cache_resource vive no processo, e no Postgres o
    # conftest fecha as conexões do teste anterior
    import streamlit as st
    st.cache_resource.clear()
    from regulaia import arquivos
    monkeypatch.setattr(arquivos, "PASTA", tmp_path / "evidencias")
    monkeypatch.delenv("REGULAIA_S3_BUCKET", raising=False)


def test_torre_abre_e_aprova_mudanca(banco_temporario):
    at = _abrir().run()
    assert not at.exception
    metricas = {m.label: m.value for m in at.metric}
    assert int(metricas["Atrasada"]) >= 1
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


def test_corrigir_antes_de_aprovar(banco_temporario):
    """Quem aprova muda a data proposta; vale a corrigida, e a decisão aparece como corrigida."""
    from datetime import date

    at = _abrir().run()
    campo = next(d for d in at.date_input if d.label == "Prazo")
    campo.set_value(date(2029, 12, 27)).run()
    next(b for b in at.button if b.label == "Aprovar com correção").click().run()
    assert not at.exception
    assert not [b for b in at.button if b.label == "Aprovar"]
    textos = " ".join(m.value for m in at.markdown)
    assert ":orange-badge[aprovada com correção]" in textos
    conn = db.conectar(db.DB_PADRAO)
    ob01 = db.versao(conn, "OB-01")
    assert ob01["prazo"] == "2029-12-27" and ob01["correcao"]


def _atrasadas(at) -> int:
    return int({m.label: m.value for m in at.metric}["Atrasada"])


def test_envio_de_fir_tira_a_b3_do_atraso(banco_temporario):
    at = _abrir().run()
    antes = _atrasadas(at)
    exemplo = next(s for s in at.selectbox if s.label.endswith("documento de exemplo"))
    exemplo.select("FIR_B3_2026-10-1Q.pdf").run()
    next(b for b in at.button if b.label == "Ler documento").click().run()
    assert not at.exception and not at.error          # FIR comum: sem alerta de ISE
    registrar = next(b for b in at.button if b.label.startswith("Registrar evidência"))
    assert registrar.label == "Registrar evidência: FIR de B3 · 1ª quinzena de outubro/2026"
    assert "R95-01" in registrar.help and "2026-10-1Q" in registrar.help     # o código fica na dica
    registrar.click().run()
    assert not at.exception
    assert _atrasadas(at) == antes - 1                # a FIR sai das atrasadas; o EIR da B3 continua
    tabela = next(d.value for d in at.dataframe if "Ativo" in d.value.columns and "Responsável" in d.value.columns)
    b3 = tabela[tabela["Ativo"].str.startswith("B3")].iloc[0]
    assert b3["Atrasadas"] == 1


def test_pdf_escaneado_sem_ocr_avisa(banco_temporario, monkeypatch):
    monkeypatch.delenv("REGULAIA_OCR", raising=False)
    at = _abrir().run()
    exemplo = next(s for s in at.selectbox if s.label.endswith("documento de exemplo"))
    exemplo.select("FIR_B3_2026-10-1Q_escaneada.pdf").run()
    next(b for b in at.button if b.label == "Ler documento").click().run()
    assert not at.exception
    assert any("o PDF é escaneado" in w.value for w in at.warning)
    assert not [b for b in at.button if b.label.startswith("Registrar evidência")]


def test_fir_com_anomalia_mostra_alerta(banco_temporario):
    at = _abrir().run()
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
    at = _abrir().run()
    valores = {m.label: m.value for m in at.metric}
    assert valores["Barragens na PNSB"] == "461"
    # 461 barragens × (R$ 1.500 + 5 × R$ 150) × 12 = R$ 12,4 mi; 10% = R$ 1,2 mi
    assert valores["Receita anual se todas as barragens da PNSB usassem"] == "R$ 12,4 mi"
    assert valores["Receita anual com 10% de adoção"] == "R$ 1,2 mi"
    next(s for s in at.slider if s.label.startswith("Adoção")).set_value(100).run()
    assert {m.label: m.value for m in at.metric}["Receita anual com 100% de adoção"] == "R$ 12,4 mi"


def test_historico_mostra_a_versao_nova_depois_de_aprovar(banco_temporario):
    at = _abrir().run()
    next(b for b in at.button if b.label == "Aprovar").click().run()
    hist = next(s for s in at.selectbox if s.label == "Obrigação")
    assert hist.value == "OB-01"                       # a que já mudou aparece primeiro
    texto = " ".join(m.value for m in at.markdown)
    assert "Versão 2" in texto and "Resolução ANM nº 245, de 31 de julho de 2026" in texto and "26/12/2029" in texto
    versoes = [m.value for m in at.markdown if m.value.startswith("**Versão")]
    assert versoes and not [v for v in versoes if "UTC" in v]
    assert "veio do cadastro inicial em" in versoes[0] and "decidida por carga inicial" not in texto
    assert "decidida por Diretoria em" in versoes[1]
    assert "sem fim" not in texto and "vale a partir de 02/08/2027" in texto
    custos = " ".join(c.value for c in at.caption if "custo" in c.value)
    assert r"US\$ 0," in custos and r"US\$ 0." not in custos
    assert "confiança 0," in custos and "confiança 0." not in custos


def test_viagem_no_tempo_para_a_res_220(banco_temporario):
    at = _abrir().run()
    next(b for b in at.button if b.label == "Res. 220").click().run()
    assert not at.exception
    assert str(at.date_input(key="hoje").value) == "2027-08-02"
    assert next(m for m in at.metric if m.label == "Dias até a Res. ANM 220/2025").value == "0"
    next(b for b in at.button if b.label == "Demo").click().run()
    assert str(at.date_input(key="hoje").value) == "2026-11-07"


def test_todas_as_visoes_em_todas_as_datas_da_viagem(banco_temporario):
    """Cada gestor, no dia da demo, na troca para a Res. 220 e depois do prazo da ZAS: nenhuma tela quebra."""
    from datetime import date

    at = _abrir().run()
    visoes = at.sidebar.selectbox[1].options
    assert len(visoes) >= 8
    for v in visoes:
        for d in (date(2026, 11, 7), date(2027, 8, 2), date(2029, 12, 27)):
            at.sidebar.selectbox[1].select(v)
            at.sidebar.date_input[0].set_value(d)
            at.run()
            assert not at.exception, (v, d, [e.value for e in at.exception])


def test_ato_ficticio_vira_mudanca_pendente(banco_temporario, monkeypatch):
    """O ato de exemplo da aba Radar roda do cache da demo (sem chave) e vira mudança para aprovar."""
    from regulaia import ia

    monkeypatch.setattr(ia, "load_dotenv", lambda *a, **k: None)
    for chave in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "OPENCODE_API_KEY"):
        monkeypatch.delenv(chave, raising=False)
    at = _abrir().run()
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
    at = _abrir().run()
    next(b for b in at.button if b.label == "Res. 220").click().run()
    exemplo = next(s for s in at.selectbox if s.label.endswith("documento de exemplo"))
    exemplo.select("FIR_B2_2027-08-1Q_Res220_EC3.pdf").run()
    next(b for b in at.button if b.label == "Ler documento").click().run()
    assert not at.exception
    assert any("Res. ANM 220/2025, art. 42" in e.value for e in at.error)
    registrar = next(b for b in at.button if b.label.startswith("Registrar evidência"))
    assert registrar.label.endswith("FIR de B2 · 1ª quinzena de agosto/2027") and "OB-02" in registrar.help
    lido = next(d.value for d in at.dataframe if "Estado de conservação" in d.value.columns)
    assert lido.iloc[0]["Estado de conservação"] == "EC1 0 · EC2 5 · EC3 5 · EC4 0 · EC5 0"   # o que a regra leu


def test_anomalia_registrada_fica_na_torre_ate_o_relatorio_da_ise(banco_temporario):
    at = _abrir().run()
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
    _abrir_ficha(at, "B2")
    assert any(m.value.startswith("Acionada em 04/11/2026 por FIR_B2_2026-11-1Q_anomalia.pdf") for m in at.markdown)
    ler_e_registrar("Relatorio_ISE_B2_2026-11-06.pdf")
    assert _atrasadas(at) == antes


def _abrir_ficha(at, codigo: str):
    """Escolhe o ativo da ficha na aba Ativos (o mesmo que clicar na linha do mapa)."""
    sel = at.selectbox(key="ativo_sel")
    sel.select(next(o for o in sel.options if o.startswith(f"{codigo} · "))).run()
    assert not at.exception


def test_detalhe_do_ativo_sem_codigo_cru(banco_temporario):
    """O vaso E1 diz quando foi o último exame, não repete a data; o dado faltando da B4 vem em português."""
    at = _abrir().run()
    _abrir_ficha(at, "E1")
    texto = " ".join(m.value for m in at.markdown)
    assert "Última evidência em 30/10/2023." in texto and "Períodos sem evidência: 30/10/2026" not in texto
    _abrir_ficha(at, "B4")
    texto = " ".join(m.value for m in at.markdown)
    assert "**se passou por modificação estrutural** (`modificacao_estrutural`)" in texto


def test_aviso_de_atraso_comeca_com_maiuscula(banco_temporario):
    at = _abrir().run()
    next(s for s in at.selectbox if s.label.endswith("documento de exemplo")).select("EIR_B3_2026-10-1Q_recibo_SIGBM.pdf").run()
    next(b for b in at.button if b.label == "Ler documento").click().run()
    assert any(i.value.lstrip("⏰ ").startswith("Enviado em 06/11/2026, 7 dias depois do prazo") for i in at.info)


def test_por_norma_explica_a_ausencia_da_res220(banco_temporario):
    at = _abrir().run()
    assert any(c.value.startswith("A Res. ANM 220/2025 ainda não aparece: entra em 02/08/2027") for c in at.caption)
    next(b for b in at.button if b.label == "Res. 220").click().run()
    assert not any(c.value.startswith("A Res. ANM 220/2025 ainda não aparece") for c in at.caption)


def test_viagem_no_tempo_explica_os_atrasos(banco_temporario):
    """Na data da Res. 220 os atrasos sobem porque o histórico da demo para em 07/11/2026: a tela diz isso."""
    at = _abrir().run()
    assert not [i for i in at.info if i.value.startswith("Viagem no tempo")]
    next(b for b in at.button if b.label == "Res. 220").click().run()
    assert [i for i in at.info if i.value.startswith("Viagem no tempo: 02/08/2027. As entregas da demo vão até 07/11/2026")]


def test_cada_gestor_so_ve_os_ativos_dele(banco_temporario):
    """A promessa do produto: o gestor vê só os ativos dele em todas as abas (texto, tabelas e títulos)."""
    import json
    import re

    ativos = json.loads((Path(APP).parent / "data" / "serra_azul.json").read_text(encoding="utf-8"))["ativos"]
    at = _abrir().run()
    for gestor in sorted({a["responsavel"] for a in ativos}):
        meus = {a["codigo"] for a in ativos if a["responsavel"] == gestor}
        alheios = {a["codigo"] for a in ativos} - meus
        at.sidebar.selectbox[1].select(gestor).run()
        assert not at.exception
        partes = [e.value for tipo in (at.markdown, at.caption, at.info, at.warning, at.error) for e in tipo]
        partes += [e.label for e in at.expander]
        partes += [d.value.to_string() for d in at.dataframe]
        texto = "\n".join(str(p) for p in partes)
        vistos = set(re.findall(r"\b(?:B[1-9]|E[1-9]|L[1-9]|U[1-9])\b", texto))
        assert meus & vistos, gestor                       # vê os dele
        assert not (vistos & alheios), (gestor, sorted(vistos & alheios))


def test_gestor_nao_registra_documento_de_ativo_alheio(banco_temporario):
    """A FIR da B3 é da Geotecnia: a Manutenção da Usina vê o aviso e não tem o botão de registrar."""
    at = _abrir().run()
    for visao, pode in [("Manutenção da Usina", False), ("Gerência de Geotecnia", True)]:
        at.sidebar.selectbox[1].select(visao).run()
        next(s for s in at.selectbox if s.label.endswith("documento de exemplo")).select("FIR_B3_2026-10-1Q.pdf").run()
        next(b for b in at.button if b.label == "Ler documento").click().run()
        assert not at.exception
        registrar = [b for b in at.button if b.label.startswith("Registrar evidência")]
        aviso = [w.value for w in at.warning if "não está entre os ativos" in w.value]
        assert bool(registrar) == pode and bool(aviso) != pode, visao


def test_importar_mineradora_do_sigbm_e_operar(banco_temporario):
    """'Sua mineradora em 30 segundos': busca pelo CNPJ, monta a torre, completa o cadastro."""
    at = _abrir()
    at.session_state["manter_importar"] = True     # no navegador o diálogo roda como fragmento e fica aberto
    at.run()
    next(t for t in at.text_input if t.label == "CNPJ ou nome da empresa").input("33.592.510/0001-54").run()
    assert not at.exception
    next(b for b in at.button if b.label.startswith("Montar a torre de VALE")).click().run()
    assert not at.exception
    assert at.sidebar.selectbox[0].value != 1                       # trocou para a empresa importada
    metricas = {m.label: int(m.value) for m in at.metric if m.label in ("Atrasada", "Dado faltando")}
    assert metricas["Atrasada"] == 0 and metricas["Dado faltando"] > 0   # nada de atraso inventado
    assert any(m.value.startswith("##### Primeiros passos") for m in at.markdown)
    # completar o cadastro de todas as barragens de uma vez
    next(r for r in at.radio if "(`modificacao_estrutural`)" in r.label).set_value("não").run()
    antes = metricas["Dado faltando"]
    next(b for b in at.button if b.label == "Salvar no cadastro").click().run()
    assert not at.exception
    assert int({m.label: m.value for m in at.metric}["Dado faltando"]) < antes
    assert any(b.label.startswith("Excel") for b in at.get("download_button"))


def test_numero_da_caixa_abre_entregas_filtrada(banco_temporario):
    """Clicar em "Ver na lista" embaixo das atrasadas leva à aba Entregas só com as atrasadas."""
    from regulaia import agenda

    at = _abrir().run()
    n = _atrasadas(at)
    at.button(key=f"kpi_{agenda.ATRASADA}").click().run()
    assert not at.exception
    assert at.session_state["aba"].endswith("Entregas") and at.session_state["f_status"] == [agenda.ATRASADA]
    tabela = next(d.value for d in at.dataframe if "Última" in d.value.columns)
    assert len(tabela) == n and set(tabela["Status"]) == {"Atrasada"}


def test_caixa_de_entrada_registra_entrega_no_dialogo(banco_temporario):
    """Cada atrasada da caixa tem o botão que resolve: o diálogo registra a entrega e ela sai da caixa."""
    at = _abrir().run()
    antes = _atrasadas(at)
    abre = next(b for b in at.button if (b.key or "").startswith("abre_cx_") and b.label == "Registrar entrega")
    abre.click().run()
    assert not at.exception and "entrega_de" in at.session_state
    next(b for b in at.button if (b.key or "").startswith("ent_dlg_")).click().run()
    assert not at.exception
    assert _atrasadas(at) == antes - 1 and "entrega_de" not in at.session_state


def test_ficha_do_ativo_completa_o_cadastro(banco_temporario):
    """A B4 não diz se passou por modificação estrutural: a caixa leva à ficha, e preencher ali tira o dado faltando."""
    at = _abrir().run()
    assert int({m.label: m.value for m in at.metric}["Dado faltando"]) == 1
    next(b for b in at.button if b.label == "Completar cadastro").click().run()
    assert at.session_state["aba"].endswith("Ativos") and at.selectbox(key="ativo_sel").value.startswith("B4 · ")
    at.radio(key="ficha_B4_modificacao_estrutural").set_value("não").run()
    at.button(key="ficha_B4_salvar").click().run()
    assert not at.exception
    assert int({m.label: m.value for m in at.metric}["Dado faltando"]) == 0


def test_mudanca_pendente_aparece_na_caixa_e_leva_a_decisao(banco_temporario):
    at = _abrir().run()
    texto = " ".join(m.value for m in at.markdown)
    assert "1 mudança de norma aguardando decisão" in texto and "**OB-01**" in texto
    next(b for b in at.button if b.label == "Decidir →").click().run()
    assert at.session_state["aba"].endswith("Regulatório") and at.session_state["aba_reg"] == "Mudanças"


def test_dia_do_calendario_lista_e_registra_entrega(banco_temporario):
    """Clicar num dia do calendário (aqui, pelo estado) lista os vencimentos e abre o registro de entrega."""
    at = _abrir().run()
    assert any(c.value.startswith("Clique num dia") for c in at.caption)
    at.session_state["cal_dia"] = "2026-11-15"
    at.run()
    assert not at.exception
    assert any(m.value.startswith("**15/11/2026** ·") for m in at.markdown)
    botoes = [b for b in at.button if b.key and b.key.startswith("abre_cal_")]
    assert botoes, "dia 15/11/2026 tem vencimentos a entregar na demo"
    botoes[0].click().run()
    assert not at.exception
    assert "entrega_de" in at.session_state


def test_mapa_e_linha_do_tempo_aparecem_na_demo(banco_temporario):
    """Empresa fictícia: mapa dos ativos (posições fictícias) e Gantt da transição, sem erro."""
    at = _abrir().run()
    assert not at.exception
    assert any(c.value.startswith("Posições fictícias") for c in at.caption)
    assert at.get("deck_gl_json_chart"), "mapa dos ativos"
    assert at.get("vega_lite_chart"), "linha do tempo da transição"


# ------------------------------------------------------------------ contas

def _senha_demo(monkeypatch) -> str:
    import json
    monkeypatch.delenv("REGULAIA_SENHA_DEMO", raising=False)
    return json.loads((Path(APP).parent / "data" / "usuarios_demo.json").read_text(encoding="utf-8"))["senha"]


def _entrar(at, email, senha):
    next(t for t in at.text_input if t.label == "E-mail").set_value(email)
    next(t for t in at.text_input if t.label == "Senha").set_value(senha)
    next(b for b in at.button if b.label == "Entrar").click().run()


def test_sem_conta_so_a_tela_de_entrar_e_o_botao_da_demo(banco_temporario):
    at = _abrir(None).run()
    assert not at.exception
    assert not at.metric and not at.tabs                       # nada da torre antes de entrar
    _entrar(at, "geotecnia@serraazul.demo", "senha-errada")
    assert any("não conferem" in e.value for e in at.error) and not at.metric
    next(b for b in at.button if b.label == "Entrar na demo").click().run()
    assert not at.exception and at.metric
    assert at.sidebar.selectbox[1].label == "Quem está olhando"


def test_gestor_entra_preso_a_propria_area(banco_temporario, monkeypatch):
    import re
    at = _abrir(None).run()
    _entrar(at, "geotecnia@serraazul.demo", _senha_demo(monkeypatch))
    assert not at.exception and at.metric
    assert not [s for s in at.sidebar.selectbox if s.label == "Quem está olhando"]
    assert not [b for b in at.sidebar.button if b.label == "Recriar demo"]
    texto = "\n".join(str(d.value.to_string()) for d in at.dataframe)
    vistos = set(re.findall(r"\b(?:B[1-9]|E[1-9]|L[1-9]|U[1-9])\b", texto))
    assert vistos and vistos <= {"B1", "B3"}, vistos           # Geotecnia: só B1 e B3
    assert not [s for s in at.selectbox if s.label == "Área responsável pelo ativo"]   # área é da Diretoria
    next(b for b in at.sidebar.button if b.label == "Sair").click().run()
    assert not at.metric and [b for b in at.button if b.label == "Entrar na demo"]


def test_ti_so_ve_contas_e_cria_gestor(banco_temporario, monkeypatch):
    senha = _senha_demo(monkeypatch)
    at = _abrir(None).run()
    _entrar(at, "ti@serraazul.demo", senha)
    assert not at.exception
    assert not at.metric                                        # a TI não vê a torre
    contas = next(d.value for d in at.dataframe if "E-mail" in d.value.columns)
    assert "geotecnia@serraazul.demo" in set(contas["E-mail"])
    next(t for t in at.text_input if t.label == "Nome").set_value("Bruno Dias")
    next(t for t in at.text_input if t.label == "E-mail").set_value("bruno@serraazul.demo")
    next(s for s in at.selectbox if s.label == "Área (só para gestor)").set_value("Manutenção da Mina")
    next(t for t in at.text_input if t.label == "Senha inicial").set_value("mina-2026!")
    next(b for b in at.button if b.label == "Criar conta").click().run()
    assert not at.exception and not at.error
    conn = db.conectar(db.DB_PADRAO)
    from regulaia import usuarios
    bruno = usuarios.autenticar(conn, "bruno@serraazul.demo", "mina-2026!")
    assert bruno["papel"] == "gestor" and bruno["area"] == "Manutenção da Mina" and bruno["criado_por"] == "Equipe de TI"


def test_diretoria_muda_area_do_ativo_e_o_gestor_passa_a_ver(banco_temporario, monkeypatch):
    senha = _senha_demo(monkeypatch)
    at = _abrir(None).run()
    _entrar(at, "diretoria@serraazul.demo", senha)
    assert not [s for s in at.sidebar.selectbox if s.label == "Quem está olhando"]
    at.selectbox(key="ativo_sel").select(next(o for o in at.selectbox(key="ativo_sel").options
                                             if o.startswith("E2 · "))).run()
    area = next(s for s in at.selectbox if s.label == "Área responsável pelo ativo")
    area.set_value("Gerência de Geotecnia").run()
    next(b for b in at.button if b.label == "Salvar área").click().run()
    assert not at.exception
    conn = db.conectar(db.DB_PADRAO)
    e2 = next(a for e in db.empresas(conn) for a in db.ativos(conn, e["id"]) if a["codigo"] == "E2")
    assert e2["responsavel"] == "Gerência de Geotecnia"
    assert db.eventos(conn, e2["id"])[0]["por"] == "Carla Mendes"


def test_conta_de_teste_tambem_olha_como_ti(banco_temporario):
    at = _abrir().run()
    at.sidebar.selectbox[1].select("TI (contas de acesso)").run()
    assert not at.exception and not at.metric
    assert any("E-mail" in d.value.columns for d in at.dataframe)
