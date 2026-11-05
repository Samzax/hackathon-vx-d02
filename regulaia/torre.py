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


def dispositivo(norma: str | None, artigo: str | None) -> str:
    """'Res. ANM 220/2025' + 'Res. ANM 220/2025 art. 38 I' não repete a norma; 'Res. ANM 95/2022' + 'art. 27' junta."""
    if norma and artigo and artigo.startswith(norma):
        return artigo
    return f"{norma}, {artigo}" if norma else (artigo or "")


def artigo_curto(norma: str | None, artigo: str | None) -> str:
    """Só o dispositivo, para quando a norma já está no cabeçalho: 'art. 38 I'."""
    return (artigo or "").removeprefix(norma or "").strip()


_SIGLAS = {"SIGBM", "IBAMA", "SNTEP", "SUPAS"}


def nome_ato(titulo: str | None) -> str | None:
    """'RESOLUÇÃO ANM Nº 245, DE 31 DE JULHO DE 2026' (como o DOU publica) vira
    'Resolução ANM nº 245, de 31 de julho de 2026'. Siglas curtas (ANM, MTE) ficam."""
    if not titulo:
        return titulo
    palavras = []
    for i, p in enumerate(titulo.split(" ")):
        nucleo = p.strip(",.;:")
        if nucleo in ("DE", "DA", "DO", "DAS", "DOS", "E", "Nº", "N°") or nucleo.lower() in agenda._MESES:
            p = p.lower()
        elif nucleo.isupper() and len(nucleo) >= 5 and nucleo not in _SIGLAS:
            p = p.capitalize() if i == 0 else p.lower()
        palavras.append(p)
    return " ".join(palavras)


def campo_legivel(campo: str) -> str:
    """'modificacao_estrutural' -> 'se passou por modificação estrutural', pelo vocabulário que a
    regra usa. Campo fora do vocabulário passa como está."""
    from .extrator import VOCABULARIO

    for atributos in VOCABULARIO.values():
        if campo in atributos:
            desc = atributos[campo]
            return desc.removeprefix("verdadeiro ") if desc.startswith("verdadeiro se ") else desc
    return campo


def _minuscula(texto: str) -> str:
    """'Relatório de ISE' -> 'relatório de ISE'; siglas ('FIE, EIE...') ficam como estão."""
    return texto[0].lower() + texto[1:] if len(texto) > 1 and texto[1].islower() else texto


def _maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _empresa_ativos(conn, empresa_id: int, tipo: str | None = None) -> list[dict]:
    return [a for a in db.ativos(conn, empresa_id) if tipo is None or a["tipo"] == tipo]


_SEM_META = {"norma": None, "area": None, "tipo_ativo": None}


def _metas(conn) -> dict[str, dict]:
    """Norma, área e tipo de ativo de cada obrigação, numa consulta só."""
    return {r["codigo"]: {"norma": r["norma"], "area": r["area"], "tipo_ativo": r["tipo_ativo"]}
            for r in conn.execute("SELECT codigo, norma, area, tipo_ativo FROM obrigacao")}


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
    metas = _metas(conn)
    abertos = db.acionamentos_abertos(conn, hoje.isoformat())
    for a in _empresa_ativos(conn, empresa_id):
        if ativo and a["codigo"] != ativo:
            continue
        for o in db.obrigacoes_do_ativo(conn, a["id"], em=hoje.isoformat()):
            v = o.vigente
            if not db.vale_em(v, hoje.isoformat()):
                continue       # só a pendente vale hoje: aparece em mudancas()
            meta = metas.get(o.codigo, _SEM_META)
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
                linha.nota = "cadastro do ativo incompleto: " + ", ".join(map(campo_legivel, o.dados_faltando))
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
                if acs := abertos.get((a["id"], o.codigo)):
                    # obrigação por evento acionada por um documento: vale o prazo do acionamento
                    ac = acs[0]
                    linha.status = agenda.ATRASADA if hoje.isoformat() > ac["prazo"] else agenda.VENCE_LOGO
                    linha.vence, linha.faltando = ac["prazo"], []
                    linha.nota = (f"acionada em {_br(ac['dia'])} por {ac['origem'] or 'documento'}: "
                                  f"aguardando {_minuscula(v['evidencia'] or 'a evidência')}")
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


