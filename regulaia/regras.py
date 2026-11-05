"""Regras de aplicabilidade: dizem se uma obrigação vale para um ativo.

A regra é um texto curto, legível por quem não programa:

    *                                   vale para todos os ativos do tipo
    trabalhadores_zas                   atributo verdadeiro
    dpa = alto                          igualdade (texto, número ou verdadeiro/falso)
    dpa2 > 4                            comparação numérica (>, <, >=, <=, !=)
    dpa2 > 4 e mapa_inundacao_validado  todas as condições ("e")

Atributo ausente no ativo nunca satisfaz a condição: na dúvida, a obrigação
não é atribuída em silêncio, e a torre mostra o dado que falta (ver faltantes()).
"""

from __future__ import annotations

import operator
import re

_OPS = {
    ">=": operator.ge,
    "<=": operator.le,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    "=": operator.eq,
}
# O valor é uma palavra só (alto, 4, 2.5); "dpa2 > 4 ou x" é erro, não o texto "4 ou x".
_COND = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*(?:(>=|<=|!=|>|<|=)\s*([^\s]+))?\s*$")


class RegraInvalida(ValueError):
    pass


def _partes(regra: str) -> list[tuple[str, str | None, str | None]]:
    regra = regra.strip()
    if regra == "*":
        return []
    partes = []
    for trecho in re.split(r"\s+e\s+", regra):
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
    _partes(regra)


def faltantes(regra: str, atributos: dict) -> list[str]:
    """Atributos que a regra usa e o ativo não informa."""
    return [campo for campo, _, _ in _partes(regra) if atributos.get(campo) is None]


def aplica(regra: str, atributos: dict) -> bool:
    for campo, op, alvo in _partes(regra):
        atual = atributos.get(campo)
        if atual is None:
            return False
        if op is None:
            if not bool(atual):
                return False
            continue
        a, b = _normaliza(atual), _valor(alvo)
        if isinstance(a, float) != isinstance(b, float):
            # comparar número com texto é erro de cadastro, não "falso"
            raise RegraInvalida(f"{campo}: {atual!r} não se compara com {alvo!r}")
        if not _OPS[op](a, b):
            return False
    return True
