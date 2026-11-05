from datetime import date

import pytest

from regulaia import agenda, db, demo, evidencias as ev, torre

HOJE = date(2026, 11, 7)
DESDE = date(2026, 5, 1)


@pytest.fixture
def conn():
    c = db.conectar(":memory:")
    demo.montar(c)
    return c


def _linha(conn, ativo, codigo):
    return {l.codigo: l for l in torre.painel(conn, 1, HOJE, DESDE, ativo=ativo)}[codigo]


def _pdf(nome):
    caminho = ev.exemplo(nome)
    if not caminho.exists():
        pytest.importorskip("reportlab")
        from regulaia import exemplos
        exemplos.gerar()
    return ev.texto_pdf(caminho)


def test_fir_da_b3_baixa_a_quinzena_atrasada(conn):
    antes = _linha(conn, "B3", "R95-01")
    assert antes.status == agenda.ATRASADA and "2026-10-1Q" in antes.faltando

    le = ev.ler(conn, _pdf("FIR_B3_2026-10-1Q.pdf"), 1, HOJE)
    assert (le.ativo, le.obrigacao, le.periodo, le.data) == ("B3", "R95-01", "2026-10-1Q", "2026-10-09")
    assert le.completa and le.metodo == "regra" and not le.gatilhos

    ev.registrar(conn, le, "FIR_B3_2026-10-1Q.pdf")
    depois = _linha(conn, "B3", "R95-01")
    assert depois.status != agenda.ATRASADA and "2026-10-1Q" not in depois.faltando


def test_fir_com_pontuacao_10_dispara_ise(conn):
    le = ev.ler(conn, _pdf("FIR_B2_2026-11-1Q_anomalia.pdf"), 1, HOJE)
    assert le.ativo == "B2"                       # "Serra I" não pode casar com "Serra II"
    assert le.pontuacao_maxima == 10
    assert le.gatilhos and "Especial" in le.gatilhos[0]


def test_boletim_de_efluentes_vai_para_a_licenca(conn):
    le = ev.ler(conn, _pdf("Boletim_efluentes_2026-09.pdf"), 1, HOJE)
    assert (le.ativo, le.obrigacao, le.periodo) == ("L1", "LO-02", "2026-09")
    ev.registrar(conn, le, "Boletim_efluentes_2026-09.pdf")
    assert _linha(conn, "L1", "LO-02").status != agenda.ATRASADA


def test_nome_parecido_nao_confunde_ativos(conn):
    ativos = db.ativos(conn, 1)
    nomes = {a["codigo"]: a["nome"] for a in ativos}
    texto = ev.normalizar(f"vistoria na {nomes['B2']}")
    assert ev._ativos_citados(texto, ativos) == ["B2"]


def test_sem_ativo_a_leitura_fica_incompleta_e_nao_registra(conn):
    le = ev.ler(conn, "Ficha de Inspeção Regular\nData da inspeção: 01/11/2026", 1, HOJE)
    assert le.ativo is None and not le.completa
    with pytest.raises(ValueError):
        ev.registrar(conn, le, "x.pdf")


def test_data_no_futuro_e_problema(conn):
    le = ev.ler(conn, "Ficha de Inspeção Regular (B3)\nData da inspeção: 20/12/2026", 1, HOJE)
    assert "data de execução no futuro" in le.problemas and le.periodo is None


class _IA:
    def __init__(self, dados):
        self.dados = dados

    def pedir_json(self, *a, **k):
        return self


def test_ia_nao_pode_inventar_data(conn):
    texto = "Ficha de Inspeção Regular (B3)\nvistoria feita sem data legível"
    le = ev.ler(conn, texto, 1, HOJE, roteador=_IA({"ativo": "B3", "data": "2026-10-09"}))
    assert le.metodo == "ia" and le.periodo is None
    assert any("não está no documento" in p for p in le.problemas)


def test_ia_completa_o_ativo_quando_a_regra_nao_acha(conn):
    texto = "Ficha de Inspeção Regular\nData da inspeção: 09/10/2026\nbarramento do córrego"
    le = ev.ler(conn, texto, 1, HOJE, roteador=_IA({"ativo": "B3", "data": None}))
    assert (le.ativo, le.periodo, le.metodo) == ("B3", "2026-10-1Q", "ia")
    assert le.completa