SEM_EVIDENCIA = "sem evidência registrada"


def pendente(l: Linha) -> str:
    """Períodos sem evidência, em português. Quando o único período é o próprio vencimento
    (entrega única, RPSB, exame do vaso), repetir a data não diz nada: diz que não há evidência.
    Sem período pendente, a nota (gatilho, acionamento)."""
    if so_o_vencimento(l):
        return f"última evidência em {_br(l.ultima)}" if l.ultima else SEM_EVIDENCIA
    rotulos = [agenda.rotulo_humano(p) for p in l.faltando]
    if len(rotulos) > 3:                 # dez meses um por um não cabem numa linha de boletim
        return f"{len(rotulos)} períodos entre {rotulos[0]} e {rotulos[-1]}"
    return ", ".join(rotulos) or l.nota


def so_o_vencimento(l: Linha) -> bool:
    return len(l.faltando) == 1 and (l.faltando[0] == "unico" or agenda.rotulo_humano(l.faltando[0]) == _br(l.vence))


def _o_que_falta(l: Linha) -> str:
    texto = pendente(l) or SEM_EVIDENCIA
    return f"falta: {texto}" if l.faltando and not so_o_vencimento(l) else texto


def _valor(v, campo: str | None = None) -> str:
    if campo == "agenda" and v:
        return agenda.descrever(v)
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
        return f"- **{l.ativo}** · {l.titulo} ({dispositivo(l.norma, l.artigo)}) — {extra}"

    para = responsavel or "Diretoria"
    out = [f"# Boletim regulatório — {para}", "",
           f"Semana de {hoje:%d/%m/%Y} · {len(ativos)} {'ativo' if len(ativos) == 1 else 'ativos'} · "
           f"{len(linhas)} obrigações aplicáveis", ""]
    if not (atrasadas or faltando or proximas or pendentes):
        out.append("Nada atrasado, nada vencendo nos próximos dias e nenhuma mudança aguardando aprovação.")
    if atrasadas:
        out += [f"## 🔴 Atrasadas ({len(atrasadas)})", ""]
        out += [item(l, f"venceu em {_br(l.vence)}; {_o_que_falta(l)}") for l in atrasadas]
        out.append("")
    if proximas:
        out += [f"## 🟡 Vencem nos próximos {janela} dias ({len(proximas)})", ""]
        out += [item(l, f"até {_br(l.vence)}") for l in proximas]
        out.append("")
    if faltando:
        out += [f"## ⚪ Falta dado no cadastro ({len(faltando)})", ""]
        out += [item(l, "informar " + ", ".join(f"{campo_legivel(c)} ({c})" for c in l.dados_faltando))
                for l in faltando]
        out.append("")
    if pendentes:
        out += [f"## ⚠️ Mudanças de norma aguardando aprovação ({len(pendentes)})", ""]
        for m in pendentes:
            campos = "; ".join(f"{CAMPOS.get(c, c)}: {_valor(a, c)} → {_valor(b, c)}"
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
                            f"{marca}{l.ativo} · {l.titulo}",
                            dispositivo(l.norma, l.artigo) + (f". {_maiuscula(l.nota)}" if l.nota else "")))
    for f in futuras(conn, empresa_id, hoje):
        if f.ativo in ativos and f.dia <= limite and not f.proposta:
            eventos.append((f.dia, f"{f.ativo}-{f.codigo}-inicio",
                            f"Começa a valer: {f.ativo} · {f.titulo}", dispositivo(f.norma, f.artigo)))
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
    metas = _metas(conn)
    for a in _empresa_ativos(conn, empresa_id):
        antes = {o.codigo: o.vigente for o in db.obrigacoes_do_ativo(conn, a["id"], em=vespera)
                 if db.vale_em(o.vigente, vespera)}
        depois = {o.codigo: o.vigente for o in db.obrigacoes_do_ativo(conn, a["id"], em=dia.isoformat())
                  if db.vale_em(o.vigente, dia.isoformat())}
        saem = [antes[c] | metas.get(c, _SEM_META) for c in sorted(set(antes) - set(depois))]
        entram = [depois[c] | metas.get(c, _SEM_META) for c in sorted(set(depois) - set(antes))]
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
    metas = _metas(conn)
    for a in _empresa_ativos(conn, empresa_id):
        for o in db.obrigacoes_do_ativo(conn, a["id"]):
            meta = metas.get(o.codigo, _SEM_META)
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
    ("Cópias do PAEBM", ("copias",)),
    ("Sirenes e alerta", ("sirene",)),
    ("Zona de Autossalvamento", ("zas", "autossalvamento")),
    ("Emergência", ("emergencia", "ise", "anomalia", "incidente")),
    ("Monitoramento", ("monitoramento", "video")),
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
    # o tema existe na norma nova, mas com regra que exclui este ativo (ex.: só DPA2 ≥ 4)
    so_para_outros: list[dict] = field(default_factory=list)

    @property
    def situacao(self) -> str:
        if self.saem and self.entram:
            return "🔁 continua, com regra nova"
        if self.entram:
            return "🆕 nova: preparar antes da data"
        if self.so_para_outros:
            return "➖ deixa de valer para este ativo: na nova norma o tema só vale para outros casos"
        return "➖ sem equivalente no cadastro da nova norma: conferir antes de abandonar"


