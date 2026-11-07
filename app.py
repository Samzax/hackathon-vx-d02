"""Mitra — Torre de Controle Regulatória (interface da demo).

Uso: uv run streamlit run app.py
"""

from __future__ import annotations

import hashlib
import html
import os
from functools import partial
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from mitra import agenda, arquivos, db, demo, impacto, ocr, operacao, pdf, sigbm, torre, usuarios
from mitra import evidencias as ev
from mitra.ia import Roteador

st.set_page_config(page_title="Mitra · Torre de Controle", page_icon="assets/marca.svg", layout="wide")
# no celular o Streamlit empilha as colunas: os 5 números do topo ocupariam a tela inteira.
# Só abaixo de 640 px, linha de métricas fica 3 por linha e com número menor; no desktop nada muda.
st.html("""<style>
@media (max-width: 640px) {
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {
    flex-direction: row !important; flex-wrap: wrap !important; gap: 0.25rem 0.75rem !important; }
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) > [data-testid="stColumn"] {
    min-width: 28% !important; flex: 1 1 28% !important; width: auto !important; }
  [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
  [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
  h1 { font-size: 1.9rem !important; }
}
</style>""")


ROTULO = {
    agenda.ATRASADA: "Atrasada",
    torre.DADO_FALTANDO: "Dado faltando",
    agenda.VENCE_LOGO: "Vence em breve",
    agenda.EM_DIA: "Em dia",
    agenda.CUMPRIDA: "Cumprida",
    agenda.GATILHO: "Por gatilho",
}
# cor só onde tem significado: o status. As cores vêm do tema (.streamlit/config.toml)
COR_STATUS = {agenda.ATRASADA: "red", torre.DADO_FALTANDO: "gray", agenda.VENCE_LOGO: "orange",
              agenda.EM_DIA: "green", agenda.CUMPRIDA: "green", agenda.GATILHO: "blue"}
# cabeçalho curto das contagens (cabe em 1280 px); o nome inteiro aparece ao passar o mouse
COLUNA = {agenda.ATRASADA: "Atrasadas", torre.DADO_FALTANDO: "Falta dado", agenda.VENCE_LOGO: "Vencendo",
          agenda.EM_DIA: "Em dia", agenda.GATILHO: "Gatilho"}
_DICA_STATUS = {COLUNA[s]: st.column_config.NumberColumn(help=ROTULO[s], width="small") for s in COLUNA}
_ESCURO = getattr(st.context.theme, "type", None) == "dark"


def _hex(cor: str) -> str:
    """Cor do tema (claro ou escuro) pelo nome: 'red', 'primary'..."""
    nome = "primaryColor" if cor == "primary" else f"{cor}Color"
    return st.get_option(f"theme.{'dark' if _ESCURO else 'light'}.{nome}") or "#888888"


def _tag(status: str, texto: str | None = None) -> str:
    """Etiqueta colorida do status, em Markdown do Streamlit."""
    return f":{COR_STATUS.get(status, 'gray')}-badge[{texto or ROTULO.get(status, status)}]"


_STATUS_DO_ROTULO = {v: k for k, v in ROTULO.items()}


def _rgba(hexa: str, alfa: float) -> str:
    h = hexa.lstrip("#")
    return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {alfa})"


def _rgb(hexa: str) -> list[int]:
    h = hexa.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _pintar(df: pd.DataFrame):
    """Tabela com a coluna Status em cor e as contagens de status coloridas quando passam de zero."""
    def _texto(v):
        s = _STATUS_DO_ROTULO.get(v)
        return f"color: {_hex(COR_STATUS[s])}; font-weight: 600" if s else ""

    def _conta(coluna):
        s = next(k for k, v in COLUNA.items() if v == coluna.name)
        cor = _hex(COR_STATUS[s]) if s not in (agenda.EM_DIA, agenda.GATILHO) else None
        return [f"color: {cor}; font-weight: 600" if cor and v else "" for v in coluna]

    est = df.style
    if "Status" in df.columns:
        est = est.map(_texto, subset=["Status"])
    contagens = [c for c in COLUNA.values() if c in df.columns]
    if contagens:
        est = est.apply(_conta, subset=contagens)
    return est


# identidade: cabeçalho compacto, cartões de número com a cor do status no topo, grupos da caixa de
# entrada com a cor na borda, números alinhados. Cores vindas do tema (claro ou escuro).
st.html(f"""<style>
:root {{ --rg-red: {_hex('red')}; --rg-orange: {_hex('orange')}; --rg-gray: {_hex('gray')};
        --rg-green: {_hex('green')}; --rg-blue: {_hex('blue')}; --rg-primary: {_hex('primary')}; }}
.block-container {{ padding-top: 2.2rem !important; }}
[data-testid="stMetricValue"], .rg-num {{ font-variant-numeric: tabular-nums; }}
.rg-head {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem;
           border-bottom: 1px solid rgba(128,128,128,.22); padding-bottom: .7rem; margin-bottom: .2rem; }}
.rg-over {{ font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; opacity: .62; font-weight: 600; }}
.rg-emp {{ font-size: 1.45rem; font-weight: 650; line-height: 1.25; }}
.rg-meta {{ font-size: .85rem; opacity: .7; text-align: right; white-space: nowrap; }}
.st-key-kpis [data-testid="stMetric"] {{ border-top: 3px solid var(--rg-gray); }}
.st-key-kpis [data-testid="stColumn"]:nth-of-type(1) [data-testid="stMetric"] {{ border-top-color: var(--rg-red); }}
.st-key-kpis [data-testid="stColumn"]:nth-of-type(2) [data-testid="stMetric"] {{ border-top-color: var(--rg-gray); }}
.st-key-kpis [data-testid="stColumn"]:nth-of-type(3) [data-testid="stMetric"] {{ border-top-color: var(--rg-orange); }}
.st-key-kpis [data-testid="stColumn"]:nth-of-type(4) [data-testid="stMetric"] {{ border-top-color: var(--rg-green); }}
.st-key-kpis [data-testid="stColumn"]:nth-of-type(5) [data-testid="stMetric"] {{ border-top-color: var(--rg-blue); }}
[class*="st-key-grupo_"] {{ border-left: 3px solid var(--rg-gray) !important; }}
.st-key-grupo_atrasada {{ border-left-color: var(--rg-red) !important; }}
.st-key-grupo_vence_logo {{ border-left-color: var(--rg-orange) !important; }}
.st-key-grupo_mudancas {{ border-left-color: var(--rg-primary) !important; }}
.st-key-doc {{ border: 1px dashed rgba(128,128,128,.45) !important; }}
</style>""")


TIPO = {"barragem": "Barragem", "unidade": "Unidade", "equipamento": "Equipamento", "licenca": "Licença",
        "estabelecimento_saude": "Estabelecimento de saúde", "abrigo_residuos": "Abrigo de resíduos"}
TROCA_NORMA = date(2027, 8, 2)   # Res. ANM 220/2025 substitui a Res. ANM 95/2022
CAMPO = {"prazo": "Prazo", "vigencia_desde": "Começa a valer em", "vigencia_ate": "Deixa de valer após",
         "periodicidade": "Periodicidade", "aplica_se_a": "Aplica-se a", "titulo": "Obrigação",
         "evidencia": "Evidência", "regra": "Regra", "agenda": "Agenda"}


def _curto(texto: str, n: int = 70) -> str:
    """Corta no limite de palavra e marca com reticências."""
    return texto if len(texto) <= n else texto[:n].rsplit(" ", 1)[0] + "…"


def _usd(valor: float, casas: int = 4) -> str:
    """US$ com vírgula decimal (o $ escapado não vira fórmula no Markdown)."""
    return "US\\$ " + f"{valor:.{casas}f}".replace(".", ",")


def _escopo(r: dict, m) -> str:
    """O tamanho da mudança dito pelos dados, não pela IA: o que foi à IA, o que muda, o que fica."""
    mudam = sorted({x["obrigacao"] for x in r["mudancas"] if not x["reprovada"]})
    iguais = [c for c in r["candidatas"] if c not in mudam]
    norma = conn.execute("SELECT norma FROM obrigacao WHERE codigo = ?", (m.codigo,)).fetchone()["norma"]
    codigos = [row[0] for row in conn.execute("SELECT codigo FROM obrigacao WHERE norma = ?", (norma,))]
    outras = len([c for c in codigos if c not in mudam])
    return (f"**Muda {len(mudam)} {'obrigação' if len(mudam) == 1 else 'obrigações'} ({', '.join(mudam)}).** "
            f"As outras {outras} da {norma} ficam iguais. Foram à IA {len(r['candidatas'])} candidatas; "
            f"{', '.join(iguais) or 'nenhuma outra'} {'ficou igual' if len(iguais) == 1 else 'ficaram iguais'}.")


def _val(campo, valor):
    """Valor de um campo de obrigação para quem aprova: datas em DD/MM/AAAA, agenda em português."""
    return agenda.descrever(valor) if campo == "agenda" and valor else _br(valor)


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


@st.cache_data(max_entries=32)
def _pdf(md: str, titulo: str) -> bytes:
    """O PDF só muda quando o texto muda. Os botões passam partial(_pdf, ...): o Streamlit só gera
    o arquivo no clique, então mudar a data ou o gestor não paga reportlab."""
    return pdf.de_markdown(md, titulo)


@st.cache_resource
def _roteador_sem_chave():
    """Só o cache: para quando a visita já gastou a cota de IA do link público."""
    return Roteador(db.conectar(impacto.CACHE_IA), env={}, provedores={})


@st.cache_resource
def _roteador():
    """IA só para o que a regra não resolve; sem chave no .env, fica só a regra (e o cache)."""
    try:
        return Roteador(db.conectar(impacto.CACHE_IA))
    except Exception:
        return None


conn = _conexao(str(db.DB_PADRAO))
spec = _spec()
empresas = {e["id"]: e for e in db.empresas(conn)}
if "empresa_nova" in st.session_state:                      # acabou de importar
    st.session_state["empresa_id"] = st.session_state.pop("empresa_nova")
if st.session_state.get("empresa_id") not in empresas:      # primeira visita, ou "Recriar demo"
    st.session_state["empresa_id"] = next(iter(empresas))
LIMITE_IA_SESSAO = int(os.environ.get("MITRA_LIMITE_SESSAO") or 0) or None   # análises pagas por visita


def _roteador_da_sessao():
    """O roteador, se esta visita ainda pode pagar IA; senão None (só regra e cache)."""
    rot = _roteador()
    if rot is not None and LIMITE_IA_SESSAO and st.session_state.get("ia_usadas", 0) >= LIMITE_IA_SESSAO:
        return None
    return rot


def _com_ia(fn):
    """Roda fn(roteador) e conta quantas respostas novas (pagas) a IA deu nesta visita."""
    rot = _roteador_da_sessao()
    antes = rot.chamadas() if rot else 0
    try:
        return fn(rot)
    finally:
        if rot:
            st.session_state["ia_usadas"] = st.session_state.get("ia_usadas", 0) + rot.chamadas() - antes


