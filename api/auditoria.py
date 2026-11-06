"""Trilha de auditoria: toda escrita da API fica registrada com quem, o quê, em quê e o resultado.

O histórico de negócio (evento, versões de obrigação) diz o que mudou na torre; a auditoria diz
quem chamou a API, de qual requisição, e também o que foi recusado."""

from __future__ import annotations

import json

from fastapi import Request


def registrar(conn, request: Request, acao: str, alvo: str | None = None, detalhe: dict | None = None,
              resultado: str = "ok") -> None:
    with conn:
        conn.execute(
            "INSERT INTO auditoria (usuario, acao, alvo, detalhe, request_id, resultado) VALUES (?, ?, ?, ?, ?, ?)",
            (getattr(request.state, "usuario", None), acao, alvo,
             json.dumps(detalhe, ensure_ascii=False, default=str) if detalhe else None,
             getattr(request.state, "request_id", None), resultado))


def listar(conn, limite: int = 200) -> list[dict]:
    rows = conn.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    return [dict(r) | {"detalhe": json.loads(r["detalhe"]) if r["detalhe"] else None} for r in rows]
