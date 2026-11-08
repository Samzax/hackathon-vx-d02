"""Assistente Mitra: o Claude responde sobre a torre usando as mesmas ferramentas de leitura do agente MCP.

O modelo não vê o banco: só o que as ferramentas devolvem, e as ferramentas falam com a torre pela API com
a sessão de quem pergunta (mesmo escopo, mesma regra de acesso). Depois da resposta, o Python confere:
todo trecho citado entre aspas, toda data e todo código de obrigação ou ativo da resposta precisam estar no
que as ferramentas devolveram. O que não estiver volta para o modelo corrigir uma vez; o que sobrar vai
marcado para quem lê.

Provedores (`[pergunta]` em modelos.toml, o primeiro com chave vale): Bedrock pela API Converse (o da AWS),
a API da Anthropic e os de formato OpenAI (DeepSeek, OpenCode Go), todos com uso de ferramentas.

Avaliação com o modelo de verdade (perguntas em `tests/pergunta_avaliacao.toml`):
    MITRA_BEDROCK=1 AWS_PROFILE=vx uv run python -m mitra.pergunta avaliar [--gravar]
"""

from __future__ import annotations

import inspect
import json
import re
import threading
import time
import tomllib
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx
from pydantic import ConfigDict, ValidationError, create_model

from .ia import CONFIG, USER_AGENT, Modelo, Roteador, SemProvedor, TetoAtingido

SISTEMA = Path(__file__).with_name("pergunta_sistema.md")
VERSAO_PROMPT = "pergunta-1"
MAX_RODADAS = 8                  # chamadas ao modelo por pergunta (cada uma pode pedir várias ferramentas)
MAX_RESULTADO = 24_000           # caracteres de cada resultado de ferramenta que vão para o modelo
MAX_HISTORICO = 8                # mensagens anteriores da conversa
MAX_PERGUNTA = 2_000
# na AWS o CloudFront espera a resposta por 60 s: a pergunta tem de fechar antes, com folga
PRAZO_S = 45.0


class ErroPergunta(RuntimeError):
    pass


class Demorou(RuntimeError):
    """A pergunta passou do prazo. Leva o que já foi gasto (`parcial`), para entrar no teto do dia."""

    def __init__(self, msg: str, parcial: "Resposta | None" = None):
        super().__init__(msg)
        self.parcial = parcial


# ------------------------------------------------------------------ ferramentas


@dataclass
class Ferramenta:
    nome: str
    descricao: str
    esquema: dict
    funcao: Callable
    validar: Any            # modelo Pydantic dos argumentos

    def chamar(self, args: dict) -> Any:
        dados = self.validar(**(args or {})).model_dump()
        return self.funcao(**dados)


def preparar(funcoes: list[Callable], fora: set[str] = frozenset()) -> list[Ferramenta]:
    """Esquema JSON de cada ferramenta a partir da assinatura (o mesmo que o MCP gera)."""
    out = []
    for fn in funcoes:
        if fn.__name__ in fora:
            continue
        campos = {}
        for nome, p in inspect.signature(fn).parameters.items():
            padrao = ... if p.default is inspect.Parameter.empty else p.default
            campos[nome] = (p.annotation, padrao)
        # argumento que a ferramenta não tem volta como erro para o modelo, em vez de sumir calado
        modelo = create_model(f"Args_{fn.__name__}", __config__=ConfigDict(extra="forbid"), **campos)
        esquema = modelo.model_json_schema()
        esquema.pop("title", None)
        for prop in esquema.get("properties", {}).values():
            prop.pop("title", None)
        out.append(Ferramenta(fn.__name__, inspect.cleandoc(fn.__doc__ or ""), esquema, fn, modelo))
    return out


def _texto_do_resultado(r: Any) -> str:
    t = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False, default=str)
    if len(t) > MAX_RESULTADO:
        t = t[:MAX_RESULTADO] + " …(resultado cortado: peça um filtro, como o ativo ou o status)"
    return t


# ------------------------------------------------------------------ provedores


@dataclass
class Chamada:
    id: str
    nome: str
    args: dict


