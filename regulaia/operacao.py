"""Dia a dia da torre: o calendário do mês, a planilha para quem vive no Excel e o período
que uma entrega manual comprova. Funções puras sobre as linhas de torre.painel()."""

from __future__ import annotations

import calendar
import io
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from . import agenda, db, torre

_FIXA = ("semanal", "quinzenal", "mensal", "trimestral", "semestral", "anual", "datas:")


@dataclass
class Vencimento:
    dia: str              # AAAA-MM-DD
    linha: torre.Linha
    periodo: str          # rótulo do período que vence nesse dia
    entregue: bool


def vencimentos_no_mes(conn, linhas: list[torre.Linha], ano: int, mes: int) -> list[Vencimento]:
    """Tudo que vence no mês, período a período (não só o próximo vencimento de cada obrigação).
    Obrigação 'a cada N anos' e prazo único entram pelo vencimento que a torre calculou."""
    ini = date(ano, mes, 1)
    fim = date(ano, mes, calendar.monthrange(ano, mes)[1])
    out = []
    for l in linhas:
        if l.status in (agenda.GATILHO, torre.DADO_FALTANDO) or not l.agenda:
            continue
        if l.agenda.startswith(_FIXA):
            feitos = set(db.evidencias(conn, l.ativo_id, l.codigo)) if l.ativo_id else set()
            # períodos que terminam até 120 dias antes podem vencer neste mês (folga de +90d etc.)
            for p in agenda.periodos(l.agenda, ini - timedelta(days=120), fim):
                if ini <= p.vence <= fim:
                    out.append(Vencimento(p.vence.isoformat(), l, p.rotulo, p.rotulo in feitos))
        elif l.vence and ini.isoformat() <= l.vence <= fim.isoformat():
            out.append(Vencimento(l.vence, l, l.vence, l.status == agenda.CUMPRIDA))
    out.sort(key=lambda v: (v.dia, v.linha.ativo, v.linha.codigo))
    return out


def periodo_para_entrega(l: torre.Linha, dia: date) -> str:
    """O período que uma entrega feita em `dia` comprova: o primeiro que está faltando, se houver;
    senão o do próprio dia (para 'a cada N anos', a data da execução)."""
    if l.faltando and l.agenda.startswith(_FIXA):
        return l.faltando[0]
    return agenda.periodo_de(l.agenda, dia) if l.agenda and l.agenda != "evento" else dia.isoformat()


def tabela(linhas: list[torre.Linha]) -> pd.DataFrame:
    rotulo = {agenda.ATRASADA: "Atrasada", torre.DADO_FALTANDO: "Dado faltando", agenda.VENCE_LOGO: "Vence em breve",
              agenda.EM_DIA: "Em dia", agenda.CUMPRIDA: "Cumprida", agenda.GATILHO: "Por gatilho"}
    return pd.DataFrame([{
        "Status": rotulo.get(l.status, l.status),
        "Ativo": l.ativo,
        "Nome do ativo": l.ativo_nome,
        "Obrigação": l.titulo,
        "Código": l.codigo,
        "Norma": l.norma,
        "Dispositivo": torre.artigo_curto(l.norma, l.artigo),
        "Periodicidade": l.periodicidade,
        "Vencimento": date.fromisoformat(l.vence) if l.vence else None,
        "Última entrega": l.ultima,
        "Responsável": l.responsavel,
        "O que falta": torre.pendente(l) if l.status in (agenda.ATRASADA, torre.DADO_FALTANDO) else "",
        "Evidência": l.evidencia,
    } for l in linhas])


def planilha(linhas: list[torre.Linha], titulo: str) -> bytes:
    """Excel com uma aba de obrigações (com filtro e cabeçalho congelado) e uma de resumo."""
    df = tabela(linhas)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="Obrigações", index=False)
        resumo = (df.groupby(["Ativo", "Status"]).size().unstack(fill_value=0).reset_index()
                  if len(df) else pd.DataFrame())
        resumo.to_excel(xw, sheet_name="Resumo por ativo", index=False)
        ws = xw.sheets["Obrigações"]
        ws.auto_filter.ref = ws.dimensions
        ws.freeze_panes = "A2"
        for col, largura in zip("ABCDEFGHIJKLM", (14, 12, 28, 60, 9, 18, 14, 18, 12, 14, 26, 50, 40), strict=True):
            ws.column_dimensions[col].width = largura
        for c in ws["I"][1:]:
            c.number_format = "DD/MM/YYYY"
        xw.book.properties.title = titulo
    return buf.getvalue()
