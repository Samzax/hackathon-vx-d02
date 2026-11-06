"""Entrar, sair, quem sou eu e (na conta de teste) trocar de visão."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from regulaia import db, usuarios

from .. import auditoria
from ..banco import conexao
from ..seguranca import VISAO_DIRETORIA, VISAO_TI, Escopo, abrir_sessao, escopo, fechar_sessao

rota = APIRouter(prefix="/auth", tags=["auth"])


class Login(BaseModel):
    email: str = Field(examples=["diretoria@serraazul.example"])
    senha: str


class Visao(BaseModel):
    visao: str = Field(examples=[VISAO_DIRETORIA, "Gerência de Geotecnia", VISAO_TI])


class Eu(BaseModel):
    id: int
    email: str
    nome: str
    papel: str = Field(description="papel da conta: admin, diretoria, regulatorio ou gestor")
    papel_efetivo: str = Field(description="o papel com que a pessoa age agora (na conta de teste, o da visão)")
    area: str | None
    teste: bool
    visao: str
    visoes: list[str] = Field(description="visões que a conta pode escolher (só a conta de teste tem mais de uma)")
    csrf: str | None = None


def _eu(conn, e: Escopo, csrf: str | None = None) -> Eu:
    u = e.usuario
    visoes = [e.visao]
    if u["teste"]:
        areas = sorted({a["responsavel"] for emp in db.empresas(conn) for a in db.ativos(conn, emp["id"])
                        if a["responsavel"]} | set(db.responsaveis(conn).values()))
        visoes = [VISAO_DIRETORIA, *areas, VISAO_TI]
    return Eu(id=u["id"], email=u["email"], nome=u["nome"], papel=u["papel"], papel_efetivo=e.papel,
              area=u.get("area"), teste=bool(u["teste"]), visao=e.visao, visoes=visoes, csrf=csrf)


def _entrar(conn, request: Request, resposta: Response, u: dict) -> Eu:
    csrf = abrir_sessao(conn, request.app.state.cfg, resposta, u)
    request.state.usuario = u["email"]
    auditoria.registrar(conn, request, "login", u["email"])
    from ..seguranca import Escopo as _E
    visao = VISAO_DIRETORIA if u["teste"] else (u["area"] or "")
    papel = usuarios.DIRETORIA if u["teste"] else u["papel"]
    return _eu(conn, _E(u, papel, None if u["teste"] else u.get("area"), visao, u["nome"]), csrf)


@rota.post("/login", response_model=Eu, summary="Entrar com e-mail e senha")
def login(dados: Login, request: Request, resposta: Response, conn=Depends(conexao)):
    u = usuarios.autenticar(conn, dados.email, dados.senha)
    if u is None:
        request.state.usuario = dados.email.strip().lower()
        auditoria.registrar(conn, request, "login", dados.email, resultado="recusado")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "e-mail ou senha não conferem")
    return _entrar(conn, request, resposta, u)


@rota.post("/demo", response_model=Eu, summary="Entrar na demo com a conta de teste (sem senha)")
def entrar_demo(request: Request, resposta: Response, conn=Depends(conexao)):
    u = usuarios.conta_demo(conn)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "esta instalação não tem conta de demo")
    return _entrar(conn, request, resposta, u)


@rota.post("/logout", status_code=204, summary="Sair")
def logout(request: Request, resposta: Response, conn=Depends(conexao)):
    fechar_sessao(conn, request, resposta)
    resposta.status_code = 204
    return resposta


@rota.get("/me", response_model=Eu, summary="Quem está na sessão e com qual visão")
def eu(e: Escopo = Depends(escopo), conn=Depends(conexao)):
    return _eu(conn, e)


@rota.put("/visao", response_model=Eu, summary="Trocar de visão (só a conta de teste)")
def trocar_visao(dados: Visao, request: Request, e: Escopo = Depends(escopo), conn=Depends(conexao)):
    if not e.usuario["teste"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só a conta de teste troca de visão")
    if dados.visao not in _eu(conn, e).visoes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"visão desconhecida: {dados.visao}")
    with conn:
        conn.execute("UPDATE sessao SET visao = ? WHERE token_hash = ?", (dados.visao, request.state.sessao))
    auditoria.registrar(conn, request, "visao", dados.visao)
    return eu(escopo(request, conn), conn)