def test_relatorio_nr13_tira_o_vaso_do_atraso(conn):
    assert _linha(conn, "E1", "N13-03").status == agenda.ATRASADA
    le = ev.ler(conn, _pdf("Relatorio_NR13_VP-101_exame_externo.pdf"), 1, HOJE)
    assert (le.ativo, le.obrigacao, le.periodo) == ("E1", "N13-03", "2026-11-03")   # pelo nome, sem código
    ev.registrar(conn, le, "Relatorio_NR13_VP-101_exame_externo.pdf")
    depois = _linha(conn, "E1", "N13-03")
    assert depois.status == agenda.EM_DIA and depois.vence == "2029-11-03"           # +3 anos (Tabela 2)


def test_relatorio_nr13_de_exame_interno_vai_para_a_outra_obrigacao(conn):
    texto = ("Relatório de inspeção de segurança do vaso de pressão\n"
             "Equipamento: VP-101 Reservatório de ar comprimido da usina\n"
             "Tipo de exame: interno\nData da inspeção: 03/11/2026")
    assert ev.ler(conn, texto, 1, HOJE).obrigacao == "N13-04"


def test_pdf_escaneado_diz_que_nao_tem_texto(conn):
    le = ev.ler(conn, "  \n ", 1, HOJE, roteador=_IA({"ativo": "B3"}))
    assert le.problemas == ["o PDF não tem texto (parece escaneado): ainda não fazemos OCR"]
    assert le.metodo == "regra"                     # nem chama a IA


def test_recibo_do_eir_comprova_a_quinzena_e_avisa_o_atraso(conn):
    le = ev.ler(conn, _pdf("EIR_B3_2026-10-1Q_recibo_SIGBM.pdf"), 1, HOJE)
    assert (le.ativo, le.obrigacao, le.periodo) == ("B3", "R95-02", "2026-10-1Q")   # período da inspeção, não do envio
    assert le.completa and len(le.avisos) == 1 and "7 dias depois do prazo (30/10/2026)" in le.avisos[0]
    ev.registrar(conn, le, "EIR_B3_2026-10-1Q_recibo_SIGBM.pdf")
    assert _linha(conn, "B3", "R95-02").status != agenda.ATRASADA


def test_envio_no_prazo_nao_gera_aviso(conn):
    texto = "Extrato de Inspeção Regular (B3)\nData da inspeção: 09/10/2026\nData do envio: 20/10/2026"
    le = ev.ler(conn, texto, 1, HOJE)
    assert le.periodo == "2026-10-1Q" and not le.avisos


def test_evidencias_do_ativo_mostra_a_mais_nova_primeiro_com_o_que_foi_lido(conn):
    le = ev.ler(conn, _pdf("EIR_B3_2026-10-1Q_recibo_SIGBM.pdf"), 1, HOJE)
    ev.registrar(conn, le, "EIR_B3_2026-10-1Q_recibo_SIGBM.pdf")
    b3 = next(a for a in db.ativos(conn, 1) if a["codigo"] == "B3")
    [ultima, *_] = db.evidencias_do_ativo(conn, b3["id"])
    assert (ultima["codigo"], ultima["periodo"]) == ("R95-02", "2026-10-1Q")
    assert ultima["extraido"]["metodo"] == "regra" and "depois do prazo" in ultima["extraido"]["avisos"][0]


DIA_220 = date(2027, 8, 2)        # primeiro dia da Res. ANM 220/2025 (botão da viagem no tempo)


def test_na_res220_a_ise_vem_das_colunas_ec(conn):
    """Res. 220, art. 42: EC1, EC3, EC4 ou EC5 = 5 obriga ISE; EC2 = 5 sozinho não."""
    le = ev.ler(conn, _pdf("FIR_B2_2027-08-1Q_Res220_EC3.pdf"), 1, DIA_220)
    assert (le.ativo, le.obrigacao, le.periodo) == ("B2", "OB-02", "2027-08-1Q")
    assert le.estado_conservacao == {"EC1": 0, "EC2": 5, "EC3": 5, "EC4": 0, "EC5": 0}
    assert len(le.gatilhos) == 1
    assert "EC3 = 5" in le.gatilhos[0] and "EC2" not in le.gatilhos[0]
    assert "Res. ANM 220/2025, art. 42" in le.gatilhos[0] and "38 §4" in le.gatilhos[0]