@dataclass
class Passo:
    texto: str
    chamadas: list[Chamada]
    tokens_in: int
    tokens_out: int
    cache_lido: int = 0          # tokens de entrada lidos do cache de prompt (cobrados a 10%)
    cache_escrito: int = 0       # tokens gravados no cache (cobrados a 125%)
    cortada: bool = False        # parou no limite de tokens, no meio da resposta


CACHE = {"cachePoint": {"type": "default"}}


class _Bedrock:
    """API Converse do Bedrock. A regra do evento (menos de 1 pedido por segundo) vale para o processo
    todo, então o intervalo é um só para todas as perguntas ao mesmo tempo.

    Cache de prompt: cada rodada reenvia o sistema, as ferramentas e a conversa até ali. Um ponto de cache
    depois das ferramentas, outro depois do sistema e outro no fim da conversa fazem a rodada seguinte
    pagar só o que é novo (o resto sai a 10% do preço)."""

    _trava = threading.Lock()
    _ultima = 0.0

    def __init__(self, cfg: dict, cliente=None):
        self.intervalo = float(cfg.get("intervalo_minimo_s", 1.1))
        if cliente is None:
            from botocore.config import Config

            from . import aws

            cliente = aws.cliente("bedrock-runtime", cfg.get("regiao"),
                                  config=Config(read_timeout=PRAZO_S, retries={"max_attempts": 2, "mode": "standard"}))
        self.cliente = cliente

    def iniciar(self, sistema: str, ferramentas: list[Ferramenta], historico: list[tuple[str, str]]) -> dict:
        msgs = [{"role": "user" if p == "usuario" else "assistant", "content": [{"text": t}]} for p, t in historico]
        tools = [{"toolSpec": {"name": f.nome, "description": f.descricao, "inputSchema": {"json": f.esquema}}}
                 for f in ferramentas] + [CACHE]
        return {"sistema": [{"text": sistema}, CACHE], "msgs": msgs, "tools": tools}

    @staticmethod
    def _marcar_fim(msgs: list[dict]) -> None:
        """Um só ponto de cache na conversa, no fim da última mensagem (o Bedrock aceita até 4 no total)."""
        for m in msgs:
            m["content"] = [b for b in m["content"] if "cachePoint" not in b]
        if msgs:
            msgs[-1]["content"].append(CACHE)

    def passo(self, estado: dict, modelo: Modelo, max_tokens: int) -> Passo:
        with self._trava:
            falta = self.intervalo - (time.monotonic() - _Bedrock._ultima)
            if falta > 0:
                time.sleep(falta)
            _Bedrock._ultima = time.monotonic()
        try:
            self._marcar_fim(estado["msgs"])
            r = self.cliente.converse(modelId=modelo.nome, system=estado["sistema"],
                                      messages=estado["msgs"], toolConfig={"tools": estado["tools"]},
                                      inferenceConfig={"maxTokens": max_tokens})
        except Exception as e:
            raise ErroPergunta(f"Bedrock: {type(e).__name__}: {str(e)[:200]}") from e
        msg = r["output"]["message"]
        estado["msgs"].append(msg)
        texto = "".join(b.get("text", "") for b in msg["content"])
        chamadas = [Chamada(b["toolUse"]["toolUseId"], b["toolUse"]["name"], b["toolUse"].get("input") or {})
                    for b in msg["content"] if "toolUse" in b]
        uso = r.get("usage") or {}
        return Passo(texto, chamadas, uso.get("inputTokens", 0), uso.get("outputTokens", 0),
                     uso.get("cacheReadInputTokens", 0), uso.get("cacheWriteInputTokens", 0),
                     r.get("stopReason") == "max_tokens")

    def resultados(self, estado: dict, res: list[tuple[Chamada, str, bool]]) -> None:
        estado["msgs"].append({"role": "user", "content": [
            {"toolResult": {"toolUseId": c.id, "content": [{"text": t}], "status": "error" if erro else "success"}}
            for c, t, erro in res]})

    def corrigir(self, estado: dict, texto: str) -> None:
        estado["msgs"].append({"role": "user", "content": [{"text": texto}]})


