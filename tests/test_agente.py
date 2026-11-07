"""O servidor MCP responde pela API real (banco da demo), só lê, e respeita o escopo da empresa."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("mcp")

from agente.cliente import ErroTorre, Torre  # noqa: E402
from agente.servidor import PENDENTES, criar_servidor  # noqa: E402
from api.config import Config  # noqa: E402
from api.main import criar_app  # noqa: E402
from tests.test_api import _banco_da_demo  # noqa: E402

TOKEN = "token-de-teste-do-agente"
HOJE = "2026-11-07"


@pytest.fixture
def http(tmp_path):
    banco, cache = _banco_da_demo(tmp_path)
    cfg = Config(banco=banco, banco_cache=cache, armazenamento=str(tmp_path / "uploads"), token_servico=TOKEN)
    with TestClient(criar_app(cfg), headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        yield c


@pytest.fixture
def ferramentas(http):
    """As funções das ferramentas, chamadas como o MCP chama (pelo nome, com argumentos)."""
    mcp = criar_servidor(Torre(http))

    def chamar(nome: str, **args):
        r = asyncio.run(mcp.call_tool(nome, args))
        assert not r.is_error, r.content
        if r.structured_content and "result" in r.structured_content:    # lista e texto
            return r.structured_content["result"]
        return json.loads(r.content[0].text)                                # dict: JSON no texto
    return chamar


def test_ferramentas_sao_so_de_leitura(http):
    tools = asyncio.run(criar_servidor(Torre(http)).list_tools())
    nomes = {t.name for t in tools}
    assert {"empresas", "pendencias", "ficha_do_ativo", "mudancas_pendentes", "linha_do_tempo",
            "analisar_ato", "boletim"} <= nomes
    assert all(t.annotations.read_only_hint and not t.annotations.destructive_hint for t in tools)
    assert not nomes & {"registrar_entrega", "decidir", "aprovar"}       # decisão é de gente, na torre


def test_nenhuma_ferramenta_escreve_na_torre(http, ferramentas, tmp_path):
    """Todas as ferramentas, chamadas de verdade: só GET, e o único POST é a análise de ato, que não grava."""
    from api.rotas.regulatorio import ATO_EXEMPLO
    from regulaia import db

    pedidos: list[tuple[str, str]] = []
    http.event_hooks["request"].append(lambda r: pedidos.append((r.method, r.url.path)))
    args = {"ficha_do_ativo": {"ativo": "B3", "hoje": HOJE}, "historico_da_obrigacao": {"codigo": "OB-01"},
            "analisar_ato": {"texto": ATO_EXEMPLO}}
    conn = db.conectar(str(tmp_path / "api.db"))
    tabelas = ("evidencia", "evento", "responsavel_obrigacao", "obrigacao_versao", "acionamento", "ativo")
    contar = lambda: {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tabelas}  # noqa: E731
    cadastro = lambda: [r["atributos"] for r in conn.execute("SELECT atributos FROM ativo ORDER BY id")]  # noqa: E731
    antes = (contar(), cadastro())
    nomes = [t.name for t in asyncio.run(criar_servidor(Torre(http)).list_tools())]
    for nome in nomes:
        ferramentas(nome, **args.get(nome, {}))
    assert (contar(), cadastro()) == antes
    escritas = {(m, p) for m, p in pedidos if m != "GET"}
    assert escritas == {("POST", "/api/v1/radar/analise")}, escritas
    conn.close()


def test_pendencias_da_demo_com_norma_e_dispositivo(ferramentas):
    p = ferramentas("pendencias", hoje=HOJE)
    assert p["contagem"]["atrasada"] == 4
    assert p["pendencias"] and all(l["status"] in PENDENTES for l in p["pendencias"])
    fir = next(l for l in p["pendencias"] if l["ativo"] == "B3" and l["obrigacao"] == "R95-01")
    assert fir["status"] == "atrasada" and fir["norma"] == "Res. ANM 95/2022" and fir["dispositivo"]
    assert fir["periodos_faltando"]


def test_ficha_mostra_a_lei_federal_da_zas_na_b2(ferramentas):
    f = ferramentas("ficha_do_ativo", ativo="b2", hoje=HOJE)
    assert f["ativo"]["codigo"] == "B2" and f["ativo"]["atributos"]["trabalhadores_zas"] is True
    zas = next(o for o in f["obrigacoes"] if o["obrigacao"] == "L12-22")
    assert zas["norma"] == "Lei 12.334/2010 (PNSB)" and "18-A" in zas["dispositivo"]
    assert "trecho" not in zas or zas["trecho"].startswith("Somente se admite na ZAS")


def test_mudanca_da_res_245_aguarda_decisao(ferramentas):
    ms = ferramentas("mudancas_pendentes")
    ob01 = next(m for m in ms if m["obrigacao"] == "OB-01")
    assert "245" in ob01["ato"] and ob01["quem_decide"]


def test_linha_do_tempo_ate_um_dia(ferramentas):
    futuras = ferramentas("linha_do_tempo", hoje=HOJE, ate="2027-12-31")
    assert futuras and all(f["dia"] <= "2027-12-31" for f in futuras)
    assert any(f["dia"] == "2027-08-02" for f in futuras)          # a Res. 220 passa a valer


def test_boletim_em_markdown(ferramentas):
    md = ferramentas("boletim", hoje=HOJE)
    assert isinstance(md, str) and "Res. ANM 95/2022" in md


def test_empresa_fixa_prende_o_escopo(http):
    t = Torre(http, empresa="Mineradora Serra Azul")
    assert [e["nome"] for e in t.empresas()] == ["Mineradora Serra Azul"]
    assert t.empresa_id(None) == t.empresas()[0]["id"]
    with pytest.raises(ErroTorre, match="não encontrada"):
        Torre(http, empresa="Outra Mineração").empresa_id("Outra Mineração")


def test_ativo_inexistente_e_token_errado_viram_erro_legivel(http):
    t = Torre(http)
    with pytest.raises(ErroTorre, match="Ativo 'B9'"):
        t.ativo(t.empresa_id(None), "B9")
    http.headers["Authorization"] = "Bearer outro"
    with pytest.raises(ErroTorre, match="401"):
        Torre(http).empresas()


def test_erro_da_torre_e_erro_de_ferramenta(http):
    """ToolError: o protocolo devolve ao cliente um resultado com isError e a mensagem, não derruba a sessão."""
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="B9"):
        asyncio.run(criar_servidor(Torre(http)).call_tool("ficha_do_ativo", {"ativo": "B9"}))
