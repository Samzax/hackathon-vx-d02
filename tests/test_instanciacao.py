"""Instanciação: as etapas com estado tirado dos dados, unidades, ativos, planilha e entrada em operação."""

from __future__ import annotations

import pytest

from regulaia import db, instanciacao as inst, usuarios

POR = "Curadoria RegulaIA"
NOME = "Mineradora Nova (fictícia)"


@pytest.fixture
def conn():
    c = db.conectar(":memory:")
    yield c
    c.close()


@pytest.fixture
def nova(conn):
    """Uma empresa recém-criada: só a etapa do cadastro pronta."""
    eid = inst.criar(conn, nome=NOME, razao_social="Mineradora Nova S.A.", cnpj="11.222.333/0001-81",
                     ufs=["mg", "MG", "pa"], por=POR, ficticia=True)
    return eid


# ------------------------------------------------------------------ etapa 1: cadastro


def test_criar_normaliza_cnpj_e_ufs_e_registra_quem_fez(conn, nova):
    i = inst.da_empresa(conn, nova)
    assert i["cnpj"] == "11222333000181" and i["razao_social"] == "Mineradora Nova S.A."
    assert i["ufs"] == ["MG", "PA"]                  # sem repetir, em maiúsculas
    assert i["criada_por"] == POR and i["nome"] == NOME
    [ev] = inst.eventos(conn, nova, inst.CADASTRO)
    assert ev["acao"] == "empresa criada" and ev["por"] == POR and ev["detalhe"]["ufs"] == ["MG", "PA"]


def test_empresa_sem_barragem_no_sigbm_entra_com_cnpj_e_nome(conn):
    eid = inst.criar(conn, nome="Só CNPJ (fictícia)", razao_social="Só CNPJ Ltda",
                     cnpj="11222333000181", ufs=[], por=POR)
    assert inst.estado(conn, eid).etapas[0].pronta


def test_empreendedor_pessoa_fisica_entra_sem_cnpj(conn):
    """As linhas do SIGBM com CPF ficam fora da base pública; a pessoa física entra informando os dados."""
    eid = inst.criar(conn, nome="João da Silva (PF, fictício)", razao_social="João da Silva",
                     cnpj=None, ufs=["MG"], por=POR)
    assert inst.da_empresa(conn, eid)["cnpj"] is None


def test_cadastro_recusa_o_que_deixaria_a_torre_torta(conn, nova):
    with pytest.raises(inst.ErroInstanciacao, match="14 dígitos"):
        inst.criar(conn, nome="X", razao_social="X", cnpj="123", ufs=[], por=POR)
    with pytest.raises(inst.ErroInstanciacao, match="razão social"):
        inst.criar(conn, nome="X", razao_social="", cnpj=None, ufs=[], por=POR)
    with pytest.raises(inst.ErroInstanciacao, match="não é uma UF"):
        inst.criar(conn, nome="X", razao_social="X", cnpj=None, ufs=["Minas"], por=POR)
    with pytest.raises(inst.ErroInstanciacao, match="já existe uma empresa"):
        inst.criar(conn, nome=NOME, razao_social="Outra", cnpj=None, ufs=[], por=POR)
    with pytest.raises(inst.ErroInstanciacao, match="já está instanciado"):
        inst.criar(conn, nome="Outra (fictícia)", razao_social="Outra", cnpj="11.222.333/0001-81",
                   ufs=[], por=POR)


# ------------------------------------------------------------------ etapa 2: ativos e unidades


def test_ativo_pertence_a_unidade_da_propria_empresa(conn, nova):
    outra = inst.criar(conn, nome="Vizinha (fictícia)", razao_social="Vizinha", cnpj=None, ufs=[], por=POR)
    inst.criar_unidade(conn, nova, "Mina Nova", POR, uf="mg", municipio="Itabirito")
    inst.criar_unidade(conn, outra, "Mina da Vizinha", POR)
    aid = inst.criar_ativo(conn, nova, tipo="barragem", codigo="B1", nome="Barragem Nova", por=POR,
                           unidade="Mina Nova", atributos={"uf": "mg", "altura_m": "25", "dpa": "alto"})
    a = db.ativo_por_codigo(conn, nova, "B1")
    assert a["id"] == aid and a["unidade"] == "Mina Nova"
    assert db.ativos(conn, nova)[0]["atributos"] == {"uf": "MG", "altura_m": 25, "dpa": "alto"}
    # a unidade da outra cliente não existe para esta
    with pytest.raises(inst.ErroInstanciacao, match="não tem a unidade"):
        inst.criar_ativo(conn, nova, tipo="barragem", codigo="B2", nome="B2", por=POR,
                         unidade="Mina da Vizinha")
    assert [u["nome"] for u in inst.unidades(conn, nova)] == ["Mina Nova"]