class _Anthropic:
    def __init__(self, cfg: dict, chave: str, http: httpx.Client):
        self.base, self.chave, self.http = cfg["base"], chave, http

    def iniciar(self, sistema, ferramentas, historico) -> dict:
        msgs = [{"role": "user" if p == "usuario" else "assistant", "content": t} for p, t in historico]
        tools = [{"name": f.nome, "description": f.descricao, "input_schema": f.esquema} for f in ferramentas]
        return {"sistema": sistema, "msgs": msgs, "tools": tools}

    def passo(self, estado, modelo: Modelo, max_tokens: int) -> Passo:
        r = self.http.post(f"{self.base}/messages", headers={
            "x-api-key": self.chave, "anthropic-version": "2023-06-01", "User-Agent": USER_AGENT},
            json={"model": modelo.nome, "system": estado["sistema"], "messages": estado["msgs"],
                  "tools": estado["tools"], "max_tokens": max_tokens})
        if r.status_code >= 400:
            raise ErroPergunta(f"Anthropic {r.status_code}: {r.text[:200]}")
        d = r.json()
        estado["msgs"].append({"role": "assistant", "content": d["content"]})
        texto = "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")
        chamadas = [Chamada(b["id"], b["name"], b.get("input") or {}) for b in d["content"] if b.get("type") == "tool_use"]
        uso = d.get("usage") or {}
        return Passo(texto, chamadas, uso.get("input_tokens", 0), uso.get("output_tokens", 0),
                     cortada=d.get("stop_reason") == "max_tokens")

    def resultados(self, estado, res) -> None:
        estado["msgs"].append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c.id, "content": t, "is_error": erro} for c, t, erro in res]})

    def corrigir(self, estado, texto: str) -> None:
        estado["msgs"].append({"role": "user", "content": texto})


class _OpenAI:
    """Formato /chat/completions com `tools` (DeepSeek, OpenCode Go)."""

    def __init__(self, cfg: dict, chave: str, http: httpx.Client):
        self.cfg, self.chave, self.http = cfg, chave, http

    def iniciar(self, sistema, ferramentas, historico) -> dict:
        msgs = [{"role": "system", "content": sistema}]
        msgs += [{"role": "user" if p == "usuario" else "assistant", "content": t} for p, t in historico]
        tools = [{"type": "function", "function": {"name": f.nome, "description": f.descricao,
                                                    "parameters": f.esquema}} for f in ferramentas]
        return {"msgs": msgs, "tools": tools, "sessao": uuid.uuid4().hex}

    def passo(self, estado, modelo: Modelo, max_tokens: int) -> Passo:
        headers = {"Authorization": f"Bearer {self.chave}", "User-Agent": USER_AGENT}
        if self.cfg.get("cabecalho_sessao"):
            headers[self.cfg["cabecalho_sessao"]] = estado["sessao"]
        payload = {"model": modelo.nome, "messages": estado["msgs"], "tools": estado["tools"], "max_tokens": max_tokens}
        if modelo.esforco:
            payload["reasoning_effort"] = modelo.esforco
        r = self.http.post(f"{self.cfg['base']}/chat/completions", headers=headers, json=payload)
        if r.status_code >= 400:
            raise ErroPergunta(f"{modelo.provedor} {r.status_code}: {r.text[:200]}")
        d = r.json()
        msg = d["choices"][0]["message"]
        estado["msgs"].append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
        chamadas = []
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_argumentos_invalidos": c["function"].get("arguments")}
            chamadas.append(Chamada(c["id"], c["function"]["name"], args))
        uso = d.get("usage") or {}
        return Passo(msg.get("content") or "", chamadas, uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0),
                     cortada=d["choices"][0].get("finish_reason") == "length")

    def resultados(self, estado, res) -> None:
        for c, t, _erro in res:
            estado["msgs"].append({"role": "tool", "tool_call_id": c.id, "content": t})

    def corrigir(self, estado, texto: str) -> None:
        estado["msgs"].append({"role": "user", "content": texto})


