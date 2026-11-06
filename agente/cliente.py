"""O agente fala com a torre só pela API, como o front: mesmas regras de acesso, mesma auditoria.

Autentica com o token de serviço (`REGULAIA_TOKEN_SERVICO`), que enxerga todas as empresas. Para dar o
agente a uma cliente, `REGULAIA_EMPRESA` prende o escopo: o agente só responde sobre aquela empresa.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

PREFIXO = "/api/v1"


class ErroTorre(ToolError):
    """A API recusou ou não achou: vira resultado de erro da ferramenta, e o modelo explica ao usuário."""


class Torre:
    def __init__(self, http: httpx.Client, empresa: str | None = None):
        self.http = http
        self.empresa_fixa = (empresa or "").strip() or None

    @classmethod
    def do_ambiente(cls) -> Torre:
        token = os.environ.get("REGULAIA_TOKEN_SERVICO")
        if not token:
            raise SystemExit("Defina REGULAIA_TOKEN_SERVICO (o mesmo token configurado na API).")
        url = os.environ.get("REGULAIA_API_URL", "http://localhost:8000").rstrip("/")
        http = httpx.Client(base_url=url, timeout=120, headers={"Authorization": f"Bearer {token}"})
        return cls(http, os.environ.get("REGULAIA_EMPRESA"))

    # ------------------------------------------------------------------ HTTP

    def _resposta(self, r: httpx.Response) -> Any:
        if r.status_code == 404:
            raise ErroTorre("Não encontrado (ou fora do escopo deste agente).")
        if r.status_code >= 400:
            try:
                detalhe = r.json().get("detail")
            except ValueError:
                detalhe = r.text[:300]
            raise ErroTorre(f"A torre recusou ({r.status_code}): {detalhe}")
        tipo = r.headers.get("content-type", "")
        return r.json() if "json" in tipo else r.text

    def get(self, caminho: str, **params) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        return self._resposta(self.http.get(PREFIXO + caminho, params=params))

    def post(self, caminho: str, corpo: dict) -> Any:
        return self._resposta(self.http.post(PREFIXO + caminho, json=corpo))

    # ------------------------------------------------------------------ escopo

    def empresas(self) -> list[dict]:
        todas = self.get("/empresas")
        if self.empresa_fixa:
            todas = [e for e in todas if self._mesma(e, self.empresa_fixa)]
        return todas

    @staticmethod
    def _mesma(e: dict, chave: str) -> bool:
        return str(e["id"]) == chave or e["nome"].casefold() == chave.casefold()

    def empresa_id(self, empresa: str | int | None) -> int:
        """Aceita id ou nome. Sem empresa: a única do escopo (ou erro pedindo para escolher)."""
        vistas = self.empresas()
        if empresa in (None, ""):
            if len(vistas) == 1:
                return vistas[0]["id"]
            nomes = ", ".join(f"{e['nome']} (id {e['id']})" for e in vistas)
            raise ErroTorre(f"Diga de qual empresa: {nomes}.")
        chave = str(empresa).strip()
        achadas = [e for e in vistas if self._mesma(e, chave)] or \
                  [e for e in vistas if chave.casefold() in e["nome"].casefold()]
        if len(achadas) != 1:
            raise ErroTorre(f"Empresa '{empresa}' não encontrada no escopo deste agente." if not achadas else
                            f"Mais de uma empresa com '{empresa}': " + ", ".join(e["nome"] for e in achadas))
        return achadas[0]["id"]

    def ativo(self, empresa_id: int, ativo: str | int) -> dict:
        """Aceita o código (B1) ou o id do ativo."""
        chave = str(ativo).strip().casefold()
        for a in self.get(f"/empresas/{empresa_id}/ativos"):
            if a["codigo"].casefold() == chave or str(a["id"]) == chave:
                return a
        raise ErroTorre(f"Ativo '{ativo}' não encontrado nessa empresa.")
