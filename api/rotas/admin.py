"""Contas (TI), auditoria, SIGBM, mercado e a demo."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from regulaia import db, demo, sigbm, usuarios

from .. import auditoria
from ..banco import conexao
from ..seguranca import Escopo, decide_normas, escopo, regulatorio, ti

rota = APIRouter(tags=["administração"])


class Conta(BaseModel):
    email: str
    nome: str
    papel: str = Field(pattern="^(admin|diretoria|regulatorio|gestor)$")
    area: str | None = None
    senha: str | None = Field(None, min_length=usuarios.SENHA_MINIMA)


class Edicao(BaseModel):
    nome: str | None = None
    papel: str | None = Field(None, pattern="^(admin|diretoria|regulatorio|gestor)$")
    area: str | None = None
    ativa: bool | None = None


class Senha(BaseModel):
    senha: str = Field(min_length=usuarios.SENHA_MINIMA)


class Importacao(BaseModel):
    cnpj: str = Field(description="CNPJ (só dígitos ou formatado) de uma empresa no SIGBM público")
    monitorado_desde: date


@rota.get("/usuarios", summary="Contas (TI)")
def contas(e: Escopo = Depends(ti), conn=Depends(conexao)):
    return {"contas": usuarios.listar(conn), "areas": usuarios.areas(conn), "papeis": usuarios.PAPEIS}


@rota.post("/usuarios", status_code=201, summary="Criar conta (TI)")
def criar(dados: Conta, request: Request, e: Escopo = Depends(ti), conn=Depends(conexao)):
    try:
        uid = usuarios.criar(conn, dados.email, dados.nome, dados.papel, area=dados.area, senha=dados.senha,
                             por=e.assinante)
    except usuarios.ErroConta as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "conta_criada", dados.email, {"papel": dados.papel, "area": dados.area})
    return {"id": uid}


@rota.patch("/usuarios/{usuario_id}", summary="Mudar papel, área ou desativar (TI)")
def editar(usuario_id: int, dados: Edicao, request: Request, e: Escopo = Depends(ti), conn=Depends(conexao)):
    try:
        u = usuarios.editar(conn, usuario_id, **dados.model_dump(exclude_none=True))
    except usuarios.ErroConta as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "conta_editada", str(usuario_id), dados.model_dump(exclude_none=True))
    return u


@rota.put("/usuarios/{usuario_id}/senha", summary="Trocar a senha de uma conta (TI)")
def senha(usuario_id: int, dados: Senha, request: Request, e: Escopo = Depends(ti), conn=Depends(conexao)):
    try:
        usuarios.definir_senha(conn, usuario_id, dados.senha)
    except usuarios.ErroConta as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    with conn:      # senha nova derruba as sessões abertas da conta
        conn.execute("DELETE FROM sessao WHERE usuario_id = ?", (usuario_id,))
    auditoria.registrar(conn, request, "senha_trocada", str(usuario_id))
    return {"ok": True}


@rota.get("/auditoria", summary="Trilha de auditoria (Diretoria, Regulatório e TI)")
def trilha(limite: int = 200, e: Escopo = Depends(escopo), conn=Depends(conexao)):
    if not (e.ve_tudo or e.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "a auditoria é da Diretoria, do Regulatório e da TI")
    return auditoria.listar(conn, min(limite, 1000))


@rota.get("/sigbm/busca", summary="Buscar mineradora no SIGBM público (CNPJ ou nome)")
def buscar(termo: str, e: Escopo = Depends(regulatorio)):
    return [{"cnpj": x.cnpj, "nome": x.nome, "barragens": len(x.barragens), "na_pnsb": len(x.na_pnsb)}
            for x in sigbm.buscar(termo)]


@rota.post("/sigbm/importar", status_code=201, summary="Montar a torre de uma mineradora real a partir do SIGBM")
def importar(dados: Importacao, request: Request, e: Escopo = Depends(decide_normas), conn=Depends(conexao)):
    achadas = [x for x in sigbm.buscar(dados.cnpj, limite=1)]
    if not achadas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CNPJ não encontrado no SIGBM público")
    eid = sigbm.importar(conn, achadas[0], dados.monitorado_desde)
    auditoria.registrar(conn, request, "sigbm_importar", achadas[0].nome, {"empresa_id": eid})
    return {"empresa_id": eid}


@rota.get("/mercado", summary="Números de mercado do SIGBM (agregados, com fonte)")
def mercado(e: Escopo = Depends(regulatorio)):
    return json.loads((db.ROOT / "data" / "mercado_sigbm.json").read_text(encoding="utf-8"))


@rota.post("/demo/recriar", summary="Voltar a demo ao estado inicial (só a conta de teste)")
def recriar(request: Request, e: Escopo = Depends(escopo)):
    if not e.usuario["teste"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "só a conta de teste recria a demo")
    cfg = request.app.state.cfg
    demo.preparar(cfg.banco, cache=cfg.cache)
    return {"ok": True}