def test_ec2_igual_a_5_nao_obriga_ise(conn):
    texto = _pdf("FIR_B2_2027-08-1Q_Res220_EC3.pdf").replace("EC3 = 5", "EC3 = 0")
    le = ev.ler(conn, texto, 1, DIA_220)
    assert le.estado_conservacao["EC2"] == 5 and not le.gatilhos


def test_pontuacao_10_nao_e_mais_a_regra_depois_da_troca(conn):
    """A FIR no modelo antigo (pontuação 10, sem colunas EC) lida sob a Res. 220: sem gatilho
    automático, mas com aviso de que falta o Quadro I.8."""
    le = ev.ler(conn, _pdf("FIR_B2_2026-11-1Q_anomalia.pdf"), 1, DIA_220)
    assert not le.gatilhos
    assert any("Quadro I.8" in a for a in le.avisos)


def _doc(titulo: str, ativo: str, data: str, resto: str = "") -> str:
    return (f"{titulo}\nEmpreendedor: Mineradora Serra Azul (fictícia)\n{ativo}\n"
            f"Data de realização: {data}\n{resto}\nDocumento fictício.")


@pytest.mark.parametrize("titulo, ativo, data, obrigacao, periodo", [
    ("REGISTRO DE TREINAMENTO INTERNO DO PAEBM", "Barragem: Barragem Serra II (B2)", "20/10/2026", "R95-11", "2026-S2"),
    ("SEMINÁRIO ORIENTATIVO - LISTA DE PRESENÇA", "Barragem: Barragem Serra II (B2)", "15/09/2026", "R95-13", "2026"),
    ("PROCESSO DE GESTÃO DE RISCOS PARA BARRAGENS DE MINERAÇÃO (PGRBM) - ATUALIZAÇÃO", "Barragem: Barragem Serra II (B2)",
     "15/10/2026", "R95-16", "2026-10-15"),
    ("RELATÓRIO DE MONITORAMENTO DA QUALIDADE DAS ÁGUAS SUPERFICIAIS", "Licença de Operação nº 000/2023 (L1)",
     "05/10/2026", "LO-01", "2026-T4"),
    ("RELATÓRIO DE EXECUÇÃO DO PLANO DE RECUPERAÇÃO DE ÁREAS DEGRADADAS", "Licença de Operação nº 000/2023 (L1)",
     "10/07/2026", "LO-04", "2026-S2"),
    ("REGISTRO DE TREINAMENTO DA BRIGADA DE EMERGÊNCIA", "Unidade: Complexo Minerário Serra Azul (U1)",
     "02/10/2026", "N22-08", "2026-10-02"),
    ("RELATÓRIO DE SIMULAÇÃO DO PLANO DE EMERGÊNCIA", "Unidade: Complexo Minerário Serra Azul (U1)",
     "18/08/2026", "N22-09", "2026"),
    ("RELATÓRIO CONSOLIDADO DE RUÍDO E VIBRAÇÃO DAS DETONAÇÕES", "Licença de Operação nº 000/2023 (L1)",
     "30/09/2026", "LO-03", "2026-T3"),
    ("RELATÓRIO ANUAL DE CUMPRIMENTO DAS CONDICIONANTES", "Licença de Operação nº 000/2023 (L1)",
     "10/03/2026", "LO-05", "2026-03-15"),
])
def test_documentos_de_paebm_pgrbm_licenca_e_brigada(conn, titulo, ativo, data, obrigacao, periodo):
    le = ev.ler(conn, _doc(titulo, ativo, data), 1, HOJE)
    assert (le.obrigacao, le.periodo) == (obrigacao, periodo), le.problemas