def provedores_da_config(env: dict, cfg: dict, http: httpx.Client | None = None) -> dict:
    """Os provedores com chave no ambiente (Bedrock: MITRA_BEDROCK=1 e a credencial AWS do ambiente)."""
    out = {}
    http = http or httpx.Client(timeout=120)
    for nome, c in cfg["provedores"].items():
        if not env.get(c["chave"]):
            continue
        if c["formato"] == "bedrock":
            out[nome] = _Bedrock(c)
        elif c["formato"] == "anthropic":
            out[nome] = _Anthropic(c, env[c["chave"]], http)
        else:
            out[nome] = _OpenAI(c, env[c["chave"]], http)
    return out


# ------------------------------------------------------------------ conferência


def _normal(t: str) -> str:
    t = unicodedata.normalize("NFKC", t).casefold()
    t = re.sub(r"[“”«»\"'‘’`]", "", t)
    return re.sub(r"\s+", " ", t).strip()


_RE_CITACAO = re.compile(r"[“\"«]([^”\"»\n]{1,600})[”\"»]")
# filtrar o trecho curto depois, não na regex: senão a aspa que fecha um trecho curto casa com a que abre o
# próximo, e o "trecho" vira o texto do meio
MIN_CITACAO = 25
_RE_DATA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_RE_DATA_BR = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
# obrigação (OB-01, R95-12, D140-03, N22-ZAS1) e ativo (B3, U1, E2, L1)
_RE_CODIGO = re.compile(r"\b[A-Z][A-Z0-9]{0,3}-(?:\d{1,3}|ZAS\d)\b|\b[BUEL]\d{1,2}\b")


def _datas(t: str) -> set[str]:
    return ({f"{a}-{m}-{d}" for a, m, d in _RE_DATA_ISO.findall(t)}
            | {f"{a}-{m}-{d}" for d, m, a in _RE_DATA_BR.findall(t)})


@dataclass
class Conferencia:
    citacoes: int = 0
    citacoes_fora: list[str] = field(default_factory=list)
    datas_fora: list[str] = field(default_factory=list)
    codigos_fora: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.citacoes_fora or self.datas_fora or self.codigos_fora)

    def resumo(self) -> str:
        partes = []
        if self.citacoes_fora:
            partes.append("trechos citados que não estão nos resultados: " + " | ".join(self.citacoes_fora))
        if self.datas_fora:
            partes.append("datas que não estão nos resultados: " + ", ".join(self.datas_fora))
        if self.codigos_fora:
            partes.append("códigos que não estão nos resultados: " + ", ".join(self.codigos_fora))
        return "; ".join(partes)


def conferir(resposta: str, resultados: list[str], pergunta: str = "") -> Conferencia:
    """O que a resposta afirma com aspas, data ou código precisa estar no que as ferramentas devolveram
    (ou na própria pergunta, que o usuário escreveu)."""
    base = "\n".join(resultados) + "\n" + pergunta
    base_n = _normal(base)
    c = Conferencia()
    for trecho in _RE_CITACAO.findall(resposta):
        if len(trecho) < MIN_CITACAO:
            continue
        c.citacoes += 1
        t = _normal(trecho).rstrip(".…")
        if t and t not in base_n:
            c.citacoes_fora.append(trecho[:120])
    c.datas_fora = sorted(_datas(resposta) - _datas(base))
    codigos_base = set(_RE_CODIGO.findall(base))
    c.codigos_fora = sorted(set(_RE_CODIGO.findall(resposta)) - codigos_base)
    return c


# ------------------------------------------------------------------ a pergunta


@dataclass
class Uso:
    ferramenta: str
    args: dict
    erro: str | None = None


@dataclass
class Resposta:
    texto: str
    modelo: str
    ferramentas: list[Uso]
    conferencia: Conferencia
    tokens_in: int
    tokens_out: int
    custo_usd: float
    corrigida: bool = False
    tokens_cache: int = 0        # dos tokens_in, quantos vieram do cache de prompt
    segundos: float = 0.0

    def para_api(self) -> dict:
        d = asdict(self)
        d["conferencia"] = {**asdict(self.conferencia), "ok": self.conferencia.ok}
        return d


