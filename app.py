"""RegulaIA — Torre de Controle Regulatória (interface da demo).

Uso: uv run streamlit run app.py
"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import streamlit as st

from regulaia import agenda, db, demo, impacto, torre
from regulaia import evidencias as ev
from regulaia.ia import Roteador

st.set_page_config(page_title="RegulaIA · Torre de Controle", page_icon="🗼", layout="wide")

ROTULO = {
    agenda.ATRASADA: "🔴 Atrasada",
    torre.DADO_FALTANDO: "⚪ Dado faltando",
    agenda.VENCE_LOGO: "🟡 Vence em breve",
    agenda.EM_DIA: "🟢 Em dia",
    agenda.CUMPRIDA: "✅ Cumprida",
    agenda.GATILHO: "🔵 Por gatilho",
}
TIPO = {"barragem": "Barragem", "unidade": "Unidade", "equipamento": "Equipamento", "licenca": "Licença"}
TROCA_NORMA = date(2027, 8, 2)   # Res. ANM 220/2025 substitui a Res. ANM 95/2022
CAMPO = {"prazo": "Prazo", "vigencia_desde": "Começa a valer em", "vigencia_ate": "Deixa de valer após",
         "periodicidade": "Periodicidade", "aplica_se_a": "Aplica-se a", "titulo": "Obrigação",
         "evidencia": "Evidência", "regra": "Regra", "agenda": "Agenda"}


def _dispositivo(norma, artigo):
    """'Res. ANM 220/2025' + 'Res. ANM 220/2025 art. 38 I' não repete a norma."""
    if norma and artigo and artigo.startswith(norma):
        return artigo
    return f"{norma}, {artigo}" if norma else artigo


def _br(valor):
    """AAAA-MM-DD -> DD/MM/AAAA; o resto passa como está."""
    try:
        return date.fromisoformat(str(valor)).strftime("%d/%m/%Y")
    except ValueError:
        return valor if valor not in (None, "") else "—"


# ------------------------------------------------------------------ dados


def _spec() -> dict:
    return json.loads(demo.HISTORICO.read_text(encoding="utf-8")) if demo.HISTORICO.exists() else {}


@st.cache_resource(show_spinner="Montando a demo (cadastro, histórico e radar do DOU)…")
def _conexao(caminho: str):
    conn, _, _ = demo.preparar(caminho)
    return conn


@st.cache_resource
def _roteador():
    """IA só para o que a regra não resolve; sem chave no .env, fica só a regra (e o cache)."""
    try:
        return Roteador(db.conectar(impacto.CACHE_IA))
    except Exception:
        return None


conn = _conexao(str(db.DB_PADRAO))
spec = _spec()
empresa = conn.execute("SELECT id, nome FROM empresa").fetchone()
ativos = db.ativos(conn, empresa["id"])

# ------------------------------------------------------------------ barra lateral

with st.sidebar:
    st.markdown("### 🗼 RegulaIA")
    st.caption(f"{empresa['nome']} · empresa fictícia")
    responsaveis = sorted({a["responsavel"] for a in ativos if a["responsavel"]})
    visao = st.selectbox("Quem está olhando", ["Diretoria (todos os ativos)"] + responsaveis)
    hoje = st.date_input("Hoje", date.fromisoformat(spec.get("hoje", date.today().isoformat())),
                         format="DD/MM/YYYY")
    desde = date.fromisoformat(spec.get("desde", "2026-05-01"))
    st.caption(f"Histórico monitorado desde {desde:%d/%m/%Y}.")
    if st.button("Recriar demo", help="Apaga decisões e volta ao estado inicial"):
        _conexao.clear()
        st.session_state.pop("leitura", None)
        st.rerun()

meus = [a for a in ativos if visao.startswith("Diretoria") or a["responsavel"] == visao]
codigos_meus = {a["codigo"] for a in meus}

st.title("Torre de Controle Regulatória")
st.caption("Cada obrigação com a norma, o dispositivo e o trecho literal que a cria. "
           "Mudanças só valem depois de aprovadas por uma pessoa.")

aba_hoje, aba_transicao, aba_mudancas, aba_radar, aba_mercado, aba_como = st.tabs(
    ["Hoje", "Transição e linha do tempo", "Mudanças", "Radar do DOU", "Mercado", "Como funciona"])

# ------------------------------------------------------------------ Hoje

with aba_hoje:
    linhas = [l for l in torre.painel(conn, empresa["id"], hoje, desde) if l.ativo in codigos_meus]
    cont = {s: sum(1 for l in linhas if l.status == s) for s in ROTULO}
    cols = st.columns(5)
    for col, s in zip(cols, [agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO, agenda.EM_DIA, agenda.GATILHO]):
        col.metric(ROTULO[s], cont[s])

    with st.expander("📄 Enviar evidência — a operação manda o documento, a torre dá baixa sozinha"):
        st.caption("O texto é lido por regra (qual ativo, qual documento, qual data). Só se a regra não fechar "
                   "a IA ajuda, e o Python confere: a data tem de estar escrita no documento.")
        c1, c2 = st.columns(2)
        enviado = c1.file_uploader("Documento em PDF", type=["pdf"])
        exemplos_pdf = sorted(p.name for p in ev.exemplo("x").parent.glob("*.pdf"))
        escolhido = c2.selectbox("…ou um documento de exemplo", ["—"] + exemplos_pdf)
        if st.button("Ler documento", disabled=enviado is None and escolhido == "—"):
            nome, conteudo = ((enviado.name, enviado.getvalue()) if enviado is not None
                              else (escolhido, ev.exemplo(escolhido).read_bytes()))
            try:
                texto_doc = ev.texto_pdf(conteudo)
            except Exception as e:      # arquivo corrompido, protegido por senha, não é PDF...
                st.session_state.pop("leitura", None)
                st.error(f"Não consegui abrir {nome} como PDF ({type(e).__name__}).")
            else:
                st.session_state["leitura"] = (nome, ev.ler(conn, texto_doc, empresa["id"], hoje,
                                                             roteador=_roteador()))
        if "leitura" in st.session_state:
            nome, le = st.session_state["leitura"]
            st.markdown(f"**{nome}** · lido por {'regra' if le.metodo == 'regra' else 'IA (conferida)'}")
            st.dataframe(pd.DataFrame([{
                "Ativo": le.ativo or "—", "Documento": le.documento or "—", "Obrigação": le.obrigacao or "—",
                "Data de execução": _br(le.data), "Período comprovado": le.periodo or "—",
                "Pontuação máxima": le.pontuacao_maxima if le.pontuacao_maxima is not None else "—",
            }]), hide_index=True, width="stretch")
            if le.ativo and le.ativo not in codigos_meus:
                st.warning(f"O documento é de {le.ativo}, que não está entre os ativos de {visao}.")
            for g in le.gatilhos:
                st.error(f"🚨 {g}")
            for p in le.problemas:
                st.warning(p)
            for a in getattr(le, "avisos", []):     # leitura guardada antes de o campo existir
                st.info(f"⏰ {a}")
            if le.completa and st.button(f"Registrar evidência de {le.ativo} · {le.obrigacao} · {le.periodo}",
                                         type="primary"):
                ev.registrar(conn, le, nome)
                del st.session_state["leitura"]
                st.toast(f"Evidência registrada: {le.ativo} {le.obrigacao} {le.periodo}")
                st.rerun()

    para = None if visao.startswith("Diretoria") else visao
    texto_boletim = torre.boletim(conn, empresa["id"], hoje, desde, responsavel=para)
    with st.expander(f"📨 Boletim da semana — {para or 'Diretoria'}"):
        st.caption("O que cada gestor receberia toda segunda, só com os ativos dele. "
                   "Aqui o boletim é só gerado; nada é enviado.")
        sufixo = f"{hoje:%Y-%m-%d}_{(para or 'diretoria').replace(' ', '_')}"
        d1, d2 = st.columns(2)
        d1.download_button("Baixar boletim (.md)", texto_boletim, file_name=f"boletim_{sufixo}.md",
                           mime="text/markdown")
        d2.download_button("Vencimentos no calendário (.ics)",
                           torre.calendario(conn, empresa["id"], hoje, desde, responsavel=para),
                           file_name=f"vencimentos_{sufixo}.ics", mime="text/calendar",
                           help="Importa no Outlook ou Google Agenda: um evento por vencimento")
        st.markdown(texto_boletim.split("\n", 2)[2].replace("\n## ", "\n#### "))   # sem o título grande

    st.markdown("##### Mapa dos ativos")
    st.caption("🔴 atrasada · ⚪ dado faltando no cadastro · 🟡 vence em até 30 dias (5 para quinzenal/mensal) · "
               "🟢 em dia · 🔵 depende de gatilho")
    mapa = pd.DataFrame([{
        "Ativo": f"{a['codigo']} · {a['nome']}",
        "Responsável": a["responsavel"],
        **{ROTULO[s].split()[0]: sum(1 for l in linhas if l.ativo == a["codigo"] and l.status == s)
           for s in [agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO, agenda.EM_DIA, agenda.GATILHO]},
    } for a in meus])
    st.dataframe(mapa, hide_index=True, width="stretch")

    with st.expander("Por norma: quem cobra o quê"):
        normas = sorted({l.norma for l in linhas if l.norma})
        def _orgao(norma: str) -> str:
            return ("ANM" if "ANM" in norma else "MTE" if norma.startswith("NR-")
                    else "Órgão ambiental" if norma.startswith(("LO ", "LC 140")) else "—")

        st.dataframe(pd.DataFrame([{
            "Órgão": _orgao(n),
            "Norma": n,
            "Obrigações": len({l.codigo for l in linhas if l.norma == n}),
            "Ativos": ", ".join(sorted({l.ativo for l in linhas if l.norma == n})),
            **{ROTULO[s].split()[0]: sum(1 for l in linhas if l.norma == n and l.status == s)
               for s in [agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO, agenda.EM_DIA, agenda.GATILHO]},
        } for n in normas]), hide_index=True, width="stretch")

    def _tabela(ls):
        return pd.DataFrame([{
            "Status": ROTULO.get(l.status, l.status),
            "Obrigação": l.titulo,
            "Norma": l.norma,
            "Dispositivo": l.artigo,
            "Vencimento": date.fromisoformat(l.vence).strftime("%d/%m/%Y") if l.vence else "",
            "Pendente": ", ".join(map(agenda.rotulo_humano, l.faltando)) or l.nota,
            "Evidência": l.evidencia,
            "Mudança aguardando": "⚠️" if l.mudanca_pendente else "",
        } for l in ls])

    st.markdown("##### Por ativo")
    for a in meus:
        do_ativo = [l for l in linhas if l.ativo == a["codigo"]]
        if not do_ativo:
            continue
        ruins = sum(1 for l in do_ativo if l.status in (agenda.ATRASADA, torre.DADO_FALTANDO))
        alerta = sum(1 for l in do_ativo if l.status == agenda.VENCE_LOGO)
        selo = "🔴" if ruins else "🟡" if alerta else "🟢"
        titulo = (f"{selo} **{a['codigo']} · {a['nome']}** — {TIPO.get(a['tipo'], a['tipo'])} · "
                  f"{a['responsavel']} · {len(do_ativo)} obrigações")
        with st.expander(titulo, expanded=bool(ruins)):
            com_data = [l for l in do_ativo if l.status != agenda.GATILHO]
            gatilho = [l for l in do_ativo if l.status == agenda.GATILHO]
            if com_data:
                st.dataframe(_tabela(com_data), hide_index=True, width="stretch")
            if gatilho:
                with st.popover(f"🔵 {len(gatilho)} obrigações por gatilho (incidente, emergência, modificação…)"):
                    st.dataframe(_tabela(gatilho)[["Obrigação", "Norma", "Dispositivo", "Evidência"]],
                                 hide_index=True, width="stretch")
            for l in do_ativo:
                if l.status in (agenda.ATRASADA, torre.DADO_FALTANDO):
                    v = db.versao(conn, l.codigo)
                    st.markdown(f"**{ROTULO[l.status]} · {l.titulo}** ({l.norma}, {l.artigo})")
                    if l.faltando:
                        st.markdown("Períodos sem evidência: " + ", ".join(map(agenda.rotulo_humano, l.faltando)))
                    if l.dados_faltando:
                        st.markdown(f"Falta no cadastro do ativo: `{'`, `'.join(l.dados_faltando)}` — "
                                    "sem esse dado não dá para dizer se a obrigação vale.")
                    if v.get("trecho"):
                        st.caption(f"“{v['trecho']}”")

# ------------------------------------------------------------------ Transição

with aba_transicao:
    faltam = (TROCA_NORMA - hoje).days
    c1, c2 = st.columns([1, 3])
    c1.metric("Dias até a Res. ANM 220/2025", max(faltam, 0))
    c2.markdown(
        f"Em **{TROCA_NORMA:%d/%m/%Y}** a Res. ANM 95/2022 deixa de valer e a Res. ANM 220/2025 entra. "
        "Para cada barragem: o que sai, o que entra e o que já precisa ser preparado.")
    trocas = [t for t in torre.transicao(conn, empresa["id"], TROCA_NORMA) if t.ativo in codigos_meus]
    if not trocas:
        st.info("Nenhum dos seus ativos muda de obrigação na troca de norma.")
    else:
        para_t = None if visao.startswith("Diretoria") else visao
        st.download_button("📋 Baixar plano de transição (.md)",
                           torre.plano_transicao(conn, empresa["id"], TROCA_NORMA, hoje, responsavel=para_t),
                           file_name=f"plano_transicao_{(para_t or 'diretoria').replace(' ', '_')}.md",
                           mime="text/markdown")

    def _lista(os_):
        if not os_:
            return "—"
        return "\n".join(f"- {o['titulo']}  \n  <small>{o['artigo']} · {o['periodicidade'] or '—'}</small>"
                         for o in os_)

    for t in trocas:
        nome = next(a["nome"] for a in ativos if a["codigo"] == t.ativo)
        with st.expander(f"**{t.ativo} · {nome}** — saem {len(t.saem)}, entram {len(t.entram)}"):
            c0, c1, c2 = st.columns([1.2, 2, 2])
            c0.markdown("**Tema**")
            c1.markdown("**Hoje · Res. 95/2022**")
            c2.markdown("**A partir de 02/08/2027 · Res. 220/2025**")
            for par in torre.pares(t):
                if par.saem and par.entram:
                    situacao = "🔁 continua, com regra nova"
                elif par.entram:
                    situacao = "🆕 nova"
                else:
                    situacao = "➖ sem equivalente no cadastro da 220"
                st.divider()
                c0, c1, c2 = st.columns([1.2, 2, 2])
                c0.markdown(f"**{par.tema}**  \n<small>{situacao}</small>", unsafe_allow_html=True)
                c1.markdown(_lista(par.saem), unsafe_allow_html=True)
                c2.markdown(_lista(par.entram), unsafe_allow_html=True)

    st.markdown("##### Linha do tempo: o que ainda vai passar a valer")
    st.caption("Datas de entrada em vigor por ativo, de todas as normas do cadastro. "
               "⏳ = data proposta por uma mudança ainda não aprovada.")
    futuras = [f for f in torre.futuras(conn, empresa["id"], hoje) if f.ativo in codigos_meus]
    por_dia: dict[str, list] = {}
    for f in futuras:
        por_dia.setdefault(f.dia, []).append(f)
    for dia, fs in por_dia.items():
        dias = (date.fromisoformat(dia) - hoje).days
        agrupado: dict[tuple, list[str]] = {}
        for f in fs:
            agrupado.setdefault((f.codigo, f.titulo, f.norma, f.artigo, f.proposta), []).append(f.ativo)
        normas_dia = sorted({n for (_, _, n, _, _) in agrupado if n})
        with st.expander(f"**{_br(dia)}** · em {dias} dias · {len(agrupado)} obrigações · {', '.join(normas_dia)}",
                         expanded=len(agrupado) <= 6):
            st.markdown("\n".join(
                f"- {'⏳ ' if prop else ''}{tit} — *{_dispositivo(norma, art)}* · {', '.join(ats)}"
                for (cod, tit, norma, art, prop), ats in agrupado.items()))

# ------------------------------------------------------------------ Mudanças

with aba_mudancas:
    pendentes = [m for m in torre.mudancas(conn, empresa["id"]) if set(m.ativos) & codigos_meus]
    if not pendentes:
        st.success("Nenhuma mudança aguardando decisão para os seus ativos.")
    radar_por_ato = {r["ato"]: r for r in (json.loads(demo.RADAR.read_text(encoding="utf-8"))
                                           if demo.RADAR.exists() else [])}
    for m in pendentes:
        with st.container(border=True):
            st.markdown(f"#### {m.codigo} · {m.titulo}")
            st.caption(f"Origem: {m.ato or m.fonte} · publicado no DOU em {_br(m.publicado_em)}")
            st.markdown("| Campo | Hoje | Proposto |\n|---|---|---|\n" + "\n".join(
                f"| {CAMPO.get(c, c)} | {_br(a)} | **{_br(b)}** |" for c, (a, b) in m.diferencas.items()))
            if m.trecho:
                st.markdown(f"> {m.trecho}")
            r = radar_por_ato.get(m.ato)
            if r:
                st.caption(f"Por quê: {r['motivo']}")
                st.caption(f"Conferido pelo Python: o trecho existe no ato ✓ · as datas propostas aparecem no trecho ✓ · "
                           f"modelo {' → '.join(r['modelos'])} · "
                           f"custo US\\$ {r.get('custo_original_usd', r['custo_usd']):.4f}")
            st.markdown(f"Ativos afetados: **{', '.join(m.ativos)}**")
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("Aprovar", key=f"ok{m.versao_id}", type="primary"):
                db.decidir(conn, m.versao_id, aprovar=True, por=visao)
                st.rerun()
            if b2.button("Rejeitar", key=f"no{m.versao_id}"):
                db.decidir(conn, m.versao_id, aprovar=False, por=visao)
                st.rerun()
    decididas = conn.execute(
        "SELECT o.codigo, v.status, v.decidida_por, v.decidida_em, a.titulo AS ato FROM obrigacao_versao v "
        "JOIN obrigacao o ON o.id = v.obrigacao_id LEFT JOIN ato a ON a.id = v.ato_id "
        "WHERE v.ato_id IS NOT NULL AND v.status != 'pendente'"
    ).fetchall()
    if decididas:
        st.markdown("##### Decisões registradas")
        st.markdown("| Obrigação | Ato | Decisão | Por | Quando (UTC) |\n|---|---|---|---|---|\n" + "\n".join(
            f"| {r['codigo']} | {r['ato'] or '—'} | {'❌ rejeitada' if r['status'] == 'rejeitada' else '✅ aprovada'} "
            f"| {r['decidida_por'].split(' (')[0]} | {r['decidida_em']} |" for r in decididas))

    st.markdown("##### Histórico de uma obrigação")
    st.caption("Por que este prazo é este? Cada versão com a origem, o trecho que a sustenta e quem decidiu.")
    codigos = sorted({o.codigo for a in meus for o in db.obrigacoes_do_ativo(conn, a["id"])})   # inclusive as futuras
    com_mudanca = [c for c in codigos if len(db.historico(conn, c)) > 1]
    escolha = st.selectbox("Obrigação", com_mudanca + [c for c in codigos if c not in com_mudanca],
                           format_func=lambda c: f"{c} · {db.versao(conn, c)['titulo'][:90]}"
                           + (" (já mudou)" if c in com_mudanca else ""))
    if escolha:
        anterior = None
        for v in db.historico(conn, escolha):
            selo = {"vigente": "🟢 vigente", "substituida": "⚪ substituída", "pendente": "⏳ pendente",
                    "rejeitada": "❌ rejeitada"}[v["status"]]
            origem = v["ato"] or v["fonte"] or "cadastro inicial"
            st.markdown(f"**Versão {v['versao']}** · {selo} · origem: {origem}"
                        + (f" · decidida por {v['decidida_por'].split(' (')[0]} em {v['decidida_em']} UTC"
                           if v["decidida_por"] else ""))
            if anterior:
                mudou = db.diferencas(anterior, v)
                if mudou:
                    st.markdown("; ".join(f"{CAMPO.get(c, c)}: {_br(a)} → **{_br(b)}**" for c, (a, b) in mudou.items()))
            else:
                st.markdown(f"Prazo: {_br(v['prazo'])} · vale de {_br(v['vigencia_desde'])} "
                            f"até {_br(v['vigencia_ate']) if v['vigencia_ate'] else 'sem fim'} · {v['artigo']}")
            if v["trecho"]:
                st.caption(f"“{v['trecho']}”")
            anterior = v

# ------------------------------------------------------------------ Radar

with aba_radar:
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Atos no DOU (ago/2026)", "7.884")
    f2.metric("Da ANM", "825")
    f3.metric("Normativos da ANM → IA", "2")
    f4.metric("Mudam o cadastro", "1")
    st.caption("Filtro por órgão e tipo de ato é regra, sem custo. Só os normativos chegam à IA, "
               "e só com as obrigações que a triagem considerou candidatas.")
    from regulaia import impacto
    gastos = db.conectar(impacto.CACHE_IA).execute(
        "SELECT tarefa, COUNT(*) AS n, COALESCE(SUM(custo_usd), 0) AS usd FROM analise_ia GROUP BY tarefa"
    ).fetchall()
    if gastos:
        nomes = {"impacto": "análise de impacto de atos", "extrator": "extração de obrigações de normas"}
        st.markdown("**Custo real de IA até agora** (cada resposta fica em cache e não é paga de novo): " + " · ".join(
            f"{nomes.get(g['tarefa'], g['tarefa'])}: {g['n']} chamadas, US\\$ {g['usd']:.3f}" for g in gastos))
    radar = json.loads(demo.RADAR.read_text(encoding="utf-8")) if demo.RADAR.exists() else []
    for r in radar:
        with st.container(border=True):
            mud = [x for x in r["mudancas"] if not x["reprovada"]]
            st.markdown(f"**{r['ato']}** — {'muda ' + ', '.join(sorted({x['obrigacao'] for x in mud})) if mud else 'não muda o cadastro'}")
            st.caption(r["motivo"])
            st.caption(f"Obrigações enviadas à IA: {', '.join(r['candidatas']) or 'nenhuma'} · "
                       f"modelo: {' → '.join(r['modelos'])} · confiança {r['confianca']} · "
                       f"custo US\\$ {r.get('custo_original_usd', r['custo_usd']):.4f}"
                       + (" (resposta já em cache: não foi paga de novo)" if not r["custo_usd"] else ""))

# ------------------------------------------------------------------ Mercado

with aba_mercado:
    mercado = json.loads((db.ROOT / "data" / "mercado_sigbm.json").read_text(encoding="utf-8"))
    st.markdown("##### Quem precisa disso (dados públicos do SIGBM)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Barragens de mineração", f"{mercado['barragens_mineracao']:,}".replace(",", "."))
    m2.metric("Empresas responsáveis", mercado["empresas"])
    m3.metric("Barragens na PNSB", mercado["barragens_na_pnsb"])
    m4.metric("Empresas com barragem na PNSB", mercado["empresas_com_barragem_na_pnsb"])
    emerg = {k: v for k, v in mercado["pnsb_por_nivel_emergencia"].items() if k != "Sem emergência"}
    st.caption(f"Fonte: {mercado['fonte']} (exportado em {_br(mercado['exportado_em'])}). "
               f"Em Minas Gerais: {mercado['mg']['barragens_na_pnsb']} barragens na PNSB, de "
               f"{mercado['mg']['empresas_com_barragem_na_pnsb']} empresas. "
               f"{sum(emerg.values())} barragens estão hoje em nível de alerta ou emergência.")

    st.markdown("##### Por que agora")
    st.markdown(
        f"- Em **{TROCA_NORMA:%d/%m/%Y}** a Res. ANM 220/2025 substitui a Res. 95/2022: as "
        f"**{mercado['empresas_com_barragem_na_pnsb']} empresas** com barragem na PNSB terão de refazer o "
        f"mapa de obrigações. Faltam {(TROCA_NORMA - hoje).days} dias.\n"
        "- A própria regra já mudou antes de valer: a Res. 245/2026 adiou parte dela para 2029. "
        "Quem acompanha norma em planilha não vê isso.\n"
        "- A mesma mineradora responde a ANM, MTE (NR-13, NR-22) e órgão ambiental. A torre junta tudo por ativo.")

    st.markdown("##### Tamanho da oportunidade (premissas ajustáveis)")
    st.caption("Os números de barragens e empresas são do SIGBM. Preço e adoção são premissas para discussão, "
               "não dados.")
    p1, p2, p3 = st.columns(3)
    preco = p1.number_input("Preço por barragem por mês (R$)", 0, 50_000, 1_500, step=250)
    outros = p2.number_input("Outros ativos por barragem (vasos, licenças, unidades)", 0, 50, 5)
    preco_outro = p3.number_input("Preço por outro ativo por mês (R$)", 0, 10_000, 150, step=50)
    adocao = st.slider("Adoção entre as barragens na PNSB (%)", 1, 100, 10)
    por_barragem = preco + outros * preco_outro
    tam = mercado["barragens_na_pnsb"] * por_barragem * 12
    som = tam * adocao / 100
    r1, r2 = st.columns(2)
    def _num(v: float, casas: int = 0) -> str:
        """Número no formato brasileiro: 1.234,5"""
        return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    r1.metric("Receita anual se todas as barragens da PNSB usassem", f"R$ {_num(tam / 1e6, 1)} mi")
    r2.metric(f"Receita anual com {adocao}% de adoção", f"R$ {_num(som / 1e6, 1)} mi")
    fora = mercado["barragens_mineracao"] - mercado["barragens_na_pnsb"]
    st.caption(f"Conta: {mercado['barragens_na_pnsb']} barragens × (R\\$ {_num(preco)} + {outros} × "
               f"R\\$ {_num(preco_outro)}) × 12 meses. Fora da conta: as {fora} barragens de mineração fora da "
               "PNSB e outros setores com o mesmo problema (energia, saneamento, óleo e gás).")

# ------------------------------------------------------------------ Como funciona

with aba_como:
    n_obrig = conn.execute("SELECT COUNT(*) FROM obrigacao").fetchone()[0]
    n_evid = conn.execute("SELECT COUNT(*) FROM evidencia").fetchone()[0]
    n_ativos = len(ativos)
    radar_c = json.loads(demo.RADAR.read_text(encoding="utf-8")) if demo.RADAR.exists() else []
    custo_radar = sum(r.get("custo_original_usd", r["custo_usd"]) for r in radar_c)
    custo_txt = f"{custo_radar:.4f}".replace(".", ",")
    st.markdown("##### Dois caminhos para a mesma torre")
    st.graphviz_chart(f"""
