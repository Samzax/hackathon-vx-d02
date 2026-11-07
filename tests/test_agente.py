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
    mcp = criar_servidor(Torre(http, empresa="Mineradora Serra Azul"))

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
    assert {"empresas", "instanciacao", "pendencias", "ficha_do_ativo", "mudancas_pendentes", "linha_do_tempo",
            "analisar_ato", "boletim", "cobertura_normativa"} <= nomes
    # analisar_ato não grava na torre, mas chama a IA (custo + cache): o cliente MCP pede confirmação
    assert all(t.annotations.read_only_hint for t in tools if t.name != "analisar_ato")
    assert all(not t.annotations.destructive_hint for t in tools)
    assert not next(t for t in tools if t.name == "analisar_ato").annotations.read_only_hint
    assert not nomes & {"registrar_entrega", "decidir", "aprovar"}       # decisão é de gente, na torre


def test_nenhuma_ferramenta_escreve_na_torre(http, ferramentas, tmp_path):
    """Todas as ferramentas, chamadas de verdade: só GET, e o único POST é a análise de ato, que não grava."""
    from api.rotas.regulatorio import ATO_EXEMPLO
    from mitra import db

    pedidos: list[tuple[str, str]] = []
    http.event_hooks["request"].append(lambda r: pedidos.append((r.method, r.url.path)))
    args = {"ficha_do_ativo": {"ativo": "B3", "hoje": HOJE}, "historico_da_obrigacao": {"codigo": "OB-01"},
            "analisar_ato": {"texto": ATO_EXEMPLO}}
    conn = db.conectar(str(tmp_path / "api.db"))
    # a Serra Azul da demo entrou pelo seed, não pela instanciação: sem esta linha a ferramenta nova
    # responde "não encontrado" e o teste pararia nela (a instanciação em si é lida duas vezes, só GET)
    with conn:
        eid = conn.execute("SELECT id FROM empresa ORDER BY id LIMIT 1").fetchone()[0]
        conn.execute("INSERT INTO instanciacao (empresa_id, cnpj, razao_social, ufs, no_sigbm, criada_por, "
                     "criada_em) VALUES (?, NULL, 'Mineradora Serra Azul S.A.', '[\"MG\"]', 1, 'teste', ?)",
                     (eid, db.agora()))
    tabelas = ("evidencia", "evento", "responsavel_obrigacao", "obrigacao_versao", "acionamento", "ativo")
    contar = lambda: {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tabelas}  # noqa: E731
    cadastro = lambda: [r["atributos"] for r in conn.execute("SELECT atributos FROM ativo ORDER BY id")]  # noqa: E731
    antes = (contar(), cadastro())
    nomes = [t.name for t in asyncio.run(criar_servidor(Torre(http, empresa="Mineradora Serra Azul")).list_tools())]
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


def test_pendencias_de_um_ativo_filtram_pelo_codigo(ferramentas):
    """O painel filtra pelo código do ativo: com o id, a lista vinha vazia e o agente dizia "nada atrasado"."""
    p = ferramentas("pendencias", hoje=HOJE, ativo="B3", status=["atrasada"])
    assert {l["obrigacao"] for l in p["pendencias"]} == {"R95-01", "R95-02"}
    assert {l["ativo"] for l in p["pendencias"]} == {"B3"} and p["contagem"]["atrasada"] == 2


def test_pin_de_empresa_esconde_obrigacao_propria_de_outra_cliente(http, tmp_path):
    """Agente preso a uma empresa: histórico e análise de ato nunca mostram a condicionante de outra."""
    from mcp.server.mcpserver.exceptions import ToolError

    from mitra import db

    conn = db.conectar(str(tmp_path / "api.db"))
    with conn:
        ob = conn.execute("INSERT INTO obrigacao (codigo, tipo_ativo, norma, empresa) "
                          "VALUES ('TAC-X-01', 'barragem', 'TAC fictício', 'Mineradora X')").lastrowid
        conn.execute(
            "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, aplica_se_a, regra, "
            "periodicidade, agenda, prazo, vigencia_desde, responsavel, evidencia, fonte, status) "
            "VALUES (?, 1, 'Caução ambiental do TAC', 'cl. 1', '*', '*', 'Anual', 'anual+0d', '-', "
            "NULL, 'X', 'Comprovante', 'TAC fictício cl. 1', 'vigente')", (ob,))
    conn.close()
    sem_pin = criar_servidor(Torre(http))
    r = asyncio.run(sem_pin.call_tool("historico_da_obrigacao", {"codigo": "TAC-X-01"}))
    assert not r.is_error                       # a plataforma (token de serviço) vê
    preso = criar_servidor(Torre(http, empresa="Mineradora Serra Azul"))
    with pytest.raises(ToolError, match="Não encontrado"):
        asyncio.run(preso.call_tool("historico_da_obrigacao", {"codigo": "TAC-X-01"}))


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


