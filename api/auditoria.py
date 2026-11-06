"""Trilha de auditoria: toda escrita da API fica registrada com quem, o quê, em quê e o resultado.

O histórico de negócio (evento, versões de obrigação) diz o que mudou na torre; a auditoria diz
quem chamou a API, de qual requisição, e também o que foi recusado. Cada linha leva a empresa
cliente de quem agiu (vazio: a plataforma); cada cliente vê só a própria trilha."""

from __future__ import annotations

import json

from fastapi import Request


def registrar(conn, request: Request, acao: str, alvo: str | None = None, detalhe: dict | None = None,
              resultado: str = "ok") -> None:
    with conn:
        conn.execute(
            "INSERT INTO auditoria (usuario, acao, alvo, detalhe, request_id, resultado, empresa) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (getattr(request.state, "usuario", None), acao, alvo,
             json.dumps(detalhe, ensure_ascii=False, default=str) if detalhe else None,
             getattr(request.state, "request_id", None), resultado, getattr(request.state, "empresa", None)))


def listar(conn, limite: int = 200, empresa: str | None = None, todas: bool = True) -> list[dict]:
    """A trilha mais recente primeiro. `todas=False`: só a da `empresa` (a de uma cliente)."""
    if todas:
        rows = conn.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM auditoria WHERE empresa = ? ORDER BY id DESC LIMIT ?",
                            (empresa, limite)).fetchall()
    return [dict(r) | {"detalhe": json.loads(r["detalhe"]) if r["detalhe"] else None} for r in rows]
