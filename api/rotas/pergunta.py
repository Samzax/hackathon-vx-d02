"""Assistente Mitra: o Claude responde sobre a torre com as ferramentas de leitura do agente.

As ferramentas falam com a própria API por requisições internas, com o cookie (ou o token) de quem
pergunta: o modelo vê exatamente o que essa pessoa veria na torre, nem uma linha a mais, e cada
consulta passa pelas mesmas regras de acesso das telas.

Por isso a rota não pede a conexão nem a sessão como dependência: segurar uma conexão do pool enquanto
o modelo pensa e as requisições internas pegam outras esgotaria o pool. A sessão é conferida por uma
requisição interna a /auth/me; a conexão é emprestada só para o teto de gasto (antes) e para o custo e
a auditoria (depois).
"""

from __future__ import annotations

import functools
import hmac
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from agente.cliente import Torre
from agente.ferramentas import CHAMA_IA, ferramentas
from mitra import pergunta as pg
from mitra import usuarios
from mitra.ia import CONFIG, SemProvedor, TetoAtingido

from .. import auditoria
from ..banco import emprestar, roteador_avulso
from ..seguranca import CABECALHO_CSRF, COOKIE_CSRF, Escopo, regulatorio

rota = APIRouter(tags=["pergunta"])
PREFIXO = "/api/v1"


class Mensagem(BaseModel):
    papel: Literal["usuario", "torre"]
    texto: str = Field(max_length=8000)


class PedidoPergunta(BaseModel):
    pergunta: str = Field(min_length=1, max_length=pg.MAX_PERGUNTA)
    historico: list[Mensagem] = Field(default_factory=list, max_length=20,
                                      description="A conversa até aqui (as últimas mensagens valem)")


class UsoFerramenta(BaseModel):
    ferramenta: str
    args: dict
    erro: str | None = None


class ConferenciaResposta(BaseModel):
    ok: bool
    citacoes: int = Field(description="Trechos entre aspas na resposta")
    citacoes_fora: list[str] = Field(description="Trechos citados que não estão no que as ferramentas devolveram")
    datas_fora: list[str]
    codigos_fora: list[str]


class RespostaPergunta(BaseModel):
    texto: str = Field(description="A resposta em Markdown")
    modelo: str
    ferramentas: list[UsoFerramenta]
    conferencia: ConferenciaResposta
    tokens_in: int
    tokens_out: int
    tokens_cache: int
    custo_usd: float
    corrigida: bool = Field(description="A conferência mandou o modelo corrigir uma vez")
    segundos: float = Field(description="Quanto a pergunta levou, do pedido à resposta")


class EstadoPergunta(BaseModel):
    ligada: bool
    modelo: str | None = Field(description="O modelo que responde agora (o primeiro provedor ligado)")
    gasto_hoje_usd: float
    teto_dia_usd: float | None


@functools.lru_cache(maxsize=1)
def _provedores_do_ambiente() -> dict:
    return pg.provedores_da_config(dict(os.environ), pg._config(CONFIG))


def _provedores(request: Request) -> dict:
    """Nos testes, `app.state.provedores_pergunta` troca o modelo por respostas gravadas."""
    return getattr(request.app.state, "provedores_pergunta", None) or _provedores_do_ambiente()


def _interno(request: Request) -> TestClient:
    """Cliente HTTP que chama a própria API em processo, com a credencial de quem pergunta."""
    headers = {}
    if auth := request.headers.get("authorization"):
        headers["Authorization"] = auth
    return TestClient(request.app, base_url="http://torre.interna", raise_server_exceptions=False,
                      cookies=dict(request.cookies), headers=headers)


@rota.get("/pergunta/estado", response_model=EstadoPergunta,
          summary="Se o Assistente Mitra está ligado, com qual modelo, e o gasto de IA do dia")
def estado(request: Request, e: Escopo = Depends(regulatorio)):
    modelos = pg.candidatos(pg._config(CONFIG), _provedores(request))
    with roteador_avulso(request.app) as rot:
        gasto, teto = float(rot.gasto_hoje()), rot.teto_dia_usd
    return EstadoPergunta(ligada=bool(modelos), modelo=modelos[0].rotulo if modelos else None,
                          gasto_hoje_usd=gasto, teto_dia_usd=teto)


@rota.post("/pergunta", response_model=RespostaPergunta,
           summary="Pergunta em linguagem natural; o modelo consulta a torre no escopo da sessão e cita a fonte")
def perguntar(dados: PedidoPergunta, request: Request):
    interno = _interno(request)
    me = interno.get(f"{PREFIXO}/auth/me")
    if me.status_code != 200:
        raise HTTPException(me.status_code, me.json().get("detail", "entre na torre para continuar"))
    eu = me.json()
    if not request.headers.get("authorization"):        # sessão de navegador: escrita pede o CSRF
        enviado, esperado = request.headers.get(CABECALHO_CSRF, ""), request.cookies.get(COOKIE_CSRF, "")
        if not enviado or not hmac.compare_digest(enviado, esperado):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "falta o cabeçalho X-CSRF-Token")
    if eu["papel_efetivo"] == usuarios.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "a TI administra contas e não vê dado regulatório")
    request.state.usuario, request.state.empresa = eu["email"], eu.get("empresa")

    with roteador_avulso(request.app) as rot:
        if rot.teto_dia_usd is not None and rot.gasto_hoje() >= rot.teto_dia_usd:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                f"o gasto de IA de hoje chegou ao teto (US$ {rot.teto_dia_usd:.2f}): volte amanhã")
    provedores = _provedores(request)
    if not pg.candidatos(pg._config(CONFIG), provedores):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "o Assistente Mitra está desligado aqui: nenhum provedor de IA configurado")

    fs = pg.preparar(ferramentas(Torre(interno)), fora=CHAMA_IA)
    historico = [(m.papel, m.texto) for m in dados.historico]
    try:
        r = pg.perguntar(dados.pergunta, fs, historico=historico, provedores=provedores)
    except pg.ErroPergunta as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro)) from None
    except pg.Demorou as erro:
        if erro.parcial is not None:          # o que já se gastou entra no teto do dia
            with roteador_avulso(request.app) as rot:
                pg.registrar_custo(rot, erro.parcial)
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, str(erro)) from None
    except TetoAtingido as erro:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(erro)) from None
    except SemProvedor as erro:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"o modelo não respondeu agora; tente de novo ({str(erro)[:200]})") from None

    with roteador_avulso(request.app) as rot:
        pg.registrar_custo(rot, r)
    with emprestar(request.app) as conn:
        auditoria.registrar(conn, request, "pergunta", dados.pergunta[:300], {
            "modelo": r.modelo, "ferramentas": [u.ferramenta for u in r.ferramentas], "custo_usd": round(r.custo_usd, 5),
            "conferencia_ok": r.conferencia.ok, "corrigida": r.corrigida})
    return RespostaPergunta(**r.para_api())
