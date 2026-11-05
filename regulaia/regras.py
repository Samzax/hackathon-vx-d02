"""Regras de aplicabilidade: dizem se uma obrigação vale para um ativo.

A regra é um texto curto, legível por quem não programa:

    *                                   vale para todos os ativos do tipo
    trabalhadores_zas                   atributo verdadeiro
    dpa = alto                          igualdade (texto, número ou verdadeiro/falso)
    dpa2 > 4                            comparação numérica (>, <, >=, <=, !=)
    dpa2 > 4 e mapa_inundacao_validado  todas as condições ("e")
    dpa = alto ou dpa2 >= 4             basta uma ("ou"); "e" vale antes de "ou":
                                        "a e b ou c" é "(a e b) ou c"

Atributo ausente no ativo nunca satisfaz a condição: na dúvida, a obrigação
não é atribuída em silêncio, e a torre mostra o dado que falta (ver faltantes()).
"""

from __future__ import annotations

import operator
import re
from functools import lru_cache

_OPS = {
    ">=": operator.ge,
    "<=": operator.le,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    "=": operator.eq,
}
# O valor é uma palavra só (alto, 4, 2.5): em "dpa2 > 4 ou x", "ou" separa duas condições.
_COND = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*(?:(>=|<=|!=|>|<|=)\s*([^\s]+))?\s*$")


class RegraInvalida(ValueError):
    pass


Condicao = tuple[str, str | None, str | None]


@lru_cache(maxsize=1024)
def _grupos(regra: str) -> tuple[tuple[Condicao, ...], ...]:
    """'a e b ou c' -> ((a, b), (c,)); '*' -> ((),) (um grupo vazio, que sempre vale).
    Cada regra é lida uma vez só: o painel avalia milhares de vezes as mesmas poucas regras."""
    regra = regra.strip()
    if regra == "*":
        return ((),)
    return tuple(tuple(_partes(g, regra)) for g in re.split(r"\s+ou\s+", regra))


def _partes(grupo: str, regra: str) -> list[Condicao]:
    partes = []
    for trecho in re.split(r"\s+e\s+", grupo):
        m = _COND.match(trecho)
        if not m:
            raise RegraInvalida(f"condição inválida: {trecho!r} em {regra!r}")
        campo, op, alvo = m.groups()
        if op in (">", "<", ">=", "<=") and not isinstance(_valor(alvo), float):
            raise RegraInvalida(f"{trecho!r}: maior/menor só com número")
        partes.append((campo, op, alvo))
    return partes


_BOOL = {"verdadeiro": True, "true": True, "sim": True, "falso": False, "false": False, "nao": False}


def _valor(texto: str):
    try:
        return float(texto)
    except ValueError:
        t = texto.strip().lower()
        return _BOOL.get(t, t)


def _normaliza(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return _valor(v)
    return v


def validar(regra: str) -> None:
    _grupos(regra)


def _vale(cond: Condicao, atributos: dict) -> bool | None:
    """True/False, ou None se o ativo não informa o atributo."""
    campo, op, alvo = cond
    atual = atributos.get(campo)
    if atual is None:
        return None
    if op is None:
        return bool(atual)
    a, b = _normaliza(atual), _valor(alvo)
    if isinstance(a, float) != isinstance(b, float):
        # comparar número com texto é erro de cadastro, não "falso"
        raise RegraInvalida(f"{campo}: {atual!r} não se compara com {alvo!r}")
    return _OPS[op](a, b)


def faltantes(regra: str, atributos: dict) -> list[str]:
    """Atributos que o ativo não informa e de que a decisão depende. Se a regra já vale,
    ou se cada alternativa já falha por um dado conhecido, nada falta."""
    if aplica(regra, atributos):
        return []
    falta: list[str] = []
    for grupo in _grupos(regra):
        valores = [_vale(c, atributos) for c in grupo]
        if False in valores:
            continue           # esta alternativa já não vale, com ou sem o dado que falta
        falta += [c[0] for c, v in zip(grupo, valores) if v is None and c[0] not in falta]
    return falta


def aplica(regra: str, atributos: dict) -> bool:
    return any(all(_vale(c, atributos) is True for c in grupo) for grupo in _grupos(regra))


def campos(regra: str) -> set[str]:
    """Atributos que a regra usa."""
    return {c for grupo in _grupos(regra) for c, _, _ in grupo}
