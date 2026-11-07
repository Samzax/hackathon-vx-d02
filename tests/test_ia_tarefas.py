"""Roteamento de IA por tarefa (decisão de 7/11/2026): tarefa sensível (texto de cliente) só sai,
em chamada nova, para os provedores de [sensibilidade] do modelos.toml; o cache vale para qualquer
modelo, porque resposta já paga não leva nada novo a provedor nenhum. A extração do catálogo
(dado público) prefere o Sonnet; tarefa não declarada é tratada como sensível."""

from __future__ import annotations

import json

import pytest

from mitra import db
from mitra.ia import Modelo, Roteador, SemProvedor


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


def test_extracao_do_catalogo_prefere_o_sonnet():
    """Decisão de 7/11: Sonnet agora; medir o Haiku 5.5 depois; DeepSeek só se o gabarito deixar."""
    rot = Roteador(None, provedores={"anthropic": Falso({"ok": True}), "opencode": Falso({"ok": True})})
    r = rot.pedir_json("extrator", 2, "s", "u", "v1")
    assert r.modelo == Modelo("anthropic", "claude-sonnet-5-5")


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
