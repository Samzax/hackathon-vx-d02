"""Leitor de evidências: o PDF da operação vira baixa na obrigação certa.

Dois passos, para uma pessoa conferir antes de gravar: `leitura` lê e devolve o que achou
(ativo, documento, período, gatilhos); `registro` grava a leitura conferida."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from regulaia import db, evidencias

from .. import armazenamento, auditoria
from ..banco import conexao, roteador
from ..config import hoje_padrao
from ..seguranca import Escopo, empresa_visivel, regulatorio

rota = APIRouter(prefix="/evidencias", tags=["evidências"])
LIMITE_BYTES = 20 * 1024 * 1024


class Leitura(BaseModel):
    ativo: str | None = None
    empresa_id: int | None = None     # o código do ativo (B3) só é único dentro da empresa
    documento: str | None = None
    obrigacao: str | None = None
    data: str | None = None
    periodo: str | None = None
    pontuacao_maxima: int | None = None
    estado_conservacao: dict[str, int] = {}
    metodo: str = "regra"
    problemas: list[str] = []
    avisos: list[str] = []
    gatilhos: list[str] = []
    acionar: list[str] = []


class ResultadoLeitura(BaseModel):
    leitura: Leitura
    completa: bool
    arquivo: str
    guardado_em: str
    sha256: str


class Registro(BaseModel):
    leitura: Leitura
    arquivo: str
    guardado_em: str | None = None


def _pode(conn, e: Escopo, empresa_id: int | None, codigo_ativo: str | None) -> None:
    if empresa_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "leitura sem empresa: leia o documento de novo")
    empresa_visivel(conn, e, empresa_id)      # a leitura de outra cliente: 404
    if e.ve_tudo or not codigo_ativo:
        return
    r = db.ativo_por_codigo(conn, empresa_id, codigo_ativo)
    if r is None or r["responsavel"] != e.area:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{codigo_ativo} é de outra área: quem registra é o gestor dele")


@rota.post("/leitura", response_model=ResultadoLeitura, summary="Ler um documento (PDF) sem gravar nada")
async def ler(request: Request, empresa_id: int, arquivo: UploadFile = File(...), hoje: date | None = None,
              e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    dados = await arquivo.read(LIMITE_BYTES + 1)
    if len(dados) > LIMITE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "documento maior que 20 MB")
    try:
        texto = evidencias.texto_pdf(dados)
    except Exception as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, evidencias.por_que_nao_abre(erro)) from None
    le = evidencias.ler(conn, texto, empresa_id, hoje or hoje_padrao(), roteador(request))
    sha = hashlib.sha256(dados).hexdigest()
    guardado = armazenamento.guardar(request.app.state.cfg, sha, arquivo.filename or "documento.pdf", dados)
    auditoria.registrar(conn, request, "evidencia_leitura", arquivo.filename,
                        {"ativo": le.ativo, "obrigacao": le.obrigacao, "periodo": le.periodo, "sha256": sha})
    return ResultadoLeitura(leitura=Leitura(**asdict(le)), completa=le.completa,
                            arquivo=arquivo.filename or "documento.pdf", guardado_em=guardado, sha256=sha)


@rota.post("/registro", status_code=201, summary="Gravar a leitura conferida: dá baixa e abre o que o documento acionou")
def registrar(dados: Registro, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    _pode(conn, e, dados.leitura.empresa_id, dados.leitura.ativo)
    le = evidencias.Leitura(**dados.leitura.model_dump())
    try:
        eid = evidencias.registrar(conn, le, dados.arquivo, dados.guardado_em)
    except (ValueError, db.ErroCadastro) as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "evidencia_registro", dados.arquivo,
                        {"ativo": le.ativo, "obrigacao": le.obrigacao, "periodo": le.periodo, "acionar": le.acionar})
    return {"evidencia_id": eid}
