"""Mudanças de norma (aprovar, corrigir, rejeitar) e o radar do DOU (triagem -> IA -> Python)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from regulaia import db, demo, impacto, torre

from .. import auditoria
from ..banco import conexao, roteador
from ..seguranca import Escopo, decide_normas, regulatorio

rota = APIRouter(tags=["regulatório"])


class Mudanca(BaseModel):
    versao_id: int
    codigo: str
    titulo: str
    diferencas: dict[str, list] = Field(description="{campo: [vigente, proposto]}")
    ato: str | None
    publicado_em: str | None
    trecho: str | None
    fonte: str | None
    ativos: list[str]


class Decisao(BaseModel):
    aprovar: bool
    correcoes: dict[str, str | None] | None = Field(
        None, description="campos corrigidos por quem aprova antes de aprovar ({campo: valor})")


class Ato(BaseModel):
    identificacao: str = Field(examples=["RESOLUÇÃO ANM Nº 245, DE 31 DE JULHO DE 2026"])
    texto: str = Field(min_length=20, max_length=200_000)


@rota.get("/empresas/{empresa_id}/mudancas", response_model=list[Mudanca],
          summary="Mudanças propostas por atos novos, aguardando decisão")
def mudancas(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    visiveis = {a["codigo"] for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)}
    out = []
    for m in torre.mudancas(conn, empresa_id):
        if e.ve_tudo or set(m.ativos) & visiveis:
            d = asdict(m)
            d["diferencas"] = {k: list(v) for k, v in m.diferencas.items()}
            out.append(Mudanca(**d))
    return out


@rota.post("/mudancas/{versao_id}/decisao", summary="Aprovar (com correção opcional) ou rejeitar uma mudança")
def decidir(versao_id: int, dados: Decisao, request: Request, e: Escopo = Depends(decide_normas),
            conn=Depends(conexao)):
    try:
        db.decidir(conn, versao_id, aprovar=dados.aprovar, por=e.assinante, correcoes=dados.correcoes)
    except db.ErroCadastro as erro:
        auditoria.registrar(conn, request, "decisao", str(versao_id), dados.model_dump(), resultado="recusado")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "decisao", str(versao_id), dados.model_dump())
    return {"ok": True}


@rota.get("/radar", summary="O radar do DOU: funil do mês, análises e custo real da IA")
def radar(e: Escopo = Depends(regulatorio), request: Request = None):
    analises = json.loads(demo.RADAR.read_text(encoding="utf-8")) if demo.RADAR.exists() else []
    rot = roteador(request, com_ia=False)
    gastos = [dict(r) for r in rot.conn.execute(
        "SELECT tarefa, COUNT(*) AS n, COALESCE(SUM(custo_usd), 0) AS usd FROM analise_ia GROUP BY tarefa "
        "ORDER BY tarefa").fetchall()]
    return {"analises": analises, "custo_ia": gastos, "ia_ligada": roteador(request).ligada}


def _analisar(conn, request: Request, dados: Ato) -> impacto.Analise:
    rot = roteador(request)
    try:
        return impacto.analisar(conn, rot, dados.identificacao, dados.texto)
    except Exception as erro:       # sem chave e sem cache, ou provedor fora do ar
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"análise indisponível: {erro}") from None


@rota.post("/radar/analise", summary="Teste com um ato: triagem por regra, IA só nas candidatas, conferência do Python")
def analisar(dados: Ato, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    an = _analisar(conn, request, dados)
    auditoria.registrar(conn, request, "radar_analise", dados.identificacao[:120],
                        {"mudancas": len(an.mudancas), "custo_usd": an.custo_usd})
    return demo.registro_radar(an) | {"reprovadas": [asdict(m) for m in an.reprovadas]}


@rota.post("/radar/propor", summary="Mandar as mudanças aprovadas pelo Python para a fila de decisão")
def propor(dados: Ato, request: Request, e: Escopo = Depends(decide_normas), conn=Depends(conexao)):
    an = _analisar(conn, request, dados)
    if not an.aprovadas:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "nenhuma mudança passou na conferência")
    ident = "upload-" + hashlib.sha256(dados.texto.encode()).hexdigest()[:16]
    ato_id = db.registrar_ato(conn, "upload", ident, dados.identificacao, texto=dados.texto)
    try:
        versoes = impacto.aplicar(conn, an, ato_id)
    except db.ErroCadastro as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    auditoria.registrar(conn, request, "radar_propor", ident, {"versoes": versoes})
    return {"ato_id": ato_id, "versoes": versoes}