def test_rco_vale_pelo_titulo_mesmo_citando_a_dco(conn):
    """O RCO (Res. 220, art. 57 I) fala da DCO no corpo: o tipo é o do título."""
    texto = _doc("RELATÓRIO DE CONFORMIDADE E OPERACIONALIDADE (RCO) DO PAEBM", "Barragem: Barragem Serra II (B2)",
                 "20/06/2028", "Fundamenta a Declaração de Conformidade e Operacionalidade (DCO) deste ano.")
    le = ev.ler(conn, texto, 1, date(2028, 7, 10))
    assert (le.documento, le.obrigacao, le.periodo) == ("RCO", "OB-14", "2028-06-30")


def test_anomalia_registrada_abre_a_ise_ate_chegar_o_relatorio(conn):
    """A FIR com pontuação 10 abre a ISE da B2 (prazo de 24 h). A torre não esquece: a ISE fica
    atrasada até o relatório da inspeção ser registrado, que a encerra."""
    le = ev.ler(conn, _pdf("FIR_B2_2026-11-1Q_anomalia.pdf"), 1, HOJE)
    assert le.acionar == ["R95-04"]
    assert _linha(conn, "B2", "R95-04").status == agenda.GATILHO
    ev.registrar(conn, le, "FIR_B2_2026-11-1Q_anomalia.pdf")

    ise = _linha(conn, "B2", "R95-04")
    assert ise.status == agenda.ATRASADA and ise.vence == "2026-11-05"
    assert ise.nota == "acionada em 04/11/2026 por FIR_B2_2026-11-1Q_anomalia.pdf: aguardando relatório de ISE"
    # viagem no tempo: antes do fato não há nada; no próprio dia, vence logo
    antes = {l.codigo: l for l in torre.painel(conn, 1, date(2026, 11, 3), DESDE, ativo="B2")}["R95-04"]
    no_dia = {l.codigo: l for l in torre.painel(conn, 1, date(2026, 11, 4), DESDE, ativo="B2")}["R95-04"]
    assert antes.status == agenda.GATILHO and no_dia.status == agenda.VENCE_LOGO

    rel = ev.ler(conn, _pdf("Relatorio_ISE_B2_2026-11-06.pdf"), 1, HOJE)
    assert (rel.documento, rel.obrigacao, rel.periodo) == ("ISE", "R95-04", "2026-11-06") and not rel.acionar
    ev.registrar(conn, rel, "Relatorio_ISE_B2_2026-11-06.pdf")
    assert _linha(conn, "B2", "R95-04").status == agenda.GATILHO


def test_na_res220_a_anomalia_abre_o_registro_no_sigbm_e_a_ise(conn):
    """Res. 220: EC3 = 5 abre a OB-18 (SIGBM em 24 h, art. 38 §4) e a OB-19 (ISE, art. 42).
    O recibo do EIE encerra só a OB-18; a ISE continua aberta até o relatório."""
    le = ev.ler(conn, _pdf("FIR_B2_2027-08-1Q_Res220_EC3.pdf"), 1, DIA_220)
    assert le.acionar == ["OB-18", "OB-19"]
    ev.registrar(conn, le, "FIR_B2_2027-08-1Q_Res220_EC3.pdf")
    depois = {l.codigo: l for l in torre.painel(conn, 1, date(2027, 8, 5), DESDE, ativo="B2")}
    assert depois["OB-18"].status == depois["OB-19"].status == agenda.ATRASADA
    assert "aguardando registro no SIGBM" in depois["OB-18"].nota

    eie = ev.ler(conn, _pdf("EIE_B2_2027-08-02_recibo_SIGBM.pdf"), 1, DIA_220)
    assert (eie.obrigacao, eie.periodo) == ("OB-18", "2027-08-02") and not eie.avisos
    ev.registrar(conn, eie, "EIE_B2_2027-08-02_recibo_SIGBM.pdf")
    depois = {l.codigo: l for l in torre.painel(conn, 1, date(2027, 8, 5), DESDE, ativo="B2")}
    assert depois["OB-18"].status == agenda.GATILHO and depois["OB-19"].status == agenda.ATRASADA