def _comecam_em(conn, dia: date) -> list[dict]:
    """Obrigações que passam a valer em `dia` (a norma nova), para qualquer ativo."""
    rows = conn.execute(
        "SELECT v.*, o.codigo, o.norma, o.area, o.tipo_ativo FROM obrigacao_versao v "
        "JOIN obrigacao o ON o.id = v.obrigacao_id "
        "WHERE v.status = 'vigente' AND v.vigencia_desde = ? ORDER BY o.codigo", (dia.isoformat(),))
    return [dict(r) for r in rows]


def pares(troca: Troca, conn=None, dia: date | None = None, novas_do_dia: list[dict] | None = None) -> list[Par]:
    """Agrupa o que sai e o que entra pelo tema: mostra o que continua, o que é novo e o que acaba.
    Com `conn` e `dia`, diz também quando o tema existe na norma nova mas não vale para o ativo."""
    grupos: dict[str, Par] = {}
    for o in troca.saem:
        grupos.setdefault(tema(o["titulo"]), Par(tema(o["titulo"]), [], [])).saem.append(o)
    for o in troca.entram:
        grupos.setdefault(tema(o["titulo"]), Par(tema(o["titulo"]), [], [])).entram.append(o)
    if conn is not None and dia is not None:
        tipo = conn.execute("SELECT tipo FROM ativo WHERE codigo = ?", (troca.ativo,)).fetchone()["tipo"]
        novas = novas_do_dia if novas_do_dia is not None else _comecam_em(conn, dia)
        for p in grupos.values():
            if not p.entram and p.tema != "Outras":
                p.so_para_outros = [o for o in novas if o["tipo_ativo"] == tipo and tema(o["titulo"]) == p.tema]
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
    novas_do_dia = _comecam_em(conn, dia)
    for t in trocas:
        a = ativos[t.ativo]
        out += [f"## {t.ativo} · {a['nome']} ({a['responsavel']})", ""]
        for p in pares(t, conn, dia, novas_do_dia):
            if p.entram and not p.saem:
                novas_total += len(p.entram)
            out.append(f"- **{p.tema}** — {p.situacao}")
            out += [f"  - antes: {o['titulo']} ({dispositivo(o['norma'], o['artigo'])})" for o in p.saem]
            out += [f"  - depois: {o['titulo']} ({dispositivo(o['norma'], o['artigo'])})" for o in p.entram]
            out += [f"  - na nova norma: {o['titulo']} ({dispositivo(o['norma'], o['artigo'])}), só para {o['aplica_se_a']}"
                    for o in p.so_para_outros]
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
                           nome_ato(r["ato"]), r["publicado_em"], pen["trecho"], pen["fonte"], afetados))
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