@st.dialog("Sua mineradora em 30 segundos", width="large")
def _importar():
    st.caption(f"Barragens reais do SIGBM (exportação pública de {_br(sigbm.EXPORTADO_EM)}), só de empresas (CNPJ). "
               "A torre monta as obrigações pelas regras do cadastro; o que o SIGBM não informa fica como "
               "**dado faltando**, para você preencher. Nada é presumido.")
    termo = st.text_input("CNPJ ou nome da empresa", placeholder="ex.: 33.592.510/0001-54, Vale, Samarco, CSN…")
    achadas = sigbm.buscar(termo) if termo else []
    if termo and not achadas:
        st.warning("Nenhuma empresa com barragem no SIGBM com esse CNPJ ou nome.")
    if not achadas:
        return
    i = st.radio("Empresa", range(len(achadas)), format_func=lambda i: (
        f"{achadas[i].nome} · {achadas[i].cnpj} · {len(achadas[i].barragens)} barragens "
        f"({len(achadas[i].na_pnsb)} na PNSB) · " + ", ".join(sorted({b['uf'] for b in achadas[i].barragens}))))
    emp = achadas[i]
    alerta = [b for b in emp.barragens if sigbm.alertas(b)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Barragens no SIGBM", len(emp.barragens))
    c2.metric("Na PNSB", len(emp.na_pnsb), help="Política Nacional de Segurança de Barragens: onde vale a Res. 95")
    c3.metric("Com alerta no SIGBM", len(alerta), help="Embargo, nível de alerta ou emergência, DCE/DCO não atestada")
    so_pnsb = st.checkbox("Só as barragens na PNSB", value=bool(emp.na_pnsb), disabled=not emp.na_pnsb,
                          help="As obrigações do cadastro (Res. ANM 95/2022) valem para barragens na PNSB")
    inicio = st.date_input("Começar a cobrar a partir de", value=st.session_state.get("hoje", date.today()),
                           format="DD/MM/YYYY",
                           help="O que venceu antes desta data não aparece como atraso: a torre não sabe o que já foi entregue")
    if st.button(f"Montar a torre de {emp.nome}", type="primary"):
        eid = sigbm.importar(conn, emp, inicio, so_pnsb=so_pnsb and bool(emp.na_pnsb))
        st.session_state["empresa_nova"] = eid      # o seletor já existe nesta rodada: troca na próxima
        st.session_state.pop("manter_importar", None)
        st.rerun()


# ------------------------------------------------------------------ barra lateral

# marca provisória (assets/): perfil de barragem com a linha d'água; versão com texto claro ou escuro
st.logo(f"assets/logo_{'escuro' if _ESCURO else 'claro'}.svg", size="large", icon_image="assets/marca.svg")


# ------------------------------------------------------------------ entrar
# A sessão guarda só o e-mail; a conta é relida a cada rerun, então desativar uma conta tira a pessoa na hora.

def _entrar(conta: dict):
    st.session_state["usuario"] = conta["email"]
    for k in ("aba", "aba_reg", "ativo_sel"):      # quem entra começa da caixa de entrada
        st.session_state.pop(k, None)


def _sair():
    for k in list(st.session_state):
        if k not in ("empresa_id", "hoje"):
            st.session_state.pop(k, None)


def _tela_entrar():
    _, meio, _ = st.columns([1, 1.4, 1])
    with meio:
        st.html("<div class='rg-over'>Torre de controle regulatória</div>")
        st.title("Entrar")
        demo_conta = usuarios.conta_demo(conn)
        if demo_conta:
            if st.button("Entrar na demo", type="primary", icon=":material/play_arrow:", width="stretch",
                         help="Conta de teste, sem senha: troque de visão (Diretoria, cada gestor, TI) pela barra lateral"):
                usuarios.registrar_acesso(conn, demo_conta["id"])
                _entrar(demo_conta)
                st.rerun()
            st.caption("Conta de teste da Mineradora Serra Azul (fictícia). Ou entre com a sua conta:")
        with st.form("entrar"):
            email = st.text_input("E-mail", autocomplete="username")
            senha = st.text_input("Senha", type="password", autocomplete="current-password")
            if st.form_submit_button("Entrar", width="stretch"):
                conta = usuarios.autenticar(conn, email, senha)
                if conta:
                    _entrar(conta)
                    st.rerun()
                st.error("E-mail ou senha não conferem, ou a conta está desativada.")
        st.caption("Esqueceu sua senha? Entre em contato com o suporte.")


usuario = usuarios.por_email(conn, st.session_state.get("usuario", ""))
if usuario is None or not usuario["ativa"]:
    st.session_state.pop("usuario", None)
    _tela_entrar()
    st.stop()


def _quem_entrou():
    with st.container(border=True):
        st.markdown(f"**{usuario['nome']}**  \n<small>{usuarios.PAPEIS[usuario['papel']]}"
                    f"{' · ' + usuario['area'] if usuario['area'] else ''}"
                    f"{' · Teste' if usuario['teste'] else ''}</small>", unsafe_allow_html=True)
        st.button("Sair", icon=":material/logout:", on_click=_sair, key="sair", width="stretch")


VISAO_TI = "TI (contas de acesso)"
VISAO_DIRETORIA = "Diretoria (todos os ativos)"


def _pagina_usuarios(quem: str):
    """Só para a TI: criar contas, mudar papel e área, desativar, trocar senha."""
    st.html("<div class='rg-head'><div><div class='rg-over'>Administração</div>"
            "<div class='rg-emp'>Usuários e acessos</div></div></div>")
    st.caption("O papel diz o que a pessoa vê: Diretoria e Regulatório veem todos os ativos; o gestor vê os da "
               "sua área. Qual área responde por cada ativo é decisão da Diretoria, na ficha do ativo. "
               "Conta de teste troca de visão à vontade (para demonstrar); conta normal fica presa à dela.")
    contas = usuarios.listar(conn)

    def _acesso(utc: str | None) -> str:
        """O banco guarda em UTC; aqui vai no horário de Brasília (sem horário de verão desde 2019)."""
        if not utc:
            return "nunca"
        return (pd.Timestamp(utc) - pd.Timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

    curto = {usuarios.ADMIN: "TI", usuarios.GESTOR: "Gestor"}
    st.dataframe(pd.DataFrame([{
        "Nome": u["nome"], "E-mail": u["email"], "Papel": curto.get(u["papel"], usuarios.PAPEIS[u["papel"]]),
        "Área": u["area"] or "—", "Tipo": "teste" if u["teste"] else "normal",
        "Situação": "ativa" if u["ativa"] else "desativada", "Último acesso": _acesso(u["ultimo_acesso"]),
    } for u in contas]), hide_index=True, width="stretch", column_config={
        "Área": st.column_config.TextColumn(width="medium"), "Papel": st.column_config.TextColumn(width="small"),
        "Tipo": st.column_config.TextColumn(width="small"), "Situação": st.column_config.TextColumn(width="small")})
    areas = usuarios.areas(conn)
    nova, editar = st.tabs(["Nova conta", "Editar conta"])
    with nova:
        with st.form("nova_conta", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Nome")
            email = c2.text_input("E-mail")
            papel = c1.selectbox("Papel", list(usuarios.PAPEIS), format_func=usuarios.PAPEIS.get,
                                 index=list(usuarios.PAPEIS).index(usuarios.GESTOR))
            area = c2.selectbox("Área (só para gestor)", areas, index=None, accept_new_options=True,
                                placeholder="escolha ou digite uma área nova")
            senha = c1.text_input("Senha inicial", type="password", help=f"Pelo menos {usuarios.SENHA_MINIMA} caracteres")
            teste = c2.checkbox("Conta de teste (troca de visão)")
            if st.form_submit_button("Criar conta", type="primary"):
                try:
                    usuarios.criar(conn, email, nome, papel, area=area if papel == usuarios.GESTOR else None,
                                   senha=senha or None, teste=teste, por=quem, empresa=usuario.get("empresa"))
                    st.toast(f"Conta de {nome.strip()} criada")
                    st.rerun()
                except usuarios.ErroConta as e:
                    st.error(str(e)[:1].upper() + str(e)[1:] + ".")
    with editar:
        por_id = {u["id"]: u for u in contas}
        uid = st.selectbox("Conta", list(por_id), key="conta_sel",
                           format_func=lambda i: f"{por_id[i]['nome']} · {por_id[i]['email']}")
        u = por_id[uid]
        with st.form(f"editar_{uid}"):
            c1, c2 = st.columns(2)
            nome_e = c1.text_input("Nome", value=u["nome"])
            papel_e = c2.selectbox("Papel", list(usuarios.PAPEIS), format_func=usuarios.PAPEIS.get,
                                   index=list(usuarios.PAPEIS).index(u["papel"]))
            opcoes = sorted(set(areas) | ({u["area"]} if u["area"] else set()))
            area_e = c1.selectbox("Área (só para gestor)", opcoes, accept_new_options=True,
                                  index=opcoes.index(u["area"]) if u["area"] else None,
                                  placeholder="escolha ou digite uma área nova")
            teste_e = c2.checkbox("Conta de teste (troca de visão)", value=u["teste"])
            ativa_e = c2.toggle("Conta ativa", value=u["ativa"])
            senha_e = c1.text_input("Nova senha (vazio: mantém a atual)", type="password")
            if st.form_submit_button("Salvar", type="primary"):
                try:
                    if senha_e:
                        usuarios.definir_senha(conn, uid, senha_e)
                    usuarios.editar(conn, uid, nome=nome_e, papel=papel_e, teste=teste_e, ativa=ativa_e,
                                    area=(area_e or "") if papel_e == usuarios.GESTOR else "")
                    st.toast(f"Conta de {nome_e.strip()} salva")
                    st.rerun()
                except usuarios.ErroConta as e:
                    st.error(str(e)[:1].upper() + str(e)[1:] + ".")


if usuario["papel"] == usuarios.ADMIN and not usuario["teste"]:
    with st.sidebar:
        _quem_entrou()
    _pagina_usuarios(usuario["nome"])
    st.stop()

with st.sidebar:
    _quem_entrou()
    st.selectbox("Empresa", list(empresas), key="empresa_id",
                 format_func=lambda i: empresas[i]["nome"] + (" · saúde" if empresas[i].get("setor") == "saude" else "")
                 + (" · fictícia" if empresas[i]["ficticia"] else ""))
    empresa = empresas[st.session_state["empresa_id"]]
    setor_saude = empresa.get("setor") == "saude"
    importada = bool(empresa["monitorado_desde"])
    if not setor_saude and (st.button("Sua mineradora (SIGBM)", icon=":material/add:", width="stretch",
                         help="Busque pelo CNPJ ou pelo nome e monte a torre com as barragens reais da empresa")
                         or st.session_state.get("manter_importar")):   # nos testes, o diálogo fica aberto entre reruns
        _importar()
    if importada:
        st.caption(f"Barragens e atributos: {empresa['origem']}. Dados públicos, sem pessoa física.")
    elif setor_saude:
        st.caption("Protótipo de saúde: dados fictícios, sem pacientes ou profissionais identificáveis.")
    ativos = db.ativos(conn, empresa["id"])
    donos = {k: v for k, v in db.responsaveis(conn).items() if k[0] in {a["id"] for a in ativos}}
    responsaveis = sorted({a["responsavel"] for a in ativos if a["responsavel"]} | set(donos.values()))
    if usuario["teste"]:        # conta de teste: escolhe a visão (demo e pitch)
        visao = st.selectbox("Quem está olhando", [VISAO_DIRETORIA] + responsaveis + [VISAO_TI])
    elif usuarios.ve_tudo(usuario):
        visao = VISAO_DIRETORIA if usuario["papel"] == usuarios.DIRETORIA else "Regulatório (todos os ativos)"
    else:                       # gestor: só a área da conta
        visao = usuario["area"]
    hoje_demo = date.fromisoformat(spec.get("hoje", date.today().isoformat()))
    st.session_state.setdefault("hoje", hoje_demo)
    hoje = st.date_input("Hoje", key="hoje", format="DD/MM/YYYY")

    def _ir_para(d: date):
        st.session_state["hoje"] = d

    if setor_saude:
        st.caption("Data de referência do protótipo:")
        st.button("Demo", on_click=_ir_para, args=(hoje_demo,), help=f"{hoje_demo:%d/%m/%Y}", width="stretch")
    else:
        st.caption("Viagem no tempo:")
        v1, v2, v3 = st.columns([1, 1.35, 0.9], gap="small")   # "Res. 220" não pode cortar em 1280 px
        v1.button("Demo", on_click=_ir_para, args=(hoje_demo,), help=f"{hoje_demo:%d/%m/%Y}", width="stretch")
        v2.button("Res. 220", on_click=_ir_para, args=(TROCA_NORMA,), help=f"{TROCA_NORMA:%d/%m/%Y}: troca de norma",
                  width="stretch")
        v3.button("ZAS", on_click=_ir_para, args=(date(2029, 12, 27),),
                  help="27/12/2029: dia seguinte ao prazo da ZAS (ANM e NR-22)", width="stretch")
    desde = date.fromisoformat(empresa["monitorado_desde"] or ("2026-01-01" if setor_saude else spec.get("desde", "2026-05-01")))
    st.caption(f"{'Monitorada' if importada else 'Histórico monitorado'} desde {desde:%d/%m/%Y}.")
    rot_ia = _roteador()
    if rot_ia is not None and rot_ia.ligada:
        teto = f" de {_usd(rot_ia.teto_dia_usd, 2)}" if rot_ia.teto_dia_usd else ""
        resta = (f" · {max(LIMITE_IA_SESSAO - st.session_state.get('ia_usadas', 0), 0)} análises novas nesta visita"
                 if LIMITE_IA_SESSAO else "")
        st.caption(f"IA ligada · gasto hoje {_usd(rot_ia.gasto_hoje(), 3)}{teto}{resta}")
    if usuario["teste"] and st.button("Recriar demo", help="Apaga decisões, entregas e empresas importadas e volta ao estado inicial"):
        _conexao.clear()
        for k in ("leitura", "analise_teste", "ato_teste", "radar_teste", "empresa_id"):
            st.session_state.pop(k, None)
        st.rerun()

# quem assina o que se faz na torre: a conta; na conta de teste, a visão escolhida (demo)
assinante = visao if usuario["teste"] else usuario["nome"]
if visao == VISAO_TI:          # conta de teste olhando como a TI
    _pagina_usuarios(assinante)
    st.stop()
diretoria = visao.endswith("(todos os ativos)")
# a área responsável por um ativo é decisão da Diretoria (a TI só cuida das contas)
decide_areas = visao == VISAO_DIRETORIA
dono_do_ativo = {a["codigo"]: a["responsavel"] for a in ativos}
todas = torre.painel(conn, empresa["id"], hoje, desde)


def _minha(l) -> bool:
    """Diretoria vê tudo; o gestor do ativo vê o ativo inteiro; quem recebeu uma obrigação vê a dela."""
    return diretoria or dono_do_ativo.get(l.ativo) == visao or l.responsavel == visao


minhas = [l for l in todas if _minha(l)]
meus = [a for a in ativos if diretoria or a["responsavel"] == visao or any(l.ativo == a["codigo"] for l in minhas)]
codigos_meus = {a["codigo"] for a in meus}

st.html(f"<div class='rg-head'><div><div class='rg-over'>Torre de controle regulatória</div>"
        f"<div class='rg-emp'>{html.escape(empresa['nome'])}</div></div>"
        f"<div class='rg-meta'><span class='rg-num'>{hoje:%d/%m/%Y}</span><br>{html.escape(visao)} · "
        f"{len(meus)} {'ativo' if len(meus) == 1 else 'ativos'}</div></div>")
if hoje > hoje_demo and not importada and not setor_saude:
    st.info(f"Viagem no tempo: {hoje:%d/%m/%Y}. As entregas da demo vão até {hoje_demo:%d/%m/%Y}; "
            "o que venceu depois disso aparece atrasado porque ninguém registrou a entrega. "
            "O ponto aqui é ver o que a torre passa a cobrar, e de qual norma.", icon=":material/history:")

# ------------------------------------------------------------------ navegação
# Por quem usa: a operação (caixa de entrada, ativos, entregas), o regulatório (mudanças, radar,
# transição) e o "sobre" do pitch. As abas guardam estado (key + rerun) para que um número, um
# item da caixa ou um ativo levem direto à tela certa, já filtrada. O conteúdo de todas roda a cada
# rerun (não usamos .open): os testes leem a torre inteira de uma vez.

ABA_CAIXA, ABA_ATIVOS, ABA_ENTREGAS, ABA_REG, ABA_SOBRE = (
    ":material/inbox: Caixa de entrada", ":material/foundation: Ativos", ":material/task_alt: Entregas",
    ":material/gavel: Regulatório", ":material/info: Sobre")
SUB_MUDANCAS, SUB_RADAR = "Mudanças", "Radar do DOU"
SUB_TRANSICAO = "Vigência e linha do tempo" if setor_saude else "Transição e linha do tempo"
STATUS_PADRAO = [agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO]


def _ir(aba: str, sub: str | None = None, estado: dict | None = None):
    """Callback de navegação: troca de aba e já deixa filtros e seleção prontos."""
    st.session_state["aba"] = aba
    if sub:
        st.session_state["aba_reg"] = sub
    st.session_state.update(estado or {})


def _filtro_entregas(status: list | None = None, ativo: list | None = None) -> dict:
    """Estado da aba Entregas com um filtro só (o resto limpo), para quem chega de um atalho."""
    return {"f_status": status or [], "f_ativo": ativo or [], "f_norma": [], "f_resp": [], "f_busca": "",
            "f_janela": None, "acoes": st.session_state.get("acoes", 0) + 1}


aba_caixa, aba_ativos, aba_entregas, aba_reg, aba_sobre = st.tabs(
    [ABA_CAIXA, ABA_ATIVOS, ABA_ENTREGAS, ABA_REG, ABA_SOBRE], key="aba", on_change="rerun")
with aba_reg:
    aba_mudancas, aba_radar, aba_transicao = st.tabs([SUB_MUDANCAS, SUB_RADAR, SUB_TRANSICAO],
                                                     key="aba_reg", on_change="rerun")
with aba_sobre:
    aba_mercado, aba_como = st.tabs(["Mercado", "Como funciona"])

pendentes = [m for m in torre.mudancas(conn, empresa["id"]) if set(m.ativos) & codigos_meus]


# ------------------------------------------------------------------ entrega (caixa, ativo e Entregas)

def _form_entrega(l, chave: str, depois):
    """Registrar a entrega de uma obrigação: dia, período que comprova, comprovante e observação."""
    if l.agenda == "evento" and l.status == agenda.GATILHO:
        st.caption("Obrigação por gatilho: registre quando o evento acontecer.")
    dia_ent = st.date_input("Feita em", value=hoje, format="DD/MM/YYYY", key=f"dia_{chave}", max_value=hoje)
    per = operacao.periodo_para_entrega(l, dia_ent)
    st.caption(f"Comprova: **{agenda.rotulo_humano(per)}**")
    anexo = st.file_uploader("Comprovante (opcional)", key=f"anexo_{chave}")
    obs = st.text_input("Observação", key=f"obs_{chave}")
    if st.button("Registrar entrega", type="primary", key=f"ent_{chave}"):
        onde = None
        if anexo is not None:
            try:
                onde = arquivos.guardar(anexo.name, anexo.getvalue())
            except Exception as e:
                st.warning(f"Não consegui guardar o arquivo ({type(e).__name__}); registro só o nome.")
                onde = anexo.name
        db.entregar(conn, l.ativo_id, l.codigo, per, dia=dia_ent.isoformat(), por=assinante,
                    arquivo=onde, obs=obs or None)
        st.toast(f"Entrega registrada: {l.ativo} · {l.codigo} · {agenda.rotulo_humano(per)}")
        depois()


def _fechar_entrega():
    st.session_state.pop("entrega_de", None)


def _entrega_feita():
    _fechar_entrega()
    st.rerun()


@st.dialog("Registrar entrega", width="large", on_dismiss=_fechar_entrega)
def _dialogo_entrega(l):
    st.markdown(f"{_tag(l.status)} **{l.ativo} · {l.titulo}**")
    st.caption(f"{torre.dispositivo(l.norma, l.artigo)} · evidência: {l.evidencia or '—'} · "
               f"pendente: {torre.pendente(l) or '—'}")
    _form_entrega(l, f"dlg_{l.ativo}_{l.codigo}", _entrega_feita)


def _botao_entrega(l, onde: str, rotulo: str = "Registrar entrega"):
    """Abre o diálogo de entrega. O alvo fica no estado: o diálogo sobrevive aos reruns de dentro
    dele (data, anexo) e fecha ao registrar ou ao clicar fora."""
    st.button(rotulo, key=f"abre_{onde}_{l.ativo}_{l.codigo}", icon=":material/check:",
              on_click=st.session_state.__setitem__,
              args=("entrega_de", (l.ativo, l.codigo)))


def _rotulo_ativo(a) -> str:
    """Rótulo do seletor de ativo, a partir de um ativo (dict) ou de uma linha da torre."""
    return f"{a['codigo']} · {a['nome']}" if isinstance(a, dict) else f"{a.ativo} · {a.ativo_nome}"


def _editor_cadastro(campos: list[str], alvos: list[dict], chave: str, todas: bool = False):
    """Preencher o que falta no cadastro (o que decide se uma obrigação vale). `todas`: só grava nos
    ativos que ainda não têm o dado; senão grava em todos os `alvos`."""
    novos = {}
    for campo in campos:
        rotulo = sigbm.FALTAM_NO_SIGBM.get(campo, torre.campo_legivel(campo))
        if campo == "dpa2":
            v = st.number_input(f"{rotulo} (`{campo}`)", 0.0, 10.0, value=None, step=1.0, key=f"{chave}_{campo}")
            if v is not None:
                novos[campo] = v
        else:
            v = st.radio(f"{rotulo[:1].upper()}{rotulo[1:]} (`{campo}`)", ["não sei", "sim", "não"],
                         horizontal=True, key=f"{chave}_{campo}")
            if v != "não sei":
                novos[campo] = v == "sim"
    if st.button("Salvar no cadastro", type="primary", disabled=not novos, key=f"{chave}_salvar"):
        n = 0
        for a in alvos:
            faltam = {k: v for k, v in novos.items() if k not in a["atributos"]} if todas else novos
            if faltam:
                db.atualizar_atributos(conn, a["id"], faltam, por=assinante)
                n += 1
        st.toast(f"Cadastro atualizado em {n} {'ativo' if n == 1 else 'ativos'}: a torre recalculou o que vale.")
        st.rerun()


# ------------------------------------------------------------------ Caixa de entrada

linhas = minhas
with aba_caixa:
    cont = {s: sum(1 for l in linhas if l.status == s) for s in ROTULO}
    cols = st.container(key="kpis").columns(5)
    for col, s in zip(cols, [agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO, agenda.EM_DIA, agenda.GATILHO], strict=True):
        col.metric(ROTULO[s], cont[s], border=True)
        col.button("Ver na lista →", key=f"kpi_{s}", type="tertiary", disabled=not cont[s],
                   on_click=_ir, args=(ABA_ENTREGAS,), kwargs={"estado": _filtro_entregas([s])},
                   help=f"Abre a aba Entregas filtrada em: {ROTULO[s].lower()}")

    if importada:
        com_alerta = [a for a in meus if a["atributos"].get("alertas_sigbm")]
        sem_dado = sorted({c for l in linhas for c in l.dados_faltando if c != torre.ULTIMA_EXECUCAO})
        sem_data = sum(1 for l in linhas if torre.ULTIMA_EXECUCAO in l.dados_faltando)
        with st.container(border=True):
            st.markdown(f"##### Primeiros passos · {len(meus)} barragens importadas do SIGBM")
            p1, p2, p3 = st.columns(3)
            p1.markdown(f"**1. O que o SIGBM já mostra.** {len(com_alerta)} barragens com alerta público "
                        "(embargo, nível de emergência, DCE ou DCO não atestada).")
            p2.markdown(f"**2. Complete o cadastro.** {len(sem_dado)} dados que o SIGBM não tem decidem se "
                        "algumas obrigações valem. Preencha abaixo, para todas de uma vez ou uma a uma.")
            p3.markdown(f"**3. Registre as últimas entregas.** {sem_data} obrigações a cada N anos (RPSB, PGRBM…) "
                        "precisam da data da última execução: aba **Entregas**.")
            if com_alerta:
                with st.expander(f"Alertas do SIGBM em {len(com_alerta)} barragens", icon=":material/warning:"):
                    st.dataframe(pd.DataFrame([{
                        "Barragem": f"{a['codigo']} · {a['nome']}",
                        "Município": f"{a['atributos'].get('municipio', '')}/{a['atributos'].get('uf', '')}",
                        "Alertas": "; ".join(a["atributos"]["alertas_sigbm"]),
                    } for a in com_alerta]), hide_index=True, width="stretch")
            if sem_dado:
                with st.expander("Completar o cadastro: o que o SIGBM não informa", icon=":material/edit_note:"):
                    alvo = st.selectbox("Barragem", ["todas"] + [a["codigo"] for a in meus],
                                        format_func=lambda c: "Todas as barragens que ainda não têm o dado" if c == "todas"
                                        else f"{c} · {next(a['nome'] for a in meus if a['codigo'] == c)}")
                    _editor_cadastro(sem_dado, meus if alvo == "todas" else [a for a in meus if a["codigo"] == alvo],
                                     "cad", todas=alvo == "todas")

    with st.container(border=True, key="doc"):
        st.markdown("##### :material/upload_file: Chegou um documento da operação?")
        st.caption(("Plano de Segurança do Paciente, PGRSS ou registro de capacitação: a regra lê ativo, documento e data, "
                    "e a torre dá baixa." if setor_saude else
                    "FIR, laudo, recibo do SIGBM ou boletim: a regra lê ativo, documento e data, e a torre dá baixa.")
                   + " A IA só entra se a regra não fechar, e o Python confere.")
        c1, c2 = st.columns(2)
        enviado = c1.file_uploader("Documento em PDF", type=["pdf"])
        exemplos_pdf = [] if setor_saude else sorted(p.name for p in ev.exemplo("x").parent.glob("*.pdf"))
        escolhido = c2.selectbox("…ou um documento de exemplo", ["—"] + exemplos_pdf)
        if st.button("Ler documento", disabled=enviado is None and escolhido == "—"):
            nome, conteudo = ((enviado.name, enviado.getvalue()) if enviado is not None
                              else (escolhido, ev.exemplo(escolhido).read_bytes()))
            try:
                lido_pdf = ocr.ler(conteudo)
            except Exception as e:      # arquivo corrompido, protegido por senha, não é PDF...
                st.session_state.pop("leitura", None)
                st.error(f"Não consegui ler {nome}: {ev.por_que_nao_abre(e)}.")
            else:
                if not "".join(lido_pdf.texto.split()):       # escaneado e sem OCR: nada para ler
                    st.session_state.pop("leitura", None)
                    st.warning(f"Não consegui ler {nome}: {lido_pdf.aviso}.")
                else:
                    le = _com_ia(lambda rot: ev.ler(conn, lido_pdf.texto, empresa["id"], hoje, roteador=rot))
                    if lido_pdf.ocr:
                        le.avisos.append(f"o texto de {lido_pdf.escaneadas} página(s) escaneada(s) veio do OCR "
                                         f"({lido_pdf.ocr}): confira ativo, data e números antes de registrar")
                    elif lido_pdf.aviso:
                        le.avisos.append(lido_pdf.aviso)
                    st.session_state["leitura"] = (nome, le)
                    st.session_state["leitura_pdf"] = conteudo
        if "leitura" in st.session_state:
            nome, le = st.session_state["leitura"]
            st.markdown(f"**{nome}** · lido por {'regra' if le.metodo == 'regra' else 'IA (conferida)'}")
            lido = {
                "Ativo": le.ativo or "—", "Documento": le.documento or "—", "Obrigação": le.obrigacao or "—",
                "Data de execução": _br(le.data), "Período comprovado": le.periodo or "—",
                "Pontuação máxima": le.pontuacao_maxima if le.pontuacao_maxima is not None else "—",
            }
            if le.estado_conservacao:      # Quadro I.8 da Res. 220: quem confere vê o que a regra leu
                lido["Estado de conservação"] = " · ".join(f"{c} {v}" for c, v in sorted(le.estado_conservacao.items()))
            st.dataframe(pd.DataFrame([lido]), hide_index=True, width="stretch")
            # cada gestor responde só pelos ativos dele: documento de outro ativo não é registrado nesta visão
            alheio = bool(le.ativo) and le.ativo not in codigos_meus
            if alheio:
                st.warning(f"O documento é de {le.ativo}, que não está entre os ativos de {visao}. "
                           "Quem registra é o responsável por esse ativo ou a Diretoria.")
            for g in le.gatilhos:
                st.error(g, icon=":material/emergency_home:")
            abre = [c for c in getattr(le, "acionar", []) if c != le.obrigacao]
            if abre and le.completa and not alheio:
                abertas = []
                for c in abre:
                    v = db.versao(conn, c) or {}
                    abertas.append(f"**{c} · {v.get('titulo', c)}** (encerra com: {v.get('evidencia') or 'a evidência'})")
                st.caption(f"Ao registrar, a torre abre em {le.ativo}, com prazo de 24 h: " + "; ".join(abertas)
                           + ". Fica aberta até chegar esse documento.")
            for p in le.problemas:
                st.warning(f"{p[:1].upper()}{p[1:]}")
            for a in getattr(le, "avisos", []):     # leitura guardada antes de o campo existir
                st.info(f"{a[:1].upper()}{a[1:]}", icon=":material/smart_toy:" if "pela IA" in a else
                        ":material/document_scanner:" if "OCR" in a else ":material/schedule:")
            if le.completa:
                o_que = f"{le.documento} de {le.ativo} · {agenda.rotulo_humano(le.periodo)}"
            if le.completa and not alheio and st.button(f"Registrar evidência: {o_que}", type="primary",
                                         help=f"Dá baixa em {le.obrigacao}, período {le.periodo}"):
                original = st.session_state.pop("leitura_pdf", None)
                onde = None
                try:                        # guarda a prova (pasta local ou S3); se falhar, registra só o nome
                    onde = arquivos.guardar(nome, original) if original else None
                except Exception as e:
                    st.warning(f"Não consegui guardar o original ({type(e).__name__}); a baixa foi registrada.")
                ev.registrar(conn, le, nome, guardado_em=onde)
                del st.session_state["leitura"]
                st.toast(f"Evidência registrada: {o_que}"
                         + (f" · aberta em {le.ativo}: {', '.join(abre)} (24 h)" if abre else ""))
                st.rerun()

    st.markdown(f"##### O que precisa de {'mim' if not diretoria else 'decisão ou ação'}")
    MAX_ITENS = 6

    def _item(l, grupo: str):
        """Uma linha da caixa: o que é, o que falta, e o botão da ação que resolve."""
        c1, c2, c3 = st.columns([6, 1.6, 1.2], vertical_alignment="center")
        if l.status == torre.DADO_FALTANDO and l.dados_faltando != [torre.ULTIMA_EXECUCAO]:
            falta = "falta no cadastro: " + "; ".join(torre.campo_legivel(c) for c in l.dados_faltando)
        elif l.status == torre.DADO_FALTANDO:
            falta = "falta a data da última execução"
        else:
            falta = (torre.pendente(l) or "—") + (f" · vence {_br(l.vence)}" if l.status == agenda.VENCE_LOGO and l.vence else "")
        c1.markdown(f"**{l.ativo}** · {_curto(l.titulo, 85)}  \n"
                    f"<small>{falta[:1].upper()}{falta[1:]} · {torre.dispositivo(l.norma, l.artigo)} · "
                    f"{l.responsavel or 'sem responsável'}</small>", unsafe_allow_html=True)
        with c2:
            if l.status == torre.DADO_FALTANDO and l.dados_faltando != [torre.ULTIMA_EXECUCAO]:
                st.button("Completar cadastro", key=f"cx_cad_{grupo}_{l.ativo}_{l.codigo}", icon=":material/edit:",
                          on_click=_ir, args=(ABA_ATIVOS,), kwargs={"estado": {"ativo_sel": _rotulo_ativo(l)}})
            else:
                _botao_entrega(l, f"cx_{grupo}", "Registrar entrega" if l.status != torre.DADO_FALTANDO
                               else "Última entrega")
        c3.button("Ver ativo", key=f"cx_ver_{grupo}_{l.ativo}_{l.codigo}", type="tertiary",
                  on_click=_ir, args=(ABA_ATIVOS,), kwargs={"estado": {"ativo_sel": _rotulo_ativo(l)}})

    nada = True
    if pendentes:
        nada = False
        with st.container(border=True, key="grupo_mudancas"):
            st.markdown(f":primary-badge[{len(pendentes)} {'mudança de norma' if len(pendentes) == 1 else 'mudanças de norma'} "
                        "aguardando decisão] nada muda sem aprovação")
            for m in pendentes:
                d1, d2 = st.columns([7.6, 1.2], vertical_alignment="center")
                difs = "; ".join(f"{CAMPO.get(c, c).lower()} {_val(c, a)} → **{_val(c, b)}**"
                                 for c, (a, b) in list(m.diferencas.items())[:2])
                d1.markdown(f"**{m.codigo}** · {_curto(m.titulo, 70)} ({', '.join(x for x in m.ativos if x in codigos_meus)})"
                            f"  \n<small>{m.ato or m.fonte}: {difs}</small>", unsafe_allow_html=True)
                d2.button("Decidir →", key=f"cx_mud_{m.versao_id}", type="primary", on_click=_ir,
                          args=(ABA_REG, SUB_MUDANCAS))
    for s, titulo_grupo in [(agenda.ATRASADA, "atrasadas"), (torre.DADO_FALTANDO, "com dado faltando"),
                            (agenda.VENCE_LOGO, "vencendo em breve")]:
        do_grupo = sorted([l for l in linhas if l.status == s], key=lambda l: (l.vence or "9999", l.ativo))
        if not do_grupo:
            continue
        nada = False
        with st.container(border=True, key=f"grupo_{s}"):
            st.markdown(_tag(s, f"{len(do_grupo)} {titulo_grupo}"))
            for l in do_grupo[:MAX_ITENS]:
                _item(l, s)
            if len(do_grupo) > MAX_ITENS:
                st.button(f"Ver as outras {len(do_grupo) - MAX_ITENS} na lista →", key=f"cx_mais_{s}", type="tertiary",
                          on_click=_ir, args=(ABA_ENTREGAS,), kwargs={"estado": _filtro_entregas([s])})
    if nada:
        st.success("Nada atrasado, nada faltando e nada vencendo nos próximos dias.", icon=":material/done_all:")

    para = None if diretoria else visao
    texto_boletim = torre.boletim(conn, empresa["id"], hoje, desde, responsavel=para)
    with st.expander(f"Boletim da semana — {para or 'Diretoria'}", icon=":material/mail:"):
        st.caption("O que cada gestor receberia toda segunda, só com os ativos dele. "
                   "Aqui o boletim é só gerado; nada é enviado.")
        sufixo = f"{hoje:%Y-%m-%d}_{(para or 'diretoria').replace(' ', '_')}"
        d1, d2, d3 = st.columns(3)
        d1.download_button("Baixar boletim (PDF)", partial(_pdf, texto_boletim, f"Boletim · {para or 'Diretoria'}"),
                           file_name=f"boletim_{sufixo}.pdf", mime="application/pdf", type="primary")
        d2.download_button("Boletim em texto (.md)", texto_boletim, file_name=f"boletim_{sufixo}.md",
                           mime="text/markdown")
        d3.download_button("Vencimentos no calendário (.ics)",
                           torre.calendario(conn, empresa["id"], hoje, desde, responsavel=para),
                           file_name=f"vencimentos_{sufixo}.ics", mime="text/calendar",
                           help="Importa no Outlook ou Google Agenda: um evento por vencimento")
        st.markdown(texto_boletim.split("\n", 2)[2].replace("\n## ", "\n#### "))   # sem o título grande


# ------------------------------------------------------------------ Ativos

def _escolheu_no_mapa(chave: str, codigos: list[str]):
    """Clicar numa linha do mapa abre a ficha daquele ativo."""
    linhas_sel = st.session_state[chave].selection.rows
    if linhas_sel:
        st.session_state["ativo_sel"] = codigos[linhas_sel[0]]       # já é o rótulo do seletor


def _tabela(ls):
    return pd.DataFrame([{
        "Status": ROTULO.get(l.status, l.status),
        "Obrigação": l.titulo,
        "Norma": l.norma,
        "Dispositivo": torre.artigo_curto(l.norma, l.artigo),
        "Vencimento": date.fromisoformat(l.vence).strftime("%d/%m/%Y") if l.vence else "",
        "Pendente": torre.pendente(l),
        "Evidência": l.evidencia,
        "Mudança aguardando": "sim" if l.mudanca_pendente else "",
    } for l in ls])


def _pior(codigo: str) -> str:
    """Pior status do ativo: atrasada > dado faltando > vencendo > em dia."""
    do_ativo = [l for l in linhas if l.ativo == codigo]
    for s in (agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO):
        if any(l.status == s for l in do_ativo):
            return s
    return agenda.EM_DIA


def _escolheu_no_mapa_geo(chave: str):
    """Clicar num ponto do mapa abre a ficha daquele ativo."""
    sel = st.session_state[chave].selection
    objs = (sel.get("objects") or {}).get("ativos") or []
    if objs:
        st.session_state["ativo_sel"] = objs[0]["rotulo"]


def _mapa_geo():
    """Mapa dos ativos da empresa fictícia (coordenadas fictícias em data/posicoes_demo.json),
    cada ponto com a cor do pior status. Empresa importada do SIGBM: sem coordenadas, sem mapa."""
    import pydeck as pdk

    arq = db.ROOT / "data" / "posicoes_demo.json"
    if setor_saude or not empresa["ficticia"] or not arq.exists():
        return
    pos = json.loads(arq.read_text(encoding="utf-8"))
    pontos = []
    for a in meus:
        if a["codigo"] not in pos:
            continue
        pior = _pior(a["codigo"])
        pontos.append({"codigo": a["codigo"], "nome": a["nome"], "rotulo": _rotulo_ativo(a),
                       "status": ROTULO[pior], "lat": pos[a["codigo"]][0], "lon": pos[a["codigo"]][1],
                       "cor": _rgb(_hex(COR_STATUS[pior])) + [235],
                       "raio": 260 if a["tipo"] == "barragem" else 150})
    if not pontos:
        return
    texto = _rgb(st.get_option(f"theme.{'dark' if _ESCURO else 'light'}.textColor") or "#222222")
    deck = pdk.Deck(
        layers=[
            pdk.Layer("ScatterplotLayer", id="ativos", data=pontos, get_position="[lon, lat]",
                      get_fill_color="cor", get_radius="raio", radius_min_pixels=6, pickable=True, stroked=True,
                      get_line_color=[255, 255, 255], line_width_min_pixels=1.5),
            pdk.Layer("TextLayer", id="codigos", data=pontos, get_position="[lon, lat]", get_text="codigo",
                      get_size=13, get_color=texto, get_pixel_offset=[0, -18], get_alignment_baseline="'bottom'",
                      font_weight=700, billboard=True),
        ],
        # centro da caixa que contém todos os pontos; zoom 10.9 cabe ~11 km de norte a sul em 300 px (deck.gl usa ladrilho de 512 px)
        initial_view_state=pdk.ViewState(latitude=(max(p["lat"] for p in pontos) + min(p["lat"] for p in pontos)) / 2,
                                         longitude=(max(p["lon"] for p in pontos) + min(p["lon"] for p in pontos)) / 2,
                                         zoom=10.9),
        tooltip={"text": "{codigo} · {nome}\n{status}"},
        map_style="dark" if _ESCURO else "light",
    )
    chave = f"mapa_geo_{visao}"
    st.pydeck_chart(deck, height=300, selection_mode="single-object", key=chave,
                    on_select=partial(_escolheu_no_mapa_geo, chave))


def _selo(codigo: str) -> str:
    """Etiqueta do pior status do ativo."""
    do_ativo = [l for l in linhas if l.ativo == codigo]
    for s in (agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO):
        if any(l.status == s for l in do_ativo):
            return _tag(s)
    return _tag(agenda.EM_DIA)


# nomes de tela dos dados do cadastro (o vocabulário das regras descreve os campos para a IA, não para gente)
NOME_DADO = {
    "uf": "UF", "municipio": "Município", "minerio": "Minério", "sigbm_codigo": "Código no SIGBM",
    "altura_m": "Altura (m)", "volume_m3": "Volume do reservatório (m³)", "inserida_pnsb": "Na PNSB",
    "metodo_construtivo": "Método construtivo", "cri": "Categoria de risco (CRI)",
    "dpa": "Dano potencial associado (DPA)", "dpa2": "Pontuação de perda de vidas do DPA",
    "situacao_operacional": "Situação operacional", "nivel_emergencia": "Nível de emergência",
    "trabalhadores_zas": "Trabalhadores na ZAS", "mapa_inundacao_validado": "Mapa de inundação validado",
    "alteamento_continuo": "Alteamento contínuo", "modificacao_estrutural": "Modificação estrutural",
    "lavra": "Lavra", "beneficiamento": "Beneficiamento mineral", "deposito_rejeitos": "Depósito de estéril ou rejeitos",
    "usa_explosivos": "Usa explosivos", "carvao": "Mina de carvão", "dragas": "Dragas flutuantes",
    "trabalhadores": "Trabalhadores", "classe": "Classe do equipamento", "categoria_vaso": "Categoria do vaso (NR-13)",
    "spie": "SPIE certificado", "em_operacao": "Em operação", "subsolo": "Em subsolo",
    "orgao": "Órgão emissor", "validade": "Validade",
    "tem_nsp": "Núcleo de Segurança do Paciente constituído", "exposicao_biologica": "Exposição a agentes biológicos",
    "gera_rss": "Gera resíduos de serviços de saúde", "grupo_rss": "Grupos de resíduos", "unidade_origem": "Unidade de origem",
}
VALOR_DADO = {"etapa_unica": "etapa única", "linha_de_centro": "linha de centro", "medio": "médio",
              "em_descaracterizacao": "em descaracterização", "ceu_aberto": "céu aberto",
              "subterranea": "subterrânea", "vaso_pressao": "vaso de pressão"}


def _valor_cadastro(v) -> str:
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, float):
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",00")
    if isinstance(v, str):
        return VALOR_DADO.get(v, _br(v).replace("_", " "))
    return str(v)


with aba_ativos:
    st.caption("Clique num ativo para abrir a ficha. Vencendo = vence em até 30 dias (5 para quinzenal e mensal).")
    if setor_saude:
        st.info("Nesta visão não há mapa: os ativos são unidades assistenciais e áreas operacionais, não pontos de uma rede geográfica. "
                "A tabela prioriza a ação, a unidade responsável e a evidência.", icon=":material/format_list_bulleted:")
    _mapa_geo()
    codigos_mapa = [a["codigo"] for a in meus]
    mapa = pd.DataFrame([{
        "Ativo": f"{a['codigo']} · {a['nome']}",
        "Responsável": a["responsavel"] or "—",
        **{COLUNA[s]: sum(1 for l in linhas if l.ativo == a["codigo"] and l.status == s)
           for s in COLUNA},
    } for a in meus])
    # texto com largura fixa: a tabela inteira cabe num projetor de 1280 px sem rolar de lado
    chave_mapa = f"mapa_{empresa['id']}_{visao}"
    st.dataframe(_pintar(mapa), hide_index=True, width="stretch", selection_mode="single-row", key=chave_mapa,
                 on_select=partial(_escolheu_no_mapa, chave_mapa, [_rotulo_ativo(a) for a in meus]), column_config={
                     "Ativo": st.column_config.TextColumn(width="medium"),
                     "Responsável": st.column_config.TextColumn(width="medium"), **_DICA_STATUS})

    with st.expander("Por norma: quem cobra o quê"):
        normas = sorted({l.norma for l in linhas if l.norma})

        def _orgao(norma: str) -> str:
            return ("ANM" if "ANM" in norma else "MTE" if norma.startswith("NR-")
                    else "Anvisa" if "Anvisa" in norma
                    else "Órgão ambiental" if norma.startswith(("LO ", "LC 140")) else "—")

        st.dataframe(_pintar(pd.DataFrame([{
            "Órgão": _orgao(n),
            "Norma": n,
            "Obrigações": len({l.codigo for l in linhas if l.norma == n}),
            "Ativos": ", ".join(sorted({l.ativo for l in linhas if l.norma == n})),
            **{COLUNA[s]: sum(1 for l in linhas if l.norma == n and l.status == s)
               for s in COLUNA},
        } for n in normas])), hide_index=True, width="stretch", column_config=_DICA_STATUS)
        if hoje < TROCA_NORMA and not setor_saude:
            st.caption(f"A Res. ANM 220/2025 ainda não aparece: entra em {TROCA_NORMA:%d/%m/%Y} no lugar da "
                       "Res. 95/2022. O que muda está em Regulatório → Transição e linha do tempo.")

    if codigos_mapa:
        # abre no ativo com mais problema; um atalho (caixa de entrada, mapa) troca o escolhido
        pior = min(codigos_mapa, key=lambda c: (
            -sum(1 for l in linhas if l.ativo == c and l.status == agenda.ATRASADA),
            -sum(1 for l in linhas if l.ativo == c and l.status in (torre.DADO_FALTANDO, agenda.VENCE_LOGO))))
        # o valor do seletor é o rótulo legível ("B3 · Barragem Córrego Fundo"): os atalhos escrevem nele
        rotulos_mapa = {_rotulo_ativo(a): a["codigo"] for a in meus}
        if st.session_state.get("ativo_sel") not in rotulos_mapa:
            st.session_state["ativo_sel"] = next(r for r, c in rotulos_mapa.items() if c == pior)
        cod = rotulos_mapa[st.selectbox("Ativo", list(rotulos_mapa), key="ativo_sel")]
        a = next(x for x in meus if x["codigo"] == cod)
        do_ativo = [l for l in linhas if l.ativo == cod]
        with st.container(border=True):
            st.markdown(f"#### {a['codigo']} · {a['nome']}")
            n_st = {s: sum(1 for l in do_ativo if l.status == s) for s in COLUNA}
            st.markdown(" ".join(_tag(s, f"{n} {ROTULO[s].lower()}") for s, n in n_st.items() if n))
            st.caption(f"{TIPO.get(a['tipo'], a['tipo'])} · responsável: {a['responsavel'] or 'ninguém'} · "
                       f"{len(do_ativo)} obrigações")
            st.button("Ver este ativo em Entregas", icon=":material/list:", key="ficha_entregas", on_click=_ir,
                      args=(ABA_ENTREGAS,),
                      kwargs={"estado": _filtro_entregas([], [cod])},
                      help="Todas as obrigações deste ativo na lista, para registrar, atribuir ou comentar")
            ruins = [l for l in do_ativo if l.status in (agenda.ATRASADA, torre.DADO_FALTANDO, agenda.VENCE_LOGO)]
            t_pend, t_obr, t_ev, t_cad = st.tabs([
                f"Pendências ({len(ruins)})", f"Obrigações ({len(do_ativo)})", "O que comprova", "Cadastro"])
            with t_pend:
                if not ruins:
                    st.success("Nada atrasado, faltando ou vencendo neste ativo.")
                for l in sorted(ruins, key=lambda l: torre.ORDEM.get(l.status, 9)):
                    v = db.versao(conn, l.codigo) or {}
                    p1, p2 = st.columns([5, 1.4], vertical_alignment="top")
                    with p1:
                        st.markdown(f"{_tag(l.status)} **{l.titulo}** ({torre.dispositivo(l.norma, l.artigo)})")
                        herdada = bool(l.nota and l.ultima and _br(l.ultima) in l.nota)   # a nota já diz a data
                        if l.faltando and not torre.so_o_vencimento(l):
                            st.markdown("Períodos sem evidência: " + ", ".join(map(agenda.rotulo_humano, l.faltando)))
                        elif l.faltando and not herdada:
                            texto = torre.pendente(l)
                            st.markdown(texto[:1].upper() + texto[1:] + ".")
                        if l.status == agenda.VENCE_LOGO and l.vence:
                            st.markdown(f"Vence em {_br(l.vence)}.")
                        if l.nota and not l.dados_faltando:
                            st.markdown(l.nota[:1].upper() + l.nota[1:] + ".")
                        if l.dados_faltando == [torre.ULTIMA_EXECUCAO]:
                            st.markdown("Falta a **data da última execução**: sem ela não dá para calcular o próximo "
                                        "vencimento. Registre a última entrega ao lado.")
                        elif l.dados_faltando:
                            campos = "; ".join(f"**{torre.campo_legivel(c)}** (`{c}`)" for c in l.dados_faltando)
                            st.markdown(f"Falta no cadastro do ativo: {campos}. Sem esse dado não dá para dizer se "
                                        "a obrigação vale: preencha na aba Cadastro, aqui na ficha.")
                        if v.get("trecho"):
                            st.caption(f"“{v['trecho']}”")
                    if not l.dados_faltando or l.dados_faltando == [torre.ULTIMA_EXECUCAO]:
                        with p2:
                            _botao_entrega(l, "ficha")
            with t_obr:
                com_data = [l for l in do_ativo if l.status != agenda.GATILHO]
                gatilho = [l for l in do_ativo if l.status == agenda.GATILHO]
                if com_data:
                    st.dataframe(_pintar(_tabela(com_data)), hide_index=True, width="stretch")
                if gatilho:
                    st.markdown(f"**{len(gatilho)} obrigações por gatilho** (incidente, emergência, modificação…)")
                    st.dataframe(_tabela(gatilho)[["Obrigação", "Norma", "Dispositivo", "Evidência"]],
                                 hide_index=True, width="stretch")
            with t_ev:
                recentes = db.evidencias_do_ativo(conn, a["id"], limite=12)
                if not recentes:
                    st.info("Nenhuma evidência registrada ainda para este ativo.")
                titulos = {l.codigo: l.titulo for l in do_ativo}
                linhas_ev = []
                for e in recentes:
                    x = e["extraido"] or {}
                    lido = {"regra": "lido por regra", "ia": "lido por IA, conferido"}.get(
                        x.get("metodo"), "baixa manual" if x.get("baixa_manual") else "histórico da demo")
                    aviso = "".join(f"  \n  :material/schedule: {av}" for av in x.get("avisos") or [])
                    linhas_ev.append(
                        f"- **{agenda.rotulo_humano(e['periodo'])}** · {e['codigo']} "
                        f"{_curto(titulos.get(e['codigo'], ''))}  \n"
                        f"  <small>{(e['arquivo'] or '—').split('/')[-1]} · {lido}</small>{aviso}")
                if linhas_ev:
                    st.markdown("\n".join(linhas_ev), unsafe_allow_html=True)
            with t_cad:
                if decide_areas:
                    areas_cad = sorted(set(usuarios.areas(conn)) | ({a["responsavel"]} if a["responsavel"] else set()))
                    r1, r2 = st.columns([3, 1], vertical_alignment="bottom")
                    nova_area = r1.selectbox(
                        "Área responsável pelo ativo", areas_cad, key=f"area_{a['id']}", accept_new_options=True,
                        index=areas_cad.index(a["responsavel"]) if a["responsavel"] else None,
                        placeholder="escolha ou digite uma área nova",
                        help="O gestor dessa área passa a ver o ativo inteiro. Obrigação com responsável "
                             "próprio continua com ele.")
                    if r2.button("Salvar área", key=f"salva_area_{a['id']}", disabled=nova_area == a["responsavel"]):
                        db.definir_responsavel(conn, a["id"], nova_area, por=assinante)
                        st.toast(f"{a['codigo']} agora com {nova_area or 'ninguém'}")
                        st.rerun()
                    if a["responsavel"] and not any(u["area"] == a["responsavel"] and u["ativa"]
                                                    for u in usuarios.listar(conn)):
                        st.caption(f"Ninguém entra na torre como {a['responsavel']} ainda: peça à TI uma conta "
                                   "de gestor com essa área.")
                    st.divider()
                faltam_cad = sorted({c for l in do_ativo for c in l.dados_faltando if c != torre.ULTIMA_EXECUCAO})
                if faltam_cad:
                    st.markdown(f"**Falta no cadastro ({len(faltam_cad)})**: decide se algumas obrigações valem.")
                    _editor_cadastro(faltam_cad, [a], f"ficha_{cod}")
                    st.divider()
                st.dataframe(pd.DataFrame([{
                    "Dado": NOME_DADO.get(k, k.replace("_", " ").capitalize()),
                    "Valor": _valor_cadastro(v),
                } for k, v in a["atributos"].items() if k != "alertas_sigbm"]), hide_index=True, width="stretch",
                    column_config={"Dado": st.column_config.TextColumn(width="medium")})
                for al in a["atributos"].get("alertas_sigbm") or []:
                    st.warning(f"SIGBM: {al}", icon=":material/warning:")

# o diálogo de entrega fica aberto entre reruns enquanto houver alvo (caixa de entrada ou ficha)
if "entrega_de" in st.session_state:
    alvo_ent = next((l for l in minhas if (l.ativo, l.codigo) == tuple(st.session_state["entrega_de"])), None)
    if alvo_ent is None:
        _fechar_entrega()
    else:
        _dialogo_entrega(alvo_ent)


# ------------------------------------------------------------------ Entregas

def _feito():
    """Depois de agir, a seleção da tabela zera: a linha pode ter sumido ou mudado de lugar."""
    st.session_state["acoes"] = st.session_state.get("acoes", 0) + 1
    st.rerun()


with aba_entregas:
    st.caption("Selecione uma ou várias linhas para registrar, atribuir ou comentar. Tudo fica no histórico.")
    # filtros com chave: os números da caixa de entrada e a ficha do ativo chegam aqui já filtrados.
    # Trocar de gestor ou de empresa muda as opções: o que não existe mais sai do filtro antes de desenhar.
    op_ativo = [a["codigo"] for a in meus]
    op_norma = sorted({l.norma for l in minhas if l.norma})
    op_resp = sorted({l.responsavel or "— sem responsável" for l in minhas})
    st.session_state.setdefault("f_status", STATUS_PADRAO)
    for k, ops in (("f_status", list(ROTULO)), ("f_ativo", op_ativo), ("f_norma", op_norma), ("f_resp", op_resp)):
        st.session_state[k] = [x for x in st.session_state.get(k, []) if x in ops]
    f1, f2, f3, f4 = st.columns([1.3, 1.3, 1.2, 1.2])
    st_fil = f1.multiselect("Status", list(ROTULO), format_func=ROTULO.get, key="f_status", placeholder="todos")
    at_fil = f2.multiselect("Ativo", op_ativo, key="f_ativo", placeholder="todos",
                            format_func=lambda c: f"{c} · {next(a['nome'] for a in meus if a['codigo'] == c)}")
    no_fil = f3.multiselect("Norma", op_norma, key="f_norma", placeholder="todas")
    re_fil = f4.multiselect("Responsável", op_resp, key="f_resp", placeholder="todos")
    g1, g2 = st.columns([2, 1])
    busca = g1.text_input("Buscar na obrigação", placeholder="ex.: FIR, RPSB, simulado, NR-13…", key="f_busca")
    janela = g2.selectbox("Vence em", [None, 7, 30, 90, 365], key="f_janela",
                          format_func=lambda d: "qualquer data" if d is None else f"até {d} dias")
    lim = (hoje + timedelta(days=janela)).isoformat() if janela else None
    filtradas = [l for l in minhas
                 if (not st_fil or l.status in st_fil) and (not at_fil or l.ativo in at_fil)
                 and (not no_fil or l.norma in no_fil)
                 and (not re_fil or (l.responsavel or "— sem responsável") in re_fil)
                 and (not busca or busca.lower() in f"{l.titulo} {l.codigo} {l.norma} {l.evidencia}".lower())
                 and (not lim or (l.vence and l.vence <= lim))]
    filtradas.sort(key=lambda l: (torre.ORDEM.get(l.status, 9), l.vence or "9999", l.ativo))
    nome_arq = f"obrigacoes_{(visao if not diretoria else 'diretoria').replace(' ', '_')}_{hoje:%Y-%m-%d}"
    e1, e2, e3 = st.columns([1, 1, 2])
    e1.download_button(f"Excel ({len(filtradas)} linhas)",
                       partial(operacao.planilha, filtradas, f"Mitra · {empresa['nome']}"), icon=":material/download:",
                       file_name=f"{nome_arq}.xlsx", disabled=not filtradas,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    e2.download_button("Agenda (.ics)",
                       partial(torre.calendario, conn, empresa["id"], hoje, desde, None if diretoria else visao),
                       icon=":material/calendar_month:",
                       file_name=f"vencimentos_{nome_arq}.ics", mime="text/calendar",
                       help="Os vencimentos de quem está olhando, para o Outlook ou Google Agenda")
    e3.caption(f"{len(filtradas)} de {len(minhas)} obrigações. Selecione uma linha (ou várias) para agir.")
    sel = st.dataframe(_pintar(pd.DataFrame([{
        "Status": ROTULO.get(l.status, l.status), "Ativo": l.ativo, "Obrigação": _curto(l.titulo, 90),
        "Vence": _br(l.vence) if l.vence else "", "Responsável": (l.responsavel or "—") + (" ✎" if l.responsavel_proprio else ""),
        "Última": agenda.rotulo_humano(l.ultima) if l.ultima else "", "Pendente": torre.pendente(l),
    } for l in filtradas])), hide_index=True, width="stretch", on_select="rerun", selection_mode="multi-row",
        key=f"sel_entregas_{empresa['id']}_{st.session_state.get('acoes', 0)}", height=min(36 * len(filtradas) + 40, 420),
        column_config={"Status": st.column_config.TextColumn(width=120)})     # "Vence em breve" sem corte
    escolhidas = [filtradas[i] for i in sel.selection.rows if i < len(filtradas)]

    if len(escolhidas) > 1:
        with st.container(border=True):
            st.markdown(f"**{len(escolhidas)} obrigações selecionadas**")
            m1, m2 = st.columns(2)
            novo_resp = m1.text_input("Passar todas para", placeholder="nome ou área", key="resp_lote")
            if m1.button("Atribuir responsável", disabled=not novo_resp.strip()):
                for l in escolhidas:
                    db.atribuir(conn, l.ativo_id, l.codigo, novo_resp, por=assinante)
                st.toast(f"{len(escolhidas)} obrigações agora com {novo_resp.strip()}")
                _feito()
            dia_lote = m2.date_input("Entregues em", value=hoje, format="DD/MM/YYYY", key="dia_lote")
            if m2.button("Marcar todas como entregues", help="Cada uma no período que está pendente"):
                for l in escolhidas:
                    if l.agenda and l.agenda != "evento":
                        db.entregar(conn, l.ativo_id, l.codigo, operacao.periodo_para_entrega(l, dia_lote),
                                    dia=dia_lote.isoformat(), por=assinante)
                st.toast(f"{len(escolhidas)} entregas registradas")
                _feito()
    elif escolhidas:
        l = escolhidas[0]
        v = db.versao(conn, l.codigo) or {}
        with st.container(border=True):
            st.markdown(f"#### {l.ativo} · {l.titulo}")
            st.markdown(_tag(l.status))
            st.caption(f"{torre.dispositivo(l.norma, l.artigo)} · {l.periodicidade or agenda.descrever(l.agenda)} · "
                       f"evidência: {l.evidencia or '—'}")
            if l.nota:
                st.markdown(l.nota[:1].upper() + l.nota[1:] + ".")
            if v.get("trecho"):
                st.caption(f"“{_curto(v['trecho'], 400)}”")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("**Registrar entrega**")
                _form_entrega(l, f"{l.ativo}_{l.codigo}", _feito)
            with a2:
                st.markdown("**Responsável**")
                st.caption(f"Hoje: {l.responsavel or 'ninguém'}" + (" (só desta obrigação)" if l.responsavel_proprio
                                                                     else " (o do ativo)" if l.responsavel else ""))
                quem = st.text_input("Passar para", key=f"quem_{l.ativo}_{l.codigo}",
                                     placeholder="nome, área ou consultoria")
                b1, b2 = st.columns(2)
                if b1.button("Atribuir", key=f"atr_{l.ativo}_{l.codigo}", disabled=not quem.strip()):
                    db.atribuir(conn, l.ativo_id, l.codigo, quem, por=assinante)
                    _feito()
                if l.responsavel_proprio and b2.button("Voltar ao do ativo", key=f"vol_{l.ativo}_{l.codigo}"):
                    db.atribuir(conn, l.ativo_id, l.codigo, "", por=assinante)
                    _feito()
            with a3:
                st.markdown("**Comentário**")
                txt = st.text_area("Comentário", key=f"com_{l.ativo}_{l.codigo}", label_visibility="collapsed",
                                   placeholder="ex.: laudo com a consultoria, chega dia 20", height=100)
                if st.button("Comentar", key=f"cbt_{l.ativo}_{l.codigo}", disabled=not txt.strip()):
                    db.registrar_evento(conn, l.ativo_id, l.codigo, "comentario", txt.strip(), por=assinante)
                    _feito()
            hist = db.eventos(conn, l.ativo_id, l.codigo, limite=20)
            evs = [e for e in db.evidencias_do_ativo(conn, l.ativo_id, limite=200) if e["codigo"] == l.codigo]
            st.markdown("**Histórico**")
            icone = {"entrega": ":material/check:", "responsavel": ":material/person:",
                     "comentario": ":material/chat_bubble:", "cadastro": ":material/edit:"}
            itens = [f"- {icone.get(e['tipo'], '•')} {torre.em_brasilia(e['em']) if len(e['em']) > 10 else _br(e['em'])}"
                     f" · {e['por'] or '—'}: {e['texto']}" for e in hist]
            manuais = {e["periodo"] for e in evs if (e["extraido"] or {}).get("baixa_manual")}
            itens += [f"- :material/attach_file: {agenda.rotulo_humano(e['periodo'])} · {(e['arquivo'] or 'sem arquivo').split('/')[-1]}"
                      for e in evs[:8] if e["periodo"] not in manuais]
            st.markdown("\n".join(itens) if itens else "Nada registrado ainda.")
            if manuais:
                desf = st.selectbox("Desfazer uma entrega manual", sorted(manuais, reverse=True),
                                    format_func=agenda.rotulo_humano, key=f"desf_{l.ativo}_{l.codigo}")
                if st.button("Desfazer", key=f"dbt_{l.ativo}_{l.codigo}"):
                    db.desfazer_entrega(conn, l.ativo_id, l.codigo, desf, por=assinante)
                    _feito()

    st.markdown("##### Calendário do mês")
    k1, k2 = st.columns([1, 3])
    meses = [date(hoje.year + (hoje.month - 1 + i) // 12, (hoje.month - 1 + i) % 12 + 1, 1) for i in range(-1, 12)]
    mes = k1.selectbox("Mês", meses, index=1, format_func=lambda d: f"{d:%m/%Y}")
    venc = operacao.vencimentos_no_mes(conn, [l for l in minhas if not at_fil or l.ativo in at_fil], mes.year, mes.month)
    k2.caption(f"{len(venc)} vencimentos em {mes:%m/%Y} · vermelho: venceu sem entrega · laranja: a vencer · "
               "verde: entregue. O filtro de ativo acima vale aqui.")
    por_dia_v: dict[int, list] = {}
    for x in venc:
        por_dia_v.setdefault(date.fromisoformat(x.dia).day, []).append(x)

    import calendar as _cal
    semanas = _cal.Calendar(firstweekday=0).monthdayscalendar(mes.year, mes.month)
    DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

    def _situacao(x) -> str:
        return "ok" if x.entregue else "atraso" if x.dia < hoje.isoformat() else "vence"

    def _celula(d: int) -> str:
        if not d:
            return ""
        n = len(por_dia_v.get(d, []))
        marca = " · hoje" if date(mes.year, mes.month, d) == hoje else ""
        return f"{d}{marca}" + (f"  ·  {n} {'venc.' if n > 1 else 'venc.'}" if n else "")

    def _cores_do_mes(df):
        """Cada dia com a cor do pior vencimento: vermelho venceu sem entrega, laranja a vencer, verde entregue."""
        estilos = pd.DataFrame("", index=df.index, columns=df.columns)
        for i, sem in enumerate(semanas):
            for j, d in enumerate(sem):
                xs = por_dia_v.get(d, []) if d else []
                sits = {_situacao(x) for x in xs}
                cor = "red" if "atraso" in sits else "orange" if "vence" in sits else "green" if xs else None
                css = [f"background-color: {_rgba(_hex(cor), .16)}; color: {_hex(cor)}; font-weight: 600"] if cor else []
                if d and date(mes.year, mes.month, d) == hoje:
                    css.append(f"color: {_hex('primary')}; font-weight: 700")
                estilos.iat[i, j] = "; ".join(css)
        return estilos

    def _escolheu_dia(chave: str):
        celulas = st.session_state[chave].selection.cells
        if celulas:
            linha_c, coluna = celulas[0]
            d = semanas[linha_c][DIAS_SEMANA.index(coluna)]
            st.session_state["cal_dia"] = date(mes.year, mes.month, d).isoformat() if d else None

    grade = pd.DataFrame([[_celula(d) for d in sem] for sem in semanas], columns=DIAS_SEMANA)
    chave_cal = f"cal_{mes:%Y%m}_{empresa['id']}_{visao}"
    st.dataframe(grade.style.apply(_cores_do_mes, axis=None), hide_index=True, width="stretch", row_height=46,
                 selection_mode="single-cell", on_select=partial(_escolheu_dia, chave_cal), key=chave_cal,
                 height=46 * len(semanas) + 40)
    dia_sel = st.session_state.get("cal_dia")
    if dia_sel and dia_sel[:7] == f"{mes:%Y-%m}":
        xs = por_dia_v.get(int(dia_sel[8:]), [])
        with st.container(border=True):
            st.markdown(f"**{_br(dia_sel)}** · {len(xs)} {'vencimento' if len(xs) == 1 else 'vencimentos'}")
            for x in xs:
                c1, c2 = st.columns([6, 1.6], vertical_alignment="center")
                tag = {"ok": ":green-badge[entregue]", "atraso": ":red-badge[venceu sem entrega]",
                       "vence": ":orange-badge[a vencer]"}[_situacao(x)]
                c1.markdown(f"{tag} **{x.linha.ativo}** · {_curto(x.linha.titulo, 80)}  \n"
                            f"<small>{agenda.rotulo_humano(x.periodo)} · {x.linha.responsavel or 'sem responsável'}</small>",
                            unsafe_allow_html=True)
                if not x.entregue:
                    with c2:
                        _botao_entrega(x.linha, f"cal_{x.periodo}")
            if not xs:
                st.caption("Nenhum vencimento neste dia.")
    else:
        st.caption("Clique num dia para ver os vencimentos e registrar a entrega.")
    if venc:
        with st.expander(f"Lista dos {len(venc)} vencimentos de {mes:%m/%Y}"):
            st.dataframe(pd.DataFrame([{
                "Dia": _br(x.dia), "Ativo": x.linha.ativo, "Obrigação": x.linha.titulo,
                "Período": agenda.rotulo_humano(x.periodo), "Situação": "entregue" if x.entregue else
                ("venceu sem entrega" if x.dia < hoje.isoformat() else "a vencer"), "Responsável": x.linha.responsavel,
            } for x in venc]), hide_index=True, width="stretch")

    st.markdown("##### Boletim por responsável")
    # cada gestor só vê o próprio boletim; a Diretoria escolhe de quem
    quem_b = st.selectbox("Prévia do boletim de", ["Diretoria"] + responsaveis if diretoria else [visao],
                          key=f"boletim_de_{visao}")
    md_b = torre.boletim(conn, empresa["id"], hoje, desde, responsavel=None if quem_b == "Diretoria" else quem_b)
    with st.container(border=True, height=360):
        st.markdown(md_b.split("\n", 2)[2].replace("\n## ", "\n#### "))
    st.download_button("Baixar este boletim (PDF)", partial(_pdf, md_b, f"Boletim · {quem_b}"),
                       file_name=f"boletim_{quem_b.replace(' ', '_')}_{hoje:%Y-%m-%d}.pdf", mime="application/pdf")

# ------------------------------------------------------------------ Transição

HORIZONTE = date(2030, 3, 31)       # cobre o prazo da ZAS (26/12/2029)


def _linha_do_tempo(futuras) -> str | None:
    """Gantt da vigência: uma barra por norma que vale para cada ativo, losangos nas datas em que
    obrigações passam a valer. Devolve o dia clicado (AAAA-MM-DD), se houver."""
    import altair as alt

    norma_de = {r["codigo"]: r["norma"] for r in conn.execute("SELECT codigo, norma FROM obrigacao")}
    faixas: dict[tuple, list[str]] = {}
    for a in meus:
        for o in db.obrigacoes_do_ativo(conn, a["id"]):
            v = o.vigente
            if not v:
                continue
            k = (a["codigo"], norma_de.get(o.codigo) or "—")
            ini_v, fim_v = v["vigencia_desde"] or "1900-01-01", v["vigencia_ate"] or "2999-12-31"
            if k in faixas:
                faixas[k] = [min(faixas[k][0], ini_v), max(faixas[k][1], fim_v)]
            else:
                faixas[k] = [ini_v, fim_v]
    def _curta(n: str) -> str:
        return n.replace("Res. ANM ", "ANM ").replace(" (fictícia)", "")

    def _rotulo_linha(at: str, n: str) -> str:
        return f"{at} · {_curta(n)}"

    barras = pd.DataFrame([{
        "Linha": _rotulo_linha(at, n), "Ativo": at, "Norma": _curta(n), "início": max(ini_v, hoje.isoformat()), "fim": min(fim_v, HORIZONTE.isoformat()),
        "Vale": f"{_br(ini_v) if ini_v > '1900-01-01' else 'antes da demo'} até "
                f"{_br(fim_v) if fim_v < '2999-12-31' else 'sem data de fim'}",
    } for (at, n), (ini_v, fim_v) in faixas.items() if ini_v <= HORIZONTE.isoformat() and fim_v >= hoje.isoformat()])
    if barras.empty:
        return None
    agrup: dict[tuple, list] = {}
    for f in futuras:
        agrup.setdefault((f.ativo, f.norma or "—", f.dia), []).append(f)
    pontos = pd.DataFrame([{
        "Linha": _rotulo_linha(at, n), "Ativo": at, "Norma": n, "dia": dia, "Data": _br(dia), "Obrigações": len(fs),
        "Quais": "; ".join(_curto(f.titulo, 50) for f in fs[:3]) + (f" e mais {len(fs) - 3}" if len(fs) > 3 else ""),
        "proposta": any(f.proposta for f in fs),
    } for (at, n, dia), fs in agrup.items() if dia <= HORIZONTE.isoformat()])
    normas = sorted(barras["Norma"].unique(), key=lambda n: ("ANM" not in n, n))
    paleta = [_hex("gray"), _hex("primary"), _hex("blue"), _hex("green"), _hex("orange"), _hex("red")]
    pos_ativo = {a["codigo"]: i for i, a in enumerate(meus)}
    # uma linha por ativo e norma, na ordem dos ativos; a ANM primeiro dentro de cada ativo
    ordem = sorted(set(barras["Linha"]), key=lambda r: (pos_ativo.get(r.split(" · ")[0], 99),
                                                       "ANM" not in r, r))
    eixo_x = alt.X("início:T", title=None, scale=alt.Scale(domain=[hoje.isoformat(), HORIZONTE.isoformat()]),
                   axis=alt.Axis(format="%m/%Y", labelAngle=0, grid=True, gridOpacity=.25))
    eixo_y = alt.Y("Linha:N", sort=ordem, title=None, axis=alt.Axis(labelLimit=220, ticks=False, domain=False,
                                                                   labelOverlap=False, labelPadding=6))
    camada_barras = alt.Chart(barras).mark_bar(cornerRadius=3, opacity=.85, height=10).encode(
        x=eixo_x, x2="fim:T", y=eixo_y,
        color=alt.Color("Norma:N", sort=normas, scale=alt.Scale(domain=normas, range=paleta[:len(normas)]),
                        legend=alt.Legend(orient="top", title=None, labelLimit=160, columnPadding=14)),
        tooltip=["Ativo", "Norma", "Vale"])
    marcos = pd.DataFrame([{"dia": hoje.isoformat(), "rótulo": "hoje"}]
                         + ([] if setor_saude else [{"dia": TROCA_NORMA.isoformat(), "rótulo": "Res. 220 entra"}]))
    camada_marcos = alt.Chart(marcos).mark_rule(strokeDash=[4, 3], color=_hex("gray")).encode(x="dia:T")
    camada_textos = alt.Chart(marcos).mark_text(align="left", baseline="bottom", dx=4, fontSize=11,
                                                color=_hex("gray")).encode(x="dia:T", y=alt.value(-4), text="rótulo")
    camadas = [camada_barras, camada_marcos, camada_textos]
    if not pontos.empty:
        clique = alt.selection_point(name="dia_tl", fields=["dia"], on="click")
        camada_pontos = alt.Chart(pontos).mark_point(shape="diamond", filled=True, size=150, stroke="white",
                                                     strokeWidth=1).encode(
            x="dia:T", y=alt.Y("Linha:N", sort=ordem),
            color=alt.condition(alt.datum.proposta, alt.value(_hex("orange")),
                                alt.value(st.get_option(f"theme.{'dark' if _ESCURO else 'light'}.textColor"))),
            tooltip=["Ativo", "Norma", "Data", "Obrigações", "Quais"]).add_params(clique)
        camadas.append(camada_pontos)
    # no Streamlit a altura é a do gráfico inteiro (eixo e legenda inclusos), por isso a folga de 90 px
    grafico = alt.layer(*camadas).resolve_scale(color="independent").properties(
        height=26 * len(ordem) + 90, padding={"top": 18, "left": 4, "right": 4, "bottom": 4})
    if pontos.empty:
        st.altair_chart(grafico, width="stretch")
        return None
    ev = st.altair_chart(grafico, width="stretch", on_select="rerun", key=f"linha_tempo_{visao}")
    escolhido = ((ev.selection or {}).get("dia_tl") or [{}])[0].get("dia")
    if isinstance(escolhido, (int, float)):            # o Vega devolve data como milissegundos
        from datetime import datetime, timezone
        escolhido = datetime.fromtimestamp(escolhido / 1000, tz=timezone.utc).date().isoformat()
    return escolhido


with aba_transicao:
    faltam = (TROCA_NORMA - hoje).days
    c1, c2 = st.columns([1, 3])
    c1.metric("Marcos de vigência" if setor_saude else "Dias até a Res. ANM 220/2025", "—" if setor_saude else max(faltam, 0))
    c2.markdown("Acompanhe quando obrigações e versões passam a valer por unidade, sem supor uma transição normativa."
                if setor_saude else f"Em **{TROCA_NORMA:%d/%m/%Y}** a Res. ANM 95/2022 deixa de valer e a Res. ANM 220/2025 entra. "
                "Para cada barragem: o que sai, o que entra e o que já precisa ser preparado.")
    trocas = ([] if setor_saude else [t for t in torre.transicao(conn, empresa["id"], TROCA_NORMA) if t.ativo in codigos_meus])
    if not trocas:
        st.info("Nenhum dos seus ativos muda de obrigação na troca de norma.")
    else:
        para_t = None if diretoria else visao
        plano_md = torre.plano_transicao(conn, empresa["id"], TROCA_NORMA, hoje, responsavel=para_t)
        nome_plano = f"plano_transicao_{(para_t or 'diretoria').replace(' ', '_')}"
        b1, b2, _ = st.columns(3)
        b1.download_button("Baixar plano de transição (PDF)",
                           partial(_pdf, plano_md, f"Plano de transição · {para_t or 'Diretoria'}"), icon=":material/download:",
                           file_name=f"{nome_plano}.pdf", mime="application/pdf")
        b2.download_button("Plano em texto (.md)", plano_md, file_name=f"{nome_plano}.md", mime="text/markdown")

    def _lista(os_):
        if not os_:
            return "—"
        return "\n".join(f"- {o['titulo']}  \n  <small>{torre.artigo_curto(o['norma'], o['artigo'])} · {o['periodicidade'] or '—'}</small>"
                         for o in os_)

    for t in trocas:
        nome = next(a["nome"] for a in ativos if a["codigo"] == t.ativo)
        with st.expander(f"**{t.ativo} · {nome}** — saem {len(t.saem)}, entram {len(t.entram)}"):
            c0, c1, c2 = st.columns([1.2, 2, 2])
            c0.markdown("**Tema**")
            c1.markdown("**Hoje · Res. 95/2022**")
            c2.markdown("**A partir de 02/08/2027 · Res. 220/2025**")
            for par in torre.pares(t, conn, TROCA_NORMA):
                st.divider()
                c0, c1, c2 = st.columns([1.2, 2, 2])
                c0.markdown(f"**{par.tema}**  \n<small>{par.situacao}</small>", unsafe_allow_html=True)
                c1.markdown(_lista(par.saem), unsafe_allow_html=True)
                if par.so_para_outros:
                    c2.markdown("Não vale para este ativo. Na Res. 220:\n" + "\n".join(
                        f"- {o['titulo']}  \n  <small>{torre.artigo_curto(o['norma'], o['artigo'])} · só para {o['aplica_se_a']}</small>"
                        for o in par.so_para_outros), unsafe_allow_html=True)
                else:
                    c2.markdown(_lista(par.entram), unsafe_allow_html=True)

    st.markdown("##### Linha do tempo: o que ainda vai passar a valer")
    st.caption("Barras: a norma que vale para cada ativo, de hoje até 2030. Losangos: dia em que obrigações "
               "passam a valer (laranja = data de uma mudança ainda não aprovada). Clique num losango para ver a lista.")
    futuras = [f for f in torre.futuras(conn, empresa["id"], hoje) if f.ativo in codigos_meus]
    por_dia: dict[str, list] = {}
    for f in futuras:
        por_dia.setdefault(f.dia, []).append(f)
    dia_tl = _linha_do_tempo(futuras)
    for dia, fs in por_dia.items():
        dias = (date.fromisoformat(dia) - hoje).days
        agrupado: dict[tuple, list[str]] = {}
        for f in fs:
            agrupado.setdefault((f.codigo, f.titulo, f.norma, f.artigo, f.proposta), []).append(f.ativo)
        normas_dia = sorted({n for (_, _, n, _, _) in agrupado if n})
        with st.expander(f"**{_br(dia)}** · em {dias} dias · {len(agrupado)} obrigações · {', '.join(normas_dia)}",
                         expanded=dia == dia_tl):
            st.markdown("\n".join(
                f"- {':orange-badge[proposta] ' if prop else ''}{tit} — *{torre.dispositivo(norma, art)}* · {', '.join(ats)}"
                for (cod, tit, norma, art, prop), ats in agrupado.items()))

# ------------------------------------------------------------------ Mudanças

with aba_mudancas:
    pendentes = [m for m in torre.mudancas(conn, empresa["id"]) if set(m.ativos) & codigos_meus]
    if not pendentes:
        st.success("Nenhuma mudança aguardando decisão para os seus ativos.")
    radar_por_ato = {torre.nome_ato(r["ato"]): r for r in (json.loads(demo.RADAR.read_text(encoding="utf-8"))
                                           if demo.RADAR.exists() else [])}
    radar_por_ato.update(st.session_state.get("radar_teste", {}))
    for m in pendentes:
        with st.container(border=True):
            st.markdown(f"#### {m.codigo} · {m.titulo}")
            st.caption(f"Origem: {m.ato or m.fonte} · publicado no DOU em {_br(m.publicado_em)}")
            st.markdown("| Campo | Hoje | Proposto |\n|---|---|---|\n" + "\n".join(
                f"| {CAMPO.get(c, c)} | {_val(c, a)} | **{_val(c, b)}** |" for c, (a, b) in m.diferencas.items()))
            if m.trecho:
                st.markdown(f"> {m.trecho}")
            r = radar_por_ato.get(m.ato)
            if r:
                st.caption(f"Por quê: {r['motivo']}")
                com_data = any(x["campo"] in impacto.CAMPOS_DATA for x in r["mudancas"] if not x["reprovada"])
                st.caption("Conferido pelo Python: a obrigação estava entre as candidatas ✓ · o trecho existe no ato ✓ · "
                           + ("as datas propostas aparecem no trecho ✓ · " if com_data else "")
                           + f"modelo {' → '.join(r['modelos'])} · "
                           f"custo {_usd(r.get('custo_original_usd', r['custo_usd']))}")
                st.markdown(_escopo(r, m))
            st.markdown(f"Ativos afetados: **{', '.join(m.ativos)}**")
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("Aprovar", key=f"ok{m.versao_id}", type="primary"):
                db.decidir(conn, m.versao_id, aprovar=True, por=assinante)
                st.rerun()
            if b2.button("Rejeitar", key=f"no{m.versao_id}"):
                db.decidir(conn, m.versao_id, aprovar=False, por=assinante)
                st.rerun()
            with st.expander("Corrigir antes de aprovar"):
                st.caption("Se a IA errou um valor, corrija aqui. Fica registrado o que foi proposto e o que foi "
                           "aprovado, e por quem.")
                correcoes = {}
                for c, (_, proposto) in m.diferencas.items():
                    if c in db.CAMPOS_DATA:
                        d = st.date_input(CAMPO.get(c, c), value=date.fromisoformat(proposto) if proposto else None,
                                          format="DD/MM/YYYY", key=f"cor{m.versao_id}{c}")
                        correcoes[c] = d.isoformat() if d else None
                    else:
                        correcoes[c] = st.text_input(CAMPO.get(c, c), value=proposto or "", key=f"cor{m.versao_id}{c}")
                if st.button("Aprovar com correção", key=f"okc{m.versao_id}"):
                    try:
                        db.decidir(conn, m.versao_id, aprovar=True, por=assinante, correcoes=correcoes)
                        st.rerun()
                    except db.ErroCadastro as e:
                        st.error(f"Correção não aceita: {e}")
    decididas = conn.execute(
        "SELECT o.codigo, v.status, v.decidida_por, v.decidida_em, v.correcao, a.titulo AS ato "
        "FROM obrigacao_versao v "
        "JOIN obrigacao o ON o.id = v.obrigacao_id LEFT JOIN ato a ON a.id = v.ato_id "
        "WHERE v.ato_id IS NOT NULL AND v.status != 'pendente'"
    ).fetchall()
    if decididas:
        st.markdown("##### Decisões registradas")
        st.markdown("| Obrigação | Ato | Decisão | Por | Quando (Brasília) |\n|---|---|---|---|---|\n" + "\n".join(
            f"| {r['codigo']} | {torre.nome_ato(r['ato']) or '—'} | "
            + (":red-badge[rejeitada]" if r["status"] == "rejeitada" else ":orange-badge[aprovada com correção]"
               if r["correcao"] else ":green-badge[aprovada]")
            + f" | {r['decidida_por'].split(' (')[0]} | {torre.em_brasilia(r['decidida_em'])} |" for r in decididas))

    st.markdown("##### Histórico de uma obrigação")
    st.caption("Por que este prazo é este? Cada versão com a origem, o trecho que a sustenta e quem decidiu.")
    codigos = sorted({o.codigo for a in meus for o in db.obrigacoes_do_ativo(conn, a["id"])})   # inclusive as futuras
    com_mudanca = [c for c in codigos if len(db.historico(conn, c)) > 1]
    escolha = st.selectbox("Obrigação", com_mudanca + [c for c in codigos if c not in com_mudanca],
                           format_func=lambda c: f"{c} · {db.versao(conn, c)['titulo'][:90]}"
                           + (" (já mudou)" if c in com_mudanca else ""))
    if escolha:
        anterior = None
        norma_escolha = conn.execute("SELECT norma FROM obrigacao WHERE codigo = ?", (escolha,)).fetchone()["norma"]
        for v in db.historico(conn, escolha):
            selo = {"vigente": ":green-badge[vigente]", "substituida": ":gray-badge[substituída]",
                    "pendente": ":orange-badge[pendente]", "rejeitada": ":red-badge[rejeitada]"}[v["status"]]
            origem = torre.nome_ato(v["ato"]) or v["fonte"] or "cadastro inicial"
            quando = torre.em_brasilia(v["decidida_em"], com_hora=False)
            quem = (v["decidida_por"] or "").split(" (")[0]
            decisao = ("" if not quem else f" · veio do cadastro inicial em {quando}" if quem == "carga inicial"
                       else f" · decidida por {quem} em {quando}")
            st.markdown(f"**Versão {v['versao']}** · {selo} · origem: {origem}{decisao}")
            if anterior:
                mudou = db.diferencas(anterior, v)
                if mudou:
                    st.markdown("; ".join(f"{CAMPO.get(c, c)}: {_val(c, a)} → **{_val(c, b)}**" for c, (a, b) in mudou.items()))
            else:
                vale = (f"vale de {_br(v['vigencia_desde'])} até {_br(v['vigencia_ate'])}" if v["vigencia_ate"]
                        else f"vale a partir de {_br(v['vigencia_desde'])}")
                st.markdown(f"Prazo: {_br(v['prazo'])} · {vale} · {torre.dispositivo(norma_escolha, v['artigo'])}")
            if v["correcao"]:
                st.markdown("Corrigida por quem aprovou: " + "; ".join(
                    f"{CAMPO.get(c, c)} proposto {_val(c, p)}, aprovado {_val(c, a)}"
                    for c, (p, a) in json.loads(v["correcao"]).items()))
            if v["trecho"]:
                st.caption(f"“{v['trecho']}”")
            anterior = v

# ------------------------------------------------------------------ Radar

with aba_radar:
    if setor_saude:
        st.info("Protótipo de saúde: o mesmo coletor de XML do DOU reconhece Ministério da Saúde e Anvisa, e as fontes "
                "oficiais de RDC e NR-32 já estão configuradas para extração e curadoria. A amostra visual abaixo ainda é "
                "a trilha de mineração; importe um ZIP mensal para alimentar o funil de saúde.", icon=":material/radar:")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Atos no DOU (ago/2026)", "7.884")
    f2.metric("Da ANM", "825")
    f3.metric("Normativos da ANM → IA", "2")
    f4.metric("Mudam o cadastro", "1")
    st.caption("Filtro por órgão e tipo de ato é regra, sem custo. Só os normativos chegam à IA, "
               "e só com as obrigações que a triagem considerou candidatas.")
    from mitra import impacto
    gastos = db.conectar(impacto.CACHE_IA).execute(
        "SELECT tarefa, COUNT(*) AS n, COALESCE(SUM(custo_usd), 0) AS usd FROM analise_ia GROUP BY tarefa"
    ).fetchall()
    if gastos:
        nomes = {"impacto": "análise de impacto de atos", "extrator": "extração de obrigações de normas"}
        st.markdown("**Custo real de IA até agora** (cada resposta fica em cache e não é paga de novo): " + " · ".join(
            f"{nomes.get(g['tarefa'], g['tarefa'])}: {g['n']} chamadas, {_usd(g['usd'], 3)}" for g in gastos))
    radar = json.loads(demo.RADAR.read_text(encoding="utf-8")) if demo.RADAR.exists() else []
    for r in radar:
        with st.container(border=True):
            mud = [x for x in r["mudancas"] if not x["reprovada"]]
            st.markdown(f"**{torre.nome_ato(r['ato'])}** — {'muda ' + ', '.join(sorted({x['obrigacao'] for x in mud})) if mud else 'não muda o cadastro'}")
            st.caption(r["motivo"])
            st.caption(f"Obrigações enviadas à IA: {', '.join(r['candidatas']) or 'nenhuma'} · "
                       f"modelo: {' → '.join(r['modelos'])} · confiança {str(r['confianca']).replace('.', ',')} · "
                       f"custo {_usd(r.get('custo_original_usd', r['custo_usd']))}"
                       + (" (resposta já em cache: não foi paga de novo)" if not r["custo_usd"] else ""))

ATO_EXEMPLO = """RESOLUÇÃO FICTÍCIA DE TESTE Nº 1, DE 2 DE MARÇO DE 2027
(texto inventado para demonstração: não é um ato real)

Art. 1º O inciso I do art. 19 da Resolução ANM nº 95, de 7 de fevereiro de 2022, passa a vigorar com a seguinte redação:
"I - preencher, semanalmente, as Fichas de Inspeção Regular (FIR);"
Art. 2º Esta Resolução entra em vigor em 1º de abril de 2027."""

with aba_radar:
    st.markdown("##### Teste com um ato seu")
    st.caption("Cole o texto de um ato. A regra escolhe as obrigações candidatas sem custo; a IA só roda se "
               "houver candidata; o Python confere o que ela disser; nada muda sem aprovação na aba Mudanças.")
    if st.button("Usar um ato fictício de exemplo"):
        st.session_state["ato_teste"] = ATO_EXEMPLO
    texto_ato = st.text_area("Texto do ato", key="ato_teste", height=180,
                             placeholder="Cole aqui o texto de uma resolução, portaria, instrução normativa…")
    if st.button("Analisar ato", type="primary", disabled=not (texto_ato or "").strip()):
        titulo_ato = torre.titulo_do_ato(texto_ato)
        if _roteador() is None:
            st.error("Não consegui iniciar o roteador de IA (veja modelos.toml e .env).")
        else:
            if _roteador_da_sessao() is None:
                st.info(f"Esta visita já usou as {LIMITE_IA_SESSAO} análises novas de IA do link público: "
                        "segue só com regra e cache.")
            with st.spinner("Triagem por regra e, se houver candidata, análise da IA…"):
                an = _com_ia(lambda rot: impacto.analisar(conn, rot or _roteador_sem_chave(), titulo_ato, texto_ato))
                st.session_state["analise_teste"] = (titulo_ato, texto_ato, an)
    if "analise_teste" in st.session_state:
        titulo_ato, texto_salvo, an = st.session_state["analise_teste"]
        st.markdown(f"**{torre.nome_ato(titulo_ato)}**")
        if an.candidatas:
            st.markdown("Candidatas escolhidas pela regra: " + " · ".join(
                f"`{c.codigo}` ({', '.join(c.motivos[:2])})" for c in an.candidatas))
        if an.candidatas:      # sem candidata, o aviso de custo zero lá embaixo já diz tudo
            st.caption(an.motivo or "—")
        if an.modelos:
            st.caption(f"Modelo: {' → '.join(an.modelos)} · custo da análise {_usd(an.custo_original_usd)}"
                       + (" (resposta já em cache: não foi paga de novo)" if an.custo_original_usd and not an.custo_usd else ""))
        for m in an.mudancas:
            selo = f":red-badge[reprovada pelo Python] {m.reprovada}" if m.reprovada else ":green-badge[conferida pelo Python]"
            st.markdown(f"- **{m.obrigacao}** · {CAMPO.get(m.campo, m.campo)}: {_br(m.valor_atual)} → "
                        f"**{_br(m.valor_novo)}** — {selo}")
            st.caption(f"“{m.trecho}”")
        if an.aprovadas:
            if st.button("Enviar para aprovação (aba Mudanças)"):
                ato_id = db.registrar_ato(conn, "teste", "teste-" + hashlib.sha256(
                    texto_salvo.encode("utf-8")).hexdigest()[:16], titulo_ato, texto=texto_salvo)
                impacto.aplicar(conn, an, ato_id)
                # o cartão em Mudanças mostra o porquê e a conferência também para o ato colado
                st.session_state.setdefault("radar_teste", {})[torre.nome_ato(titulo_ato)] = demo.registro_radar(an)
                del st.session_state["analise_teste"]
                st.toast("Mudança proposta: aprove ou rejeite na aba Mudanças.")
                st.rerun()
        elif not an.candidatas:
            st.info("Nenhuma obrigação do cadastro é tocada por este ato: a IA nem foi chamada (custo zero).")

# ------------------------------------------------------------------ Mercado

with aba_mercado:
    mercado = json.loads((db.ROOT / "data" / "mercado_sigbm.json").read_text(encoding="utf-8"))
    st.markdown("##### Quem precisa disso (dados públicos do SIGBM)")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Barragens de mineração", f"{mercado['barragens_mineracao']:,}".replace(",", "."))
    m2.metric("Empresas responsáveis", mercado["empresas"])
    m3.metric("Barragens na PNSB", mercado["barragens_na_pnsb"])
    m4.metric("Empresas na PNSB", mercado["empresas_com_barragem_na_pnsb"],
              help="Empresas com pelo menos uma barragem na Política Nacional de Segurança de Barragens")
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
    outros = p2.number_input("Outros ativos por barragem", 0, 50, 5,
                             help="Vasos de pressão, licenças ambientais e unidades de mineração ligados a cada barragem")
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
    n_obrig = len({l.codigo for l in todas})
    n_evid = sum(len(db.evidencias_do_ativo(conn, a["id"])) for a in ativos)
    n_ativos = len(ativos)
    radar_c = json.loads(demo.RADAR.read_text(encoding="utf-8")) if demo.RADAR.exists() else []
    custo_radar = sum(r.get("custo_original_usd", r["custo_usd"]) for r in radar_c)
    custo_txt = f"{custo_radar:.4f}".replace(".", ",")
    escuro = getattr(st.context.theme, "type", None) == "dark"
    cor_rotulo = "#b0b0b0" if escuro else "#555555"     # rótulo das setas legível nos dois temas
    st.markdown("##### Dois caminhos para a mesma torre")
    st.graphviz_chart(f"""
digraph {{
  rankdir=TB; bgcolor="transparent"; nodesep=0.35; ranksep=0.35; node [shape=box style="rounded,filled" fillcolor="#f0f2f6" fontname="Helvetica" fontsize=11];
  edge [fontname="Helvetica" fontsize=9 color="#888888" fontcolor="{cor_rotulo}"];
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
