"""Descoberta de normas: a cobertura normativa de cada cliente e a fila da curadoria RegulaIA.

A busca nas fontes oficiais e a triagem pela IA não viram rota: leem dezenas de milhares de normas e
chamam a IA, por isso rodam como job (`python -m api.jobs descoberta`). Aqui fica o que as telas usam:
a cobertura (o que está no catálogo, até onde cada fonte foi lida, as lacunas conhecidas e o que ainda
espera triagem, curadoria ou extração) e a curadoria (aprovar ou descartar, com nome e nota, na auditoria).

A cobertura nunca diz "coberta" sobre o que não foi lido: jurisdição sem fonte automática sai como
"cobertura não verificada", e mesmo a coberta leva as lacunas conhecidas ao lado."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from regulaia import db, descoberta

from .. import auditoria
from ..banco import conexao
from ..seguranca import Escopo, curadoria, empresa_visivel, plataforma, regulatorio

rota = APIRouter(tags=["descoberta"])

StatusCandidata = Literal["nova", "relevante", "irrelevante", "catalogada", "aprovada", "descartada"]


class FonteLida(BaseModel):
    fonte: str = Field(examples=["almg"])
    nome: str = Field(examples=["Assembleia de Minas"])
    cobre: str = Field(description="o que a fonte lista", examples=["leis, leis complementares e decretos de Minas Gerais"])
    desde: int = Field(description="primeiro ano lido")
    ate: int = Field(description="último ano lido")
    em: str = Field(description="quando foi lida (UTC, AAAA-MM-DD HH:MM:SS)")


class NormaNaCobertura(BaseModel):
    chave: str = Field(examples=["MG:DEC:48747/2023"])
    titulo: str
    ementa: str
    url: str | None = Field(description="o texto oficial")
    deveres: str = Field(description="o que a triagem da IA disse que a norma cobra de quem opera o ativo")
    cita_catalogo: list[str] = Field(
        description="normas do catálogo que esta altera ou regulamenta: conferir se o texto consolidado já tem")


class ItemCobertura(BaseModel):
    """Uma jurisdição e um tipo de ativo da carteira da empresa."""
    jurisdicao: str = Field(examples=["MG"])
    jurisdicao_nome: str = Field(examples=["Minas Gerais", "Brasil (federal)"])
    tipo_ativo: str = Field(examples=["barragem"])
    ativos: list[str] = Field(description="códigos dos ativos da empresa que precisam desta cobertura")
    estado: str = Field(description="sem_fonte, nao_buscada, triagem_pendente, curadoria_pendente, extracao_pendente "
                                    "ou coberta")
    estado_rotulo: str
    verificada: bool = Field(description="as fontes automáticas da jurisdição foram lidas; falso: cobertura não verificada")
    fontes: list[FonteLida] = Field(description="as fontes lidas para a jurisdição")
    lacunas: list[str] = Field(description="o que a plataforma sabe que não cobre por fonte automática")
    catalogadas: list[str] = Field(description="normas do catálogo que valem aqui")
    triagem_pendente: int = Field(description="candidatas que ainda não passaram pela IA")
    em_curadoria: list[NormaNaCobertura] = Field(description="relevantes pela IA, esperando a curadoria RegulaIA")
    aprovadas: list[NormaNaCobertura] = Field(description="aprovadas pela curadoria, falta extrair as obrigações")


class TriagemIA(BaseModel):
    relevante: bool
    tipos_ativo: list[str]
    deveres: str
    motivo: str
    confianca: float
    modelo: str
    custo_usd: float = 0.0
    leu_texto: bool = Field(False, description="a IA leu o texto oficial; falso: decidiu só pela ementa")


class NormaCandidata(BaseModel):
    chave: str = Field(examples=["MG:DEC:48747/2023"])
    jurisdicao: str
    jurisdicao_nome: str
    fonte: str
    fonte_nome: str
    tipo: str
    numero: str
    ano: int
    titulo: str
    ementa: str
    indexacao: str | None = Field(None, description="assunto e indexação da fonte (só na consulta de uma norma)")
    data: str | None
    url: str | None = Field(description="o texto oficial")
    situacao: str | None = Field(description="a vigência, como a fonte diz (VIGENTE...)")
    temas: list[str] = Field(description="tipos de ativo cujos termos a norma cita")
    triagem: TriagemIA | None = Field(description="o que a IA disse; vazio: ainda não triada")
    status: StatusCandidata
    status_rotulo: str
    decidida_por: str | None
    decidida_em: str | None
    nota: str | None
    cita_catalogo: list[str] = Field(
        description="normas do catálogo que esta altera ou regulamenta: conferir se o texto consolidado já tem")


class Jurisdicao(BaseModel):
    sigla: str
    nome: str


class FilaCandidatas(BaseModel):
    normas: list[NormaCandidata]
    contagem: dict[str, int] = Field(description="quantas normas há em cada status (na jurisdição filtrada)")
    status_rotulos: dict[str, str]
    jurisdicoes: list[Jurisdicao] = Field(description="as jurisdições que têm candidatas, para o filtro")
    decide: bool = Field(description="se quem pede pode aprovar ou descartar")


class DecisaoCandidata(BaseModel):
    decisao: Literal["aprovar", "descartar"]
    nota: str | None = Field(None, max_length=2000, examples=["regulamenta a Lei 23.291: extrair a caução"])


def _norma(d: dict, com_indexacao: bool = False) -> NormaCandidata:
    return NormaCandidata(
        chave=d["chave"], jurisdicao=d["jurisdicao"], jurisdicao_nome=descoberta.nome_jurisdicao(d["jurisdicao"]),
        fonte=d["fonte"], fonte_nome=descoberta.NOMES_FONTES.get(d["fonte"], d["fonte"]), tipo=d["tipo"],
        numero=str(d["numero"]), ano=d["ano"], titulo=d["titulo"], ementa=d.get("ementa") or "",
        indexacao=(d.get("indexacao") or None) if com_indexacao else None, data=d.get("data"), url=d.get("url"),
        situacao=d.get("situacao"), temas=d["temas"], triagem=TriagemIA(**d["triagem"]) if d["triagem"] else None,
        status=d["status"], status_rotulo=descoberta.ROTULOS_STATUS.get(d["status"], d["status"]),
        decidida_por=d.get("decidida_por"), decidida_em=d.get("decidida_em"), nota=d.get("nota"),
        cita_catalogo=d.get("cita_catalogo") or [])


def _na_cobertura(c: dict) -> NormaNaCobertura:
    return NormaNaCobertura(chave=c["chave"], titulo=c["titulo"], ementa=c.get("ementa") or "", url=c.get("url"),
                            deveres=c.get("deveres") or "", cita_catalogo=c.get("cita_catalogo") or [])


@rota.get("/empresas/{empresa_id}/cobertura", response_model=list[ItemCobertura],
          summary="Cobertura normativa: por jurisdição e tipo de ativo, o que está no catálogo, o que foi lido e o que falta")
def cobertura(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    # o gestor vê só as linhas (e os ativos) da área dele, como no resto da torre
    visiveis = None if e.ve_tudo else {a["codigo"] for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)}
    out = []
    for i in descoberta.cobertura(conn, empresa_id):
        ativos = i.ativos if visiveis is None else [a for a in i.ativos if a in visiveis]
        if not ativos:
            continue
        out.append(ItemCobertura(
            jurisdicao=i.jurisdicao, jurisdicao_nome=descoberta.nome_jurisdicao(i.jurisdicao), tipo_ativo=i.tipo_ativo,
            ativos=ativos, estado=i.estado, estado_rotulo=descoberta.ROTULOS_ESTADO[i.estado],
            verificada=i.estado in descoberta.VERIFICADOS,
            fontes=[FonteLida(**f, nome=descoberta.NOMES_FONTES.get(f["fonte"], f["fonte"])) for f in i.fontes],
            lacunas=i.lacunas, catalogadas=i.catalogadas, triagem_pendente=i.triagem_pendente,
            em_curadoria=[_na_cobertura(c) for c in i.em_curadoria], aprovadas=[_na_cobertura(c) for c in i.aprovadas]))
    return out


@rota.get("/normas-candidatas", response_model=FilaCandidatas,
          summary="A fila da curadoria RegulaIA: normas já publicadas que a busca achou e a IA triou (só a plataforma)")
def fila(status_: list[StatusCandidata] = Query(["relevante"], alias="status"),
         jurisdicao: str | None = Query(None, examples=["MG"]), e: Escopo = Depends(plataforma), conn=Depends(conexao)):
    jur = (jurisdicao or "").strip().upper() or None
    normas = [_norma(d) for d in descoberta.fila(conn, tuple(dict.fromkeys(status_)), jur)]
    sql, args = "SELECT status, COUNT(*) AS n FROM norma_candidata", ()
    if jur:
        sql, args = sql + " WHERE jurisdicao = ?", (jur,)
    contagem = {s: 0 for s in descoberta.STATUS} | {r["status"]: r["n"] for r in conn.execute(sql + " GROUP BY status", args)}
    siglas = [r["jurisdicao"] for r in conn.execute("SELECT DISTINCT jurisdicao FROM norma_candidata")]
    conn.commit()
    return FilaCandidatas(
        normas=normas, contagem=contagem, status_rotulos=descoberta.ROTULOS_STATUS,
        jurisdicoes=[Jurisdicao(sigla=s, nome=descoberta.nome_jurisdicao(s)) for s in sorted(siglas, key=lambda s: (s != "BR", s))],
        decide=e.ve_tudo)


@rota.get("/normas-candidatas/{chave:path}", response_model=NormaCandidata,
          summary="Uma norma candidata, com a triagem da IA e a indexação da fonte (só a plataforma)")
def candidata(chave: str, e: Escopo = Depends(plataforma), conn=Depends(conexao)):
    d = descoberta.candidata(conn, chave)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"norma {chave} não está na fila")
    return _norma(d, com_indexacao=True)


@rota.post("/normas-candidatas/{chave:path}/decisao", response_model=NormaCandidata,
           summary="Curadoria RegulaIA: aprovar (vai para a extração das obrigações) ou descartar, com nota")
def decidir(chave: str, dados: DecisaoCandidata, request: Request, e: Escopo = Depends(curadoria),
            conn=Depends(conexao)):
    if descoberta.candidata(conn, chave) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"norma {chave} não está na fila")
    try:
        d = descoberta.decidir(conn, chave, dados.decisao, e.usuario["email"], dados.nota)
    except descoberta.ErroDescoberta as erro:
        auditoria.registrar(conn, request, "descoberta.decidir", chave, dados.model_dump(), resultado="recusado")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "descoberta.decidir", chave, dados.model_dump())
    return _norma(d, com_indexacao=True)
