"""O agente fala com a torre só pela API, como o front: mesmas regras de acesso, mesma auditoria.

Autentica com o token de serviço (`MITRA_TOKEN_SERVICO`), que enxerga todas as empresas. Para dar o
agente a uma cliente, `MITRA_EMPRESA` prende o escopo: o agente só responde sobre aquela empresa.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

PREFIXO = "/api/v1"


class ErroTorre(Exception):
    """A API recusou ou não achou: vira resultado de erro da ferramenta (ToolError no MCP, texto no
    chat), e o modelo explica ao usuário."""


class NaoEncontrado(ErroTorre):
    """404 da API: não existe, ou está fora do escopo deste agente. Uma ferramenta que sabe o motivo
    (ex.: empresa que não passou pela instanciação) captura isto e explica melhor, sem depender do
    texto da mensagem."""


def _detalhe(r: httpx.Response) -> str:
    """O `detail` da API numa frase. O 422 de validação vem como lista de dicts: vira 'campo: mensagem',
    não a repr de Python, para o modelo entender o que corrigir."""
    try:
        corpo = r.json()
    except ValueError:
        return r.text[:300]
    detalhe = corpo.get("detail") if isinstance(corpo, dict) else corpo
    if isinstance(detalhe, list):
        partes = []
        for d in detalhe:
            if not isinstance(d, dict):
                continue
            campo = ".".join(str(x) for x in d.get("loc", []) if x not in ("body", "query", "path"))
            partes.append(f"{campo}: {d.get('msg', 'inválido')}" if campo else str(d.get("msg", "inválido")))
        return "; ".join(partes) or str(detalhe)[:300]
    return str(detalhe)[:300]


class Torre:
    def __init__(self, http: httpx.Client, empresa: str | None = None):
        self.http = http
        self.empresa_fixa = (empresa or "").strip() or None

    @classmethod
    def do_ambiente(cls) -> Torre:
        token = os.environ.get("MITRA_TOKEN_SERVICO")
        if not token:
            raise SystemExit("Defina MITRA_TOKEN_SERVICO (o mesmo token configurado na API).")
        url = os.environ.get("MITRA_API_URL", "http://localhost:8000").rstrip("/")
        http = httpx.Client(base_url=url, timeout=120, headers={"Authorization": f"Bearer {token}"})
        return cls(http, os.environ.get("MITRA_EMPRESA"))

    # ------------------------------------------------------------------ HTTP

    def _resposta(self, r: httpx.Response) -> Any:
        if r.status_code == 404:
            raise NaoEncontrado("Não encontrado: não existe, ou está fora do escopo deste agente.")
        if r.status_code >= 400:
            raise ErroTorre(f"A torre recusou ({r.status_code}): {_detalhe(r)}")
        tipo = r.headers.get("content-type", "")
        return r.json() if "json" in tipo else r.text

    def get(self, caminho: str, **params) -> Any:
        params = {k: v for k, v in params.items() if v is not None}
        try:
            r = self.http.get(PREFIXO + caminho, params=params)
        except httpx.HTTPError as e:    # API fora do ar, tempo esgotado: erro legível, não traceback
            raise ErroTorre(f"A torre não respondeu ({type(e).__name__}): confira a API e tente de novo.") from e
        return self._resposta(r)

    def post(self, caminho: str, corpo: dict) -> Any:
        try:
            r = self.http.post(PREFIXO + caminho, json=corpo)
        except httpx.HTTPError as e:
            raise ErroTorre(f"A torre não respondeu ({type(e).__name__}): confira a API e tente de novo.") from e
        return self._resposta(r)

    # ------------------------------------------------------------------ escopo

    def empresas(self) -> list[dict]:
        todas = self.get("/empresas")
        if self.empresa_fixa:
            todas = [e for e in todas if self._mesma(e, self.empresa_fixa)]
            if not todas:   # pin que não casa não pode destravar o agente em silêncio (ids mudam na demo)
                raise ErroTorre(f"MITRA_EMPRESA={self.empresa_fixa!r} não casa com nenhuma empresa da "
                                "torre: confira o nome (o id muda quando a demo é recriada).")
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
        """Aceita o código (B1), o id ou um pedaço do nome que só um ativo tenha ("VP-101", "Córrego
        Fundo"): quem pergunta fala do ativo pelo nome que usa no dia a dia, não pelo código da torre."""
        chave = str(ativo).strip().casefold()
        todos = self.get(f"/empresas/{empresa_id}/ativos")
        for a in todos:
            if a["codigo"].casefold() == chave or str(a["id"]) == chave:
                return a
        pelo_nome = [a for a in todos if chave and chave in a["nome"].casefold()]
        if len(pelo_nome) == 1:
            return pelo_nome[0]
        if pelo_nome:
            raise ErroTorre(f"Mais de um ativo com '{ativo}' no nome: "
                            + ", ".join(f"{a['codigo']} ({a['nome']})" for a in pelo_nome))
        raise ErroTorre(f"Ativo '{ativo}' não encontrado nessa empresa. Ativos: "
                        + ", ".join(f"{a['codigo']} ({a['nome']})" for a in todos[:30]))