def _config(config: Path) -> dict:
    return tomllib.loads(config.read_text(encoding="utf-8"))


def candidatos(cfg: dict, provedores: dict) -> list[Modelo]:
    return [Modelo(m["provedor"], m["modelo"], m.get("esforco")) for m in cfg["pergunta"]["modelos"]
            if m["provedor"] in provedores]


def perguntar(pergunta: str, ferramentas: list[Ferramenta], *, historico: list[tuple[str, str]] | None = None,
              provedores: dict, roteador: Roteador | None = None, config: Path = CONFIG,
              max_tokens: int = 2000, prazo: float = PRAZO_S) -> Resposta:
    """Uma pergunta, com o histórico da conversa (pares (papel, texto), papel 'usuario' ou 'torre')."""
    pergunta = (pergunta or "").strip()
    if not pergunta:
        raise ErroPergunta("pergunta vazia")
    if len(pergunta) > MAX_PERGUNTA:
        raise ErroPergunta(f"pergunta longa demais (máximo {MAX_PERGUNTA} caracteres)")
    cfg = _config(config)
    modelos = candidatos(cfg, provedores)
    if not modelos:
        raise SemProvedor("nenhum provedor de IA ligado para o Assistente Mitra")
    if roteador is not None and roteador.teto_dia_usd is not None and roteador.gasto_hoje() >= roteador.teto_dia_usd:
        raise TetoAtingido(f"teto diário de IA atingido (US$ {roteador.teto_dia_usd:.2f}); volte amanhã")
    inicio = time.monotonic()
    sistema = SISTEMA.read_text(encoding="utf-8")
    hist = [(p, t[:4000]) for p, t in (historico or [])[-MAX_HISTORICO:] if t.strip()]
    # a conversa precisa começar pelo usuário e alternar (exigência do Bedrock e da Anthropic)
    while hist and hist[0][0] != "usuario":
        hist.pop(0)
    hist.append(("usuario", pergunta))
    por_nome = {f.nome: f for f in ferramentas}

    falhas = []
    for modelo in modelos:
        prov = provedores[modelo.provedor]
        estado = prov.iniciar(sistema, ferramentas, hist)
        usos: list[Uso] = []
        resultados: list[str] = []
        tin = tout = lido = escrito = 0
        corrigida = False
        try:
            texto = ""
            for _ in range(MAX_RODADAS):
                if time.monotonic() - inicio > prazo:
                    custo = _custo(cfg, modelo.nome, tin, tout, lido, escrito)
                    parcial = Resposta("", modelo.rotulo, usos, conferir("", []), tin + lido + escrito, tout,
                                       custo, corrigida, lido, round(time.monotonic() - inicio, 1))
                    raise Demorou(f"a pergunta passou de {prazo:.0f} s; tente uma pergunta mais específica "
                                  "(um ativo, uma norma)", parcial)
                p = prov.passo(estado, modelo, max_tokens)
                tin, tout = tin + p.tokens_in, tout + p.tokens_out
                lido, escrito = lido + p.cache_lido, escrito + p.cache_escrito
                if p.chamadas:
                    res = []
                    for c in p.chamadas:
                        f = por_nome.get(c.nome)
                        try:
                            if f is None:
                                raise ErroPergunta(f"ferramenta desconhecida: {c.nome}")
                            t, erro = _texto_do_resultado(f.chamar(c.args)), None
                        except ValidationError as e:
                            t = erro = f"argumentos inválidos: {e.errors()[:3]}"
                        except Exception as e:       # ErroTorre (404, 403...) e afins: o modelo explica
                            t = erro = f"{type(e).__name__}: {e}"
                        usos.append(Uso(c.nome, c.args, erro if erro else None))
                        if not erro:
                            # o que o modelo consultou (ex.: hoje = 2027-08-02) também é base da conferência
                            resultados.append(json.dumps(c.args, ensure_ascii=False) + "\n" + t)
                        else:
                            # a mensagem de erro também é dado da torre (ex.: "não encontrado" traz a lista
                            # de ativos, que o prompt manda usar); os argumentos de uma chamada que falhou, não
                            resultados.append(t)
                        res.append((c, t, bool(erro)))
                    prov.resultados(estado, res)
                    continue
                texto = p.texto.strip()
                conf = conferir(texto, resultados, pergunta)
                if p.cortada and not corrigida:
                    corrigida = True
                    prov.corrigir(estado, "Sua resposta passou do limite de tamanho e foi cortada no meio. "
                                  "Reescreva do começo, mais curta (até 250 palavras): o essencial, com a "
                                  "fonte, e onde agir na torre.")
                    continue
                if p.cortada:
                    texto += "\n\n_(resposta cortada no limite de tamanho: peça o detalhe de uma parte)_"
                if conf.ok or corrigida:
                    break
                corrigida = True
                prov.corrigir(estado, "Conferência automática: " + conf.resumo() + ". Reescreva a resposta "
                              "citando só o que veio das ferramentas (consulte de novo se precisar); o que "
                              "não estiver nelas, diga que não sabe.")
            else:
                raise ErroPergunta(f"sem resposta em {MAX_RODADAS} rodadas")
        except ErroPergunta as e:
            falhas.append(f"{modelo.rotulo}: {e}")
            continue
        conf = conferir(texto, resultados, pergunta)
        custo = _custo(cfg, modelo.nome, tin, tout, lido, escrito)
        r = Resposta(texto, modelo.rotulo, usos, conf, tin + lido + escrito, tout, custo, corrigida, lido,
                     round(time.monotonic() - inicio, 1))
        if roteador is not None:
            registrar_custo(roteador, r)
        return r
    raise SemProvedor("todos os modelos falharam: " + " | ".join(falhas))


