"""Mudanças de norma (aprovar, corrigir, rejeitar) e o radar do DOU (triagem -> IA -> Python).

Quem decide depende de quem é a obrigação: mudança de norma pública (Res. ANM, NR...) é aprovada
pela curadoria da RegulaIA (plataforma), uma vez para todas as clientes; a cliente vê a mudança
como "aguardando curadoria RegulaIA". Obrigação própria de uma empresa (condicionante da licença,
TAC) é aprovada pelo Regulatório ou pela Diretoria dela."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from regulaia import db, demo, impacto, torre

from .. import auditoria
from ..banco import conexao, roteador
from ..seguranca import Escopo, curadoria, decide_normas, empresa_visivel, regulatorio

rota = APIRouter(tags=["regulatório"])

NORMA_PUBLICA, PROPRIA = "norma pública", "empresa"


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
    empresa: str | None = Field(description="dona da obrigação própria; vazio: norma pública")
    escopo: str = Field(description="'norma pública' (vale para todas as clientes) ou 'empresa' (só desta)")
    decide: bool = Field(description="se quem pede pode aprovar ou rejeitar esta mudança")
    quem_decide: str = Field(examples=["curadoria RegulaIA", "Regulatório ou Diretoria da Mineradora Serra Azul"])


class Decisao(BaseModel):
    aprovar: bool
    correcoes: dict[str, str | None] | None = Field(
        None, description="campos corrigidos por quem aprova antes de aprovar ({campo: valor})")


class Ato(BaseModel):
    identificacao: str = Field(examples=["RESOLUÇÃO ANM Nº 245, DE 31 DE JULHO DE 2026"])
    texto: str = Field(min_length=20, max_length=200_000)


def _quem_decide(dona: str | None) -> str:
    return "curadoria RegulaIA" if dona is None else f"Regulatório ou Diretoria da {dona}"


@rota.get("/empresas/{empresa_id}/mudancas", response_model=list[Mudanca],
          summary="Mudanças propostas por atos novos, aguardando decisão (da curadoria ou da empresa)")
def mudancas(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    visiveis = {a["codigo"] for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)}
    out = []
    for m in torre.mudancas(conn, empresa_id):
        if e.ve_tudo or set(m.ativos) & visiveis:
            d = asdict(m)
            d["diferencas"] = {k: list(v) for k, v in m.diferencas.items()}
            out.append(Mudanca(**d, escopo=NORMA_PUBLICA if m.empresa is None else PROPRIA,
                               decide=e.decide(m.empresa), quem_decide=_quem_decide(m.empresa)))
    return out


@rota.post("/mudancas/{versao_id}/decisao", summary="Aprovar (com correção opcional) ou rejeitar uma mudança")
def decidir(versao_id: int, dados: Decisao, request: Request, e: Escopo = Depends(decide_normas),
            conn=Depends(conexao)):
    r = conn.execute("SELECT o.empresa FROM obrigacao_versao v JOIN obrigacao o ON o.id = v.obrigacao_id "
                     "WHERE v.id = ?", (versao_id,)).fetchone()
    if r is None or not e.ve_obrigacao(r["empresa"]):     # a de outra cliente: 404, como se não existisse
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"mudança {versao_id} não existe")
    if not e.decide(r["empresa"]):
        auditoria.registrar(conn, request, "decisao", str(versao_id), dados.model_dump(), resultado="recusado")
        motivo = ("mudança de norma pública: quem aprova é a curadoria da RegulaIA, uma vez para todas as clientes"
                  if r["empresa"] is None else
                  f"obrigação própria da {r['empresa']}: quem aprova é o Regulatório ou a Diretoria dela")
        raise HTTPException(status.HTTP_403_FORBIDDEN, motivo)
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


def _analisar(conn, request: Request, dados: Ato, e: Escopo) -> impacto.Analise:
    rot = roteador(request)
    try:    # a cliente só analisa contra as normas públicas e as obrigações dela
        return impacto.analisar(conn, rot, dados.identificacao, dados.texto, empresa=None if e.plataforma else e.empresa)
    except Exception as erro:       # sem chave e sem cache, ou provedor fora do ar
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"análise indisponível: {erro}") from None


@rota.post("/radar/analise", summary="Teste com um ato: triagem por regra, IA só nas candidatas, conferência do Python")
def analisar(dados: Ato, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    an = _analisar(conn, request, dados, e)
    auditoria.registrar(conn, request, "radar_analise", dados.identificacao[:120],
                        {"mudancas": len(an.mudancas), "custo_usd": an.custo_usd})
    return demo.registro_radar(an) | {"reprovadas": [asdict(m) for m in an.reprovadas]}


@rota.post("/radar/propor", summary="Mandar as mudanças aprovadas pelo Python para a fila de decisão (curadoria)")
def propor(dados: Ato, request: Request, e: Escopo = Depends(curadoria), conn=Depends(conexao)):
    an = _analisar(conn, request, dados, e)
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
