"""Torre de controle: o que a interface mostra, calculado a partir do banco.

- painel():    "Hoje" — cada obrigação vigente de cada ativo, com status de agenda
- transicao(): o que entra e o que sai numa data de troca de norma (ex.: Res. 95 -> 220)
- mudancas():  versões pendentes (vindas de atos novos), com diferença, trecho e ativos afetados

Nada aqui escreve no banco; a interface só lê, e as decisões passam por db.decidir().
"""

from __future__ import annotations

import json
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
                s = agenda.situacao(v["agenda"], db.evidencias(conn, a["id"], o.codigo), hoje, ini,
                                    prazo=_prazo_unico(v))
                linha.status, linha.ultima, linha.nota = s.status, s.ultima, s.nota
                linha.vence = s.proximo.vence.isoformat() if s.proximo else None
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
