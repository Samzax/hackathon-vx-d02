"""O cadastro do ativo para quem preenche: nome de tela, tipo do campo e valores possíveis.

A tabela dos campos é do domínio (`regulaia/campos.py`): a instanciação confere com ela o que chega pelo
formulário e pela planilha. Aqui fica só o que a API mostra. Campo fora da lista continua editável como texto."""

from __future__ import annotations

from regulaia.campos import (BOOL, CAMPOS, DATA, NUMERO, OPCOES, TEXTO, VALORES, ValorInvalido, conferir,
                             pergunta, valor_legivel)

__all__ = ["BOOL", "CAMPOS", "DATA", "NUMERO", "OPCOES", "TEXTO", "VALORES", "ValorInvalido", "conferir",
           "pergunta", "valor"]


def valor(v) -> str:
    return valor_legivel(v)
