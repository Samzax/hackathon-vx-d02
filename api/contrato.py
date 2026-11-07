"""Gera api/openapi.json, o contrato versionado da API (o front gera os tipos TypeScript dele).

    uv run python -m api.contrato
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .main import criar_app

DESTINO = Path(__file__).with_name("openapi.json")


def gerar() -> dict:
    return criar_app(Config(montar_demo=False)).openapi()


if __name__ == "__main__":
    DESTINO.write_text(json.dumps(gerar(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"contrato em {DESTINO}")
