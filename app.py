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


# ------------------------------------------------------------------ dados


def _spec() -> dict:
    return json.loads(demo.HISTORICO.read_text(encoding="utf-8")) if demo.HISTORICO.exists() else {}


if "pronto" not in st.session_state:
    with st.spinner("Montando a demo (cadastro, histórico e radar do DOU)…"):
        demo.preparar()
    st.session_state.pronto = True

conn = db.conectar(db.DB_PADRAO)
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
        demo.preparar()
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
            tabela = pd.DataFrame([{
                "Status": ROTULO.get(l.status, l.status),
                "Obrigação": l.titulo,
                "Norma": l.norma,
                "Dispositivo": l.artigo,
                "Próximo vencimento": date.fromisoformat(l.vence).strftime("%d/%m/%Y") if l.vence else "",
                "Pendente": ", ".join(l.faltando) or l.nota,
                "Evidência": l.evidencia,
                "Mudança aguardando": "⚠️" if l.mudanca_pendente else "",
            } for l in do_ativo])
            st.dataframe(tabela, hide_index=True, width="stretch")
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
    for t in trocas:
        nome = next(a["nome"] for a in ativos if a["codigo"] == t.ativo)
        with st.expander(f"**{t.ativo} · {nome}** — saem {len(t.saem)}, entram {len(t.entram)}"):
            e, d = st.columns(2)
            e.markdown("**Saem** (Res. 95)")
            e.dataframe(pd.DataFrame([{"Obrigação": o["titulo"], "Dispositivo": o["artigo"],
                                       "Periodicidade": o["periodicidade"]} for o in t.saem]),
                        hide_index=True, width="stretch")
            d.markdown("**Entram** (Res. 220)")
            d.dataframe(pd.DataFrame([{"Obrigação": o["titulo"], "Dispositivo": o["artigo"],
                                       "Periodicidade": o["periodicidade"]} for o in t.entram]),
                        hide_index=True, width="stretch")

# ------------------------------------------------------------------ Mudanças

with aba_mudancas:
    pendentes = [m for m in torre.mudancas(conn, empresa["id"]) if set(m.ativos) & codigos_meus]
    if not pendentes:
        st.success("Nenhuma mudança aguardando decisão para os seus ativos.")
    for m in pendentes:
        with st.container(border=True):
            st.markdown(f"#### {m.codigo} · {m.titulo}")
            st.caption(f"Origem: {m.ato or m.fonte} · publicado em {m.publicado_em or '—'}")
            st.dataframe(pd.DataFrame([{"Campo": c, "Hoje": a, "Proposto": b}
                                       for c, (a, b) in m.diferencas.items()]),
                         hide_index=True, width="stretch")
            if m.trecho:
                st.markdown(f"> {m.trecho}")
            st.markdown(f"Ativos afetados: **{', '.join(m.ativos)}**")
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("Aprovar", key=f"ok{m.versao_id}", type="primary"):
                db.decidir(conn, m.versao_id, aprovar=True, por=visao)
                st.rerun()
            if b2.button("Rejeitar", key=f"no{m.versao_id}"):
                db.decidir(conn, m.versao_id, aprovar=False, por=visao)
                st.rerun()
    decididas = conn.execute(
        "SELECT o.codigo, v.status, v.decidida_por, v.decidida_em FROM obrigacao_versao v "
        "JOIN obrigacao o ON o.id = v.obrigacao_id WHERE v.ato_id IS NOT NULL AND v.status != 'pendente'"
    ).fetchall()
    if decididas:
        st.markdown("##### Decisões registradas")
        st.dataframe(pd.DataFrame([dict(r) for r in decididas]), hide_index=True, width="stretch")

# ------------------------------------------------------------------ Radar

with aba_radar:
    st.markdown("Agosto de 2026 no DOU, seção 1: **7.884 atos → 825 da ANM → 2 normativos** "
                "(Res. 245 e Res. 246). Só esses dois chegam à IA; o resto sai por regra, sem custo.")
    radar = json.loads(demo.RADAR.read_text(encoding="utf-8")) if demo.RADAR.exists() else []
    for r in radar:
        with st.container(border=True):
            mud = [x for x in r["mudancas"] if not x["reprovada"]]
            st.markdown(f"**{r['ato']}** — {'muda ' + ', '.join(sorted({x['obrigacao'] for x in mud})) if mud else 'não muda o cadastro'}")
            st.caption(r["motivo"])
            st.caption(f"Obrigações enviadas à IA: {', '.join(r['candidatas']) or 'nenhuma'} · "
                       f"modelo: {' → '.join(r['modelos'])} · confiança {r['confianca']} · "
                       f"custo US$ {r['custo_usd']:.4f}")