def test_ativo_recusa_tipo_codigo_repetido_e_valor_que_nao_serve(conn, nova):
    inst.criar_ativo(conn, nova, tipo="barragem", codigo="B1", nome="B1", por=POR)
    with pytest.raises(inst.ErroInstanciacao, match="já tem o ativo B1"):
        inst.criar_ativo(conn, nova, tipo="barragem", codigo="B1", nome="outra", por=POR)
    with pytest.raises(inst.ErroInstanciacao, match="tipo de ativo desconhecido"):
        inst.criar_ativo(conn, nova, tipo="usina", codigo="X1", nome="X", por=POR)
    with pytest.raises(inst.ErroInstanciacao, match="não é número"):
        inst.criar_ativo(conn, nova, tipo="barragem", codigo="B9", nome="B9", por=POR,
                         atributos={"altura_m": "alta"})
    with pytest.raises(inst.ErroInstanciacao, match="não é campo do cadastro de barragem"):
        inst.criar_ativo(conn, nova, tipo="barragem", codigo="B8", nome="B8", por=POR,
                         atributos={"classe": "caldeira"})


# ------------------------------------------------- a planilha (modelo CSV, erro na linha)


def test_modelo_csv_traz_as_colunas_fixas_e_os_campos_do_tipo():
    modelo = inst.modelo_csv("barragem")
    cabecalho = modelo.splitlines()[0].split(",")
    assert cabecalho[:5] == ["tipo", "codigo", "nome", "unidade", "responsavel"]
    assert "dpa2" in cabecalho and "cri" in cabecalho and "classe" not in cabecalho
    assert "Zona de Autossalvamento" in modelo.splitlines()[1]       # a pergunta de quem preenche
    assert "classe" in inst.modelo_csv("equipamento").splitlines()[0]


def test_planilha_valida_linha_a_linha_com_o_erro_na_linha(conn, nova):
    inst.criar_unidade(conn, nova, "Mina Nova", POR)
    csv = (
        "tipo,codigo,nome,unidade,responsavel,uf,altura_m,dpa\n"
        "# ajuda do modelo,ex.: B1,,,,,,\n"
        "barragem,B1,Barragem Um,Mina Nova,Geotecnia,MG,30,alto\n"
        "barragem,B2,Barragem Dois,Mina Fantasma,,MG,30,alto\n"
        "barragem,,Sem código,,,MG,10,baixo\n"
        "mina,B4,Tipo errado,,,MG,10,baixo\n"
        "barragem,B1,Código repetido,,,MG,10,baixo\n"
        "barragem,B6,Altura errada,,,MG,muito alta,baixo\n"
    )
    linhas = inst.ler_planilha(csv, nova, conn)
    assert [l.linha for l in linhas] == [3, 4, 5, 6, 7, 8]      # a linha de ajuda sai
    ok, fantasma, sem_codigo, tipo, repetido, altura = linhas
    assert ok.erro is None and ok.atributos == {"uf": "MG", "altura_m": 30, "dpa": "alto"}
    assert ok.unidade == "Mina Nova" and ok.responsavel == "Geotecnia"
    assert "não tem a unidade 'Mina Fantasma'" in fantasma.erro
    assert "código vazio" in sem_codigo.erro
    assert "use barragem, unidade, equipamento, licenca" in tipo.erro
    assert "repetido (também na linha 3)" in repetido.erro
    assert "não é número" in altura.erro
    # nada foi gravado: a leitura só confere
    assert db.ativos(conn, nova) == []


def test_planilha_entra_inteira_ou_nada(conn, nova):
    ruim = "tipo,codigo,nome\nbarragem,B1,Um\nbarragem,,Sem código\n"
    linhas = inst.importar_planilha(conn, nova, ruim, POR)
    assert any(l.erro for l in linhas) and db.ativos(conn, nova) == []    # meia importação, nunca
    boa = "tipo,codigo,nome,uf\nbarragem,B1,Um,MG\nbarragem,B2,Dois,MG\nequipamento,E1,Vaso,\n"
    linhas = inst.importar_planilha(conn, nova, boa, POR)
    assert not any(l.erro for l in linhas)
    assert [a["codigo"] for a in db.ativos(conn, nova)] == ["B1", "B2", "E1"]
    # repetir a importação não duplica: o código já existe
    assert all(l.erro for l in inst.importar_planilha(conn, nova, boa, POR))


def test_planilha_aceita_ponto_e_virgula_e_acento_do_excel(conn, nova):
    csv = "tipo;codigo;nome;uf;municipio\nbarragem;B1;Barragem São João;MG;Nova Lima\n"
    linhas = inst.ler_planilha(csv.encode("latin-1"), nova, conn)
    assert len(linhas) == 1 and linhas[0].erro is None
    assert linhas[0].nome == "Barragem São João" and linhas[0].atributos["municipio"] == "Nova Lima"


