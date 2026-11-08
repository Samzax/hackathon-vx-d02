"""Assistente Mitra: o laço com as ferramentas, a conferência do Python, a rota (sessão, CSRF, papel,
escopo da área, teto, auditoria) e as respostas gravadas do modelo de verdade, repetidas sem chave."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from agente.cliente import Torre
from agente.ferramentas import CHAMA_IA, ferramentas
from api.main import criar_app
from api.rotas import pergunta as rota_pergunta
from mitra import db
from mitra import pergunta as pg
from mitra.ia import SemProvedor
from tests.test_api import _url, cfg, como, entrar  # noqa: F401  (cfg é fixture)

SERRA = "Mineradora Serra Azul"


def _passo(texto="", chamadas=(), tin=100, tout=20, **kw) -> dict:
    return {"texto": texto, "chamadas": [{"id": f"c{i}", "nome": n, "args": a} for i, (n, a) in enumerate(chamadas)],
            "tokens_in": tin, "tokens_out": tout, **kw}


@pytest.fixture
def http(cfg):  # noqa: F811
    with TestClient(criar_app(cfg), headers={"Authorization": f"Bearer {cfg.token_servico}"}) as c:
        yield c


@pytest.fixture
def fs(http):
    return pg.preparar(ferramentas(Torre(http, empresa=SERRA)), fora=CHAMA_IA)


def _perguntar(fs, passos, pergunta="O que está atrasado na B3?", **kw):
    rep = pg.Repetidor(passos)
    return pg.perguntar(pergunta, fs, provedores={"bedrock": rep}, **kw), rep


# ------------------------------------------------------------------ conferência


def test_conferencia_aceita_o_que_veio_das_ferramentas_e_marca_o_inventado():
    res = ['{"trecho": "I - preencher, quinzenalmente ou em menor período, a seu critério, as FIR", '
           '"vence": "2026-10-15", "obrigacao": "R95-01", "ativo": "B3"}']
    boa = 'A **R95-01** da B3 venceu em 2026-10-15 (15/10/2026): "preencher, quinzenalmente ou em menor período, a seu critério, as FIR".'
    c = pg.conferir(boa, res)
    assert c.ok and c.citacoes == 1
    ruim = 'A R95-07 da B9 vence em 2026-12-31: "preencher a ficha toda semana, sem falta, no sistema da ANM".'
    c = pg.conferir(ruim, res)
    assert not c.ok
    assert c.datas_fora == ["2026-12-31"] and c.codigos_fora == ["B9", "R95-07"] and len(c.citacoes_fora) == 1


def test_conferencia_nao_junta_o_fim_de_uma_citacao_curta_com_o_comeco_da_proxima():
    res = ['{"situacao": "aprovadas, falta extrair", "fila": "fora do catálogo esperando curadoria"}']
    texto = ('A lista "aprovadas, falta extrair" está vazia; estas abaixo estão na lista '
             '"fora do catálogo esperando curadoria".')
    c = pg.conferir(texto, res)
    assert c.ok and c.citacoes == 1


def test_resposta_cortada_no_limite_pede_uma_mais_curta(fs):
    r, rep = _perguntar(fs, [_passo("Na B3 há muito a dizer e", cortada=True),
                             _passo("Na B3, a R95-01 está atrasada.")], pergunta="E a B3?")
    assert r.corrigida and r.texto == "Na B3, a R95-01 está atrasada." and "cortada" in rep.vistos[-1][0][1]
    r, _ = _perguntar(fs, [_passo("Começo", cortada=True), _passo("Começo de novo", cortada=True)], pergunta="E a B3?")
    assert r.texto.startswith("Começo de novo") and "resposta cortada" in r.texto


def test_conferencia_aceita_o_que_esta_na_propria_pergunta():
    assert pg.conferir("A B9 não existe na torre.", [], pergunta="O que vence na B9?").ok


# ------------------------------------------------------------------ o laço


def test_ferramentas_do_chat_sao_as_do_agente_menos_a_que_chama_ia(fs):
    nomes = {f.nome for f in fs}
    assert {"pendencias", "ficha_do_ativo", "mudancas_pendentes", "cobertura_normativa"} <= nomes
    assert "analisar_ato" not in nomes
    p = next(f for f in fs if f.nome == "pendencias")
    assert set(p.esquema["properties"]) == {"empresa", "hoje", "ativo", "status"} and "Código do ativo" in json.dumps(p.esquema, ensure_ascii=False)


def test_pergunta_consulta_a_torre_e_responde_com_a_fonte(fs):
    r, rep = _perguntar(fs, [
        _passo(chamadas=[("pendencias", {"ativo": "B3", "status": ["atrasada"]})]),
        _passo('Na B3, a **R95-01** (Res. ANM 95/2022, art. 19 I) está atrasada desde 2026-10-15.')])
    assert r.conferencia.ok and not r.corrigida and r.modelo == "bedrock:us.anthropic.claude-haiku-5-5"
    [[(nome, texto, erro)]] = rep.vistos
    assert nome == "pendencias" and not erro and "R95-01" in texto and "N13-03" not in texto
    assert r.custo_usd == pytest.approx((200 * 0.10 + 40 * 0.50) / 1e6)


def test_resposta_com_data_inventada_volta_para_corrigir_uma_vez(fs):
    r, rep = _perguntar(fs, [
        _passo(chamadas=[("pendencias", {"ativo": "B3", "status": ["atrasada"]})]),
        _passo("A R95-01 da B3 vence em 2026-12-31."),
        _passo("A R95-01 da B3 venceu em 2026-10-15.")])
    assert r.corrigida and r.conferencia.ok and r.texto.endswith("2026-10-15.")
    correcao = rep.vistos[-1][0]
    assert correcao[0] == "correcao" and "2026-12-31" in correcao[1]


def test_o_que_sobrar_da_correcao_vai_marcado_para_quem_le(fs):
    r, _ = _perguntar(fs, [_passo("A B3 tem a OB-99 vencendo em 2030-01-01."), _passo("A OB-99 vence em 2030-01-01.")])
    assert r.corrigida and not r.conferencia.ok and r.conferencia.codigos_fora == ["OB-99"]


def test_argumento_que_a_ferramenta_nao_tem_e_ferramenta_inexistente_voltam_como_erro(fs):
    r, rep = _perguntar(fs, [
        _passo(chamadas=[("linha_do_tempo", {"ativo": "B2"}), ("apagar_tudo", {})]),
        _passo("Não consegui filtrar por ativo.")])
    erros = {u.ferramenta: u.erro for u in r.ferramentas}
    assert "argumentos inválidos" in erros["linha_do_tempo"] and "desconhecida" in erros["apagar_tudo"]
    assert all(erro for _, _, erro in rep.vistos[0])


def test_erro_da_torre_vira_resultado_que_o_modelo_explica(fs):
    r, rep = _perguntar(fs, [_passo(chamadas=[("ficha_do_ativo", {"ativo": "B9"})]),
                             _passo("Não encontrei a B9.")], pergunta="Como está a B9?")
    assert "não encontrado" in r.ferramentas[0].erro and "B1 (" in rep.vistos[0][0][1]


def test_lista_de_ativos_da_mensagem_de_erro_passa_na_conferencia(fs):
    """O prompt manda escolher pela lista que vem no "não encontrado": citá-la não é inventar."""
    r, _ = _perguntar(fs, [_passo(chamadas=[("ficha_do_ativo", {"ativo": "B9"})]),
                           _passo("A B9 não existe nesta empresa. Os ativos são B1, B2, B3, B4, E1, E2, L1 e U1.")],
                      pergunta="Como está a B9?")
    assert r.conferencia.ok and not r.corrigida, r.conferencia.resumo()


def test_ativo_pelo_nome_que_a_empresa_usa(fs):
    r, rep = _perguntar(fs, [_passo(chamadas=[("ficha_do_ativo", {"ativo": "VP-101"})]),
                             _passo("O E1 está com a N13-03 atrasada.")], pergunta="Como está o VP-101?")
    assert r.ferramentas[0].erro is None and '"codigo": "E1"' in rep.vistos[0][0][1]


def test_historico_comeca_pelo_usuario_e_termina_na_pergunta(fs):
    _, rep = _perguntar(fs, [_passo("Ok.")], pergunta="E a B4?",
                        historico=[("torre", "Olá"), ("usuario", "O que vence na B3?"), ("torre", "Nada.")])
    assert rep.historico == [("usuario", "O que vence na B3?"), ("torre", "Nada."), ("usuario", "E a B4?")]


def test_sem_resposta_em_tantas_rodadas_desiste(fs):
    passos = [_passo(chamadas=[("empresas", {})])] * (pg.MAX_RODADAS + 1)
    with pytest.raises(SemProvedor, match="rodadas"):
        _perguntar(fs, passos)


def test_data_que_o_modelo_consultou_conta_como_conhecida(fs):
    r, _ = _perguntar(fs, [_passo(chamadas=[("pendencias", {"ativo": "B3", "hoje": "2027-08-02"})]),
                           _passo("Em 2027-08-02 o quadro da B3 muda.")], pergunta="E em agosto de 2027?")
    assert r.conferencia.ok and not r.corrigida


def test_pergunta_que_passa_do_prazo_para_e_leva_o_que_gastou(fs):
    passos = [_passo(chamadas=[("empresas", {})])] * 3
    with pytest.raises(pg.Demorou, match="passou de") as e:
        _perguntar(fs, passos, prazo=0.0)
    assert e.value.parcial is not None and e.value.parcial.texto == ""
    r, _ = _perguntar(fs, [_passo("Ok.")])
    assert 0 <= r.segundos < pg.PRAZO_S


def test_pergunta_vazia_ou_longa_demais(fs):
    with pytest.raises(pg.ErroPergunta):
        _perguntar(fs, [], pergunta="  ")
    with pytest.raises(pg.ErroPergunta):
        _perguntar(fs, [], pergunta="x" * (pg.MAX_PERGUNTA + 1))


# ------------------------------------------------------------------ Bedrock (Converse)


class _BotoFalso:
    def __init__(self, respostas):
        self.respostas, self.pedidos = list(respostas), []

    def converse(self, **kw):
        self.pedidos.append(json.loads(json.dumps(kw, default=str)))
        return self.respostas.pop(0)


class _NegaHaiku(pg.Repetidor):
    """Bedrock da conta do evento: recusa o Haiku 5.5, responde com o que estiver gravado nos outros."""

    def __init__(self, passos):
        super().__init__(passos)
        self.modelos = []

    def passo(self, estado, modelo, max_tokens):
        self.modelos.append(modelo.nome)
        if modelo.nome == "us.anthropic.claude-haiku-5-5":
            raise pg.ErroPergunta("Bedrock: AccessDeniedException", recusado=True)
        return super().passo(estado, modelo, max_tokens)


def test_chat_recusado_no_haiku_fica_no_sonnet_5_sem_tentar_de_novo(fs):
    prov = _NegaHaiku([_passo("Nada atrasado na B3."), _passo("Nada novo na B3.")])
    r = pg.perguntar("E a B3?", fs, provedores={"bedrock": prov})
    assert r.modelo == "bedrock:us.anthropic.claude-sonnet-5"
    assert pg.candidatos(pg._config(pg.CONFIG), {"bedrock": prov})[0].nome == "us.anthropic.claude-sonnet-5"
    pg.perguntar("E a B3?", fs, provedores={"bedrock": prov})
    assert prov.modelos == ["us.anthropic.claude-haiku-5-5", "us.anthropic.claude-sonnet-5",
                            "us.anthropic.claude-sonnet-5"]


def test_opencode_fala_anthropic_com_o_haiku_e_openai_com_o_deepseek(fs):
    import httpx

    pedidos = []

    def responder(req: httpx.Request) -> httpx.Response:
        pedidos.append(req)
        if req.url.path.endswith("/messages"):
            return httpx.Response(200, json={"content": [{"type": "text", "text": "A B3 tem a R95-01 atrasada."}],
                                             "usage": {"input_tokens": 10, "output_tokens": 5}, "stop_reason": "end_turn"})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Ok, a R95-01."},
                                                      "finish_reason": "stop"}], "usage": {}})

    conf = pg._config(pg.CONFIG)
    provs = pg.provedores_da_config({"OPENCODE_API_KEY": "k"}, conf, httpx.Client(transport=httpx.MockTransport(responder)))
    r = pg.perguntar("E a B3?", fs, provedores=provs)
    assert r.modelo == "opencode:claude-haiku-5-5"
    req = pedidos[-1]
    assert str(req.url) == conf["provedores"]["opencode"]["base_anthropic"] + "/messages"
    assert req.headers["x-opencode-session"] and json.loads(req.content)["model"] == "claude-haiku-5-5"
    estado = provs["opencode"].iniciar("s", fs, [("usuario", "oi")])
    provs["opencode"].passo(estado, pg.Modelo("opencode", "deepseek-v4.1-flash"), 100)
    assert pedidos[-1].url.path.endswith("/chat/completions")


def test_bedrock_usa_cache_de_prompt_e_cobra_o_cache_pelo_preco_certo(fs, monkeypatch):
    monkeypatch.setattr(pg.time, "sleep", lambda s: None)
    boto = _BotoFalso([
        {"output": {"message": {"role": "assistant", "content": [
            {"toolUse": {"toolUseId": "t1", "name": "pendencias", "input": {"ativo": "B3"}}}]}},
         "usage": {"inputTokens": 1000, "outputTokens": 50, "cacheWriteInputTokens": 4000}},
        {"output": {"message": {"role": "assistant", "content": [{"text": "A B3 tem a R95-01 atrasada."}]}},
         "usage": {"inputTokens": 300, "outputTokens": 30, "cacheReadInputTokens": 5000}},
    ])
    prov = pg._Bedrock({"intervalo_minimo_s": 0}, cliente=boto)
    r = pg.perguntar("O que está atrasado na B3?", fs, provedores={"bedrock": prov})
    p1, p2 = boto.pedidos
    assert p1["toolConfig"]["tools"][-1] == pg.CACHE and p1["system"][-1] == pg.CACHE
    assert p1["modelId"] == "us.anthropic.claude-haiku-5-5"
    for p in (p1, p2):      # um ponto de cache só na conversa, no fim
        pontos = [b for m in p["messages"] for b in m["content"] if "cachePoint" in b]
        assert len(pontos) == 1 and "cachePoint" in p["messages"][-1]["content"][-1]
    assert p2["messages"][-1]["content"][0]["toolResult"]["status"] == "success"
    esperado = (1300 * 0.1 + 5000 * 0.1 * 0.1 + 4000 * 0.1 * 1.25 + 80 * 0.5) / 1e6
    assert r.custo_usd == pytest.approx(esperado) and r.tokens_cache == 5000 and r.tokens_in == 10300


# ------------------------------------------------------------------ respostas gravadas do modelo de verdade


CASOS = [c for c in pg.casos() if (pg.GRAVACOES / f"{c['id']}.json").exists()]


@pytest.mark.parametrize("caso", CASOS, ids=[c["id"] for c in CASOS])
def test_avaliacao_com_as_respostas_gravadas(caso, fs):
    """O modelo de verdade respondeu estas perguntas (`python -m mitra.pergunta avaliar --gravar`); aqui
    as respostas dele voltam na ordem, as ferramentas rodam de verdade contra a demo, e os critérios do
    caso e a conferência precisam passar. Se a demo mudar e a resposta gravada ficar errada, este teste
    avisa: regrave."""
    passos = json.loads((pg.GRAVACOES / f"{caso['id']}.json").read_text(encoding="utf-8"))
    r, _ = _perguntar(fs, passos, pergunta=caso["pergunta"])
    assert pg.avaliar_resposta(caso, r) == []


def test_avaliacao_aceita_a_data_nas_duas_formas():
    r = pg.Resposta("A LO-06 vence em 15/11/2026.", "m", [], pg.conferir("", []), 1, 1, 0.0)
    assert pg.avaliar_resposta({"contem": ["2026-11-15", "LO-06"]}, r) == []
    assert pg.avaliar_resposta({"contem": ["2026-11-16"]}, r) == ["falta: 2026-11-16 ou 16/11/2026"]


def test_ha_respostas_gravadas_para_todos_os_casos():
    assert len(CASOS) == len(pg.casos()) >= 10


# ------------------------------------------------------------------ a rota


@pytest.fixture
def cliente(cfg):  # noqa: F811
    app = criar_app(cfg)
    with TestClient(app) as c:
        c.app_ = app
        yield c


def _gravadas(c, passos) -> pg.Repetidor:
    rep = pg.Repetidor(passos)
    c.app_.state.provedores_pergunta = {"bedrock": rep}
    return rep


def test_rota_responde_audita_e_soma_o_custo_no_dia(cliente, cfg):  # noqa: F811
    entrar(cliente)
    _gravadas(cliente, [_passo(chamadas=[("pendencias", {"ativo": "B3", "status": ["atrasada"]})]),
                        _passo("A **R95-01** da B3 está atrasada desde 2026-10-15.")])
    r = cliente.post(_url("/pergunta"), json={"pergunta": "O que está atrasado na B3?"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["conferencia"]["ok"] and d["ferramentas"][0]["ferramenta"] == "pendencias" and "R95-01" in d["texto"]
    aud = cliente.get(_url("/auditoria")).json()
    reg = next(a for a in aud if a["acao"] == "pergunta")
    assert reg["alvo"] == "O que está atrasado na B3?" and reg["usuario"] == "demo@serraazul.demo"
    cache = db.conectar(cfg.cache)
    assert cache.execute("SELECT COUNT(*) FROM analise_ia WHERE tarefa = 'pergunta'").fetchone()[0] == 1


def test_rota_pede_sessao_csrf_e_nao_e_da_ti(cliente):
    _gravadas(cliente, [_passo("Ok.")])
    assert cliente.post(_url("/pergunta"), json={"pergunta": "Oi"}).status_code == 401
    entrar(cliente)
    csrf = cliente.headers.pop("X-CSRF-Token")
    assert cliente.post(_url("/pergunta"), json={"pergunta": "Oi"}).status_code == 403
    cliente.headers["X-CSRF-Token"] = csrf
    como(cliente, "ti@serraazul.demo")
    r = cliente.post(_url("/pergunta"), json={"pergunta": "Oi"})
    assert r.status_code == 403 and "TI" in r.json()["detail"]


def test_gestor_so_ve_pelo_chat_o_que_ve_na_torre(cliente):
    """As ferramentas rodam com a sessão de quem pergunta: o gestor da usina não recebe a B3 da Geotecnia."""
    como(cliente, "usina@serraazul.demo")
    rep = _gravadas(cliente, [_passo(chamadas=[("pendencias", {})]), _passo("A E1 tem a N13-03 atrasada.")])
    r = cliente.post(_url("/pergunta"), json={"pergunta": "O que está atrasado?"})
    assert r.status_code == 200, r.text
    texto = rep.vistos[0][0][1]
    assert "N13-03" in texto and "R95-01" not in texto and '"ativo": "B3"' not in texto


def test_teto_do_dia_e_ia_desligada(cliente, cfg, monkeypatch):  # noqa: F811
    entrar(cliente)
    monkeypatch.setattr(rota_pergunta, "_provedores_do_ambiente", lambda: {})
    cliente.app_.state.provedores_pergunta = None
    assert cliente.get(_url("/pergunta/estado")).json()["ligada"] is False
    assert cliente.post(_url("/pergunta"), json={"pergunta": "Oi"}).status_code == 503
    _gravadas(cliente, [_passo("Ok.")])
    monkeypatch.setenv("MITRA_TETO_DIA_USD", "0.000001")
    cache = db.conectar(cfg.cache)
    with cache:
        cache.execute("INSERT INTO analise_ia (chave, tarefa, provedor, modelo, resposta, tokens_in, tokens_out, "
                      "custo_usd) VALUES ('x', 'pergunta', 'bedrock', 'm', '{}', 1, 1, 0.5)")
    r = cliente.post(_url("/pergunta"), json={"pergunta": "Oi"})
    assert r.status_code == 429 and "teto" in r.json()["detail"]
    e = cliente.get(_url("/pergunta/estado")).json()
    assert e["ligada"] and e["gasto_hoje_usd"] >= 0.5 and e["teto_dia_usd"] == pytest.approx(0.000001)


def test_rota_que_passa_do_prazo_responde_504_e_conta_o_gasto(cliente, cfg, monkeypatch):  # noqa: F811
    """Na AWS o CloudFront corta em 60 s: a rota fecha antes, com 504 e mensagem, e o gasto entra no teto."""
    entrar(cliente)
    _gravadas(cliente, [_passo(chamadas=[("empresas", {})])] * 3)
    monkeypatch.setattr(pg, "PRAZO_S", 0.0)
    monkeypatch.setattr(pg.perguntar, "__kwdefaults__", {**pg.perguntar.__kwdefaults__, "prazo": 0.0})
    r = cliente.post(_url("/pergunta"), json={"pergunta": "Oi"})
    assert r.status_code == 504 and "mais específica" in r.json()["detail"]
    cache = db.conectar(cfg.cache)
    assert cache.execute("SELECT COUNT(*) FROM analise_ia WHERE tarefa = 'pergunta'").fetchone()[0] == 1