def test_ise_aberta_vai_para_o_calendario_e_o_boletim(conn):
    """Quem só recebe o .ics ou o boletim também vê a ISE aberta, com o motivo."""
    ev.registrar(conn, ev.ler(conn, _pdf("FIR_B2_2026-11-1Q_anomalia.pdf"), 1, HOJE),
                 "FIR_B2_2026-11-1Q_anomalia.pdf")
    ics = torre.calendario(conn, 1, HOJE, DESDE).replace("\r\n ", "")
    evento = ics.split("UID:B2-R95-04-vence-20261105")[1].split("END:VEVENT")[0]
    assert "SUMMARY:ATRASADA · B2" in evento and "Acionada em 04/11/2026" in evento
    b = torre.boletim(conn, 1, HOJE, DESDE)
    atrasadas = b.split("## 🔴")[1].split("##")[0]
    assert ("**B2** · Realizar ISE" in atrasadas
            and "venceu em 05/11/2026; acionada em 04/11/2026 por FIR_B2_2026-11-1Q_anomalia.pdf" in atrasadas)


def test_citacao_da_res220_nao_repete_a_norma(conn):
    assert torre.dispositivo("Res. ANM 220/2025", "Res. ANM 220/2025 art. 42") == "Res. ANM 220/2025 art. 42"
    assert torre.dispositivo("Res. ANM 95/2022", "art. 27") == "Res. ANM 95/2022, art. 27"
    ics = torre.calendario(conn, 1, HOJE, DESDE, dias=365 * 4).replace("\r\n ", "").replace(r"\,", ",")
    b = torre.boletim(conn, 1, date(2027, 8, 10), DESDE)
    for texto in (ics, b):
        assert "Res. ANM 220/2025, Res. ANM 220/2025" not in texto
    assert "Res. ANM 220/2025 art." in ics


def test_diz_por_que_nao_achou_o_ativo(conn):
    """Quem mandou o documento precisa saber o que corrigir: código desconhecido ou dois ativos."""
    desconhecido = ev.ler(conn, "Ficha de Inspeção Regular da barragem (B9). Data de inspeção: 05/11/2026", 1, HOJE)
    assert desconhecido.problemas[0].startswith("o documento cita B9, que não é ativo cadastrado")
    rotulado = ev.ler(conn, "Ficha de Inspeção Regular. Barragem B9. Data de inspeção: 05/11/2026", 1, HOJE)
    assert rotulado.problemas[0].startswith("o documento cita B9, que não é ativo cadastrado")
    nada = ev.ler(conn, "Ficha de Inspeção Regular. Data de inspeção: 05/11/2026", 1, HOJE)
    assert '"Ativo: B3"' in nada.problemas[0]
    dois = ev.ler(conn, "Ficha de Inspeção Regular (B1) e (B2). Data de inspeção: 05/11/2026", 1, HOJE)
    assert dois.problemas[0] == "o documento cita mais de um ativo (B1, B2): não dá para saber de qual é"
    assert not desconhecido.completa and not dois.completa


def test_pdf_que_nao_abre_vira_frase_para_o_operador():
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter

    original = PdfReader(str(ev.exemplo("FIR_B3_2026-10-1Q.pdf")))

    def cifrado(senha_de_leitura: str) -> bytes:
        w = PdfWriter()
        for p in original.pages:
            w.add_page(p)
        w.encrypt(user_password=senha_de_leitura, owner_password="dono")
        b = BytesIO()
        w.write(b)
        return b.getvalue()

    # só a senha do dono (impede editar/imprimir): abre normalmente
    assert "FICHA DE INSPE" in ev.texto_pdf(cifrado(""))
    for conteudo, esperado in [(cifrado("segredo"), "protegido por senha"),
                               (b"isto nao e pdf", "não parece um PDF válido")]:
        with pytest.raises(Exception) as erro:
            ev.texto_pdf(conteudo)
        frase = ev.por_que_nao_abre(erro.value)
        assert esperado in frase and "Error" not in frase


