"""Cliente de IA com troca de provedor por configuração, cache e custo medido.

Fala três formatos de API, o que cobre Anthropic, DeepSeek, OpenCode Go e Amazon Bedrock:
  - openai:    POST {base}/chat/completions
  - anthropic: POST {base}/messages
  - bedrock:   API Converse do Bedrock (boto3), credencial pelo perfil AWS, sem chave no .env
Quem atende cada camada está em modelos.toml. As chaves vêm do .env.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

CONFIG = Path(__file__).with_name("modelos.toml")
ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "mitra/0.1 (hackathon-vx-d02)"


class SemProvedor(RuntimeError):
    """Nenhum modelo da camada tem chave configurada, ou todos falharam."""


class TetoAtingido(SemProvedor):
    """O gasto de IA do dia chegou ao teto (MITRA_TETO_DIA_USD): só regra e cache até amanhã."""


class RespostaInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Modelo:
    provedor: str
    nome: str
    esforco: str | None = None

    @property
    def rotulo(self) -> str:
        return f"{self.provedor}:{self.nome}" + (f"@{self.esforco}" if self.esforco else "")


@dataclass
class Resposta:
    dados: dict
    modelo: Modelo
    tokens_in: int
    tokens_out: int
    custo_usd: float
    do_cache: bool = False
    tentativas: list[str] = field(default_factory=list)   # modelos que falharam antes


def extrair_json(texto: str) -> dict:
    """Aceita JSON puro ou dentro de ```json ... ```; recusa qualquer outra coisa."""
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto, re.S)
    if m:
        texto = m.group(1)
    elif not texto.startswith("{"):
        inicio, fim = texto.find("{"), texto.rfind("}")
        if inicio < 0 or fim < inicio:
            raise RespostaInvalida("resposta sem JSON")
        texto = texto[inicio : fim + 1]
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise RespostaInvalida(f"JSON inválido: {e}") from e
    if not isinstance(dados, dict):
        raise RespostaInvalida("o JSON precisa ser um objeto")
    return dados


# ------------------------------------------------------------------ provedores


class ClienteHTTP:
    """Chamada real a um provedor. Devolve (texto, tokens_in, tokens_out)."""

    def __init__(self, nome: str, cfg: dict, chave: str, http: httpx.Client):
        self.nome, self.cfg, self.chave, self.http = nome, cfg, chave, http

    def _formato(self, modelo: str) -> tuple[str, str]:
        if modelo in self.cfg.get("modelos_anthropic", []):
            return "anthropic", self.cfg["base_anthropic"]
        return self.cfg["formato"], self.cfg["base"]

    def chamar(self, modelo: Modelo, sistema: str, usuario: str, max_tokens: int,
               sessao: str) -> tuple[str, int, int]:
        formato, base = self._formato(modelo.nome)
        headers = {"User-Agent": USER_AGENT}
        if self.cfg.get("cabecalho_sessao"):
            headers[self.cfg["cabecalho_sessao"]] = sessao

        if formato == "openai":
            headers["Authorization"] = f"Bearer {self.chave}"
            payload = {
                "model": modelo.nome,
                "messages": [{"role": "system", "content": sistema},
                             {"role": "user", "content": usuario}],
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            }
            if modelo.esforco:
                payload["reasoning_effort"] = modelo.esforco
            r = self.http.post(f"{base}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            d = r.json()
            texto = d["choices"][0]["message"].get("content") or ""
            uso = d.get("usage") or {}
            return texto, uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0)

        headers |= {"x-api-key": self.chave, "anthropic-version": "2023-06-01"}
        payload = {
            "model": modelo.nome,
            "system": sistema,
            "messages": [{"role": "user", "content": usuario}],
            "max_tokens": max_tokens,
        }
        r = self.http.post(f"{base}/messages", headers=headers, json=payload)
        r.raise_for_status()
        d = r.json()
        texto = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        uso = d.get("usage") or {}
        return texto, uso.get("input_tokens", 0), uso.get("output_tokens", 0)


# -------------------------------------------------------------------- roteador


class FalhaProvedor(RuntimeError):
    """Erro de um provedor que não fala HTTP direto (ex.: Bedrock via boto3), já sem detalhe de SDK."""


class ClienteBedrock:
    """Amazon Bedrock pela API Converse (boto3), a mesma para Claude, DeepSeek e Nova.

    Sem chave: a credencial vem do perfil AWS do ambiente (AWS_PROFILE), e a região do AWS_REGION
    (us-east-1 no evento). A regra do evento é menos de 1 requisição por segundo: o cliente espera
    o intervalo mínimo entre uma chamada e outra.
    """

    def __init__(self, nome: str, cfg: dict, cliente=None, relogio=None, dormir=None):
        import time

        self.nome, self.cfg = nome, cfg
        self.intervalo = float(cfg.get("intervalo_minimo_s", 1.1))
        self._relogio, self._dormir = relogio or time.monotonic, dormir or time.sleep
        self._ultima: float | None = None
        if cliente is None:
            from botocore.config import Config

            from . import aws

            cliente = aws.cliente("bedrock-runtime", cfg.get("regiao"),
                                  config=Config(read_timeout=180, retries={"max_attempts": 2, "mode": "standard"}))
        self.cliente = cliente

    def chamar(self, modelo: Modelo, sistema: str, usuario: str, max_tokens: int,
               sessao: str) -> tuple[str, int, int]:
        if self._ultima is not None and (falta := self.intervalo - (self._relogio() - self._ultima)) > 0:
            self._dormir(falta)
        self._ultima = self._relogio()
        try:
            r = self.cliente.converse(
                modelId=modelo.nome,
                system=[{"text": sistema}],
                messages=[{"role": "user", "content": [{"text": usuario}]}],
                inferenceConfig={"maxTokens": max_tokens},
            )
        except Exception as e:      # ClientError, throttling, credencial: o roteador tenta o próximo modelo
            raise FalhaProvedor(f"{type(e).__name__}: {str(e)[:200]}") from e
        blocos = r.get("output", {}).get("message", {}).get("content", [])
        texto = "".join(b.get("text", "") for b in blocos)
        uso = r.get("usage") or {}
        return texto, uso.get("inputTokens", 0), uso.get("outputTokens", 0)


def _cliente(nome: str, cfg: dict, chave: str, http: httpx.Client):
    return ClienteBedrock(nome, cfg) if cfg.get("formato") == "bedrock" else ClienteHTTP(nome, cfg, chave, http)


class Roteador:
    """Escolhe o modelo de cada camada, usa o cache e mede o custo.

    `provedores` permite injetar clientes falsos nos testes: {nome: objeto com chamar()}.
    """

    def __init__(self, conn=None, config: Path = CONFIG, env: dict | None = None,
                 provedores: dict | None = None, timeout: float = 180.0):
        if env is None:
            load_dotenv(ROOT / ".env")
            env = dict(os.environ)
        self.cfg = tomllib.loads(config.read_text(encoding="utf-8"))
        self.conn = conn
        # no link público: teto de gasto por dia (UTC), somado do cache, que guarda o custo de cada chamada
        try:
            self.teto_dia_usd = float(env.get("MITRA_TETO_DIA_USD") or 0) or None
        except ValueError:
            self.teto_dia_usd = None
        if provedores is not None:
            self.provedores = provedores
        else:
            http = httpx.Client(timeout=timeout)
            self.provedores = {
                nome: _cliente(nome, c, env[c["chave"]], http)
                for nome, c in self.cfg["provedores"].items()
                if env.get(c["chave"])
            }

    def candidatos(self, camada: int) -> list[Modelo]:
        return [
            Modelo(m["provedor"], m["modelo"], m.get("esforco"))
            for m in self.cfg["camadas"][str(camada)]["modelos"]
            if m["provedor"] in self.provedores
        ]

    def custo(self, modelo: str, tin: int, tout: int) -> float:
        preco_in, preco_out = self.cfg["precos"].get(modelo, (0.0, 0.0))
        return (tin * preco_in + tout * preco_out) / 1_000_000

    def _chave(self, tarefa: str, modelo: Modelo, versao_prompt: str, sistema: str, usuario: str) -> str:
        bruto = "\x1f".join([tarefa, modelo.rotulo, versao_prompt, sistema, usuario])
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()

    def _do_cache(self, chave: str):
        if self.conn is None:
            return None
        return self.conn.execute("SELECT * FROM analise_ia WHERE chave = ?", (chave,)).fetchone()

    def _guardar(self, chave, tarefa, modelo: Modelo, dados, tin, tout, custo):
        if self.conn is None:
            return
        with self.conn:
            self.conn.execute(
                "INSERT INTO analise_ia (chave, tarefa, provedor, modelo, resposta, "
                "tokens_in, tokens_out, custo_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (chave) DO UPDATE SET tarefa = excluded.tarefa, provedor = excluded.provedor, "
                "modelo = excluded.modelo, resposta = excluded.resposta, tokens_in = excluded.tokens_in, "
                "tokens_out = excluded.tokens_out, custo_usd = excluded.custo_usd, criada_em = excluded.criada_em",
                (chave, tarefa, modelo.provedor, modelo.rotulo,
                 json.dumps(dados, ensure_ascii=False), tin, tout, custo),
            )

    def pedir_json(self, tarefa: str, camada: int, sistema: str, usuario: str,
                   versao_prompt: str, max_tokens: int = 4000) -> Resposta:
        # 1) cache de qualquer modelo da camada, mesmo sem chave: a demo roda sem internet
        todos = [Modelo(m["provedor"], m["modelo"], m.get("esforco"))
                 for m in self.cfg["camadas"][str(camada)]["modelos"]]
        for modelo in todos:
            chave = self._chave(tarefa, modelo, versao_prompt, sistema, usuario)
            if (row := self._do_cache(chave)) is not None:
                return Resposta(json.loads(row["resposta"]), modelo, row["tokens_in"],
                                row["tokens_out"], row["custo_usd"], do_cache=True)
        # 2) chamada de verdade, na ordem da camada, só nos provedores com chave
        modelos = self.candidatos(camada)
        if not modelos:
            raise SemProvedor(f"nenhum provedor da camada {camada} tem chave no .env")
        if self.teto_dia_usd is not None and self.gasto_hoje() >= self.teto_dia_usd:
            raise TetoAtingido(f"teto diário de IA atingido (US$ {self.teto_dia_usd:.2f}): "
                               "até amanhã, só regra e respostas em cache")
        falhas = []
        for modelo in modelos:
            chave = self._chave(tarefa, modelo, versao_prompt, sistema, usuario)
            try:
                texto, tin, tout = self.provedores[modelo.provedor].chamar(
                    modelo, sistema, usuario, max_tokens, sessao=chave[:32]
                )
                dados = extrair_json(texto)
            except (httpx.HTTPError, FalhaProvedor, RespostaInvalida, KeyError) as e:
                falhas.append(f"{modelo.rotulo}: {type(e).__name__}: {str(e)[:160]}")
                continue
            custo = self.custo(modelo.nome, tin, tout)
            self._guardar(chave, tarefa, modelo, dados, tin, tout, custo)
            return Resposta(dados, modelo, tin, tout, custo, tentativas=falhas)
        raise SemProvedor("todos os modelos falharam: " + " | ".join(falhas))

    @property
    def ligada(self) -> bool:
        return bool(self.provedores)

    def gasto_hoje(self) -> float:
        if self.conn is None:
            return 0.0
        return self.conn.execute("SELECT COALESCE(SUM(custo_usd), 0) FROM analise_ia "
                                 "WHERE substr(criada_em, 1, 10) = ?",
                                 (datetime.now(timezone.utc).date().isoformat(),)).fetchone()[0]

    def chamadas(self) -> int:
        """Respostas guardadas: a diferença antes e depois de uma análise diz se houve chamada paga."""
        if self.conn is None:
            return 0
        return self.conn.execute("SELECT COUNT(*) FROM analise_ia").fetchone()[0]

    def custo_total(self) -> float:
        if self.conn is None:
            return 0.0
        return self.conn.execute("SELECT COALESCE(SUM(custo_usd), 0) FROM analise_ia").fetchone()[0]
