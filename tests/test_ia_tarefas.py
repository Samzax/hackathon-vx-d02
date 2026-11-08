"""Roteamento de IA por tarefa (decisão de 7/11/2026): tarefa sensível (texto de cliente) só sai,
em chamada nova, para os provedores de [sensibilidade] do modelos.toml; o cache vale para qualquer
modelo, porque resposta já paga não leva nada novo a provedor nenhum. Tarefa não declarada é tratada
como sensível. A ordem é uma só (Haiku 5.5 primeiro); modelo que o provedor recusa sai da fila por um
tempo e volta a ser tentado depois."""

from __future__ import annotations

import json

import pytest

from mitra import db
from mitra.ia import (Disponibilidade, FalhaProvedor, Modelo, Roteador, SemProvedor, modelos_da_lista,
                      recusa_permanente, sondar)


class Falso:
    def __init__(self, dados):
        self.dados, self.chamadas = dados, 0

    def chamar(self, modelo, sistema, usuario, max_tokens, sessao):
        self.chamadas += 1
        return json.dumps(self.dados), 10, 5


def test_tarefa_sensivel_nao_sai_para_provedor_barato():
    rot = Roteador(None, provedores={"opencode": Falso({"ok": True}), "deepseek": Falso({"ok": True})})
    with pytest.raises(SemProvedor) as erro:
        rot.pedir_json("evidencia", 2, "s", "u", "v1")
    assert "sensível" in str(erro.value)


def test_tarefa_publica_usa_o_provedor_barato():
    falso = Falso({"ok": True})
    rot = Roteador(None, provedores={"opencode": falso})
    r = rot.pedir_json("impacto", 2, "s", "u", "v1")
    assert r.modelo.provedor == "opencode" and falso.chamadas == 1


def test_tarefa_desconhecida_e_tratada_como_sensivel():
    rot = Roteador(None, provedores={"deepseek": Falso({"ok": True})})
    with pytest.raises(SemProvedor):
        rot.pedir_json("tarefa-que-ninguem-declarou", 2, "s", "u", "v1")


def test_tarefa_sensivel_sai_pelo_provedor_de_confianca():
    falso = Falso({"ok": True})
    rot = Roteador(None, provedores={"anthropic": falso, "deepseek": Falso({"nunca": True})})
    r = rot.pedir_json("condicionantes", 3, "s", "u", "v1")
    assert r.modelo.provedor == "anthropic" and falso.chamadas == 1


HAIKU = "us.anthropic.claude-haiku-5-5"
SONNET = "us.anthropic.claude-sonnet-5"


def test_haiku_5_5_vem_primeiro_em_qualquer_provedor_que_o_tenha():
    rot = Roteador(None, provedores={"anthropic": Falso({"ok": True}), "opencode": Falso({"ok": True})})
    assert rot.pedir_json("extrator", 2, "s", "u", "v1").modelo == Modelo("anthropic", "claude-haiku-5-5")
    rot = Roteador(None, provedores={"opencode": Falso({"ok": True})})
    assert rot.pedir_json("impacto", 2, "s", "u", "v1").modelo == Modelo("opencode", "claude-haiku-5-5")
    rot = Roteador(None, provedores={"bedrock": Falso({"ok": True})})
    assert rot.pedir_json("impacto", 2, "s", "u", "v1").modelo == Modelo("bedrock", HAIKU)


def test_catalogo_vira_um_modelo_por_provedor_na_ordem_da_lista():
    cfg = {"catalogo": {"a": {"bedrock": "id-a", "opencode": "a", "preco": [1, 2]}, "b": {"opencode": "b"}}}
    assert modelos_da_lista(cfg, ["a", "b@high", {"provedor": "x", "modelo": "y"}, "a"]) == [
        Modelo("bedrock", "id-a"), Modelo("opencode", "a"), Modelo("opencode", "b", "high"), Modelo("x", "y")]


class _Negado:
    """Bedrock que recusa o Haiku 5.5 (como a conta do evento) e atende o resto."""

    def __init__(self):
        self.pedidos = []

    def chamar(self, modelo, sistema, usuario, max_tokens, sessao):
        self.pedidos.append(modelo.nome)
        if modelo.nome == HAIKU:
            raise FalhaProvedor("AccessDeniedException: no access to the model", recusado=True)
        return '{"ok": true}', 10, 5


