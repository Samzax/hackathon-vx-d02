"""Sessão, CSRF, papéis e o escopo do que cada pessoa vê.

- Sessão: cookie HttpOnly com um token aleatório de 256 bits; no banco fica só o SHA-256.
- CSRF: double submit. O login devolve também um cookie legível `regulaia_csrf`, e toda
  escrita (POST/PUT/PATCH/DELETE) precisa mandar o mesmo valor no cabeçalho X-CSRF-Token.
- Papel: TI só administra contas; Diretoria e Regulatório veem tudo; gestor vê a própria área.
- Conta de teste (demo e pitch): escolhe a visão (Diretoria, uma área ou TI) e age como ela.
- Token de serviço (Bearer): o agente MCP e os jobs agem como Regulatório, sem cookie.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response, status

from regulaia import usuarios

from .banco import conexao
from .config import Config

COOKIE_SESSAO = "regulaia_sessao"
COOKIE_CSRF = "regulaia_csrf"
CABECALHO_CSRF = "X-CSRF-Token"
VISAO_DIRETORIA = "Diretoria (todos os ativos)"
VISAO_TI = "TI (usuários e acessos)"
_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(frozen=True)
class Escopo:
    """Quem está agindo e o que pode ver: vem da conta e, na conta de teste, da visão escolhida."""
    usuario: dict
    papel: str               # papel efetivo (na conta de teste, o da visão)
    area: str | None         # gestor: a área que ele vê
    visao: str
    assinante: str           # o nome que fica no histórico ("por")

    @property
    def ve_tudo(self) -> bool:
        return self.papel in usuarios.VE_TUDO

    @property
    def admin(self) -> bool:
        return self.papel == usuarios.ADMIN

    def ve_ativo(self, ativo: dict) -> bool:
        return self.ve_tudo or (self.area is not None and ativo.get("responsavel") == self.area)

    def ve_linha(self, linha, dono_do_ativo: str | None) -> bool:
        return self.ve_tudo or (self.area is not None and self.area in (linha.responsavel, dono_do_ativo))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def abrir_sessao(conn, cfg: Config, resposta: Response, usuario: dict) -> str:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    expira = _agora() + timedelta(hours=cfg.horas_sessao)
    visao = VISAO_DIRETORIA if usuario["teste"] else None
    with conn:
        conn.execute("DELETE FROM sessao WHERE expira_em < ?", (_fmt(_agora()),))
        conn.execute("INSERT INTO sessao (token_hash, usuario_id, expira_em, visao) VALUES (?, ?, ?, ?)",
                     (_hash(token), usuario["id"], _fmt(expira), visao))
    usuarios.registrar_acesso(conn, usuario["id"])
    idade = cfg.horas_sessao * 3600
    resposta.set_cookie(COOKIE_SESSAO, token, max_age=idade, httponly=True, secure=cfg.cookie_seguro,
                        samesite="lax", path="/")
    resposta.set_cookie(COOKIE_CSRF, csrf, max_age=idade, httponly=False, secure=cfg.cookie_seguro,
                        samesite="lax", path="/")
    return csrf


def fechar_sessao(conn, request: Request, resposta: Response) -> None:
    if token := request.cookies.get(COOKIE_SESSAO):
        with conn:
            conn.execute("DELETE FROM sessao WHERE token_hash = ?", (_hash(token),))
    resposta.delete_cookie(COOKIE_SESSAO, path="/")
    resposta.delete_cookie(COOKIE_CSRF, path="/")


def _sessao(conn, token: str) -> dict | None:
    r = conn.execute("SELECT * FROM sessao WHERE token_hash = ?", (_hash(token),)).fetchone()
    if r is None or r["expira_em"] < _fmt(_agora()):
        return None
    return dict(r)


def _conta_servico(conn) -> dict:
    return {"id": 0, "email": "servico@regulaia", "nome": "Agente RegulaIA", "papel": usuarios.REGULATORIO,
            "area": None, "teste": 0, "ativa": 1}


def escopo(request: Request, conn=Depends(conexao)) -> Escopo:
    cfg: Config = request.app.state.cfg
    autorizacao = request.headers.get("authorization", "")
    if cfg.token_servico and autorizacao.startswith("Bearer "):
        if hmac.compare_digest(autorizacao[7:].strip(), cfg.token_servico):
            u = _conta_servico(conn)
            request.state.usuario = u["email"]
            return Escopo(u, u["papel"], None, "serviço", u["nome"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token de serviço inválido")
    token = request.cookies.get(COOKIE_SESSAO)
    sessao = _sessao(conn, token) if token else None
    if sessao is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "entre na torre para continuar")
    if request.method in _ESCRITA:
        enviado = request.headers.get(CABECALHO_CSRF, "")
        esperado = request.cookies.get(COOKIE_CSRF, "")
        if not enviado or not hmac.compare_digest(enviado, esperado):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "falta o cabeçalho X-CSRF-Token")
    r = conn.execute("SELECT * FROM usuario WHERE id = ?", (sessao["usuario_id"],)).fetchone()
    if r is None or not r["ativa"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "conta desativada")
    u = {k: r[k] for k in r.keys() if k != "senha"}
    request.state.usuario = u["email"]
    request.state.sessao = sessao["token_hash"]
    if u["teste"]:
        visao = sessao["visao"] or VISAO_DIRETORIA
        if visao == VISAO_DIRETORIA:
            return Escopo(u, usuarios.DIRETORIA, None, visao, visao)
        if visao == VISAO_TI:
            return Escopo(u, usuarios.ADMIN, None, visao, visao)
        return Escopo(u, usuarios.GESTOR, visao, visao, visao)
    if u["papel"] == usuarios.GESTOR:
        return Escopo(u, u["papel"], u["area"], u["area"] or "", u["nome"])
    rotulo = {usuarios.DIRETORIA: VISAO_DIRETORIA, usuarios.REGULATORIO: "Regulatório (todos os ativos)",
              usuarios.ADMIN: VISAO_TI}[u["papel"]]
    return Escopo(u, u["papel"], None, rotulo, u["nome"])


def regulatorio(e: Escopo = Depends(escopo)) -> Escopo:
    """Dado regulatório: todo mundo menos a TI."""
    if e.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "a TI administra contas e não vê dado regulatório")
    return e


def decide_normas(e: Escopo = Depends(regulatorio)) -> Escopo:
    if not e.ve_tudo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só Regulatório e Diretoria decidem mudanças de norma")
    return e


def diretoria(e: Escopo = Depends(regulatorio)) -> Escopo:
    if e.papel != usuarios.DIRETORIA:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só a Diretoria decide qual área responde por um ativo")
    return e


def ti(e: Escopo = Depends(escopo)) -> Escopo:
    if not e.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só a TI administra contas")
    return e
