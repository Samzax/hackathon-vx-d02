"""RegulaIA — Torre de Controle Regulatória (interface da demo).

Uso: uv run streamlit run app.py
"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import streamlit as st

from regulaia import agenda, db, demo, torre

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
        st.rerun()

meus = [a for a in ativos if visao.startswith("Diretoria") or a["responsavel"] == visao]
codigos_meus = {a["codigo"] for a in meus}

st.title("Torre de Controle Regulatória")
st.caption("Cada obrigação com a norma, o dispositivo e o trecho literal que a cria. "
           "Mudanças só valem depois de aprovadas por uma pessoa.")

aba_hoje, aba_transicao, aba_mudancas, aba_radar = st.tabs(
    ["Hoje", "Transição 95 → 220", "Mudanças", "Radar do DOU"])

# ------------------------------------------------------------------ Hoje

with aba_hoje:
    linhas = [l for l in torre.painel(conn, empresa["id"], hoje, desde) if l.ativo in codigos_meus]
    cont = {s: sum(1 for l in linhas if l.status == s) for s in ROTULO}
    cols = st.columns(5)
    for col, s in zip(cols, [agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO, agenda.EM_DIA, agenda.GATILHO]):
        col.metric(ROTULO[s], cont[s])

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

    def _tabela(ls):
        return pd.DataFrame([{
            "Status": ROTULO.get(l.status, l.status),
            "Obrigação": l.titulo,
            "Norma": l.norma,
            "Dispositivo": l.artigo,
            "Vencimento": date.fromisoformat(l.vence).strftime("%d/%m/%Y") if l.vence else "",
            "Pendente": ", ".join(l.faltando) or l.nota,
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
                        st.markdown(f"Períodos sem evidência: `{'`, `'.join(l.faltando)}`")
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
                           f"modelo {' → '.join(r['modelos'])} · custo US\\$ {r['custo_usd']:.4f}")
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
                       f"custo US\\$ {r['custo_usd']:.4f}")
