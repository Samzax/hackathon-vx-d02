"""Licenças e condicionantes: o PDF da licença virando obrigações próprias da empresa.

Dois passos, como no leitor de evidências, para uma pessoa conferir antes de valer:
1. `POST /empresas/{id}/licencas` guarda o PDF e o texto lido; `POST /licencas/{id}/leitura` manda o
   texto à IA, que propõe as condicionantes **com o trecho literal**, e o Python confere o trecho
   palavra por palavra. O que não passa não entra nem como proposta.
2. As propostas ficam pendentes. Quem aprova ou rejeita é o **Regulatório ou a Diretoria da própria
   empresa** (`seguranca.da_empresa` + `ve_tudo`): a plataforma não decide obrigação da cliente.
   Aprovada, vira obrigação própria vigente, com código único por empresa.

A validade da licença vira obrigação de renovação (`POST /licencas/{id}/renovacao`).
Dado pessoal não vai para a IA: o texto enviado passa por `pessoal.sem_cpf` no domínio.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from regulaia import evidencias as ev, licencas as dominio, ocr
from regulaia.ia import Roteador

from .. import armazenamento, auditoria
from ..banco import conexao, roteador
from ..seguranca import Escopo, da_empresa, empresa_visivel, regulatorio

rota = APIRouter(tags=["licenças"])
LIMITE_BYTES = 20 * 1024 * 1024


class Licenca(BaseModel):
    id: int
    tipo: str = Field(description="LP, LI, LO, LAC, outorga ou autorizacao")
    numero: str
    orgao: str | None
    emitida_em: str | None
    validade: str | None = Field(description="AAAA-MM-DD; vira obrigação de renovação")
    renovar_dias: int = Field(description="quantos dias antes do vencimento pedir a renovação")
    unidade: str | None
    ativo_codigo: str | None
    arquivo: str | None
    sha256: str | None
    enviada_por: str
    enviada_em: str
    condicionantes: dict[str, int] = Field(description="quantas condicionantes em cada status")


class Nova(BaseModel):
    tipo: str = Field(pattern="^(LP|LI|LO|LAC|outorga|autorizacao)$")
    numero: str = Field(min_length=1, max_length=60)
    orgao: str | None = Field(None, max_length=200)
    emitida_em: str | None = Field(None, description="AAAA-MM-DD")
    validade: str | None = Field(None, description="AAAA-MM-DD")
    renovar_dias: int = Field(dominio.RENOVACAO_PADRAO, ge=1, le=1095)
    unidade: str | None = None
    ativo_codigo: str | None = None


class Condicionante(BaseModel):
    id: int
    licenca_id: int
    licenca: str = Field(description="a licença de onde ela veio", examples=["LO 123/2026"])
    titulo: str
    prazo: str | None
    periodicidade: str | None
    agenda: str | None = Field(description="a agenda que a torre usa (ver regulaia/agenda.py)")
    evidencia: str | None
    aplica_a: str | None = Field(description="empresa, unidade ou ativo")
    alvo: str | None
    trecho: str = Field(description="o texto literal da licença, conferido palavra por palavra")
    pagina: int | None = Field(description="em que página do PDF está o trecho")
    status: str = Field(description="pendente, aprovada ou rejeitada")
    codigo: str | None = Field(description="a obrigação criada na aprovação")
    proposta_em: str
    decidida_por: str | None
    decidida_em: str | None
    decide: bool = Field(description="se quem pede pode aprovar ou rejeitar")
    quem_decide: str = Field(examples=["Regulatório ou Diretoria da Mineradora Serra Azul"])


class Reprovada(BaseModel):
    titulo: str
    motivo: str = Field(description="por que o Python não aceitou a proposta da IA")


class Leitura(BaseModel):
    licenca_id: int
    propostas: list[Condicionante] = Field(description="as que passaram na conferência e ficaram pendentes")
    reprovadas: list[Reprovada] = Field(description="o que a IA propôs e o Python recusou (não entra)")
    validade_lida: str | None = Field(description="a validade que a IA achou no texto, para conferir")
    numero_lido: str | None
    orgao_lido: str | None
    modelo: str | None
    custo_usd: float
    problemas: list[str] = []


class Decisao(BaseModel):
    aprovar: bool
    correcoes: dict[str, str | None] | None = Field(None, description=(
        "o que quem aprova corrigiu antes (titulo, prazo, periodicidade, agenda, evidencia, aplica_a, alvo)"))
    nota: str | None = Field(None, max_length=2000)


class Decidida(BaseModel):
    status: str
    codigo: str | None = Field(description="o código da obrigação criada, quando aprovada")


class Renovacao(BaseModel):
    codigo: str | None = Field(description="a obrigação de renovar; vazio se a licença não tem validade")


def _quem_decide(empresa: str) -> str:
    return f"Regulatório ou Diretoria da {empresa}"


def _condicionante(c: dict, e: Escopo, empresa: str) -> Condicionante:
    return Condicionante(
        **{k: c[k] for k in ("id", "licenca_id", "titulo", "prazo", "periodicidade", "agenda", "evidencia",
                             "aplica_a", "alvo", "trecho", "pagina", "status", "codigo", "proposta_em",
                             "decidida_por", "decidida_em")},
        licenca=f"{c['licenca_tipo']} {c['licenca_numero']}",
        decide=bool(c["status"] == dominio.PENDENTE and e.ve_tudo and not e.so_leitura),
        quem_decide=_quem_decide(empresa))


def _erro(erro: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro))


# ------------------------------------------------------------------ a licença


@rota.get("/empresas/{empresa_id}/licencas", response_model=list[Licenca],
          summary="As licenças da empresa, com a contagem de condicionantes por status")
def listar(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    return [Licenca(**{k: v for k, v in x.items() if k not in ("empresa_id", "guardado_em")})
            for x in dominio.licencas(conn, empresa_id)]


@rota.post("/empresas/{empresa_id}/licencas", status_code=201, response_model=Licenca,
           summary="Enviar o PDF da licença (a própria empresa): o texto fica para conferir os trechos")
async def enviar(empresa_id: int, request: Request, tipo: str, numero: str,
                 arquivo: UploadFile = File(...), orgao: str | None = None,
                 emitida_em: str | None = None, validade: str | None = None,
                 renovar_dias: int = dominio.RENOVACAO_PADRAO, unidade: str | None = None,
                 ativo_codigo: str | None = None, e: Escopo = Depends(da_empresa),
                 conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    dados = await arquivo.read(LIMITE_BYTES + 1)
    if len(dados) > LIMITE_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "a licença é maior que 20 MB")
    if not dados:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "arquivo vazio")
    try:
        lido = ocr.ler(dados)
    except Exception as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, ev.por_que_nao_abre(erro)) from None
    sha = hashlib.sha256(dados).hexdigest()
    nome = arquivo.filename or "licenca.pdf"
    guardado = armazenamento.guardar(request.app.state.cfg, sha, nome, dados)
    try:
        lid = dominio.guardar_licenca(conn, empresa_id, tipo=tipo, numero=numero, por=e.assinante,
                                      orgao=orgao, emitida_em=emitida_em, validade=validade,
                                      renovar_dias=renovar_dias, unidade=unidade,
                                      ativo_codigo=ativo_codigo, arquivo=nome, guardado_em=guardado,
                                      sha256=sha, texto=lido.texto)
    except dominio.ErroLicenca as erro:
        auditoria.registrar(conn, request, "licenca_enviada", f"{tipo} {numero}", {"sha256": sha},
                            resultado="recusado")
        raise _erro(erro) from None
    auditoria.registrar(conn, request, "licenca_enviada", f"{tipo} {numero}",
                        {"sha256": sha, "paginas": lido.paginas, "escaneadas": lido.escaneadas})
    x = next(y for y in dominio.licencas(conn, empresa_id) if y["id"] == lid)
    return Licenca(**{k: v for k, v in x.items() if k not in ("empresa_id", "guardado_em")})


@rota.post("/licencas/{licenca_id}/leitura", response_model=Leitura,
           summary="Ler a licença: a IA propõe as condicionantes e o Python confere o trecho literal")
def ler(licenca_id: int, empresa_id: int, request: Request, e: Escopo = Depends(da_empresa),
        conn=Depends(conexao), rot: Roteador = Depends(roteador)):
    emp = empresa_visivel(conn, e, empresa_id)
    lic = dominio.licenca(conn, empresa_id, licenca_id)
    if lic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"licença {licenca_id} não existe")
    le = dominio.ler(conn, rot, empresa_id, lic["texto"] or "")
    ids = dominio.propor(conn, empresa_id, licenca_id, le, e.assinante) if le.aprovadas else []
    auditoria.registrar(conn, request, "licenca_leitura", f"{lic['tipo']} {lic['numero']}",
                        {"propostas": len(ids), "reprovadas": len(le.propostas) - len(le.aprovadas),
                         "custo_usd": le.custo_usd})
    pendentes = {c["id"]: c for c in dominio.condicionantes(conn, empresa_id, licenca_id=licenca_id)}
    return Leitura(
        licenca_id=licenca_id,
        propostas=[_condicionante(pendentes[i], e, emp["nome"]) for i in ids if i in pendentes],
        reprovadas=[Reprovada(titulo=p.titulo, motivo=p.reprovada) for p in le.propostas if p.reprovada],
        validade_lida=le.validade, numero_lido=le.numero_licenca, orgao_lido=le.orgao,
        modelo=le.modelo, custo_usd=le.custo_usd, problemas=le.problemas)


# ------------------------------------------------------------------ as condicionantes


@rota.get("/empresas/{empresa_id}/condicionantes", response_model=list[Condicionante],
          summary="As condicionantes da empresa (propostas, aprovadas e rejeitadas)")
def condicionantes(empresa_id: int, status_: str | None = None, licenca_id: int | None = None,
                   e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    return [_condicionante(c, e, emp["nome"])
            for c in dominio.condicionantes(conn, empresa_id, status_, licenca_id)]


@rota.post("/condicionantes/{condicionante_id}/decisao", response_model=Decidida,
           summary="Aprovar (vira obrigação da empresa) ou rejeitar: só o Regulatório ou a Diretoria dela")
def decidir(condicionante_id: int, empresa_id: int, dados: Decisao, request: Request,
            e: Escopo = Depends(da_empresa), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    c = dominio.condicionante(conn, empresa_id, condicionante_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"condicionante {condicionante_id} não existe")
    if not e.ve_tudo:
        auditoria.registrar(conn, request, "condicionante_decisao", str(condicionante_id),
                            dados.model_dump(), resultado="recusado")
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "condicionante da licença: quem aprova é o Regulatório ou a Diretoria da empresa")
    try:
        if dados.aprovar:
            codigo = dominio.aprovar(conn, empresa_id, condicionante_id, e.assinante,
                                     correcoes=dados.correcoes, nota=dados.nota)
        else:
            dominio.rejeitar(conn, empresa_id, condicionante_id, e.assinante, nota=dados.nota)
            codigo = None
    except (dominio.ErroLicenca, ValueError) as erro:
        auditoria.registrar(conn, request, "condicionante_decisao", str(condicionante_id),
                            dados.model_dump(), resultado="recusado")
        raise _erro(erro) from None
    auditoria.registrar(conn, request, "condicionante_decisao", str(condicionante_id),
                        {"aprovar": dados.aprovar, "codigo": codigo, "correcoes": dados.correcoes})
    return Decidida(status="aprovada" if dados.aprovar else "rejeitada", codigo=codigo)


@rota.post("/licencas/{licenca_id}/renovacao", response_model=Renovacao,
           summary="A validade da licença vira obrigação: pedir a renovação com a antecedência dela")
def renovacao(licenca_id: int, empresa_id: int, request: Request, e: Escopo = Depends(da_empresa),
              conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    if not e.ve_tudo:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "criar a obrigação de renovação é do Regulatório ou da Diretoria da empresa")
    try:
        codigo = dominio.obrigacao_de_renovacao(conn, empresa_id, licenca_id, e.assinante)
    except dominio.ErroLicenca as erro:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(erro)) from None
    if codigo:
        auditoria.registrar(conn, request, "licenca_renovacao", str(licenca_id), {"codigo": codigo})
    return Renovacao(codigo=codigo)