@pytest.mark.parametrize("texto, esperado", [
    ("Data da inspeção: 03/11/2026", date(2026, 11, 3)),
    ("Data da inspeção: 3 de novembro de 2026", date(2026, 11, 3)),
    ("Data da inspeção: 1º de novembro de 2026", date(2026, 11, 1)),
    ("Data da inspeção: 03.11.2026", date(2026, 11, 3)),
    ("Data da inspeção: 03-11-2026", date(2026, 11, 3)),
    ("Inspeção realizada em 03/11/2026. Próxima inspeção: 18/11/2026", date(2026, 11, 3)),
    ("Data de inspeção 03/11/2026 Emitido em 04/11/2026", date(2026, 11, 3)),
    ("Vistoria em 3/11/2026", date(2026, 11, 3)),
    ("Data da inspeção: 3/11/26", None),              # ano com 2 dígitos: ambíguo, não adivinha
    ("Data da inspeção: 31/02/2026", None),           # data impossível: não quebra, só não lê
    ("Inspeção em 03/11/2026, retorno em 18/11/2026", None),   # duas datas sem rótulo: não escolhe
])
def test_data_do_documento_em_varios_formatos(texto, esperado):
    assert ev._data(texto) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("Barragem Córrego Fundo (B3)", ["B3"]),
    ("BARRAGEM CORREGO FUNDO", ["B3"]),
    ("Córrego Fundo", ["B3"]),                        # nome sem o tipo
    ("Barragem B3", ["B3"]),                          # código depois de rótulo
    ("Ativo: B3", ["B3"]),
    ("Código da barragem: B3", ["B3"]),
    ("Serra I", ["B1"]),
    ("Serra II", ["B2"]),                             # "Serra I" não casa "Serra II"
    ("Vaso VP-101", ["E1"]),                          # tag do equipamento
    ("VP-1010", []),                                  # tag maior não é a mesma
    ("Relatório EC1 = 5, B3 ok", []),                 # código solto, sem rótulo: não adivinha
    ("Serra Azul", []),                               # nome da empresa não é ativo
    ("Ativo: B1 e Ativo: B2", ["B1", "B2"]),          # dois ativos continuam sendo dois
])
def test_jeitos_de_citar_o_ativo(conn, texto, esperado):
    assert ev._ativos_citados(ev.normalizar(texto), db.ativos(conn, 1)) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("EC3 = 5", {"EC3": 5}),
    ("EC 3 = 5", {"EC3": 5}),
    ("EC-3 = 5", {"EC3": 5}),
    ("EC3: 5", {"EC3": 5}),
    ("Estado de Conservação EC3 (5)", {"EC3": 5}),
    ("EC1=0 EC2=5 EC3=0", {"EC1": 0, "EC2": 5, "EC3": 0}),
    ("conforme o art. 38 §2, sec3: 5", {}),           # "ec" dentro de outra palavra não conta
])
def test_colunas_de_estado_de_conservacao_em_varios_formatos(texto, esperado):
    """Ler menos do que está escrito aqui é perder uma ISE obrigatória."""
    assert ev._estado_conservacao(ev.normalizar(texto)) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("Pontuação máxima: 10", 10),
    ("Pontuação máxima obtida = 10", 10),
    ("Maior pontuação: 10", 10),
    ("Pontuação total: 6; pontuação máxima: 10", 10),
    ("pontuação 6 na anomalia do talude", None),      # sem "máxima"/"maior": não é a do documento
])
def test_pontuacao_maxima_em_varios_formatos(texto, esperado):
    assert ev._pontuacao(ev.normalizar(texto)) == esperado


def test_ec_escrito_com_espaco_ainda_abre_a_ise(conn):
    """A mesma FIR da Res. 220 com "EC 3 = 5" no lugar de "EC3 = 5": a ISE tem de abrir igual."""
    texto = _pdf("FIR_B2_2027-08-1Q_Res220_EC3.pdf").replace("EC3 = 5", "EC 3 = 5")
    assert "EC 3 = 5" in texto
    le = ev.ler(conn, texto, 1, DIA_220)
    assert le.estado_conservacao["EC3"] == 5 and len(le.gatilhos) == 1 and "art. 42" in le.gatilhos[0]