def test_planilha_sem_as_colunas_do_modelo_diz_o_que_fazer(conn, nova):
    [linha] = inst.ler_planilha("a,b,c\n1,2,3\n", nova, conn)
    assert "não tem a coluna" in linha.erro and "baixe o modelo" in linha.erro
    [vazia] = inst.ler_planilha("tipo,codigo,nome\n", nova, conn)
    assert "nenhuma linha preenchida" in vazia.erro


# ------------------------------------------------------------------ etapa 3: dados que faltam


def test_dados_que_faltam_sao_lista_de_tarefas_com_as_obrigacoes(conn):
    """A barragem importada do SIGBM não traz o que as regras pedem: a torre mostra, não presume."""
    from regulaia import demo

    demo.montar(conn)
    eid = db.empresas(conn)[0]["id"]
    faltam = inst.dados_que_faltam(conn, eid)
    assert faltam and all(d.obrigacoes for d in faltam)
    [b4] = [d for d in faltam if d.ativo == "B4"]       # a B4 é a que ninguém informou na demo
    assert b4.campo == "modificacao_estrutural" and "modificação estrutural" in b4.pergunta
    assert b4.obrigacoes == ["OB-09", "R95-08"]         # as obrigações que dependem do dado


# ------------------------------------------------------------------ o estado das etapas


def test_etapas_saem_dos_dados_e_o_percentual_das_etapas(conn, nova):
    e = inst.estado(conn, nova)
    assert [x.etapa for x in e.etapas] == list(inst.ETAPAS)
    assert e.etapas[0].pronta and e.etapas[0].por == POR
    assert {x.etapa for x in e.pendencias} == set(inst.ETAPAS) - {inst.CADASTRO}
    assert e.percentual == 12 and not e.em_operacao          # 1 de 8 etapas
    assert all(x.falta for x in e.pendencias)               # cada pendência diz o que fazer

    inst.criar_ativo(conn, nova, tipo="barragem", codigo="B1", nome="B1", por=POR,
                     atributos={"uf": "MG", "inserida_pnsb": "não"})
    e = inst.estado(conn, nova)
    por_etapa = {x.etapa: x for x in e.etapas}
    assert por_etapa[inst.ATIVOS].pronta and por_etapa[inst.ATIVOS].numeros["ativos"] == 1
    assert por_etapa[inst.COBERTURA].pronta                 # roda assim que há ativos
    assert por_etapa[inst.CONTAS].estado == inst.PENDENTE

    usuarios.criar(conn, "ti@nova.demo", "TI Nova", usuarios.ADMIN, senha="senha-provisoria",
                   empresa=NOME, por=POR)
    e2 = {x.etapa: x for x in inst.estado(conn, nova).etapas}
    assert e2[inst.CONTAS].pronta and e2[inst.CONTAS].numeros["ti"] == 1
    assert inst.estado(conn, nova).percentual > e.percentual


def test_estado_de_empresa_que_nao_foi_instanciada(conn):
    eid = db.criar_empresa(conn, "Importada do SIGBM (fictícia)")
    with pytest.raises(inst.ErroInstanciacao, match="não tem instanciação"):
        inst.estado(conn, eid)


# ------------------------------------------------------------------ etapa 8: entrar em operação


def test_entrar_em_operacao_grava_monitorado_desde_e_aceita_pendencia(conn, nova):
    with pytest.raises(inst.ErroInstanciacao, match="nenhum ativo"):
        inst.entrar_em_operacao(conn, nova, POR)
    inst.criar_ativo(conn, nova, tipo="barragem", codigo="B1", nome="B1", por=POR, atributos={"uf": "MG"})
    dia = inst.entrar_em_operacao(conn, nova, POR, desde="2026-11-07")
    assert dia == "2026-11-07"
    e = inst.estado(conn, nova)
    assert e.em_operacao and e.monitorado_desde == "2026-11-07"
    assert {x.etapa for x in e.pendencias}                  # entrou com pendência, e ela continua visível
    [ev] = [x for x in inst.eventos(conn, nova, inst.OPERACAO)]
    assert ev["acao"] == "entrou em operação" and inst.LICENCAS in ev["detalhe"]["pendencias"]
    with pytest.raises(inst.ErroInstanciacao, match="já está em operação"):
        inst.entrar_em_operacao(conn, nova, POR)


