"""API da RegulaIA.

    uv run uvicorn api.main:app --reload          # http://localhost:8000/docs

Tudo o que a torre faz passa por aqui: o front (Next.js), o agente MCP e os jobs (radar do DOU)
falam só com esta API. O domínio continua em `regulaia/`, igual para SQLite e Postgres.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from regulaia import db, demo, usuarios

from .banco import abrir_pool, conexao
from .config import Config
from .observabilidade import RequestId, configurar_logs, log
from .rotas import admin, auth, descoberta, evidencias, instanciacao, pergunta, regulatorio, torre

VERSAO = "1.0.0"
PREFIXO = "/api/v1"


def _preparar_banco(cfg: Config) -> None:
    """Primeiro start: esquema aplicado e, se o banco estiver vazio, a demo montada."""
    conn = db.conectar(cfg.banco)
    try:
        vazio = conn.execute("SELECT COUNT(*) FROM empresa").fetchone()[0] == 0
    finally:
        conn.close()
    if vazio and cfg.montar_demo:
        log.info("montando a demo", extra={"extra_json": {"banco": "postgres" if cfg.postgres else "sqlite"}})
        demo.preparar(cfg.banco, cache=cfg.cache)
    conn = db.conectar(cfg.banco)
    try:
        # sem demo (produção), a conta de teste sem senha fica de fora: ela entra por /auth/demo sem
        # credencial e abre a visão da curadoria (que recria a demo e decide norma pública)
        usuarios.semear(conn, com_senha_apenas=not cfg.montar_demo)
    finally:
        conn.close()


def criar_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or Config()
    configurar_logs()

    @asynccontextmanager
    async def ciclo(app: FastAPI):
        _preparar_banco(cfg)
        app.state.pool = abrir_pool(cfg)        # Postgres: o pool de conexões; SQLite: None
        try:
            yield
        finally:
            if app.state.pool is not None:
                app.state.pool.close()
                app.state.pool = None

    app = FastAPI(
        title="RegulaIA API",
        version=VERSAO,
        summary="Torre de controle regulatória: cada obrigação de cada ativo, com a norma, o trecho e o prazo.",
        description=(
            "Autenticação por cookie de sessão HttpOnly (POST /auth/login ou /auth/demo). "
            "Toda escrita precisa do cabeçalho X-CSRF-Token com o valor do cookie regulaia_csrf. "
            "O agente e os jobs usam Authorization: Bearer <REGULAIA_TOKEN_SERVICO>."),
        lifespan=ciclo,
        openapi_url=f"{PREFIXO}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.cfg = cfg
    app.state.pool = None
    app.add_middleware(RequestId)
    app.add_middleware(CORSMiddleware, allow_origins=list(cfg.origens), allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-Id"])
    for r in (auth.rota, torre.rota, regulatorio.rota, descoberta.rota, evidencias.rota, pergunta.rota,
              instanciacao.rota, admin.rota):
        app.include_router(r, prefix=PREFIXO)

    @app.get("/health", tags=["operação"], summary="Vivo e com banco")
    def health(conn=Depends(conexao)):
        conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "versao": VERSAO, "banco": "postgres" if cfg.postgres else "sqlite"}

    @app.exception_handler(Exception)
    async def erro_inesperado(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", None)
        log.exception("erro inesperado", extra={"extra_json": {"request_id": rid, "rota": request.url.path}})
        return JSONResponse({"detail": "erro inesperado", "request_id": rid}, status_code=500)

    _servir_front(app, Path(cfg.front))
    return app


def _servir_front(app: FastAPI, pasta: Path) -> None:
    """O front exportado (front/out) na mesma origem da API: o cookie de sessão e o CSRF valem sem CORS.
    Rota da API que não existe continua respondendo JSON, não a página 404 do front."""
    if not (pasta / "index.html").exists():
        return

    @app.api_route(PREFIXO + "/{resto:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   include_in_schema=False)
    def rota_inexistente(resto: str):
        raise HTTPException(404, "Not Found")

    app.mount("/", StaticFiles(directory=pasta, html=True), name="front")


app = criar_app()
