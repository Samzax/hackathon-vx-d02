"""Entrar, sair, quem sou eu e (na conta de teste) trocar de visão."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from regulaia import usuarios

from .. import auditoria
from ..banco import conexao
from ..config import hoje_padrao
from ..seguranca import (VISAO_CURADORIA, VISAO_DIRETORIA, VISAO_TI, Escopo, abrir_sessao, areas_da_empresa,
                         empresa_da_conta, escopo, escopo_da_conta, fechar_sessao)

rota = APIRouter(prefix="/auth", tags=["auth"])


class Login(BaseModel):
    # max_length: a tentativa recusada vai inteira para a auditoria; sem teto, cada requisição anônima
    # gravaria o que o cliente mandasse (e-mail de 200 KB = linha de 400 KB na trilha)
    email: str = Field(examples=["diretoria@serraazul.example"], max_length=320)
    senha: str = Field(max_length=200)


class Visao(BaseModel):
    visao: str = Field(examples=[VISAO_DIRETORIA, "Gerência de Geotecnia", VISAO_TI, VISAO_CURADORIA])


class Eu(BaseModel):
    id: int
    email: str
    nome: str
    papel: str = Field(description="papel da conta: admin, diretoria, regulatorio ou gestor")
    papel_efetivo: str = Field(description="o papel com que a pessoa age agora (na conta de teste, o da visão)")
    area: str | None
    teste: bool
    empresa: str | None = Field(description="a empresa cliente que a sessão vê; vazio na plataforma (vê todas)")
    plataforma: bool = Field(description="age como a equipe da RegulaIA (curadoria das normas públicas)")
    so_leitura: bool = Field(description="nos dados operacionais das clientes (entrega, comprovante, evidência, "
                                         "comentário, atribuição, cadastro e responsável do ativo) a sessão só lê")
    visao: str
    visoes: list[str] = Field(description="visões que a conta pode escolher (só a conta de teste tem mais de uma)")
    hoje: str = Field(description="o hoje da torre (na demo, 7/11/2026): o padrão de toda consulta sem `hoje`")
    csrf: str | None = None


def _eu(conn, e: Escopo, csrf: str | None = None) -> Eu:
    u = e.usuario
    visoes = [e.visao]
    if u["teste"]:      # as áreas são as da empresa da conta, mesmo olhando como a curadoria
        visoes = [VISAO_DIRETORIA, *areas_da_empresa(conn, empresa_da_conta(conn, u)), VISAO_TI, VISAO_CURADORIA]
    return Eu(id=u["id"], email=u["email"], nome=u["nome"], papel=u["papel"], papel_efetivo=e.papel,
              area=u.get("area"), teste=bool(u["teste"]), empresa=e.empresa, plataforma=e.plataforma,
              so_leitura=e.so_leitura, visao=e.visao, visoes=visoes, hoje=hoje_padrao().isoformat(), csrf=csrf)


def _entrar(conn, request: Request, resposta: Response, u: dict) -> Eu:
    request.state.usuario = u["email"]
    request.state.empresa = None if u.get("plataforma") else u.get("empresa")
    try:
        e = escopo_da_conta(conn, u, VISAO_DIRETORIA if u["teste"] else None)
    except HTTPException:       # conta sem empresa (ou com empresa que não está na torre)
        auditoria.registrar(conn, request, "login", u["email"], resultado="recusado")
        raise
    csrf = abrir_sessao(conn, request.app.state.cfg, resposta, u)
    auditoria.registrar(conn, request, "login", u["email"])
    return _eu(conn, e, csrf)


@rota.post("/login", response_model=Eu, summary="Entrar com e-mail e senha")
def login(dados: Login, request: Request, resposta: Response, conn=Depends(conexao)):
    u = usuarios.autenticar(conn, dados.email, dados.senha)
    if u is None:
        request.state.usuario = dados.email.strip().lower()
        conta = usuarios.por_email(conn, dados.email)     # a tentativa fica na trilha da empresa da conta
        request.state.empresa = conta.get("empresa") if conta and not conta.get("plataforma") else None
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


@rota.get("/me", response_model=Eu, summary="Quem está na sessão, de qual empresa e com qual visão")
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
