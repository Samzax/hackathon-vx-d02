"""Leitor de evidências: o PDF da operação vira baixa na obrigação certa.

Dois passos, para uma pessoa conferir antes de gravar: `leitura` lê e devolve o que achou
(ativo, documento, período, gatilhos); `registro` grava a leitura conferida. Ler é aberto a quem vê
a empresa; registrar é só da própria empresa (a plataforma só lê)."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from regulaia import agenda, db, evidencias, ocr
from regulaia.ia import Roteador

from .. import armazenamento, auditoria
from ..banco import conexao, roteador
from ..config import hoje_padrao
from ..seguranca import Escopo, da_empresa, empresa_visivel, regulatorio

rota = APIRouter(prefix="/evidencias", tags=["evidências"])
LIMITE_BYTES = 20 * 1024 * 1024
EXEMPLOS = db.ROOT / "data" / "exemplos"


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


class Acionada(BaseModel):
    codigo: str
    titulo: str
    evidencia: str | None = Field(description="o documento que encerra a obrigação aberta")


class ResultadoLeitura(BaseModel):
    leitura: Leitura
    completa: bool
    arquivo: str
    guardado_em: str
    sha256: str
    periodo_rotulo: str | None = Field(None, description="o período comprovado, em português")
    abre: list[Acionada] = Field([], description="o que o registro abre no ativo, com prazo de 24 h (ex.: a ISE)")


class Registro(BaseModel):
    leitura: Leitura
    arquivo: str
    guardado_em: str | None = None


class Registrada(BaseModel):
    evidencia_id: int


class Exemplo(BaseModel):
    nome: str
    bytes: int


def _pode(conn, e: Escopo, empresa_id: int | None, codigo_ativo: str | None) -> None:
    if empresa_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "leitura sem empresa: leia o documento de novo")
    empresa_visivel(conn, e, empresa_id)      # a leitura de outra cliente: 404
    if e.ve_tudo or not codigo_ativo:
        return
    r = db.ativo_por_codigo(conn, empresa_id, codigo_ativo)
    if r is None or r["responsavel"] != e.area:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{codigo_ativo} é de outra área: quem registra é o gestor dele")


def _exemplos() -> list:
    return sorted(EXEMPLOS.glob("*.pdf")) if EXEMPLOS.exists() else []


@rota.get("/exemplos", response_model=list[Exemplo], summary="Documentos de exemplo (fictícios) para testar o leitor")
def exemplos(e: Escopo = Depends(regulatorio)):
    return [Exemplo(nome=p.name, bytes=p.stat().st_size) for p in _exemplos()]


@rota.get("/exemplos/{nome}", summary="Baixar um documento de exemplo")
def exemplo(nome: str, e: Escopo = Depends(regulatorio)):
    p = next((x for x in _exemplos() if x.name == nome), None)     # só o que está na lista: nada de caminho
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"exemplo {nome} não existe")
    return FileResponse(p, media_type="application/pdf", filename=p.name)


@rota.post("/leitura", response_model=ResultadoLeitura, summary="Ler um documento (PDF) sem gravar nada")
async def ler(request: Request, empresa_id: int, arquivo: UploadFile = File(...), hoje: date | None = None,
              e: Escopo = Depends(regulatorio), conn=Depends(conexao), rot: Roteador = Depends(roteador)):
    empresa_visivel(conn, e, empresa_id)
    dados = await arquivo.read(LIMITE_BYTES + 1)
    if len(dados) > LIMITE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "documento maior que 20 MB")
    try:        # páginas escaneadas vão para o OCR, se houver (REGULAIA_OCR=textract)
        lido = ocr.ler(dados)
    except Exception as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, evidencias.por_que_nao_abre(erro)) from None
    le = evidencias.ler(conn, lido.texto, empresa_id, hoje or hoje_padrao(), rot)
    if lido.ocr:
        le.avisos.append(f"o texto de {lido.escaneadas} página(s) escaneada(s) veio do OCR ({lido.ocr}): "
                         "confira ativo, data e números antes de registrar")
    elif lido.aviso and not "".join(lido.texto.split()):
        le.problemas = [lido.aviso]
    elif lido.aviso:
        le.avisos.append(lido.aviso)
    sha = hashlib.sha256(dados).hexdigest()
    nome = arquivo.filename or "documento.pdf"
    guardado = armazenamento.guardar(request.app.state.cfg, sha, nome, dados)
    auditoria.registrar(conn, request, "evidencia_leitura", nome,
                        {"ativo": le.ativo, "obrigacao": le.obrigacao, "periodo": le.periodo, "sha256": sha})
    abre = []
    dona = conn.execute("SELECT nome FROM empresa WHERE id = ?", (empresa_id,)).fetchone()["nome"]
    for c in (c for c in le.acionar if c != le.obrigacao):
        v = db.versao(conn, c, empresa=dona) or {}
        abre.append(Acionada(codigo=c, titulo=v.get("titulo") or c, evidencia=v.get("evidencia")))
    return ResultadoLeitura(leitura=Leitura(**asdict(le)), completa=le.completa, arquivo=nome, guardado_em=guardado,
                            sha256=sha, periodo_rotulo=agenda.rotulo_humano(le.periodo) if le.periodo else None,
                            abre=abre)


@rota.post("/registro", status_code=201, response_model=Registrada,
           summary="Gravar a leitura conferida: dá baixa e abre o que o documento acionou")
def registrar(dados: Registro, request: Request, e: Escopo = Depends(da_empresa), conn=Depends(conexao)):
    _pode(conn, e, dados.leitura.empresa_id, dados.leitura.ativo)
    le = evidencias.Leitura(**dados.leitura.model_dump())
    try:
        eid = evidencias.registrar(conn, le, dados.arquivo, dados.guardado_em)
    except (ValueError, db.ErroCadastro) as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "evidencia_registro", dados.arquivo,
                        {"ativo": le.ativo, "obrigacao": le.obrigacao, "periodo": le.periodo, "acionar": le.acionar})
    return Registrada(evidencia_id=eid)