def test_instanciadas_mostra_as_que_faltam_entrar_primeiro(conn, nova):
    outra = inst.criar(conn, nome="Já em operação (fictícia)", razao_social="X", cnpj=None, ufs=[], por=POR)
    inst.criar_ativo(conn, outra, tipo="barragem", codigo="B1", nome="B1", por=POR)
    inst.entrar_em_operacao(conn, outra, POR, desde="2026-01-01")
    assert [i["empresa_id"] for i in inst.instanciadas(conn)] == [nova, outra]


# ------------------------------------------- código da obrigação único por empresa (migração 0005)


def _condicionante(conn, empresa_id: int, empresa: str, codigo: str, titulo: str) -> int:
    """Uma obrigação própria da empresa, como a aprovação de uma condicionante de licença cria."""
    with conn:
        ob = conn.execute("INSERT INTO obrigacao (codigo, tipo_ativo, norma, area, empresa) "
                          "VALUES (?, 'licenca', ?, 'ambiental', ?)",
                          (codigo, f"LO 000/2023 de {empresa}", empresa)).lastrowid
        conn.execute(
            "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, aplica_se_a, regra, "
            "periodicidade, agenda, prazo, vigencia_desde, responsavel, evidencia, fonte, status, "
            "decidida_por, decidida_em) VALUES (?, 1, ?, 'cond. 1', 'a licença', '*', 'Mensal', "
            "'mensal+10d', 'até 10 dias após o mês', '2023-03-15', 'Ambiental', 'Laudo', ?, 'vigente', "
            "?, ?)", (ob, titulo, f"LO 000/2023 de {empresa} cond. 1", "Regulatório da empresa", db.agora()))
    return ob


def test_duas_clientes_tem_cada_uma_a_sua_lo01(conn):
    """O código era UNIQUE global: duas clientes não podiam ter cada uma a sua "LO-01" (migração 0005).
    Cada uma vê e entrega só a sua, e a norma pública continua igual para as duas."""
    a = inst.criar(conn, nome="Cliente A (fictícia)", razao_social="A", cnpj=None, ufs=["MG"], por=POR)
    b = inst.criar(conn, nome="Cliente B (fictícia)", razao_social="B", cnpj=None, ufs=["MG"], por=POR)
    la = inst.criar_ativo(conn, a, tipo="licenca", codigo="L1", nome="LO da A", por=POR)
    lb = inst.criar_ativo(conn, b, tipo="licenca", codigo="L1", nome="LO da B", por=POR)
    _condicionante(conn, a, "Cliente A (fictícia)", "LO-01", "Monitorar as águas (A)")
    _condicionante(conn, b, "Cliente B (fictícia)", "LO-01", "Plantar as mudas (B)")
    # uma norma pública com o mesmo código entraria aqui também, e continua única entre as públicas
    publica = _condicionante(conn, a, None, "OB-PUB", "Norma pública")
    conn.execute("UPDATE obrigacao SET empresa = NULL WHERE id = ?", (publica,))
    conn.commit()

    # cada cliente vê a sua condicionante com o mesmo código
    assert db.versao(conn, "LO-01", empresa="Cliente A (fictícia)")["titulo"] == "Monitorar as águas (A)"
    assert db.versao(conn, "LO-01", empresa="Cliente B (fictícia)")["titulo"] == "Plantar as mudas (B)"
    # cada ativo recebe a condicionante da própria dona, e a norma pública vale para as duas
    assert {o.vigente["titulo"] for o in db.obrigacoes_do_ativo(conn, la)} == {"Monitorar as águas (A)",
                                                                               "Norma pública"}
    assert {o.vigente["titulo"] for o in db.obrigacoes_do_ativo(conn, lb)} == {"Plantar as mudas (B)",
                                                                               "Norma pública"}

    # a entrega de uma não dá baixa na da outra: a busca por código leva a empresa dona do ativo
    db.entregar(conn, la, "LO-01", "2026-10", dia="2026-10-20", por="Ambiental da A")
    assert db.evidencias(conn, la, "LO-01") == ["2026-10"]
    assert db.evidencias(conn, lb, "LO-01") == []

    # sem dizer de qual empresa, o código ambíguo é erro: nunca se escolhe uma dona por acaso
    with pytest.raises(db.ErroCadastro, match="existe em mais de uma empresa"):
        db.versao(conn, "LO-01")
    assert db.versao(conn, "OB-PUB")["titulo"] == "Norma pública"        # pública, sem ambiguidade


def test_a_mesma_empresa_nao_repete_o_codigo(conn):
    a = inst.criar(conn, nome="Cliente A (fictícia)", razao_social="A", cnpj=None, ufs=[], por=POR)
    _condicionante(conn, a, "Cliente A (fictícia)", "LO-01", "Primeira")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        _condicionante(conn, a, "Cliente A (fictícia)", "LO-01", "Repetida na mesma empresa")