def registrar_custo(roteador: Roteador, r: Resposta) -> None:
    """O custo entra na mesma conta do dia que as outras chamadas de IA (`analise_ia`): é ela que o teto
    diário (MITRA_TETO_DIA_USD) soma."""
    provedor, _, nome = r.modelo.partition(":")
    roteador._guardar(f"pergunta-{uuid.uuid4().hex}", "pergunta", Modelo(provedor, nome),
                      {"ferramentas": [u.ferramenta for u in r.ferramentas], "conferencia_ok": r.conferencia.ok},
                      r.tokens_in, r.tokens_out, r.custo_usd)


def _custo(cfg: dict, modelo: str, tin: int, tout: int, lido: int = 0, escrito: int = 0) -> float:
    pin, pout = cfg["precos"].get(modelo, (0.0, 0.0))
    return (tin * pin + lido * pin * 0.1 + escrito * pin * 1.25 + tout * pout) / 1_000_000


# ------------------------------------------------------------------ avaliação

AVALIACAO = Path(__file__).resolve().parent.parent / "tests" / "pergunta_avaliacao.toml"


@dataclass
class Nota:
    id: str
    pergunta: str
    passou: bool
    falhas: list[str]
    resposta: str
    ferramentas: list[str]
    modelo: str
    custo_usd: float
    segundos: float = 0.0


