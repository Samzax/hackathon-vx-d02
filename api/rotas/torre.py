"""A torre: painel por ativo, ficha do ativo, entregas, responsáveis, transição e boletim."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from regulaia import agenda, db, operacao, pdf, torre

from .. import auditoria
from ..banco import conexao
from ..config import desde_padrao, hoje_padrao
from ..seguranca import Escopo, diretoria, regulatorio

rota = APIRouter(tags=["torre"])

ROTULO = {agenda.ATRASADA: "atrasada", torre.DADO_FALTANDO: "dado faltando", agenda.VENCE_LOGO: "vence em breve",
          agenda.EM_DIA: "em dia", agenda.CUMPRIDA: "cumprida", agenda.GATILHO: "por gatilho"}


# ------------------------------------------------------------------ modelos


class Empresa(BaseModel):
    id: int
    nome: str
    ficticia: bool
    monitorado_desde: str | None = None
    origem: str | None = None


class LinhaPainel(BaseModel):
    ativo: str
    ativo_id: int | None
    ativo_nome: str
    tipo_ativo: str
    responsavel: str | None
    responsavel_proprio: bool
    codigo: str
    norma: str | None
    area: str | None
    titulo: str
    artigo: str
    dispositivo: str = Field(description="norma e artigo prontos para mostrar")
    periodicidade: str | None
    agenda: str
    status: str = Field(description="atrasada, dado_faltando, vence_logo, em_dia, cumprida, gatilho")
    status_rotulo: str
    vence: str | None
    faltando: list[str]
    pendente: str = Field(description="o que falta, em português")
    ultima: str | None
    dados_faltando: list[str]
    mudanca_pendente: bool
    evidencia: str | None
    nota: str


class Painel(BaseModel):
    hoje: str
    desde: str
    contagem: dict[str, int]
    por_ativo: dict[str, dict[str, int]]
    linhas: list[LinhaPainel]


class Ativo(BaseModel):
    id: int
    codigo: str
    nome: str
    tipo: str
    responsavel: str | None
    atributos: dict
    contagem: dict[str, int]


class Ficha(BaseModel):
    ativo: Ativo
    linhas: list[LinhaPainel]
    evidencias: list[dict]
    eventos: list[dict]


class Entrega(BaseModel):
    ativo_id: int
    codigo: str = Field(examples=["R95-01"])
    dia: date | None = Field(None, description="dia da entrega; padrão: o hoje da torre")
    periodo: str | None = Field(None, description="período comprovado; padrão: o primeiro que falta")
    obs: str | None = None
    arquivo: str | None = None


class Atribuicao(BaseModel):
    ativo_id: int
    codigo: str
    responsavel: str = Field(description="área; vazio devolve a obrigação ao responsável do ativo")


class Comentario(BaseModel):
    ativo_id: int
    codigo: str | None = None
    texto: str = Field(min_length=1, max_length=2000)


class Atributos(BaseModel):
    atributos: dict


class Responsavel(BaseModel):
    area: str | None


# ------------------------------------------------------------------ apoio


def _empresa(conn, empresa_id: int) -> dict:
    r = conn.execute("SELECT * FROM empresa WHERE id = ?", (empresa_id,)).fetchone()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"empresa {empresa_id} não existe")
    return dict(r)


def _ativo(conn, ativo_id: int, e: Escopo) -> dict:
    r = conn.execute("SELECT * FROM ativo WHERE id = ?", (ativo_id,)).fetchone()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"ativo {ativo_id} não existe")
    a = db.ativos(conn, r["empresa_id"])
    ativo = next(x for x in a if x["id"] == ativo_id)
    # gestor vê o ativo da sua área e também o ativo em que alguma obrigação foi passada para ela
    if not e.ve_ativo(ativo) and not any(k[0] == ativo_id and v == e.area for k, v in db.responsaveis(conn).items()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "este ativo é de outra área")
    return ativo


def _linha(l: torre.Linha) -> LinhaPainel:
    return LinhaPainel(**{k: v for k, v in asdict(l).items()},
                       dispositivo=torre.dispositivo(l.norma, l.artigo), status_rotulo=ROTULO.get(l.status, l.status),
                       pendente=torre.pendente(l))


def _visiveis(conn, e: Escopo, empresa_id: int, hoje: date, desde: date, ativo: str | None = None):
    donos = {a["codigo"]: a["responsavel"] for a in db.ativos(conn, empresa_id)}
    return [l for l in torre.painel(conn, empresa_id, hoje, desde, ativo=ativo) if e.ve_linha(l, donos.get(l.ativo))]


def _contagem(linhas) -> dict[str, int]:
    out = {s: 0 for s in ROTULO}
    for l in linhas:
        out[l.status] = out.get(l.status, 0) + 1
    return out


# ------------------------------------------------------------------ leitura


@rota.get("/empresas", response_model=list[Empresa], summary="Empresas na torre (a demo primeiro)")
def empresas(e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    return [Empresa(**{**x, "ficticia": bool(x["ficticia"])}) for x in db.empresas(conn)]


@rota.get("/empresas/{empresa_id}/painel", response_model=Painel,
          summary="Status de cada obrigação que vale no dia, por ativo, no escopo de quem pede")
def painel(empresa_id: int, hoje: date | None = None, ativo: str | None = None,
           status_: list[str] | None = Query(None, alias="status"),
           e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = _empresa(conn, empresa_id)
    hoje = hoje or hoje_padrao()
    desde = desde_padrao(emp)
    linhas = _visiveis(conn, e, empresa_id, hoje, desde, ativo)
    contagem = _contagem(linhas)
    if status_:
        linhas = [l for l in linhas if l.status in status_]
    return Painel(hoje=hoje.isoformat(), desde=desde.isoformat(), contagem=contagem,
                  por_ativo=torre.resumo(linhas), linhas=[_linha(l) for l in linhas])


@rota.get("/empresas/{empresa_id}/ativos", response_model=list[Ativo], summary="Ativos com a contagem por status")
def ativos(empresa_id: int, hoje: date | None = None, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = _empresa(conn, empresa_id)
    linhas = _visiveis(conn, e, empresa_id, hoje or hoje_padrao(), desde_padrao(emp))
    com_linha = {l.ativo for l in linhas}
    out = []
    for a in db.ativos(conn, empresa_id):
        if not (e.ve_ativo(a) or a["codigo"] in com_linha):
            continue
        out.append(Ativo(id=a["id"], codigo=a["codigo"], nome=a["nome"], tipo=a["tipo"], responsavel=a["responsavel"],
                         atributos=a["atributos"], contagem=_contagem([l for l in linhas if l.ativo == a["codigo"]])))
    return out


@rota.get("/ativos/{ativo_id}", response_model=Ficha, summary="Ficha do ativo: pendências, evidências e histórico")
def ficha(ativo_id: int, hoje: date | None = None, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    emp = _empresa(conn, a["empresa_id"])
    linhas = _visiveis(conn, e, emp["id"], hoje or hoje_padrao(), desde_padrao(emp), ativo=a["codigo"])
    return Ficha(ativo=Ativo(id=a["id"], codigo=a["codigo"], nome=a["nome"], tipo=a["tipo"],
                             responsavel=a["responsavel"], atributos=a["atributos"], contagem=_contagem(linhas)),
                 linhas=[_linha(l) for l in linhas], evidencias=db.evidencias_do_ativo(conn, ativo_id, 20),
                 eventos=db.eventos(conn, ativo_id, limite=50))


@rota.get("/obrigacoes/{codigo}/historico", summary="Todas as versões de uma obrigação, com a origem e quem decidiu")
def historico(codigo: str, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    h = db.historico(conn, codigo)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"obrigação {codigo} não existe")
    return h


@rota.get("/empresas/{empresa_id}/calendario", summary="Vencimentos do mês, período a período")
def calendario_mes(empresa_id: int, ano: int, mes: int = Query(ge=1, le=12), hoje: date | None = None,
                   e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = _empresa(conn, empresa_id)
    linhas = _visiveis(conn, e, empresa_id, hoje or hoje_padrao(), desde_padrao(emp))
    return [{"dia": v.dia, "periodo": v.periodo, "entregue": v.entregue, "ativo": v.linha.ativo,
             "ativo_id": v.linha.ativo_id, "codigo": v.linha.codigo, "titulo": v.linha.titulo,
             "status": v.linha.status} for v in operacao.vencimentos_no_mes(conn, linhas, ano, mes)]


@rota.get("/empresas/{empresa_id}/transicao", summary="O que sai, o que entra e o que continua na troca de norma")
def transicao(empresa_id: int, dia: date = date(2027, 8, 2), e: Escopo = Depends(regulatorio),
              conn=Depends(conexao)):
    _empresa(conn, empresa_id)
    visiveis = {a["codigo"] for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)}
    out = []
    for t in torre.transicao(conn, empresa_id, dia):
        if t.ativo not in visiveis:
            continue
        out.append({"ativo": t.ativo, "temas": [
            {"tema": p.tema, "situacao": p.situacao, "saem": [_resumo_ob(o) for o in p.saem],
             "entram": [_resumo_ob(o) for o in p.entram]} for p in torre.pares(t, conn, dia)]})
    return out


def _resumo_ob(o: dict) -> dict:
    return {k: o.get(k) for k in ("codigo", "titulo", "norma", "artigo", "periodicidade", "agenda", "trecho")}


@rota.get("/empresas/{empresa_id}/linha-do-tempo", summary="Obrigações que passam a valer depois do dia")
def linha_do_tempo(empresa_id: int, hoje: date | None = None, e: Escopo = Depends(regulatorio),
                   conn=Depends(conexao)):
    _empresa(conn, empresa_id)
    visiveis = {a["codigo"] for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)}
    return [asdict(f) for f in torre.futuras(conn, empresa_id, hoje or hoje_padrao()) if f.ativo in visiveis]


@rota.get("/empresas/{empresa_id}/boletim", summary="Boletim da semana (Markdown ou PDF), nunca enviado")
def boletim(empresa_id: int, formato: str = Query("md", pattern="^(md|pdf)$"), responsavel: str | None = None,
            hoje: date | None = None, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = _empresa(conn, empresa_id)
    if not e.ve_tudo:
        responsavel = e.area
    md = torre.boletim(conn, empresa_id, hoje or hoje_padrao(), desde_padrao(emp), responsavel=responsavel)
    if formato == "pdf":
        return Response(pdf.de_markdown(md, "Boletim da semana"), media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="boletim.pdf"'})
    return Response(md, media_type="text/markdown; charset=utf-8")


@rota.get("/empresas/{empresa_id}/calendario.ics", summary="Vencimentos em .ics para a agenda (só download)")
def calendario_ics(empresa_id: int, responsavel: str | None = None, hoje: date | None = None,
                   e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = _empresa(conn, empresa_id)
    if not e.ve_tudo:
        responsavel = e.area
    ics = torre.calendario(conn, empresa_id, hoje or hoje_padrao(), desde_padrao(emp), responsavel=responsavel)
    return Response(ics, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="regulaia.ics"'})


@rota.get("/empresas/{empresa_id}/planilha", summary="As pendências em Excel")
def planilha(empresa_id: int, hoje: date | None = None, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    emp = _empresa(conn, empresa_id)
    linhas = _visiveis(conn, e, empresa_id, hoje or hoje_padrao(), desde_padrao(emp))
    return Response(operacao.planilha(linhas, emp["nome"]),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="regulaia.xlsx"'})


# ------------------------------------------------------------------ escrita


@rota.post("/entregas", status_code=201, summary="Registrar a entrega de um período (com ou sem comprovante)")
def entregar(dados: Entrega, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, dados.ativo_id, e)
    emp = _empresa(conn, a["empresa_id"])
    dia = dados.dia or hoje_padrao()
    linhas = [l for l in _visiveis(conn, e, emp["id"], dia, desde_padrao(emp), ativo=a["codigo"])
              if l.codigo == dados.codigo]
    if not linhas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{dados.codigo} não vale para {a['codigo']} em {dia}")
    periodo = dados.periodo or operacao.periodo_para_entrega(linhas[0], dia)
    try:
        eid = db.entregar(conn, a["id"], dados.codigo, periodo, dia=dia.isoformat(), por=e.assinante,
                          arquivo=dados.arquivo, obs=dados.obs)
    except db.ErroCadastro as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    auditoria.registrar(conn, request, "entrega", f"{a['codigo']}/{dados.codigo}", {"periodo": periodo})
    return {"evidencia_id": eid, "periodo": periodo}


@rota.delete("/entregas", summary="Desfazer uma entrega registrada por engano")
def desfazer(ativo_id: int, codigo: str, periodo: str, request: Request, e: Escopo = Depends(regulatorio),
             conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    if not db.desfazer_entrega(conn, a["id"], codigo, periodo, por=e.assinante):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "não havia entrega desse período")
    auditoria.registrar(conn, request, "entrega_desfeita", f"{a['codigo']}/{codigo}", {"periodo": periodo})
    return {"ok": True}


@rota.post("/atribuicoes", summary="Passar uma obrigação para outra área")
def atribuir(dados: Atribuicao, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, dados.ativo_id, e)
    db.atribuir(conn, a["id"], dados.codigo, dados.responsavel.strip(), por=e.assinante)
    auditoria.registrar(conn, request, "atribuicao", f"{a['codigo']}/{dados.codigo}", {"para": dados.responsavel})
    return {"ok": True}


@rota.post("/comentarios", status_code=201, summary="Comentar uma obrigação ou o ativo")
def comentar(dados: Comentario, request: Request, e: Escopo = Depends(regulatorio), conn=Depends(conexao)):
    a = _ativo(conn, dados.ativo_id, e)
    db.registrar_evento(conn, a["id"], dados.codigo, "comentario", dados.texto, e.assinante)
    auditoria.registrar(conn, request, "comentario", f"{a['codigo']}/{dados.codigo or '-'}")
    return {"ok": True}


@rota.patch("/ativos/{ativo_id}/atributos", summary="Completar ou corrigir o cadastro do ativo")
def atributos(ativo_id: int, dados: Atributos, request: Request, e: Escopo = Depends(regulatorio),
              conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    novo = db.atualizar_atributos(conn, a["id"], dados.atributos, por=e.assinante)
    auditoria.registrar(conn, request, "cadastro", a["codigo"], dados.atributos)
    return novo


@rota.put("/ativos/{ativo_id}/responsavel", summary="Qual área responde pelo ativo (Diretoria)")
def responsavel(ativo_id: int, dados: Responsavel, request: Request, e: Escopo = Depends(diretoria),
                conn=Depends(conexao)):
    a = _ativo(conn, ativo_id, e)
    mudou = db.definir_responsavel(conn, a["id"], dados.area, por=e.assinante)
    auditoria.registrar(conn, request, "responsavel_ativo", a["codigo"], {"area": dados.area})
    return {"mudou": mudou}
