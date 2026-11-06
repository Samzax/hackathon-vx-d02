"""Uma conexão por requisição, aberta e fechada aqui."""

from __future__ import annotations

from fastapi import Request

from regulaia import db
from regulaia.ia import Roteador


def conexao(request: Request):
    conn = db.conectar(request.app.state.cfg.banco)
    try:
        yield conn
    finally:
        conn.close()


def roteador(request: Request, com_ia: bool = True) -> Roteador:
    """IA só para o que a regra não resolve. Sem chave, só a regra e as respostas em cache."""
    cache = db.conectar(request.app.state.cfg.cache)
    if com_ia:
        try:
            return Roteador(cache)
        except Exception:
            pass
    return Roteador(cache, env={}, provedores={})
