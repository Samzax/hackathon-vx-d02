"""Servidor MCP da Mitra: um agente (Claude, ou qualquer cliente MCP) consulta a torre.

Só leitura. O agente explica, cruza e prioriza; quem decide é gente, na torre: aprovar mudança de norma,
registrar entrega e mexer no cadastro continuam nos botões, com nome na auditoria. A única ferramenta que
chama IA (`analisar_ato`) não grava nada: mostra o que mudaria e a conferência do Python.

As ferramentas estão em `agente/ferramentas.py` (as mesmas do "Pergunte à torre" do front); aqui elas só
ganham o embrulho do protocolo.

Uso:
    MITRA_TOKEN_SERVICO=... uv run python -m agente            # stdio (Claude Desktop)
    MITRA_TOKEN_SERVICO=... uv run python -m agente --http     # streamable HTTP na 8100
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .cliente import ErroTorre, Torre
from .ferramentas import CHAMA_IA, INSTRUCOES, PENDENTES, ferramentas

LEITURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
# analisar_ato não escreve na torre, mas chama a IA (gasta dinheiro e grava a resposta no cache):
# readOnlyHint=False para o cliente MCP pedir confirmação em vez de executar como leitura
CHAMA_A_IA = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)


def _erro_de_ferramenta(fn: Callable) -> Callable:
    """Erro da torre vira ToolError: o protocolo devolve isError com a mensagem e a sessão continua."""
    @functools.wraps(fn)
    def embrulho(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ErroTorre as e:
            raise ToolError(str(e)) from e
    return embrulho


def criar_servidor(torre: Torre) -> MCPServer:
    mcp = MCPServer(name="Mitra", title="Mitra: torre de controle regulatória",
                    instructions=INSTRUCOES, version="1.0.0")
    for fn in ferramentas(torre):
        mcp.add_tool(_erro_de_ferramenta(fn), name=fn.__name__,
                     annotations=CHAMA_A_IA if fn.__name__ in CHAMA_IA else LEITURA)
    return mcp


__all__ = ["ErroTorre", "PENDENTES", "Torre", "criar_servidor"]
