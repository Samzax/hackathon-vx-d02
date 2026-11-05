"""Agenda de uma obrigação: quando ela vence e se está em dia.

Cada obrigação tem uma `agenda` em texto curto, que a máquina lê:

  semanal+3d        semanas de segunda a domingo; vence 3 dias após o domingo
  quinzenal+15d     períodos 1–15 e 16–fim do mês; vence 15 dias após o fim do período
  mensal+10d        mês a mês; vence 10 dias após o fim do mês
  trimestral+30d    trimestres do ano civil
  semestral+30d     jan–jun e jul–dez
  anual+0d          ano civil
  datas:03-31,09-30 datas fixas todo ano (campanhas de entrega da DCE, por exemplo)
  anos:3            a cada 3 anos contados da última execução
  meses:6           a cada 6 meses contados da última execução
  data:2027-08-02   uma vez, até a data
  unica             uma vez, até a data do campo `prazo` (que uma norma nova pode mudar)
  evento            depende de um gatilho (incidente, modificação...): sem calendário

Cada execução comprovada é uma evidência com um `periodo`:
  semanal "2026-W44" | quinzenal "2026-10-2Q" | mensal "2026-10" | trimestral "2026-T3" | semestral "2026-S2" | anual "2026"
  datas "2026-09-30" (a data que vence) | anos/meses/data: a data em que foi feita
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

AVISO_DIAS = 30          # "vence logo" = dentro de 30 dias
AVISO_DIAS_CURTO = 5     # para quinzenal e mensal, 30 dias seria sempre amarelo

EM_DIA, VENCE_LOGO, ATRASADA, GATILHO, CUMPRIDA = "em_dia", "vence_logo", "atrasada", "gatilho", "cumprida"


class AgendaInvalida(ValueError):
    pass


@dataclass
class Periodo:
    rotulo: str
    fim: date        # último dia do período
    vence: date      # até quando a evidência deve existir


@dataclass
class Situacao:
    status: str
    proximo: Periodo | None = None             # o próximo que vence
    faltando: list[Periodo] = field(default_factory=list)   # vencidos sem evidência
    ultima: str | None = None                  # período da última evidência
    nota: str = ""


_FREQ = re.compile(r"^(semanal|quinzenal|mensal|trimestral|semestral|anual)\+(\d+)d$")


def validar(agenda: str) -> None:
    a = (agenda or "").strip()
    if a in ("evento", "unica") or _FREQ.match(a):
        return
    if m := re.match(r"^datas:(.+)$", a):
        for d in m.group(1).split(","):
            if not re.fullmatch(r"\d\d-\d\d", d.strip()):
                raise AgendaInvalida(f"data {d!r} não é MM-DD")
        return
    if re.fullmatch(r"(anos|meses):\d+", a):
        return
    if m := re.match(r"^data:(\d{4}-\d\d-\d\d)$", a):
        date.fromisoformat(m.group(1))
        return
    raise AgendaInvalida(f"agenda {agenda!r} não reconhecida")


def _fim_mes(a: int, m: int) -> date:
    return date(a, m, calendar.monthrange(a, m)[1])


def _somar_meses(d: date, n: int) -> date:
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    return date(a, m, min(d.day, calendar.monthrange(a, m)[1]))


def periodos(agenda: str, desde: date, ate: date) -> list[Periodo]:
    """Períodos de calendário cujo fim cai entre `desde` e `ate`, mais o seguinte."""
    m = _FREQ.match(agenda)
    if m:
        freq, folga = m.group(1), timedelta(days=int(m.group(2)))
        out, d = [], desde
        while True:
            if freq == "semanal":
                ano, semana, _ = d.isocalendar()
                rot, fim = f"{ano}-W{semana:02d}", d + timedelta(days=6 - d.weekday())
            elif freq == "quinzenal":
                if d.day <= 15:
                    rot, fim = f"{d:%Y-%m}-1Q", date(d.year, d.month, 15)
                else:
                    rot, fim = f"{d:%Y-%m}-2Q", _fim_mes(d.year, d.month)
            elif freq == "mensal":
                rot, fim = f"{d:%Y-%m}", _fim_mes(d.year, d.month)
            elif freq == "trimestral":
                t = (d.month - 1) // 3 + 1
                rot, fim = f"{d.year}-T{t}", _fim_mes(d.year, 3 * t)
            elif freq == "semestral":
                s = 1 if d.month <= 6 else 2
                rot, fim = f"{d.year}-S{s}", _fim_mes(d.year, 6 * s)
            else:
                rot, fim = f"{d.year}", date(d.year, 12, 31)
            out.append(Periodo(rot, fim, fim + folga))
            if fim + folga > ate:
                return out
            d = fim + timedelta(days=1)
    m = re.match(r"^datas:(.+)$", agenda)
    if m:
        mmdd = sorted(x.strip() for x in m.group(1).split(","))
        out = []
        for ano in range(desde.year, ate.year + 2):
            for x in mmdd:
                d = date.fromisoformat(f"{ano}-{x}")
                if d < desde:
                    continue
                out.append(Periodo(d.isoformat(), d, d))
                if d > ate:
                    return out
        return out
    raise AgendaInvalida(f"agenda {agenda!r} não tem calendário fixo")


def periodo_de(agenda: str, dia: date) -> str:
    """Rótulo do período que uma execução feita em `dia` comprova."""
    validar(agenda)
    m = _FREQ.match(agenda)
    if m:
        freq = m.group(1)
        if freq == "semanal":
            ano, semana, _ = dia.isocalendar()
            return f"{ano}-W{semana:02d}"
        if freq == "quinzenal":
            return f"{dia:%Y-%m}-{'1Q' if dia.day <= 15 else '2Q'}"
        if freq == "mensal":
            return f"{dia:%Y-%m}"
        if freq == "trimestral":
            return f"{dia.year}-T{(dia.month - 1) // 3 + 1}"
        if freq == "semestral":
            return f"{dia.year}-S{1 if dia.month <= 6 else 2}"
        return f"{dia.year}"
    if agenda.startswith("datas:"):
        # a entrega vale para a próxima data fixa (a campanha em curso)
        return periodos(agenda, dia, dia)[0].rotulo
    return dia.isoformat()      # anos, meses, data, unica, evento: a data da execução


_PALAVRA_FREQ = {"semanal": "semanal", "quinzenal": "quinzenal", "mensal": "mensal",
                 "trimestral": "trimestral", "semestral": "semestral", "anual": "anual"}


def agenda_para(periodicidade: str, agenda_atual: str) -> str | None:
    """Uma norma nova muda a periodicidade em texto ('Semanal'); a agenda acompanha por regra,
    mantendo a folga de entrega. Só para agendas de calendário e quando o texto não deixa dúvida."""
    m = _FREQ.match(agenda_atual or "")
    if not m:
        return None
    t = (periodicidade or "").lower()
    achadas = {f for palavra, f in _PALAVRA_FREQ.items() if re.search(rf"\b{palavra}(?:mente)?\b", t)}
    if len(achadas) != 1:
        return None
    nova = f"{achadas.pop()}+{m.group(2)}d"
    return nova if nova != agenda_atual else None


_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro"]


def rotulo_humano(periodo: str) -> str:
    """'2026-10-1Q' -> '1ª quinzena de outubro/2026'; datas viram DD/MM/AAAA."""
    if m := re.fullmatch(r"(\d{4})-(\d\d)-([12])Q", periodo):
        return f"{m.group(3)}ª quinzena de {_MESES[int(m.group(2)) - 1]}/{m.group(1)}"
    if m := re.fullmatch(r"(\d{4})-W(\d\d)", periodo):
        segunda = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
        return f"semana de {segunda:%d/%m/%Y}"
    if m := re.fullmatch(r"(\d{4})-(\d\d)", periodo):
        return f"{_MESES[int(m.group(2)) - 1]}/{m.group(1)}"
    if m := re.fullmatch(r"(\d{4})-T([1-4])", periodo):
        return f"{m.group(2)}º trimestre/{m.group(1)}"
    if m := re.fullmatch(r"(\d{4})-S([12])", periodo):
        return f"{m.group(2)}º semestre/{m.group(1)}"
    if re.fullmatch(r"\d{4}-\d\d-\d\d", periodo):
        return date.fromisoformat(periodo).strftime("%d/%m/%Y")
    if periodo == "primeira":
        return "primeira execução (nenhuma registrada)"
    if periodo == "unico":
        return "entrega única"
    return periodo


def situacao(agenda: str, evidencias: list[str], hoje: date, desde: date,
             prazo: str | None = None) -> Situacao:
    """Situação da obrigação em `hoje`, olhando os períodos desde `desde`.

    `evidencias` são os rótulos de período já comprovados; `prazo` (AAAA-MM-DD)
    é usado pela agenda "unica".
    """
    validar(agenda)
    if agenda == "unica":
        try:
            agenda = f"data:{date.fromisoformat(prazo or ''):%Y-%m-%d}"
        except ValueError:
            return Situacao(GATILHO, nota=f"prazo {prazo!r} não é data")
    feitos = set(evidencias)
    ultima = max(feitos) if feitos else None
    if agenda == "evento":
        return Situacao(GATILHO, ultima=ultima, nota="depende de gatilho")

    if m := re.match(r"^data:(.+)$", agenda):
        prazo = date.fromisoformat(m.group(1))
        p = Periodo("unico", prazo, prazo)
        if feitos:
            return Situacao(CUMPRIDA, ultima=ultima)
        if hoje > prazo:
            return Situacao(ATRASADA, faltando=[p])
        return Situacao(VENCE_LOGO if (prazo - hoje).days <= AVISO_DIAS else EM_DIA, proximo=p)

    if m := re.match(r"^(anos|meses):(\d+)$", agenda):
        n = int(m.group(2)) * (12 if m.group(1) == "anos" else 1)
        if not feitos:
            p = Periodo("primeira", desde, desde)
            return Situacao(ATRASADA, faltando=[p], nota="nenhuma execução registrada")
        vence = _somar_meses(date.fromisoformat(ultima), n)
        p = Periodo(vence.isoformat(), vence, vence)
        if hoje > vence:
            return Situacao(ATRASADA, faltando=[p], ultima=ultima)
        return Situacao(VENCE_LOGO if (vence - hoje).days <= AVISO_DIAS else EM_DIA,
                        proximo=p, ultima=ultima)

    ps = periodos(agenda, desde, hoje)
    vencidos = [p for p in ps if p.vence < hoje]
    faltando = [p for p in vencidos if p.rotulo not in feitos]
    proximo = next((p for p in ps if p.vence >= hoje and p.rotulo not in feitos), None)
    if faltando:
        return Situacao(ATRASADA, proximo, faltando, ultima)
    aviso = AVISO_DIAS_CURTO if agenda.startswith(("semanal", "quinzenal", "mensal")) else AVISO_DIAS
    if proximo and (proximo.vence - hoje).days <= aviso:
        return Situacao(VENCE_LOGO, proximo, [], ultima)
    return Situacao(EM_DIA, proximo, [], ultima)
