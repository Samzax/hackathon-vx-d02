"""Torre de controle: o que a interface mostra, calculado a partir do banco.

- painel():    "Hoje" — cada obrigação vigente de cada ativo, com status de agenda
- transicao(): o que entra e o que sai numa data de troca de norma (ex.: Res. 95 -> 220)
- mudancas():  versões pendentes (vindas de atos novos), com diferença, trecho e ativos afetados

Nada aqui escreve no banco; a interface só lê, e as decisões passam por db.decidir().
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from . import agenda, db

DADO_FALTANDO = "dado_faltando"

ORDEM = {agenda.ATRASADA: 0, DADO_FALTANDO: 1, agenda.VENCE_LOGO: 2, agenda.EM_DIA: 3,
         agenda.CUMPRIDA: 4, agenda.GATILHO: 5}


@dataclass
class Linha:
    ativo: str
    ativo_nome: str
    tipo_ativo: str
    responsavel: str | None
    codigo: str
    norma: str | None
    area: str | None
    titulo: str
    artigo: str
    periodicidade: str | None
    status: str
    vence: str | None = None               # AAAA-MM-DD do próximo vencimento
    faltando: list[str] = field(default_factory=list)
    ultima: str | None = None
    dados_faltando: list[str] = field(default_factory=list)
    mudanca_pendente: bool = False
    evidencia: str | None = None
    nota: str = ""


def _empresa_ativos(conn, empresa_id: int, tipo: str | None = None) -> list[dict]:
    return [a for a in db.ativos(conn, empresa_id) if tipo is None or a["tipo"] == tipo]


def _meta(conn, codigo: str) -> dict:
    r = conn.execute("SELECT norma, area FROM obrigacao WHERE codigo = ?", (codigo,)).fetchone()
    return dict(r) if r else {"norma": None, "area": None}


def _prazo_unico(v: dict) -> str | None:
    """Prazo de obrigação de evento único: nunca antes de ela entrar em vigor."""
    prazo, desde = v.get("prazo"), v.get("vigencia_desde")
    try:
        date.fromisoformat(prazo or "")
    except ValueError:
        return desde
    return max(prazo, desde) if desde else prazo


def _herdadas(conn, ativo_id: int, codigo: str, titulo: str) -> tuple[list[str], str | None]:
    """Obrigação contada da última execução (RPSB a cada N anos) que acabou de entrar por norma nova:
    a última RPSB feita pela norma anterior continua valendo. Equivalência = mesmo tema (ver TEMAS)."""
    t = tema(titulo)
    if t == "Outras":
        return [], None
    melhor: tuple[list[str], str | None] = ([], None)
    for o in db.obrigacoes_do_ativo(conn, ativo_id):
        if o.codigo == codigo or tema(o.vigente["titulo"]) != t:
            continue
        evs = [e for e in db.evidencias(conn, ativo_id, o.codigo) if re.fullmatch(r"\d{4}-\d\d-\d\d", e)]
        if evs and (not melhor[0] or max(evs) > max(melhor[0])):
            melhor = (evs, o.codigo)
    return melhor


def painel(conn, empresa_id: int, hoje: date, desde: date, ativo: str | None = None) -> list[Linha]:
    """Status de cada obrigação que vale hoje, por ativo. `desde` é o início do monitoramento."""
    out = []
    for a in _empresa_ativos(conn, empresa_id):
        if ativo and a["codigo"] != ativo:
            continue
        for o in db.obrigacoes_do_ativo(conn, a["id"], em=hoje.isoformat()):
            v = o.vigente
            if not db.vale_em(v, hoje.isoformat()):
                continue       # só a pendente vale hoje: aparece em mudancas()
            meta = _meta(conn, o.codigo)
            ini = max(desde, date.fromisoformat(v["vigencia_desde"])) if v["vigencia_desde"] else desde
            linha = Linha(
                ativo=a["codigo"], ativo_nome=a["nome"], tipo_ativo=a["tipo"], responsavel=a["responsavel"],
                codigo=o.codigo, norma=meta["norma"], area=meta["area"], titulo=v["titulo"],
                artigo=v["artigo"], periodicidade=v["periodicidade"], status=agenda.GATILHO,
                dados_faltando=o.dados_faltando, mudanca_pendente=o.pendente is not None,
                evidencia=v["evidencia"],
            )
            if o.dados_faltando:
                linha.status = DADO_FALTANDO
                linha.nota = "cadastro do ativo incompleto: " + ", ".join(o.dados_faltando)
            else:
                evs = db.evidencias(conn, a["id"], o.codigo)
                herdada = None
                if not evs and re.fullmatch(r"(anos|meses):\d+", v["agenda"]):
                    evs, herdada = _herdadas(conn, a["id"], o.codigo, v["titulo"])
                s = agenda.situacao(v["agenda"], evs, hoje, ini, prazo=_prazo_unico(v))
                linha.status, linha.ultima, linha.nota = s.status, s.ultima, s.nota
                if herdada:
                    linha.nota = (f"conta a última execução registrada em {herdada} "
                                  f"({_br(s.ultima)}), obrigação equivalente da norma anterior")
                # atrasada: a data que venceu primeiro; senão, a próxima
                alvo = s.faltando[0] if s.faltando else s.proximo
                linha.vence = alvo.vence.isoformat() if alvo else None
                linha.faltando = [p.rotulo for p in s.faltando]
            out.append(linha)
    out.sort(key=lambda l: (l.ativo, ORDEM.get(l.status, 9), l.vence or "9999"))
    return out


def resumo(linhas: list[Linha]) -> dict[str, dict[str, int]]:
    """{ativo: {status: quantidade}}"""
    out: dict[str, dict[str, int]] = {}
    for l in linhas:
        out.setdefault(l.ativo, {}).setdefault(l.status, 0)
        out[l.ativo][l.status] += 1
    return out


CAMPOS = {"prazo": "prazo", "vigencia_desde": "começa a valer em", "vigencia_ate": "deixa de valer após",
          "periodicidade": "periodicidade", "aplica_se_a": "aplica-se a", "titulo": "obrigação",
          "evidencia": "evidência", "regra": "regra", "agenda": "agenda"}


def _br(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "—"


def _valor(v) -> str:
    try:
        return _br(str(v)) if v else "—"
    except ValueError:
        return str(v)


def boletim(conn, empresa_id: int, hoje: date, desde: date, responsavel: str | None = None,
            janela: int = 30) -> str:
    """Boletim em Markdown para um gestor (ou a diretoria): o que está atrasado, o que vence
    nos próximos `janela` dias, o que falta no cadastro e as mudanças aguardando aprovação.
    É o que iria por e-mail toda segunda; aqui só é gerado, nunca enviado."""
    ativos = {a["codigo"]: a for a in _empresa_ativos(conn, empresa_id)
              if responsavel is None or a["responsavel"] == responsavel}
    linhas = [l for l in painel(conn, empresa_id, hoje, desde) if l.ativo in ativos]
    atrasadas = [l for l in linhas if l.status == agenda.ATRASADA]
    faltando = [l for l in linhas if l.status == DADO_FALTANDO]
    limite = date.fromordinal(hoje.toordinal() + janela).isoformat()
    proximas = sorted((l for l in linhas if l.status in (agenda.VENCE_LOGO, agenda.EM_DIA)
                       and l.vence and l.vence <= limite), key=lambda l: l.vence)
    pendentes = [m for m in mudancas(conn, empresa_id) if set(m.ativos) & set(ativos)]

    def item(l: Linha, extra: str) -> str:
        return f"- **{l.ativo}** · {l.titulo} ({l.norma}, {l.artigo}) — {extra}"

    para = responsavel or "Diretoria"
    out = [f"# Boletim regulatório — {para}", "",
           f"Semana de {hoje:%d/%m/%Y} · {len(ativos)} {'ativo' if len(ativos) == 1 else 'ativos'} · "
           f"{len(linhas)} obrigações aplicáveis", ""]
    if not (atrasadas or faltando or proximas or pendentes):
        out.append("Nada atrasado, nada vencendo nos próximos dias e nenhuma mudança aguardando aprovação.")
    if atrasadas:
        out += [f"## 🔴 Atrasadas ({len(atrasadas)})", ""]
        out += [item(l, f"venceu em {_br(l.vence)}; falta: {', '.join(map(agenda.rotulo_humano, l.faltando)) or l.nota}") for l in atrasadas]
        out.append("")
    if proximas:
        out += [f"## 🟡 Vencem nos próximos {janela} dias ({len(proximas)})", ""]
        out += [item(l, f"até {_br(l.vence)}") for l in proximas]
        out.append("")
    if faltando:
        out += [f"## ⚪ Falta dado no cadastro ({len(faltando)})", ""]
        out += [item(l, "informar " + ", ".join(l.dados_faltando)) for l in faltando]
        out.append("")
    if pendentes:
        out += [f"## ⚠️ Mudanças de norma aguardando aprovação ({len(pendentes)})", ""]
        for m in pendentes:
            campos = "; ".join(f"{CAMPOS.get(c, c)}: {_valor(a)} → {_valor(b)}"
                               for c, (a, b) in m.diferencas.items())
            out.append(f"- **{m.codigo}** · {m.titulo} — {m.ato}: {campos} "
                       f"(ativos: {', '.join(sorted(set(m.ativos) & set(ativos)))})")
        out.append("")
    out.append("Gerado pela RegulaIA. Cada item traz a norma e o dispositivo; o trecho literal está na torre.")
    return "\n".join(out)


def _ics_texto(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_dobra(linha: str) -> list[str]:
    """RFC 5545: linhas de até 75 octetos; a continuação começa com espaço."""
    out, atual = [], ""
    for ch in linha:
        if len((atual + ch).encode("utf-8")) > (75 if not out else 74):
            out.append(atual)
            atual = ""
        atual += ch
    out.append(atual)
    return [out[0]] + [" " + x for x in out[1:]]


def calendario(conn, empresa_id: int, hoje: date, desde: date, responsavel: str | None = None,
               dias: int = 400) -> str:
    """Arquivo .ics com o próximo vencimento de cada obrigação (e as que começam a valer) dentro
    de `dias`, para importar no Outlook ou Google Agenda. Os UIDs são estáveis: importar de novo
    na semana seguinte atualiza em vez de duplicar. Só gera o arquivo; não envia nada."""
    ativos = {a["codigo"]: a for a in _empresa_ativos(conn, empresa_id)
              if responsavel is None or a["responsavel"] == responsavel}
    limite = date.fromordinal(hoje.toordinal() + dias).isoformat()
    eventos = []
    for l in painel(conn, empresa_id, hoje, desde):
        if l.ativo in ativos and l.vence and l.vence <= limite and l.status != agenda.CUMPRIDA:
            marca = "ATRASADA · " if l.status == agenda.ATRASADA else ""
            eventos.append((l.vence, f"{l.ativo}-{l.codigo}-vence",
                            f"{marca}{l.ativo} · {l.titulo}", f"{l.norma}, {l.artigo}"))
    for f in futuras(conn, empresa_id, hoje):
        if f.ativo in ativos and f.dia <= limite and not f.proposta:
            eventos.append((f.dia, f"{f.ativo}-{f.codigo}-inicio",
                            f"Começa a valer: {f.ativo} · {f.titulo}", f"{f.norma}, {f.artigo}"))
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//RegulaIA//Torre de Controle//PT-BR",
              "CALSCALE:GREGORIAN", f"X-WR-CALNAME:RegulaIA · {_ics_texto(responsavel or 'Diretoria')}"]
    carimbo = f"{hoje:%Y%m%d}T000000Z"
    for dia, uid, resumo, desc in sorted(eventos):
        d = date.fromisoformat(dia)
        linhas += ["BEGIN:VEVENT", f"UID:{uid}-{d:%Y%m%d}@regulaia", f"DTSTAMP:{carimbo}",
                   f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                   f"DTEND;VALUE=DATE:{date.fromordinal(d.toordinal() + 1):%Y%m%d}",
                   f"SUMMARY:{_ics_texto(resumo)}", f"DESCRIPTION:{_ics_texto(desc)}", "END:VEVENT"]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(x for l in linhas for x in _ics_dobra(l)) + "\r\n"


# ------------------------------------------------------------------ transição


@dataclass
class Troca:
    ativo: str
    saem: list[dict]      # obrigações que deixam de valer no dia da troca
    entram: list[dict]    # obrigações que passam a valer no dia da troca


def transicao(conn, empresa_id: int, dia: date) -> list[Troca]:
    """Para cada ativo: o que vale na véspera e não no dia, e o contrário."""
    vespera = date.fromordinal(dia.toordinal() - 1).isoformat()
    out = []
    for a in _empresa_ativos(conn, empresa_id):
        antes = {o.codigo: o.vigente for o in db.obrigacoes_do_ativo(conn, a["id"], em=vespera)
                 if db.vale_em(o.vigente, vespera)}
        depois = {o.codigo: o.vigente for o in db.obrigacoes_do_ativo(conn, a["id"], em=dia.isoformat())
                  if db.vale_em(o.vigente, dia.isoformat())}
        saem = [antes[c] | _meta(conn, c) for c in sorted(set(antes) - set(depois))]
        entram = [depois[c] | _meta(conn, c) for c in sorted(set(depois) - set(antes))]
        if saem or entram:
            out.append(Troca(a["codigo"], saem, entram))
    return out


@dataclass
class Futura:
    dia: str              # AAAA-MM-DD em que passa a valer
    ativo: str
    codigo: str
    titulo: str
    norma: str | None
    artigo: str
    proposta: bool        # True: data vem de uma mudança ainda não aprovada


def futuras(conn, empresa_id: int, hoje: date) -> list[Futura]:
    """Linha do tempo: obrigações que passam a valer depois de hoje, por ativo."""
    out = []
    for a in _empresa_ativos(conn, empresa_id):
        for o in db.obrigacoes_do_ativo(conn, a["id"]):
            meta = _meta(conn, o.codigo)
            for v, proposta in ((o.vigente, False), (o.pendente, True)):
                if v and v["vigencia_desde"] and v["vigencia_desde"] > hoje.isoformat():
                    if proposta and v["vigencia_desde"] == o.vigente["vigencia_desde"]:
                        continue
                    out.append(Futura(v["vigencia_desde"], a["codigo"], o.codigo, v["titulo"],
                                      meta["norma"], v["artigo"], proposta))
    out.sort(key=lambda f: (f.dia, f.ativo, f.codigo))
    return out


# Temas para casar obrigações equivalentes entre a norma que sai e a que entra.
# Ordem importa: o primeiro tema que casar com o título vence.
TEMAS = [
    ("Ficha de Inspeção Regular (FIR)", ("fir", "ficha de inspecao")),
    ("Extrato de Inspeção Regular (EIR)", ("eir", "extrato de inspecao")),
    ("RISR e DCE", ("risr", "dce")),
    ("Revisão Periódica (RPSB)", ("rpsb", "revisao periodica")),
    ("DCO e RCO do PAEBM", ("dco", "rco", "conformidade e operacionalidade")),
    ("Treinamento do PAEBM", ("treinamento",)),
    ("Exercício simulado", ("simulad",)),
    ("Seminário orientativo", ("seminario",)),
    ("Zona de Autossalvamento", ("zas", "autossalvamento")),
    ("Emergência", ("emergencia", "ise", "anomalia", "incidente")),
    ("Monitoramento", ("monitoramento", "sirene")),
    ("PGRBM", ("pgrbm", "gestao de riscos")),
]


def tema(titulo: str) -> str:
    from .triagem import normalizar
    t = f" {normalizar(titulo)} "
    for nome, chaves in TEMAS:
        if any(f" {c}" in t for c in chaves):
            return nome
    return "Outras"


@dataclass
class Par:
    tema: str
    saem: list[dict]
    entram: list[dict]


def pares(troca: Troca) -> list[Par]:
    """Agrupa o que sai e o que entra pelo tema: mostra o que continua, o que é novo e o que acaba."""
    grupos: dict[str, Par] = {}
    for o in troca.saem:
        grupos.setdefault(tema(o["titulo"]), Par(tema(o["titulo"]), [], [])).saem.append(o)
    for o in troca.entram:
        grupos.setdefault(tema(o["titulo"]), Par(tema(o["titulo"]), [], [])).entram.append(o)
    ordem = [n for n, _ in TEMAS] + ["Outras"]
    return sorted(grupos.values(), key=lambda p: ordem.index(p.tema))


def plano_transicao(conn, empresa_id: int, dia: date, hoje: date, responsavel: str | None = None) -> str:
    """Plano de transição em Markdown: por ativo, o que continua, o que é novo e o que acaba
    na troca de norma de `dia`. É o documento que a empresa montaria lendo as duas resoluções."""
    ativos = {a["codigo"]: a for a in _empresa_ativos(conn, empresa_id)
              if responsavel is None or a["responsavel"] == responsavel}
    trocas = [t for t in transicao(conn, empresa_id, dia) if t.ativo in ativos]
    faltam = (dia - hoje).days
    out = [f"# Plano de transição — {responsavel or 'Diretoria'}", "",
           f"Troca de norma em {dia:%d/%m/%Y} (faltam {faltam} dias). Gerado em {hoje:%d/%m/%Y}.", ""]
    if not trocas:
        out.append("Nenhum dos ativos muda de obrigação nessa data.")
    novas_total = 0
    for t in trocas:
        a = ativos[t.ativo]
        out += [f"## {t.ativo} · {a['nome']} ({a['responsavel']})", ""]
        for p in pares(t):
            if p.saem and p.entram:
                rotulo = "🔁 continua, com regra nova"
            elif p.entram:
                rotulo = "🆕 nova: preparar antes da data"
                novas_total += len(p.entram)
            else:
                rotulo = "➖ sem equivalente no cadastro da nova norma: conferir antes de abandonar"
            out.append(f"- **{p.tema}** — {rotulo}")
            out += [f"  - antes: {o['titulo']} ({o['artigo']})" for o in p.saem]
            out += [f"  - depois: {o['titulo']} ({o['artigo']})" for o in p.entram]
        out.append("")
    if trocas:
        out.insert(4, f"{len(trocas)} ativos afetados · {novas_total} obrigações sem equivalente na norma atual.\n")
    out.append("Gerado pela RegulaIA a partir do cadastro aprovado. Mudanças ainda pendentes não entram.")
    return "\n".join(out)


# ------------------------------------------------------------------- mudanças


@dataclass
class Mudanca:
    versao_id: int
    codigo: str
    titulo: str
    diferencas: dict[str, tuple]
    ato: str | None
    publicado_em: str | None
    trecho: str | None
    fonte: str | None
    ativos: list[str]


def mudancas(conn, empresa_id: int) -> list[Mudanca]:
    rows = conn.execute(
        "SELECT v.id, o.codigo, a.titulo AS ato, a.publicado_em FROM obrigacao_versao v "
        "JOIN obrigacao o ON o.id = v.obrigacao_id LEFT JOIN ato a ON a.id = v.ato_id "
        "WHERE v.status = 'pendente' ORDER BY o.codigo"
    ).fetchall()
    ativos = _empresa_ativos(conn, empresa_id)
    out = []
    for r in rows:
        pen = db.versao(conn, r["codigo"], "pendente")
        vig = db.versao(conn, r["codigo"])
        afetados = [a["codigo"] for a in ativos
                    if any(o.codigo == r["codigo"] and o.pendente for o in db.obrigacoes_do_ativo(conn, a["id"]))]
        out.append(Mudanca(r["id"], r["codigo"], vig["titulo"], db.diferencas(vig, pen),
                           r["ato"], r["publicado_em"], pen["trecho"], pen["fonte"], afetados))
    return out


def para_json(obj) -> str:
    """Ajuda de depuração: imprime qualquer resultado daqui."""
    from dataclasses import asdict, is_dataclass

    def conv(x):
        if is_dataclass(x):
            return asdict(x)
        if isinstance(x, list):
            return [conv(i) for i in x]
        return x
    return json.dumps(conv(obj), ensure_ascii=False, indent=1, default=str)
