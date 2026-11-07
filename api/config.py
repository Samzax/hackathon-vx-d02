"""Configuração da API: tudo vem de variável de ambiente, com padrões que rodam localmente."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from regulaia import db, demo


def _bool(nome: str, padrao: bool) -> bool:
    v = os.environ.get(nome)
    return padrao if v is None else v.strip().lower() in ("1", "true", "sim", "yes")


@dataclass(frozen=True)
class Config:
    # banco: URL postgresql://... (Compose, AWS RDS) ou caminho de arquivo SQLite (dev)
    banco: str = field(default_factory=lambda: os.environ.get("REGULAIA_DATABASE_URL") or str(db.DB_PADRAO))
    # cache das respostas de IA: no Postgres fica no mesmo banco; no SQLite, no arquivo de sempre
    banco_cache: str | None = field(default_factory=lambda: os.environ.get("REGULAIA_CACHE_URL"))
    # Postgres: o pool de conexões da API (no SQLite é uma conexão por requisição). `pool_min` ficam
    # sempre abertas, até `pool_max` em uso ao mesmo tempo (quem passa disso espera uma ser devolvida),
    # e a que sobra acima do mínimo fecha depois de `pool_ociosa_s` segundos parada.
    pool_min: int = field(default_factory=lambda: int(os.environ.get("REGULAIA_POOL_MIN", "1")))
    pool_max: int = field(default_factory=lambda: int(os.environ.get("REGULAIA_POOL_MAX", "5")))
    pool_ociosa_s: float = field(default_factory=lambda: float(os.environ.get("REGULAIA_POOL_OCIOSA_S", "600")))
    # quanto uma requisição espera por uma conexão livre antes de responder 503
    pool_espera_s: float = field(default_factory=lambda: float(os.environ.get("REGULAIA_POOL_ESPERA_S", "30")))
    # cookie só por HTTPS em produção (atrás do load balancer); local roda em http
    cookie_seguro: bool = field(default_factory=lambda: _bool("REGULAIA_COOKIE_SEGURO", False))
    horas_sessao: int = field(default_factory=lambda: int(os.environ.get("REGULAIA_HORAS_SESSAO", "12")))
    # onde os documentos enviados ficam: s3://bucket/prefixo ou uma pasta local
    armazenamento: str = field(default_factory=lambda: os.environ.get(
        "REGULAIA_ARMAZENAMENTO", str(db.ROOT / "data" / "uploads")))
    # origens que podem chamar a API com cookie (front em outro host durante o desenvolvimento)
    origens: tuple[str, ...] = field(default_factory=lambda: tuple(
        o for o in os.environ.get("REGULAIA_ORIGENS", "http://localhost:3000").split(",") if o))
    # monta a demo (cadastro, histórico, radar) no primeiro start se o banco estiver vazio
    montar_demo: bool = field(default_factory=lambda: _bool("REGULAIA_MONTAR_DEMO", True))
    # token de serviço para o agente MCP e jobs (Bearer); vazio desliga
    token_servico: str | None = field(default_factory=lambda: os.environ.get("REGULAIA_TOKEN_SERVICO") or None)
    # o front (Next.js exportado): servido pela própria API, na mesma origem, se a pasta existir
    front: str = field(default_factory=lambda: os.environ.get("REGULAIA_FRONT") or str(db.ROOT / "front" / "out"))

    @property
    def postgres(self) -> bool:
        return self.banco.startswith(("postgresql://", "postgres://"))

    @property
    def cache(self) -> str:
        if self.banco_cache:
            return self.banco_cache
        return self.banco if self.postgres else str(db.ROOT / "data" / "cache_ia.db")


def spec_demo() -> dict:
    return json.loads(demo.HISTORICO.read_text(encoding="utf-8")) if demo.HISTORICO.exists() else {}


def hoje_padrao() -> date:
    """O "hoje" da demo (7/11/2026, dia do hackathon); fora da demo, o dia de verdade."""
    return date.fromisoformat(spec_demo().get("hoje", date.today().isoformat()))


def desde_padrao(empresa: dict) -> date:
    return date.fromisoformat(empresa.get("monitorado_desde") or spec_demo().get("desde", "2026-05-01"))


def pasta_local(cfg: Config) -> Path | None:
    return None if cfg.armazenamento.startswith("s3://") else Path(cfg.armazenamento)