def test_modelo_recusado_sai_da_fila_e_volta_depois_do_prazo():
    agora = [0.0]
    disp = Disponibilidade(relogio=lambda: agora[0])
    bedrock = _Negado()
    rot = Roteador(None, provedores={"bedrock": bedrock}, disponibilidade=disp)
    r = rot.pedir_json("impacto", 2, "s", "u1", "v1")
    assert r.modelo.nome == SONNET and r.tentativas[0].startswith(f"bedrock:{HAIKU}")
    rot.pedir_json("impacto", 2, "s", "u2", "v1")
    assert bedrock.pedidos == [HAIKU, SONNET, SONNET]          # a segunda já vai direto ao Sonnet 5
    assert rot.candidatos(2)[0].nome == SONNET
    agora[0] += 31 * 60                                         # passou o prazo: tenta o Haiku 5.5 de novo
    rot.pedir_json("impacto", 2, "s", "u3", "v1")
    assert bedrock.pedidos[-2:] == [HAIKU, SONNET]


def test_falha_passageira_nao_tira_o_modelo_da_fila():
    class Instavel:
        def chamar(self, *a, **k):
            raise FalhaProvedor("ThrottlingException: Too many requests")

    disp = Disponibilidade()
    rot = Roteador(None, provedores={"bedrock": Instavel(), "anthropic": Falso({"ok": True})}, disponibilidade=disp)
    assert rot.pedir_json("impacto", 2, "s", "u", "v1").modelo.provedor == "anthropic"
    assert rot.candidatos(2)[0] == Modelo("bedrock", HAIKU)


def test_todos_recusados_ainda_tenta_em_vez_de_ficar_sem_ninguem():
    disp = Disponibilidade()
    rot = Roteador(None, provedores={"bedrock": Falso({"ok": True})}, disponibilidade=disp)
    for m in rot._ordem(2):
        disp.recusar(m)
    assert rot.pedir_json("impacto", 2, "s", "u", "v1").dados == {"ok": True}


class _ClientError(Exception):
    def __init__(self, codigo, mensagem):
        super().__init__(mensagem)
        self.response = {"Error": {"Code": codigo, "Message": mensagem}}


def test_o_que_conta_como_recusa_do_modelo():
    import httpx

    assert recusa_permanente(_ClientError("AccessDeniedException", "no access to the model"))
    assert recusa_permanente(_ClientError("ValidationException", "The provided model identifier is invalid."))
    assert recusa_permanente(_ClientError("ResourceNotFoundException", "Model not found"))
    assert not recusa_permanente(_ClientError("ValidationException", "messages: roles must alternate"))
    assert not recusa_permanente(_ClientError("ThrottlingException", "Too many requests"))
    assert not recusa_permanente(RuntimeError("AccessDeniedException"))
    pedido = httpx.Request("POST", "https://x")
    for status, recusa in ((403, True), (404, True), (401, True), (429, False), (500, False)):
        erro = httpx.HTTPStatusError("x", request=pedido, response=httpx.Response(status, request=pedido))
        assert recusa_permanente(erro) is recusa


def test_sondagem_marca_o_recusado_e_para_no_primeiro_que_responde():
    disp = Disponibilidade()
    bedrock = _Negado()
    modelos = [m for m in Roteador(None, provedores={})._ordem(2) if m.provedor == "bedrock"]
    assert sondar({"bedrock": bedrock}, modelos, disp) == Modelo("bedrock", SONNET)
    assert bedrock.pedidos == [HAIKU, SONNET]
    assert not disp.disponivel(Modelo("bedrock", HAIKU))


def test_cache_vale_mesmo_para_tarefa_sensivel_sem_provedor():
    """A demo roda sem internet: resposta guardada volta do cache seja de que modelo for; a
    sensibilidade só vale para chamada nova."""
    conn = db.conectar(":memory:")
    rot = Roteador(conn, provedores={})
    barato = Modelo("opencode", "deepseek-v4.1-flash", "high")      # está na camada 2 do modelos.toml
    chave = rot._chave("evidencia", barato, "v1", "s", "u")
    rot._guardar(chave, "evidencia", barato, {"do_cache": True}, 10, 5, 0.001)
    r = rot.pedir_json("evidencia", 2, "s", "u", "v1")
    assert r.do_cache and r.dados == {"do_cache": True}
    with pytest.raises(SemProvedor):                                 # pergunta nova: aí não tem quem atenda
        rot.pedir_json("evidencia", 2, "s", "outra pergunta", "v1")


def test_prompt_do_impacto_por_vertical_sem_invalidar_o_cache():
    from mitra import impacto

    assert impacto.sistema() == impacto.SISTEMA                      # byte a byte: o cache pago continua
    assert "barragens de mineração" in impacto.SISTEMA
    outra = impacto.sistema("obras civis")
    assert "obras civis" in outra and '"mudancas"' in outra          # o .replace não mexe no exemplo JSON