def avaliar_resposta(caso: dict, r: Resposta) -> list[str]:
    """Critérios objetivos do caso: o que a resposta precisa conter, o que não pode conter, quais
    ferramentas precisam ter sido usadas, e a conferência limpa."""
    falhas = []
    texto = _normal(r.texto)
    for item in caso.get("contem", []):
        opcoes = item if isinstance(item, list) else [item]
        # data vale em qualquer das duas formas que a conferência aceita (2027-08-02 ou 02/08/2027)
        opcoes = opcoes + [f"{m[3]}/{m[2]}/{m[1]}" for o in opcoes
                           if (m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", o))]
        if not any(_normal(o) in texto for o in opcoes):
            falhas.append(f"falta: {' ou '.join(opcoes)}")
    for item in caso.get("nao_contem", []):
        if _normal(item) in texto:
            falhas.append(f"não devia dizer: {item}")
    usadas = {u.ferramenta for u in r.ferramentas}
    for f in caso.get("ferramentas", []):
        opcoes = f if isinstance(f, list) else [f]
        if not usadas & set(opcoes):
            falhas.append(f"não usou: {' ou '.join(opcoes)}")
    if not r.conferencia.ok:
        falhas.append("conferência: " + r.conferencia.resumo())
    return falhas


def casos(arquivo: Path = AVALIACAO) -> list[dict]:
    return tomllib.loads(arquivo.read_text(encoding="utf-8"))["caso"]


def _main(argv: list[str]) -> int:   # pragma: no cover - roda com o modelo de verdade
    import argparse
    import os
    import tempfile

    from dotenv import load_dotenv
    from fastapi.testclient import TestClient

    from agente.cliente import Torre
    from agente.ferramentas import CHAMA_IA, ferramentas as funcoes
    from api.config import Config
    from api.main import criar_app

    from . import demo

    ap = argparse.ArgumentParser(prog="python -m mitra.pergunta")
    ap.add_argument("acao", choices=["avaliar"])
    ap.add_argument("--caso", action="append", help="só estes ids")
    ap.add_argument("--gravar", action="store_true", help="grava as respostas do modelo para o teste do CI")
    a = ap.parse_args(argv)

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    env = dict(os.environ)
    pasta = Path(tempfile.mkdtemp(prefix="mitra-pergunta-"))
    banco = pasta / "demo.db"
    # a demo monta só com o cache de IA do repositório: sem provedor ligado, nenhuma chamada paga aqui
    ligados = {c["chave"]: os.environ.pop(c["chave"], None) for c in _config(CONFIG)["provedores"].values()}
    demo.preparar(str(banco))
    os.environ.update({k: v for k, v in ligados.items() if v is not None})
    token = uuid.uuid4().hex
    app = criar_app(Config(banco=str(banco), banco_cache=str(pasta / "cache.db"),
                           armazenamento=str(pasta / "uploads"), token_servico=token))
    http = TestClient(app, headers={"Authorization": f"Bearer {token}"})
    cfg = _config(CONFIG)
    gravador = Gravador(provedores_da_config(env, cfg)) if a.gravar else None
    provs = gravador.provedores if gravador else provedores_da_config(env, cfg)
    notas = []
    for caso in casos():
        if a.caso and caso["id"] not in a.caso:
            continue
        torre = Torre(http, empresa=caso.get("empresa", "Mineradora Serra Azul"))
        fs = preparar(funcoes(torre), fora=CHAMA_IA)
        if gravador:
            gravador.comecar(caso["id"])
        try:
            r = perguntar(caso["pergunta"], fs, provedores=provs)
        except Demorou as e:        # estourou o prazo: o caso reprova, a avaliação segue
            p = e.parcial
            notas.append(Nota(caso["id"], caso["pergunta"], False, [str(e)],
                              (p.texto if p else "") or "", [u.ferramenta for u in p.ferramentas] if p else [],
                              p.modelo if p else "-", p.custo_usd if p else 0.0, p.segundos if p else 0.0))
            print(f"FALHOU {caso['id']}: {e}", flush=True)
            continue
        falhas = avaliar_resposta(caso, r)
        notas.append(Nota(caso["id"], caso["pergunta"], not falhas, falhas, r.texto,
                          [u.ferramenta for u in r.ferramentas], r.modelo, r.custo_usd, r.segundos))
        print(f"{'OK ' if not falhas else 'FALHOU'} {caso['id']}: {', '.join(falhas) or 'tudo certo'}"
              f" ({r.modelo}, US$ {r.custo_usd:.4f}, {r.segundos:.1f} s)", flush=True)
    if gravador:
        gravador.salvar()
    passou = sum(n.passou for n in notas)
    print(f"\n{passou}/{len(notas)} casos; custo US$ {sum(n.custo_usd for n in notas):.4f}")
    relatorio = Path(__file__).resolve().parent.parent / "docs" / "AVALIACAO_PERGUNTA.md"
    escrever_relatorio(relatorio, notas)
    return 0 if passou == len(notas) else 1


def escrever_relatorio(arquivo: Path, notas: list[Nota]) -> None:
    passou = sum(n.passou for n in notas)
    linhas = ["# Avaliação do Assistente Mitra", "",
              f"Gerado por `python -m mitra.pergunta avaliar` contra a demo (Mineradora Serra Azul), com o "
              f"modelo de verdade. **{passou} de {len(notas)} casos passaram**; custo total "
              f"US$ {sum(n.custo_usd for n in notas):.4f}; a mais lenta levou "
              f"{max((n.segundos for n in notas), default=0):.1f} s (o prazo é {PRAZO_S:.0f} s).", "",
              "Cada caso tem critérios objetivos em `tests/pergunta_avaliacao.toml`: o que a resposta precisa "
              "conter, o que não pode conter, que ferramenta precisa ter usado, e a conferência do Python "
              "(trecho entre aspas, data e código de obrigação ou ativo precisam estar no que as ferramentas "
              "devolveram).", ""]
    for n in notas:
        linhas += [f"## {'✅' if n.passou else '❌'} {n.id}", "", f"**Pergunta:** {n.pergunta}", "",
                   f"**Modelo:** `{n.modelo}` · **ferramentas:** {', '.join(n.ferramentas) or 'nenhuma'} · "
                   f"US$ {n.custo_usd:.4f} · {n.segundos:.1f} s", ""]
        if n.falhas:
            linhas += ["**Falhas:** " + "; ".join(n.falhas), ""]
        linhas += ["<details><summary>Resposta</summary>", "", n.resposta, "", "</details>", ""]
    arquivo.write_text("\n".join(linhas), encoding="utf-8")


# ------------------------------------------------------------------ gravação para o CI

GRAVACOES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pergunta"


class Gravador:
    """Grava cada passo do modelo de verdade, por caso, para o CI repetir sem chave (`Repetidor`)."""

    def __init__(self, provedores: dict):
        self.passos: dict[str, list[dict]] = {}
        self.caso = ""
        self.provedores = {nome: _Gravado(p, self) for nome, p in provedores.items()}

    def comecar(self, caso: str) -> None:
        self.caso = caso
        self.passos[caso] = []

    def salvar(self) -> None:
        GRAVACOES.mkdir(parents=True, exist_ok=True)
        for caso, passos in self.passos.items():
            (GRAVACOES / f"{caso}.json").write_text(json.dumps(passos, ensure_ascii=False, indent=1), encoding="utf-8")


class _Gravado:
    def __init__(self, prov, gravador: Gravador):
        self.prov, self.g = prov, gravador

    def iniciar(self, *a):
        return self.prov.iniciar(*a)

    def passo(self, estado, modelo, max_tokens):
        p = self.prov.passo(estado, modelo, max_tokens)
        self.g.passos[self.g.caso].append({"modelo": modelo.nome, **asdict(p)})
        return p

    def resultados(self, *a):
        return self.prov.resultados(*a)

    def corrigir(self, *a):
        return self.prov.corrigir(*a)


class Repetidor:
    """Provedor falso que devolve os passos gravados, na ordem (testes e CI, sem chave e sem custo)."""

    def __init__(self, passos: list[dict]):
        self.passos = list(passos)
        self.vistos: list[list] = []      # o que voltou de ferramenta a cada rodada, para o teste conferir

    def iniciar(self, sistema, ferramentas, historico):
        self.sistema, self.ferramentas, self.historico = sistema, ferramentas, historico
        return {}

    def passo(self, estado, modelo, max_tokens) -> Passo:
        if not self.passos:
            raise ErroPergunta("acabaram os passos gravados")
        d = self.passos.pop(0)
        return Passo(d["texto"], [Chamada(**c) for c in d["chamadas"]], d["tokens_in"], d["tokens_out"],
                     d.get("cache_lido", 0), d.get("cache_escrito", 0), d.get("cortada", False))

    def resultados(self, estado, res) -> None:
        self.vistos.append([(c.nome, t, erro) for c, t, erro in res])

    def corrigir(self, estado, texto) -> None:
        self.vistos.append([("correcao", texto, False)])


if __name__ == "__main__":   # pragma: no cover
    import sys

    raise SystemExit(_main(sys.argv[1:]))
