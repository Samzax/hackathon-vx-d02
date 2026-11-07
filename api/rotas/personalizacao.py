"""Personalização da empresa: prazo interno, normas internas e responsável padrão por área.

Tudo aqui é da **própria empresa** (`seguranca.da_empresa` + `ve_tudo`): são as regras dela sobre o que
já vale, e a plataforma só lê. Nada disso muda a norma: o prazo legal continua o que a norma diz, e o
prazo interno é meta da empresa, que a torre mostra ao lado e cobra mais cedo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from mitra import personalizacao as dominio

from .. import auditoria
from ..banco import conexao
from ..seguranca import Escopo, da_empresa, empresa_visivel, regulatorio

rota = APIRouter(tags=["personalização"])


class PrazoInterno(BaseModel):
    codigo: str
    dias_antes: int = Field(description="quantos dias antes do prazo legal a empresa quer entregar")
    definido_por: str
    definido_em: str


class NovoPrazo(BaseModel):
    codigo: str = Field(max_length=40, examples=["R95-01"])
    dias_antes: int = Field(ge=0, le=dominio.LIMITE_DIAS,
                            description="0 tira a meta e volta a cobrar só pelo prazo legal")


class ResponsavelPadrao(BaseModel):
    area: str = Field(description="barragem, emergencia, ambiental, equipamento, seguranca_trabalho, "
                                  "documentacao ou comunicacao")
    responsavel: str = Field(description="vazio tira o padrão")


class NormaInterna(BaseModel):
    codigo: str
    norma: str
    area: str
    tipo_ativo: str
    titulo: str
    agenda: str | None
    periodicidade: str | None
    prazo: str | None
    evidencia: str | None
    responsavel: str | None
    vigencia_desde: str | None
    decidida_por: str | None
    decidida_em: str | None


class NovaNormaInterna(BaseModel):
    titulo: str = Field(min_length=3, max_length=300, examples=["Inspeção interna mensal da pilha"])
    tipo_ativo: str = Field("barragem", pattern="^(barragem|unidade|equipamento|licenca|obra)$")
    area: str = Field("documentacao")
    agenda: str = Field("evento", description="a agenda da torre (mensal+10d, anos:3, evento...)")
    periodicidade: str | None = Field(None, examples=["Mensal"])
    prazo: str | None = Field(None, examples=["Até 10 dias após o fim do mês"])
    evidencia: str | None = Field(None, examples=["Relatório interno assinado"])
    aplica_se_a: str = Field("todos os ativos do tipo")
    regra: str = Field("*", description="a regra de aplicabilidade (ver mitra/regras.py)")
    norma: str = Field("Padrão interno", max_length=120)
    vigencia_desde: str | None = Field(None, description="AAAA-MM-DD; vazio: vale desde já")


class Criada(BaseModel):
    codigo: str


class Ok(BaseModel):
    ok: bool


class Personalizacao(BaseModel):
    prazos_internos: list[PrazoInterno]
    responsaveis_padrao: dict[str, str] = Field(description="{área: responsável}")
    normas_internas: list[NormaInterna]
    areas: list[str] = Field(description="as áreas que uma obrigação pode ter")


def _da_propria_empresa(e: Escopo) -> None:
    if not e.ve_tudo:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "as regras próprias da empresa são do Regulatório ou da Diretoria dela")


@rota.get("/empresas/{empresa_id}/personalizacao", response_model=Personalizacao,
          summary="As regras próprias da empresa: prazo interno, responsável padrão e normas internas")
def ver(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    return Personalizacao(
        prazos_internos=[PrazoInterno(**vars(p)) for p in dominio.prazos_internos(conn, empresa_id).values()],
        responsaveis_padrao=dominio.responsaveis_padrao(conn, empresa_id),
        normas_internas=[NormaInterna(**n) for n in dominio.normas_internas(conn, empresa_id)],
        areas=list(dominio.AREAS))


@rota.put("/empresas/{empresa_id}/prazos-internos", response_model=Ok,
          summary="Adiantar o prazo de uma obrigação nesta empresa (a norma não muda)")
def prazo_interno(empresa_id: int, dados: NovoPrazo, request: Request, e: Escopo = Depends(da_empresa),
                  conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    _da_propria_empresa(e)
    try:
        dominio.definir_prazo_interno(conn, empresa_id, dados.codigo, dados.dias_antes, e.assinante)
    except dominio.ErroPersonalizacao as erro:
        auditoria.registrar(conn, request, "prazo_interno", dados.codigo, dados.model_dump(),
                            resultado="recusado")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "prazo_interno", dados.codigo, {"dias_antes": dados.dias_antes})
    return Ok(ok=True)


@rota.put("/empresas/{empresa_id}/responsaveis-padrao", response_model=Ok,
          summary="Quem responde por obrigação nova de uma área nesta empresa")
def responsavel_padrao(empresa_id: int, dados: ResponsavelPadrao, request: Request,
                       e: Escopo = Depends(da_empresa), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    _da_propria_empresa(e)
    try:
        dominio.definir_responsavel_padrao(conn, empresa_id, dados.area, dados.responsavel, e.assinante)
    except dominio.ErroPersonalizacao as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "responsavel_padrao", dados.area,
                        {"responsavel": dados.responsavel})
    return Ok(ok=True)


@rota.post("/empresas/{empresa_id}/normas-internas", status_code=201, response_model=Criada,
           summary="Obrigação própria sem licença (padrão corporativo), aprovada pela própria empresa")
def norma_interna(empresa_id: int, dados: NovaNormaInterna, request: Request,
                  e: Escopo = Depends(da_empresa), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    _da_propria_empresa(e)
    try:
        codigo = dominio.nova_norma_interna(
            conn, empresa_id, titulo=dados.titulo, por=e.assinante, tipo_ativo=dados.tipo_ativo,
            area=dados.area, agenda=dados.agenda, periodicidade=dados.periodicidade, prazo=dados.prazo,
            evidencia=dados.evidencia, aplica_se_a=dados.aplica_se_a, regra=dados.regra,
            norma=dados.norma, vigencia_desde=dados.vigencia_desde)
    except dominio.ErroPersonalizacao as erro:
        auditoria.registrar(conn, request, "norma_interna", dados.titulo[:120], dados.model_dump(),
                            resultado="recusado")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "norma_interna", codigo,
                        {"titulo": dados.titulo, "tipo_ativo": dados.tipo_ativo, "agenda": dados.agenda})
    return Criada(codigo=codigo)
