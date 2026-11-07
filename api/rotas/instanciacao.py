"""Instanciação de uma cliente: as etapas, as unidades, os ativos (formulário e planilha) e a entrada
em operação.

Quem faz o quê:
- **Criar a empresa** e escolher as barragens do SIGBM é da **curadoria da plataforma** (`seguranca.curadoria`):
  é ela que leva a cliente nova para dentro. A cliente não cria a si mesma.
- **Cadastrar ativo, unidade e completar o cadastro** é da **própria empresa** (`seguranca.da_empresa`):
  nos dados operacionais a plataforma só lê (decisão de 07/11). Enquanto a cliente não tem conta, a
  curadoria vê o estado e o que falta, mas quem preenche é ela.
- **Entrar em operação** é da Diretoria ou do Regulatório da empresa: é a hora em que a torre passa a
  cobrar. A plataforma não decide por ela.
Toda escrita vai para a auditoria com a empresa de quem agiu.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from regulaia import db, instanciacao as dominio, sigbm

from .. import auditoria
from ..banco import conexao
from ..seguranca import Escopo, curadoria, da_empresa, empresa_visivel, regulatorio

rota = APIRouter(tags=["instanciação"])
LIMITE_PLANILHA = 5 * 1024 * 1024


# ------------------------------------------------------------------ modelos


class Etapa(BaseModel):
    etapa: str = Field(description="cadastro, ativos, dados, cobertura, licencas, responsaveis, contas, operacao")
    titulo: str
    estado: str = Field(description="pendente, em_andamento ou pronta")
    falta: str = Field(description="o que fazer agora, em português; vazio quando a etapa está pronta")
    numeros: dict[str, int] = Field(description="os números da etapa (ativos, propostas, contas...)")
    por: str | None = Field(description="quem mexeu nela por último")
    em: str | None


class Estado(BaseModel):
    empresa_id: int
    empresa: str
    cnpj: str | None
    razao_social: str
    ufs: list[str]
    no_sigbm: bool = Field(description="o CNPJ tem barragem no SIGBM público")
    etapas: list[Etapa]
    percentual: int = Field(description="vem das etapas prontas e em andamento, não de um número inventado")
    em_operacao: bool
    monitorado_desde: str | None = Field(description="a partir de quando a torre cobra")
    criada_por: str
    criada_em: str


class Nova(BaseModel):
    nome: str = Field(min_length=2, max_length=200, description="o nome que aparece na torre (único)")
    razao_social: str = Field(min_length=2, max_length=200)
    cnpj: str | None = Field(None, max_length=20, description="vazio: empreendedor pessoa física")
    ufs: list[str] = Field([], description="UFs em que opera (duas letras)")
    ficticia: bool = Field(False, description="empresa de demonstração")


class Criada(BaseModel):
    empresa_id: int
    estado: Estado


class NovaUnidade(BaseModel):
    nome: str = Field(min_length=2, max_length=200, examples=["Mina Serra Azul"])
    uf: str | None = Field(None, max_length=2)
    municipio: str | None = Field(None, max_length=120)


class Unidade(BaseModel):
    id: int
    nome: str
    uf: str | None
    municipio: str | None
    criada_por: str | None
    criada_em: str
    ativos: list[str] = Field([], description="os ativos da empresa que pertencem a esta unidade")


class NovoAtivo(BaseModel):
    tipo: str = Field(description="barragem, unidade, equipamento ou licenca")
    codigo: str = Field(min_length=1, max_length=40, examples=["B1"])
    nome: str = Field(min_length=1, max_length=200)
    unidade: str | None = Field(None, description="a operação a que pertence (crie a unidade antes)")
    responsavel: str | None = Field(None, description="a área responsável")
    atributos: dict = Field({}, description="os campos do cadastro (ver GET /cadastro/campos)")


class AtivoCriado(BaseModel):
    ativo_id: int
    codigo: str


class LinhaPlanilha(BaseModel):
    linha: int = Field(description="o número da linha no arquivo, como a pessoa vê")
    tipo: str
    codigo: str
    nome: str
    unidade: str | None
    responsavel: str | None
    atributos: dict
    erro: str | None = Field(description="o que está errado nesta linha; vazio: a linha está boa")


class Planilha(BaseModel):
    linhas: list[LinhaPlanilha]
    importados: int = Field(description="quantos ativos entraram (0 se alguma linha tem erro)")
    erros: int


class DadoFaltando(BaseModel):
    ativo: str
    ativo_id: int
    ativo_nome: str
    campo: str
    pergunta: str = Field(description="o que perguntar a quem preenche")
    obrigacoes: list[str] = Field(description="as obrigações que dependem deste dado")


class BarragemSigbm(BaseModel):
    codigo: str = Field(description="o código da barragem no SIGBM")
    nome: str
    uf: str | None
    municipio: str | None
    na_pnsb: bool
    alertas: list[str] = Field(description="o que o SIGBM já mostra de problema (embargo, emergência, DCE/DCO)")


class DoSigbm(BaseModel):
    cnpj: str
    nome: str
    exportado_em: str
    barragens: list[BarragemSigbm] = Field(description="todas as do CNPJ, não só as da PNSB")


class EscolhaSigbm(BaseModel):
    codigos: list[str] = Field(description="os códigos SIGBM das barragens que entram na torre")


class Operacao(BaseModel):
    desde: date | None = Field(None, description="a partir de quando a torre cobra; padrão: hoje")


class EmOperacao(BaseModel):
    monitorado_desde: str
    pendencias: list[str] = Field(description="as etapas que continuam pendentes (entrar em operação não exige tudo)")


# ------------------------------------------------------------------ apoio


def _estado(conn, empresa_id: int) -> Estado:
    e = dominio.estado(conn, empresa_id)
    return Estado(empresa_id=e.empresa_id, empresa=e.empresa, cnpj=e.cnpj, razao_social=e.razao_social,
                  ufs=e.ufs, no_sigbm=e.no_sigbm, percentual=e.percentual, em_operacao=e.em_operacao,
                  monitorado_desde=e.monitorado_desde, criada_por=e.criada_por, criada_em=e.criada_em,
                  etapas=[Etapa(etapa=x.etapa, titulo=x.titulo, estado=x.estado, falta=x.falta,
                                numeros=x.numeros, por=x.por, em=x.em) for x in e.etapas])


def _instanciada(conn, e: Escopo, empresa_id: int) -> dict:
    """A empresa, se a sessão a vê (a de outra cliente é 404) e se ela foi instanciada."""
    empresa_visivel(conn, e, empresa_id)
    i = dominio.da_empresa(conn, empresa_id)
    if i is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"a empresa {empresa_id} não passou pela instanciação (entrou por outro caminho)")
    return i


def _erro(erro: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro))


# ------------------------------------------------------------------ etapa 1: cadastro


@rota.post("/instanciacoes", status_code=201, response_model=Criada,
           summary="Criar a empresa e a instanciação dela (curadoria da plataforma)")
def criar(dados: Nova, request: Request, e: Escopo = Depends(curadoria), conn=Depends(conexao)):
    achadas = sigbm.buscar(dados.cnpj, limite=1) if dados.cnpj else []
    try:
        eid = dominio.criar(conn, nome=dados.nome, razao_social=dados.razao_social, cnpj=dados.cnpj,
                            ufs=dados.ufs, por=e.assinante, no_sigbm=bool(achadas),
                            ficticia=dados.ficticia)
    except dominio.ErroInstanciacao as erro:
        auditoria.registrar(conn, request, "instanciacao_criar", dados.nome, dados.model_dump(),
                            resultado="recusado")
        raise _erro(erro) from None
    auditoria.registrar(conn, request, "instanciacao_criar", dados.nome,
                        {"empresa_id": eid, "cnpj": dados.cnpj, "ufs": dados.ufs})
    return Criada(empresa_id=eid, estado=_estado(conn, eid))


@rota.get("/instanciacoes", response_model=list[Estado],
          summary="As instanciações que a sessão vê, as que ainda não entraram em operação primeiro")
def listar(e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    return [_estado(conn, i["empresa_id"]) for i in dominio.instanciadas(conn)
            if e.ve_empresa(i["empresa_id"])]


@rota.get("/empresas/{empresa_id}/instanciacao", response_model=Estado,
          summary="As etapas da instanciação, o que falta em cada uma e quem mexeu por último")
def estado(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    _instanciada(conn, e, empresa_id)
    return _estado(conn, empresa_id)


@rota.get("/instanciacoes/sigbm", response_model=DoSigbm,
          summary="As barragens do CNPJ no SIGBM público (todas, não só as da PNSB), para escolher quais entram")
def do_sigbm(cnpj: str = Query(description="CNPJ formatado ou só os dígitos", examples=["00.000.000/0001-00"]),
             e: Escopo = Depends(curadoria)):
    achadas = sigbm.buscar(cnpj, limite=1)
    if not achadas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CNPJ não encontrado no SIGBM público")
    emp = achadas[0]
    return DoSigbm(cnpj=emp.cnpj, nome=emp.nome, exportado_em=sigbm.EXPORTADO_EM, barragens=[
        BarragemSigbm(codigo=b["codigo"], nome=b["barragem"] or f"Barragem {b['codigo']}", uf=b.get("uf"),
                      municipio=b.get("municipio"), na_pnsb=b["pnsb"] == "Sim", alertas=sigbm.alertas(b))
        for b in emp.barragens])


@rota.post("/empresas/{empresa_id}/instanciacao/sigbm", status_code=201, response_model=Estado,
           summary="Trazer do SIGBM as barragens escolhidas (curadoria da plataforma)")
def importar_do_sigbm(empresa_id: int, dados: EscolhaSigbm, request: Request,
                      e: Escopo = Depends(curadoria), conn=Depends(conexao)):
    i = _instanciada(conn, e, empresa_id)
    if not i["cnpj"]:
        raise _erro(dominio.ErroInstanciacao("a empresa não tem CNPJ: não há o que buscar no SIGBM"))
    achadas = sigbm.buscar(i["cnpj"], limite=1)
    if not achadas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CNPJ não encontrado no SIGBM público")
    por_codigo = {b["codigo"]: b for b in achadas[0].barragens}
    desconhecidos = [c for c in dados.codigos if c not in por_codigo]
    if desconhecidos:
        raise _erro(dominio.ErroInstanciacao(
            f"o SIGBM não tem a barragem {', '.join(desconhecidos)} neste CNPJ"))
    entraram = []
    for codigo in dados.codigos:
        b = por_codigo[codigo]
        atributos = sigbm.atributos(b) | {"sigbm_codigo": codigo, "municipio": b["municipio"],
                                          "minerio": b["minerio"]}
        try:
            dominio.criar_ativo(conn, empresa_id, tipo="barragem", codigo=f"SIGBM-{codigo}",
                                nome=b["barragem"] or f"Barragem {codigo}", por=e.assinante,
                                atributos={k: v for k, v in atributos.items() if v not in (None, "")})
        except dominio.ErroInstanciacao as erro:
            raise _erro(erro) from None
        entraram.append(codigo)
    auditoria.registrar(conn, request, "instanciacao_sigbm", i["nome"], {"barragens": entraram})
    return _estado(conn, empresa_id)


# ------------------------------------------------------------------ etapa 2: unidades e ativos


@rota.get("/empresas/{empresa_id}/unidades", response_model=list[Unidade],
          summary="As unidades (operações) da empresa, com os ativos de cada uma")
def unidades(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    por_unidade: dict[str, list[str]] = {}
    for a in db.ativos(conn, empresa_id):
        if a.get("unidade"):
            por_unidade.setdefault(a["unidade"], []).append(a["codigo"])
    return [Unidade(**{k: u[k] for k in ("id", "nome", "uf", "municipio", "criada_por", "criada_em")},
                    ativos=sorted(por_unidade.get(u["nome"], [])))
            for u in dominio.unidades(conn, empresa_id)]


@rota.post("/empresas/{empresa_id}/unidades", status_code=201, response_model=Unidade,
           summary="Criar uma unidade (a própria empresa)")
def criar_unidade(empresa_id: int, dados: NovaUnidade, request: Request,
                  e: Escopo = Depends(da_empresa), conn=Depends(conexao)):
    _instanciada(conn, e, empresa_id)
    try:
        uid = dominio.criar_unidade(conn, empresa_id, dados.nome, e.assinante, uf=dados.uf,
                                    municipio=dados.municipio)
    except dominio.ErroInstanciacao as erro:
        raise _erro(erro) from None
    auditoria.registrar(conn, request, "unidade_criada", dados.nome, dados.model_dump())
    u = next(x for x in dominio.unidades(conn, empresa_id) if x["id"] == uid)
    return Unidade(**{k: u[k] for k in ("id", "nome", "uf", "municipio", "criada_por", "criada_em")})


@rota.post("/empresas/{empresa_id}/instanciacao/ativos", status_code=201, response_model=AtivoCriado,
           summary="Cadastrar um ativo por formulário (a própria empresa)")
def criar_ativo(empresa_id: int, dados: NovoAtivo, request: Request, e: Escopo = Depends(da_empresa),
                conn=Depends(conexao)):
    _instanciada(conn, e, empresa_id)
    try:
        aid = dominio.criar_ativo(conn, empresa_id, tipo=dados.tipo, codigo=dados.codigo, nome=dados.nome,
                                  por=e.assinante, atributos=dados.atributos, unidade=dados.unidade,
                                  responsavel=dados.responsavel)
    except dominio.ErroInstanciacao as erro:
        auditoria.registrar(conn, request, "ativo_criado", dados.codigo, dados.model_dump(),
                            resultado="recusado")
        raise _erro(erro) from None
    auditoria.registrar(conn, request, "ativo_criado", dados.codigo,
                        {"tipo": dados.tipo, "nome": dados.nome, "unidade": dados.unidade})
    return AtivoCriado(ativo_id=aid, codigo=dados.codigo)


@rota.get("/instanciacoes/modelo.csv", summary="O modelo de planilha para cadastrar ativos em lote")
def modelo(tipo: str = Query("barragem", pattern="^(barragem|unidade|equipamento|licenca)$"),
           e: Escopo = Depends(regulatorio)):
    return Response(dominio.modelo_csv(tipo), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="modelo_{tipo}.csv"'})


@rota.post("/empresas/{empresa_id}/instanciacao/planilha", response_model=Planilha,
           summary="Conferir e importar a planilha de ativos (a própria empresa): tudo ou nada")
async def planilha(empresa_id: int, request: Request, arquivo: UploadFile = File(...),
                   conferir: bool = Query(False, description="só conferir, sem gravar nada"),
                   e: Escopo = Depends(da_empresa), conn=Depends(conexao)):
    _instanciada(conn, e, empresa_id)
    dados = await arquivo.read(LIMITE_PLANILHA + 1)
    if len(dados) > LIMITE_PLANILHA:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "planilha maior que 5 MB")
    if not dados:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "arquivo vazio")
    linhas = (dominio.ler_planilha(dados, empresa_id, conn) if conferir
              else dominio.importar_planilha(conn, empresa_id, dados, e.assinante))
    erros = sum(1 for linha in linhas if linha.erro)
    if not conferir:
        auditoria.registrar(conn, request, "ativos_planilha", arquivo.filename or "planilha.csv",
                            {"linhas": len(linhas), "erros": erros})
    return Planilha(linhas=[LinhaPlanilha(**vars(linha)) for linha in linhas],
                    importados=0 if (erros or conferir) else len(linhas), erros=erros)


# ------------------------------------------------------------------ etapa 3: dados que faltam


@rota.get("/empresas/{empresa_id}/dados-faltando", response_model=list[DadoFaltando],
          summary="O que as regras do catálogo pedem e ninguém informou (lista de tarefas, não bloqueio)")
def dados_faltando(empresa_id: int, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    visiveis = {a["codigo"] for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)} if not e.ve_tudo else None
    return [DadoFaltando(**vars(d)) for d in dominio.dados_que_faltam(conn, empresa_id)
            if visiveis is None or d.ativo in visiveis]


# ------------------------------------------------------------------ etapa 8: entrar em operação


@rota.post("/empresas/{empresa_id}/instanciacao/operacao", response_model=EmOperacao,
           summary="Entrar em operação: a torre passa a cobrar (a própria empresa; aceita pendência)")
def entrar_em_operacao(empresa_id: int, dados: Operacao, request: Request,
                       e: Escopo = Depends(da_empresa), conn=Depends(conexao)):
    _instanciada(conn, e, empresa_id)
    if not e.ve_tudo:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "entrar em operação é da Diretoria ou do Regulatório da empresa")
    try:
        dia = dominio.entrar_em_operacao(conn, empresa_id, e.assinante, dados.desde)
    except dominio.ErroInstanciacao as erro:
        auditoria.registrar(conn, request, "instanciacao_operacao", str(empresa_id),
                            dados.model_dump(mode="json"), resultado="recusado")
        raise _erro(erro) from None
    pendencias = [x.etapa for x in dominio.estado(conn, empresa_id).pendencias]
    auditoria.registrar(conn, request, "instanciacao_operacao", str(empresa_id),
                        {"monitorado_desde": dia, "pendencias": pendencias})
    return EmOperacao(monitorado_desde=dia, pendencias=pendencias)