digraph {{
  rankdir=TB; bgcolor="transparent"; nodesep=0.35; ranksep=0.35; node [shape=box style="rounded,filled" fillcolor="#f0f2f6" fontname="Helvetica" fontsize=11];
  edge [fontname="Helvetica" fontsize=9 color="#888888" fontcolor="#aaaaaa"];
  dou [label="Diário Oficial\n7.884 atos/mês"];
  regra [label="Regras e busca local\n(órgão, tipo, artigo citado)\ncusto zero"];
  ia [label="IA barata, com cache\nUS$ {custo_txt} na demo" fillcolor="#fff4d6"];
  py [label="Python confere\ntrecho, dispositivo, datas"];
  pessoa [label="Pessoa aprova" fillcolor="#e3f5e1"];
  cad [label="Cadastro versionado\n{n_obrig} obrigações" fillcolor="#dde8ff"];
  torre [label="Torre por ativo\n{n_ativos} ativos" fillcolor="#dde8ff" penwidth=2];
  doc [label="Documento da operação\n(FIR, laudo, boletim)"];
  leitor [label="Leitor de evidência\nregra primeiro"];
  ev [label="Evidências\n{n_evid} registradas"];
  norma [label="Norma inteira\n(ANM, NR, licença)"];
  extr [label="Extrator + curadoria\nUS$ 0,01–0,07 por norma" fillcolor="#fff4d6"];
  dou -> regra [label="825 da ANM"]; regra -> ia [label="2 candidatos"]; ia -> py; py -> pessoa [label="mudança proposta"];
  pessoa -> cad; norma -> extr -> cad; cad -> torre; doc -> leitor -> ev -> torre;
  {{ rank=same; dou; norma; doc; }}
}}
""")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**A IA nunca decide sozinha.** O Python confere se o trecho citado existe no ato e se as "
                "datas aparecem nele; uma pessoa aprova. Toda versão guarda o ato, o trecho e quem decidiu.")
    c2.markdown("**Regra antes de IA.** Órgão, tipo de ato e artigo citado resolvem 99,97% do volume. "
                "A IA só vê o que sobra, e cada resposta fica em cache: a mesma pergunta nunca é paga duas vezes.")
    c3.markdown("**Traga sua chave.** Provedor e modelo são configuração (DeepSeek, Anthropic, Bedrock). "
                "A empresa pode rodar com a conta dela, e os documentos não passam pela nossa.")
    st.caption("Stack: Python 3.13 · SQLite (Postgres em produção, só `db.py` muda) · Streamlit · "
               "pypdf · DOU por dados abertos (o robots.txt do site proíbe robôs). Detalhes em docs/ARQUITETURA.md.")
