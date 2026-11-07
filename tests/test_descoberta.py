"""Descoberta de normas: perfil da carteira, fontes oficiais, triagem pela IA, curadoria e cobertura.

As fontes vêm de trechos reais guardados em tests/fixtures/descoberta (Senado, ANMlegis e ALMG);
a IA é um provedor roteirizado. Nada sai para a internet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mitra import db, demo, descoberta as d
from mitra.ia import Roteador

FIX = Path(__file__).parent / "fixtures" / "descoberta"


class BaixadorFixo(d.Baixador):
    """As três fontes, lidas dos trechos reais em vez da internet."""

    def __init__(self, tmp_path, hoje=None):
        from datetime import date

        super().__init__(pasta=tmp_path, http=object(), pausa_s=0, hoje=hoje or date(2026, 11, 6))
        self.pedidos = []

    def senado(self, tipo, ano):
        self.pedidos.append(("senado", ano))
        return [c for c in d.ler_senado((FIX / "senado.xml").read_bytes()) if c.tipo == tipo and c.ano == ano]

    def almg(self, ano):
        self.pedidos.append(("almg", ano))
        return [c for c in d.ler_almg((FIX / "almg.csv").read_bytes()) if c.ano == ano]

    def anm(self, ano):
        self.pedidos.append(("anm", ano))
        return [c for c in d.ler_anm((FIX / "anm.html").read_text(encoding="utf-8")) if c.ano == ano]


class IAFalsa:
    """Responde pela norma do pedido; camada 2 = esforço high, camada 3 = max."""

    def __init__(self, respostas: dict, padrao=None):
        self.respostas, self.padrao, self.chamadas = respostas, padrao, []

    def chamar(self, modelo, sistema, usuario, max_tokens, sessao):
        pedido = json.loads(usuario)
        norma = pedido["norma"]
        if "texto" in pedido:           # segunda leitura, pelo texto oficial
            self.chamadas.append((norma, "texto"))
            r = self.respostas.get((norma, "texto"), self.padrao)
            return (r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)), 3000, 150
        self.chamadas.append((norma, modelo.esforco))
        r = self.respostas.get((norma, modelo.esforco), self.respostas.get(norma, self.padrao))
        return (r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)), 800, 120


IRRELEVANTE = {"relevante": False, "tipos_ativo": [], "deveres": "", "motivo": "organiza o Estado", "confianca": 0.9}


def _roteador(conn, respostas, padrao=IRRELEVANTE):
    ia = IAFalsa(respostas, padrao)
    return Roteador(conn, provedores={"opencode": ia}), ia


@pytest.fixture
def serra():
    conn = db.conectar(":memory:")
    demo.montar(conn, com_historico=False)
    return conn


@pytest.fixture
def buscada(serra, tmp_path):
    d.buscar(serra, BaixadorFixo(tmp_path), desde=1967)
    return serra


def _status(conn, chave):
    r = conn.execute("SELECT status FROM norma_candidata WHERE chave = ?", (chave,)).fetchone()
    return r["status"] if r else None


# ------------------------------------------------------------------- leitura das fontes


def test_senado_le_lei_decreto_lei_e_decreto_com_chave_e_link():
    cs = {c.chave: c for c in d.ler_senado((FIX / "senado.xml").read_bytes())}
    assert {"BR:DEL:227/1967", "BR:LEI:12334/2010", "BR:DEC:9406/2018"} <= set(cs)
    dl = cs["BR:DEL:227/1967"]
    assert dl.data == "1967-02-28" and "Código de Mineração" in dl.indexacao
    assert dl.url.startswith("https://legis.senado.leg.br/norma/")


def test_almg_le_a_lei_mineira_com_situacao_e_link_do_texto():
    cs = {c.chave: c for c in d.ler_almg((FIX / "almg.csv").read_bytes())}
    lei = cs["MG:LEI:23291/2019"]
    assert lei.titulo == "Lei MG 23.291/2019" and lei.situacao == "VIGENTE" and lei.data == "2019-02-25"
    assert lei.url == "https://www.almg.gov.br/legislacao-mineira/texto/LEI/23291/2019/"
    assert "Barragem de Rejeitos" in lei.indexacao


def test_anm_le_cada_resolucao_e_marca_a_revogada():
    cs = {c.chave: c for c in d.ler_anm((FIX / "anm.html").read_text(encoding="utf-8"))}
    assert cs["BR:RES-ANM:108/2022"].situacao == "REVOGADA"
    assert "Revogada pela" not in cs["BR:RES-ANM:108/2022"].ementa       # a nota sai da ementa
    assert cs["BR:RES-ANM:127/2022"].situacao == "VIGENTE" and cs["BR:RES-ANM:127/2022"].data == "2022-12-22"
    assert "&link=S" not in cs["BR:RES-ANM:127/2022"].url


@pytest.mark.parametrize("norma, chave", [
    ("Lei 12.334/2010 (PNSB)", "BR:LEI:12334/2010"), ("Lei MG 23.291/2019", "MG:LEI:23291/2019"),
    ("Decreto MG 48.078/2020 (PAE)", "MG:DEC:48078/2020"), ("Res. ANM 95/2022", "BR:RES-ANM:95/2022"),
    ("Decreto-Lei 227/1967", "BR:DEL:227/1967"), ("LC 140/2011", "BR:LCP:140/2011"),
    ("NR-22", None), ("LO 000/2023 (fictícia)", None), (None, None),
])
def test_chave_da_norma_do_catalogo(norma, chave):
    assert d.chave_da_norma(norma) == chave


# ------------------------------------------------------------------- camada 0


def _c(ementa, indexacao="", situacao=None, jur="MG"):
    return d.Candidata("X", jur, "almg", "LEI", "1", 2020, "Lei X", ementa, indexacao=indexacao, situacao=situacao)


def test_termo_e_por_palavra_inteira_lavras_nao_e_lavra():
    cfg = d.temas()
    assert d.temas_da(_c("Declara de utilidade pública entidade com sede no Município de Lavras."), cfg) == []
    assert d.temas_da(_c("Dispõe sobre a lavra de recursos minerais"), cfg) == ["unidade"]
    assert d.temas_da(_c("Política estadual de segurança de barragens"), cfg) == ["barragem"]
    assert d.temas_da(_c("Inspeção de caldeiras e vasos de pressão"), cfg) == ["equipamento"]


@pytest.mark.parametrize("ementa", [
    "ABRE O CREDITO SUPLEMENTAR DE CR$ 200.000,00 A SECRETARIA DE ESTADO DE MINAS E ENERGIA",
    "Declara de utilidade pública a Associação dos Mineradores",
    "CONCEDE A MINERAÇÃO FAISCA LTDA. O DIREITO DE LAVRAR QUARTZO NO MUNICIPIO DE X",
    "DECLARA A CADUCIDADE DA CONCESSÃO DE LAVRA QUE MENCIONA.",
    "Dá denominação à barragem de contenção de cheias",
])
def test_regra_descarta_o_que_nunca_cobra_nada(ementa):
    assert d.descartada_pela_regra(_c(ementa), d.temas())


def test_regra_nao_descarta_o_que_pode_cobrar():
    cfg = d.temas()
    assert not d.descartada_pela_regra(_c("Concede anistia de multas a mineradoras que regularizarem barragens"), cfg)
    assert not d.descartada_pela_regra(_c("Institui a política estadual de segurança de barragens."), cfg)


def test_citacao_na_ementa_vira_chave_na_jurisdicao_e_na_federal():
    c = _c("Regulamenta o Decreto-Lei nº 227, de 28 de fevereiro de 1967, e a Lei nº 23.291, de 25 de "
           "fevereiro de 2019, e altera a Resolução ANM nº 95/2022.")
    assert {"BR:DEL:227/1967", "MG:LEI:23291/2019", "BR:RES-ANM:95/2022"} <= d.citadas(c)


# ------------------------------------------------------------------- perfil e busca


def test_perfil_da_carteira_por_jurisdicao_e_tipo_de_ativo(serra):
    p = {(n.jurisdicao, n.tipo_ativo): ativos for n, ativos in d.perfil(serra).items()}
    assert set(p) == {("BR", "barragem"), ("MG", "barragem"), ("BR", "unidade"), ("MG", "unidade"),
                      ("BR", "equipamento")}      # equipamento sem UF: só a lei federal; licença: não entra
    assert [a for _, a in p[("MG", "barragem")]] == ["B1", "B2", "B3", "B4"]


def test_busca_grava_candidatas_e_tira_o_que_ja_esta_no_catalogo(buscada):
    assert _status(buscada, "BR:LEI:12334/2010") == "catalogada"
    assert _status(buscada, "MG:LEI:23291/2019") == "catalogada"
    assert _status(buscada, "BR:RES-ANM:95/2022") == "catalogada"
    assert _status(buscada, "BR:DEL:227/1967") == "nova"            # pelo apelido "Código de Mineração"
    assert _status(buscada, "MG:DEC:48747/2023") == "nova"
    assert _status(buscada, "BR:RES-ANM:127/2022") == "nova"


def test_busca_deixa_fora_revogada_regra_e_o_que_nao_e_da_carteira(buscada):
    assert _status(buscada, "BR:RES-ANM:108/2022") is None          # revogada
    assert _status(buscada, "MG:DEC:31032/1990") is None            # crédito orçamentário
    assert _status(buscada, "MG:LEI:23260/2019") is None            # Lavras, o município
    assert _status(buscada, "BR:DEC:66014/1969") is None            # concessão de lavra a uma empresa


def test_decreto_que_so_cita_o_codigo_de_mineracao_entra_pela_citacao(buscada):
    """A ementa do Decreto 9.406/2018 não tem palavra de mineração: entra porque regulamenta o DL 227."""
    r = buscada.execute("SELECT status, temas FROM norma_candidata WHERE chave = 'BR:DEC:9406/2018'").fetchone()
    assert r["status"] == "nova" and json.loads(r["temas"]) == ["unidade"]


def test_busca_registra_ate_onde_cada_fonte_foi_lida(buscada):
    buscas = {r["fonte"]: dict(r) for r in buscada.execute("SELECT * FROM descoberta_busca")}
    assert set(buscas) == {"senado", "anm", "almg"}
    assert buscas["almg"]["jurisdicao"] == "MG" and buscas["almg"]["ate"] == 2026
    assert buscas["anm"]["desde"] == 2018           # a ANM existe desde 2018


def test_jurisdicao_sem_cliente_nao_e_lida(tmp_path):
    conn = db.conectar(":memory:")
    demo.carregar_cadastro(conn)
    emp = db.criar_empresa(conn, "Só Federal")
    db.criar_ativo(conn, emp, "barragem", "X1", "Sem UF", {}, "Geotecnia")
    b = BaixadorFixo(tmp_path)
    d.buscar(conn, b, desde=2018)
    assert not [p for p in b.pedidos if p[0] == "almg"]


def test_buscar_de_novo_nao_apaga_triagem_nem_decisao(buscada, tmp_path):
    rot, _ = _roteador(buscada, {"Decreto nº 9.406 de 12/06/2018": {
        "relevante": True, "tipos_ativo": ["unidade"], "deveres": "Plano de aproveitamento e relatórios",
        "motivo": "regulamenta o Código de Mineração", "confianca": 0.9}})
    d.triar(buscada, rot)
    d.decidir(buscada, "BR:DEC:9406/2018", "aprovar", "curadoria@mitra.com.br", "prioridade")
    d.buscar(buscada, BaixadorFixo(tmp_path), desde=1967)
    c = d.candidata(buscada, "BR:DEC:9406/2018")
    assert c["status"] == "aprovada" and c["triagem"]["deveres"] and c["nota"] == "prioridade"


def test_fonte_fora_do_ar_nao_derruba_as_outras(serra, tmp_path):
    class Quebrado(BaixadorFixo):
        def anm(self, ano):
            raise OSError("fora do ar")
    res = {r.fonte: r for r in d.buscar(serra, Quebrado(tmp_path), desde=2018)}
    assert res["anm"].falhas and not res["almg"].falhas
    fontes = {r["fonte"] for r in serra.execute("SELECT fonte FROM descoberta_busca")}
    assert "anm" not in fontes and "almg" in fontes      # a que falhou não conta como lida


# ------------------------------------------------------------------- triagem


def test_triagem_separa_relevante_e_irrelevante(buscada):
    rot, ia = _roteador(buscada, {"Lei MG 48.747/2023": None, "Decreto MG 48.747/2023": {
        "relevante": True, "tipos_ativo": ["barragem", "foguete"], "deveres": "Prestar caução ambiental",
        "motivo": "regulamenta a caução da Lei 23.291", "confianca": 0.93}})
    r = d.triar(buscada, rot)
    assert r["erro"] is None and r["restam"] == 0 and r["triadas"] == len(ia.chamadas)
    c = d.candidata(buscada, "MG:DEC:48747/2023")
    assert c["status"] == "relevante" and c["triagem"]["tipos_ativo"] == ["barragem"]    # tipo inventado sai
    assert _status(buscada, "BR:RES-ANM:127/2022") == "irrelevante"


def test_confianca_baixa_sobe_para_a_camada_3(buscada):
    titulo = "Decreto MG 48.747/2023"
    rot, ia = _roteador(buscada, {
        (titulo, "high"): {"relevante": True, "tipos_ativo": ["barragem"], "deveres": "x", "motivo": "?",
                           "confianca": 0.4},
        (titulo, "max"): {"relevante": True, "tipos_ativo": ["barragem"], "deveres": "Caução", "motivo": "ok",
                          "confianca": 0.9}})
    d.triar(buscada, rot)
    assert [e for n, e in ia.chamadas if n == titulo] == ["high", "max"]
    assert d.candidata(buscada, "MG:DEC:48747/2023")["triagem"]["confianca"] == 0.9


def test_resposta_invalida_deixa_a_norma_para_a_proxima_rodada(buscada):
    rot, _ = _roteador(buscada, {"Decreto MG 48.747/2023": "sem json nenhum"})
    r = d.triar(buscada, rot)
    assert _status(buscada, "MG:DEC:48747/2023") == "nova"
    assert any("MG:DEC:48747/2023" in f for f in r["falhas"]) and r["erro"] is None


def test_sem_provedor_para_e_nao_marca_nada(buscada):
    r = d.triar(buscada, Roteador(buscada, provedores={}))
    assert r["triadas"] == 0 and r["erro"] and r["restam"] > 0


def test_mesma_norma_nao_e_paga_duas_vezes(buscada):
    rot, ia = _roteador(buscada, {})
    d.triar(buscada, rot, limite=1)
    buscada.execute("UPDATE norma_candidata SET status = 'nova', triagem = NULL")
    buscada.commit()
    n = len(ia.chamadas)
    d.triar(buscada, rot, limite=1)
    assert len(ia.chamadas) == n            # veio do cache


# ------------------------------------------------------------------- curadoria


@pytest.fixture
def triada(buscada):
    rot, _ = _roteador(buscada, {"Decreto MG 48.747/2023": {
        "relevante": True, "tipos_ativo": ["barragem"], "deveres": "Prestar caução ambiental",
        "motivo": "regulamenta a Lei 23.291", "confianca": 0.9}})
    d.triar(buscada, rot)
    return buscada


def test_curadoria_aprova_com_nome_e_nota(triada):
    c = d.decidir(triada, "MG:DEC:48747/2023", "aprovar", "curadoria@mitra.com.br", "extrair em seguida")
    assert c["status"] == "aprovada" and c["decidida_por"] == "curadoria@mitra.com.br" and c["decidida_em"]


def test_curadoria_pode_discordar_da_ia(triada):
    assert d.decidir(triada, "BR:RES-ANM:127/2022", "aprovar", "ana")["status"] == "aprovada"


@pytest.mark.parametrize("chave, decisao, quem, erro", [
    ("MG:DEC:48747/2023", "talvez", "ana", "decisão"),
    ("MG:DEC:48747/2023", "aprovar", " ", "quem decide"),
    ("BR:LEI:12334/2010", "aprovar", "ana", "já está no catálogo"),
    ("BR:LEI:1/1900", "aprovar", "ana", "não encontrada"),
])
def test_curadoria_recusa(triada, chave, decisao, quem, erro):
    with pytest.raises(d.ErroDescoberta, match=erro):
        d.decidir(triada, chave, decisao, quem)


def test_nao_decide_antes_da_triagem(buscada):
    with pytest.raises(d.ErroDescoberta, match="triagem"):
        d.decidir(buscada, "MG:DEC:48747/2023", "aprovar", "ana")


def test_fila_da_curadoria_traz_as_relevantes(triada):
    assert [c["chave"] for c in d.fila(triada)] == ["MG:DEC:48747/2023"]
    assert d.fila(triada, jurisdicao="BR") == []


# ------------------------------------------------------------------- cobertura


def _por(itens):
    return {(i.jurisdicao, i.tipo_ativo): i for i in itens}


def test_cobertura_antes_da_busca_diz_que_a_fonte_nao_foi_lida(serra):
    itens = _por(d.cobertura(serra, 1))
    assert itens[("MG", "barragem")].estado == "nao_buscada"
    assert "Lei MG 23.291/2019" in itens[("MG", "barragem")].catalogadas


def test_cobertura_mostra_catalogo_lacunas_e_o_que_espera(triada):
    itens = _por(d.cobertura(triada, 1))
    br = itens[("BR", "barragem")]
    assert {"Res. ANM 220/2025", "Res. ANM 95/2022", "Lei 12.334/2010 (PNSB)"} <= set(br.catalogadas)
    assert any("Conama" in lac for lac in br.lacunas)
    mg = itens[("MG", "barragem")]
    assert mg.estado == "curadoria_pendente" and [c["chave"] for c in mg.em_curadoria] == ["MG:DEC:48747/2023"]
    assert any("Copam" in lac for lac in mg.lacunas) and mg.ativos == ["B1", "B2", "B3", "B4"]
    assert {f["fonte"] for f in mg.fontes} == {"almg"}


def test_cobertura_fica_coberta_quando_tudo_foi_decidido(triada):
    d.decidir(triada, "MG:DEC:48747/2023", "descartar", "ana", "já coberto pela Lei 23.291")
    assert _por(d.cobertura(triada, 1))[("MG", "barragem")].estado == "coberta"


def test_aprovada_sai_da_curadoria_e_espera_a_extracao(triada):
    d.decidir(triada, "MG:DEC:48747/2023", "aprovar", "curadoria@mitra.demo")
    mg = _por(d.cobertura(triada, 1))[("MG", "barragem")]
    assert mg.estado == "extracao_pendente" and mg.em_curadoria == []
    assert [c["chave"] for c in mg.aprovadas] == ["MG:DEC:48747/2023"]
    assert mg.estado in d.VERIFICADOS and mg.estado != "coberta"       # aprovada não é catalogada


def test_rotulos_para_a_tela_cobrem_todos_os_estados_status_e_fontes(triada):
    estados = {i.estado for i in d.cobertura(triada)} | {"sem_fonte", "nao_buscada", "extracao_pendente"}
    assert estados <= set(d.ROTULOS_ESTADO) and set(d.ROTULOS_STATUS) == set(d.STATUS)
    assert set(d.NOMES_FONTES) == set(d.FONTES) and d.NOMES_FONTES["almg"] == "Assembleia de Minas"
    assert not {"sem_fonte", "nao_buscada"} & set(d.VERIFICADOS)       # o que não foi lido nunca é verificado
    assert (d.nome_jurisdicao("BR"), d.nome_jurisdicao("MG"), d.nome_jurisdicao("PA")) == (
        "Brasil (federal)", "Minas Gerais", "Pará")


def test_estado_sem_conector_nunca_aparece_como_coberto(triada):
    emp = db.criar_empresa(triada, "Mineradora do Norte")
    db.criar_ativo(triada, emp, "barragem", "P1", "Barragem no Pará", {"uf": "PA"}, "Geotecnia")
    pa = _por(d.cobertura(triada, emp))[("PA", "barragem")]
    assert pa.estado == "sem_fonte" and pa.sem_fonte and pa.fontes == []


def test_cobertura_so_traz_a_empresa_pedida(triada):
    emp = db.criar_empresa(triada, "Outra")
    db.criar_ativo(triada, emp, "barragem", "Z1", "Z", {"uf": "PA"}, "Geotecnia")
    assert ("PA", "barragem") not in _por(d.cobertura(triada, 1))


# ------------------------------------------------------------------- demo


def test_exportar_e_semear_ida_e_volta_sem_sobrescrever_decisao(triada, tmp_path):
    arq = tmp_path / "fila.json"
    n = d.exportar(triada, arq)
    novo = db.conectar(":memory:")
    demo.montar(novo, com_historico=False)
    assert d.semear(novo, arq) == n
    assert d.candidata(novo, "MG:DEC:48747/2023")["status"] == "relevante"
    d.decidir(novo, "MG:DEC:48747/2023", "descartar", "ana")
    d.semear(novo, arq)
    assert d.candidata(novo, "MG:DEC:48747/2023")["status"] == "descartada"


def test_fila_da_demo_e_so_dado_publico_e_bem_formado():
    if not d.DEMO.exists():
        pytest.skip("data/descoberta_demo.json ainda não gerado")
    dados = json.loads(d.DEMO.read_text(encoding="utf-8"))
    assert {b["fonte"] for b in dados["buscas"]} == set(d.FONTES)
    for c in dados["candidatas"]:
        assert c["status"] in d.STATUS and c["jurisdicao"] in ("BR", "MG")
        assert c["chave"].split(":")[0] == c["jurisdicao"]
        assert c["url"].startswith(("https://legis.senado.leg.br/", "https://anmlegis.datalegis.net/",
                                    "https://www.almg.gov.br/"))
        if c["status"] in ("relevante", "irrelevante"):
            assert c["triagem"] and json.loads(c["triagem"])["motivo"]


def test_triagem_em_paralelo_da_o_mesmo_resultado(buscada):
    rots = []

    def novo():     # cada linha de execução com o seu Roteador (aqui sem cache: o banco é :memory:)
        ia = IAFalsa({"Decreto MG 48.747/2023": {
            "relevante": True, "tipos_ativo": ["barragem"], "deveres": "Caução", "motivo": "ok", "confianca": 0.9}},
            IRRELEVANTE)
        rots.append(ia)
        return Roteador(None, provedores={"opencode": ia})
    r = d.triar(buscada, novo(), paralelo=3, novo_roteador=novo)
    assert r["restam"] == 0 and r["erro"] is None
    assert _status(buscada, "MG:DEC:48747/2023") == "relevante" and len(rots) > 1


def test_com_bedrock_a_triagem_e_uma_por_vez(buscada):
    class BedrockFalso(IAFalsa):
        pass
    ia = BedrockFalso({}, IRRELEVANTE)
    rot = Roteador(buscada, provedores={"bedrock": ia, "opencode": ia})
    criados = []
    d.triar(buscada, rot, paralelo=4, novo_roteador=lambda: criados.append(1) or rot)
    assert criados == []            # nenhum Roteador extra: um pedido por vez, no ritmo do Bedrock


def test_quem_altera_norma_do_catalogo_vem_marcado_para_conferir_o_consolidado(triada):
    c = d.candidata(triada, "MG:DEC:48747/2023")       # regulamenta a Lei 23.291, que está no catálogo
    assert c["cita_catalogo"] == ["Lei MG 23.291/2019"]
    mg = _por(d.cobertura(triada, 1))[("MG", "barragem")]
    assert mg.em_curadoria[0]["cita_catalogo"] == ["Lei MG 23.291/2019"]



# ------------------------------------------------------------------- segunda leitura pelo texto

PEAB = "Decreto MG 48.747/2023"
DUVIDOSA = {"relevante": False, "tipos_ativo": [], "deveres": "", "motivo": "institui política", "confianca": 0.78}
PELO_TEXTO = {"relevante": True, "tipos_ativo": ["barragem"], "deveres": "art. 7º: prestar caução",
              "motivo": "o texto cobra do empreendedor", "confianca": 0.9}


def test_descarte_duvidoso_rele_pelo_texto_oficial(buscada):
    lidos = []
    rot, ia = _roteador(buscada, {PEAB: DUVIDOSA, (PEAB, "texto"): PELO_TEXTO})
    d.triar(buscada, rot, texto=lambda linha: lidos.append(linha["chave"]) or "Art. 1º ... Art. 7º O empreendedor")
    c = d.candidata(buscada, "MG:DEC:48747/2023")
    assert c["status"] == "relevante" and c["triagem"]["leu_texto"] and "art. 7º" in c["triagem"]["deveres"]
    assert "MG:DEC:48747/2023" in lidos
    assert "BR:RES-ANM:127/2022" not in lidos           # descarte com confiança alta não relê


def test_sem_texto_fica_a_decisao_pela_ementa(buscada):
    rot, _ = _roteador(buscada, {PEAB: DUVIDOSA, (PEAB, "texto"): PELO_TEXTO})
    d.triar(buscada, rot, texto=lambda linha: None)       # o Planalto, por exemplo
    c = d.candidata(buscada, "MG:DEC:48747/2023")
    assert c["status"] == "irrelevante" and not c["triagem"]["leu_texto"]


def test_fonte_do_texto_fora_do_ar_nao_derruba_a_triagem(buscada):
    def quebra(linha):
        raise OSError("fora do ar")
    rot, _ = _roteador(buscada, {PEAB: DUVIDOSA})
    r = d.triar(buscada, rot, texto=quebra)
    assert r["erro"] is None and _status(buscada, "MG:DEC:48747/2023") == "irrelevante"


def test_revisar_rele_so_os_descartes_duvidosos_e_a_ementa_vem_do_cache(buscada):
    rot, ia = _roteador(buscada, {PEAB: DUVIDOSA, (PEAB, "texto"): PELO_TEXTO})
    d.triar(buscada, rot)                                   # primeira rodada, sem texto
    assert _status(buscada, "MG:DEC:48747/2023") == "irrelevante"
    antes = len(ia.chamadas)
    d.triar(buscada, rot, texto=lambda linha: "Art. 1º ...", revisar=True)
    novas = ia.chamadas[antes:]
    assert novas == [(PEAB, "texto")]                       # só a duvidosa, e a ementa não foi paga de novo
    assert _status(buscada, "MG:DEC:48747/2023") == "relevante"


def test_texto_da_pagina_comeca_no_artigo_primeiro():
    pagina = ("<html><head><script>var a = 'Art. 1º falso';</script><style>p{}</style></head><body>"
              "<h1>Lei nº 1</h1><p>Art. 1º &ndash; Fica instituída a política.</p><p>Art. 2º O empreendedor deve...</p>")
    assert d.texto_da_pagina(pagina) == "Art. 1º – Fica instituída a política. Art. 2º O empreendedor deve..."


def test_revisar_soma_o_custo_da_primeira_leitura(buscada):
    rot, _ = _roteador(buscada, {PEAB: DUVIDOSA, (PEAB, "texto"): PELO_TEXTO})
    d.triar(buscada, rot)
    primeira = d.candidata(buscada, "MG:DEC:48747/2023")["triagem"]["custo_usd"]
    d.triar(buscada, rot, texto=lambda linha: "Art. 1º ...", revisar=True)
    total = d.candidata(buscada, "MG:DEC:48747/2023")["triagem"]["custo_usd"]
    assert primeira > 0 and total > primeira