def test_cobertura_normativa_das_barragens_em_mg(ferramentas):
    """'Que normas valem para as minhas barragens em MG e quais ainda não estão no catálogo?'"""
    itens = ferramentas("cobertura_normativa", jurisdicao="mg", tipo_ativo="Barragem")
    assert len(itens) == 1
    mg = itens[0]
    assert (mg["jurisdicao"], mg["jurisdicao_nome"], mg["ativos"]) == ("MG", "Minas Gerais", ["B1", "B2", "B3", "B4"])
    assert mg["verificada"] and mg["estado"] == "normas relevantes esperando a curadoria"
    assert {"Lei MG 23.291/2019", "Decreto MG 48.078/2020 (PAE)"} <= set(mg["no_catalogo"])
    assert mg["fontes_lidas"][0].startswith("Assembleia de Minas (") and "1989–2026" in mg["fontes_lidas"][0]
    assert any("Copam" in lac for lac in mg["lacunas_conhecidas"])
    fora = {n["norma"]: n for n in mg["fora_do_catalogo_esperando_curadoria"]}
    caucao = fora["Decreto MG 48.747/2023"]
    assert caucao["altera_do_catalogo"] == ["Lei MG 23.291/2019"] and caucao["deveres"]
    assert caucao["texto_oficial"].startswith("https://www.almg.gov.br/")
    assert mg["aprovadas_falta_extrair"] == []
    todas = ferramentas("cobertura_normativa")
    assert {(i["jurisdicao"], i["tipo_ativo"]) for i in todas} >= {("BR", "barragem"), ("MG", "barragem"),
                                                                    ("BR", "equipamento")}


def test_empresa_fixa_prende_o_escopo(http):
    t = Torre(http, empresa="Mineradora Serra Azul")
    assert [e["nome"] for e in t.empresas()] == ["Mineradora Serra Azul"]
    assert t.empresa_id(None) == t.empresas()[0]["id"]
    # pin que não casa com nada é erro na cara, não um agente destravado em silêncio
    with pytest.raises(ErroTorre, match="não casa com nenhuma empresa"):
        Torre(http, empresa="Outra Mineração").empresa_id("Outra Mineração")


def test_ativo_inexistente_e_token_errado_viram_erro_legivel(http):
    t = Torre(http, empresa="Mineradora Serra Azul")
    with pytest.raises(ErroTorre, match="Ativo 'B9'"):
        t.ativo(t.empresa_id(None), "B9")
    http.headers["Authorization"] = "Bearer outro"
    with pytest.raises(ErroTorre, match="401"):
        Torre(http).empresas()


def test_erro_de_validacao_vira_frase_nao_repr(http):
    """O 422 do FastAPI chega como lista de dicts: o agente traduz para 'campo: mensagem'."""
    t = Torre(http, empresa="Mineradora Serra Azul")
    with pytest.raises(ErroTorre, match="hoje") as e:
        t.get(f"/empresas/{t.empresa_id(None)}/painel", hoje="07/11/2026")
    assert "[{" not in str(e.value)


def test_erro_da_torre_e_erro_de_ferramenta(http):
    """ToolError: o protocolo devolve ao cliente um resultado com isError e a mensagem, não derruba a sessão."""
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match="B9"):
        asyncio.run(criar_servidor(Torre(http, empresa="Mineradora Serra Azul")).call_tool("ficha_do_ativo", {"ativo": "B9"}))


def _empresa_instanciada(tmp_path, nome: str) -> int:
    """Uma empresa que passou pela instanciação, direto no banco do teste: a Serra Azul da demo entrou
    pelo seed, então a rota da instanciação responde 404 para ela."""
    from mitra import db, instanciacao

    conn = db.conectar(str(tmp_path / "api.db"))
    eid = instanciacao.criar(conn, nome=nome, razao_social=f"{nome} S.A.", cnpj=None, ufs=["mg"], por="teste")
    instanciacao.criar_ativo(conn, eid, tipo="barragem", codigo="B1", nome="Barragem da nova", por="teste")
    conn.close()
    return eid


def test_instanciacao_conta_as_etapas_e_os_dados_que_faltam(http, tmp_path):
    """'Em que pé está a instanciação?': as 8 etapas, o que falta em cada uma e o cadastro a completar.
    Agente sem escopo (plataforma): a empresa instanciada não é a Serra Azul da fixture."""
    from mitra import instanciacao as dominio

    nome = "Mineradora Instanciada (fictícia)"
    _empresa_instanciada(tmp_path, nome)
    mcp = criar_servidor(Torre(http))
    r = asyncio.run(mcp.call_tool("instanciacao", {"empresa": nome}))
    assert not r.is_error, r.content
    i = r.structured_content["result"] if r.structured_content and "result" in r.structured_content \
        else json.loads(r.content[0].text)
    assert i["empresa"] == nome and i["em_operacao"] is False and i["monitorado_desde"] is None
    etapas = {e["titulo"]: e for e in i["etapas"]}
    assert set(etapas) == set(dominio.TITULOS.values()) and len(i["etapas"]) == len(dominio.ETAPAS)
    assert etapas["Cadastro da empresa"]["estado"] == "pronta" and etapas["Cadastro da empresa"]["por"] == "teste"
    assert etapas["Ativos e unidades"]["estado"] == "pronta"
    assert etapas["Ativos e unidades"]["numeros"] == {"ativos": 1, "unidades": 0}
    assert etapas["Revisão e entrada em operação"]["estado"] == "pendente"
    assert etapas["Revisão e entrada em operação"]["falta"]
    assert 0 < i["percentual"] < 100
    faltando = i["dados_faltando"]
    assert faltando["total"] == len(faltando["itens"]) >= 1
    assert all(item["ativo"] == "B1" and item["pergunta"] and item["obrigacoes"] for item in faltando["itens"])


def test_instanciacao_de_empresa_sem_instanciacao_e_erro_legivel(http):
    """A empresa que entrou por outro caminho não tem etapas: a ferramenta diz isso, não inventa."""
    from mcp.server.mcpserver.exceptions import ToolError

    mcp = criar_servidor(Torre(http))
    with pytest.raises(ToolError, match="não passou pela instanciação"):
        asyncio.run(mcp.call_tool("instanciacao", {"empresa": "Mineradora Serra Azul"}))
