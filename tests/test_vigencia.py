"""Vigência e alterações das normas federais pela ficha da Câmara (regulaia/vigencia.py).

As páginas vêm de cópias reais em tests/fixtures/vigencia: o resolvedor de URN do LexML para a
Lei 12.334/2010 e o Decreto 62.934/1968 (revogado pelo Decreto 9.406/2018), as fichas da Câmara e o
texto atualizado da Lei 12.334 (já com a Lei 15.355/2026). Nada sai para a rede.
"""

from pathlib import Path

import pytest

from regulaia import db, demo
from regulaia import descoberta as d
from regulaia import vigencia as v

FIX = Path(__file__).parent / "fixtures" / "vigencia"
CAMARA = "https://www2.camara.leg.br/legin/fed/"
FICHA_12334 = CAMARA + "lei/2010/lei-12334-20-setembro-2010-608607-norma-pl.html"
TEXTO_12334 = CAMARA + "lei/2010/lei-12334-20-setembro-2010-608607-normaatualizada-pl.html"
FICHA_62934 = CAMARA + "decret/1960-1969/decreto-62934-2-julho-1968-404797-norma-pe.html"

PAGINAS = {
    v.LEXML + "urn:lex:br:federal:lei:2010;12334": "lexml_lei_12334.html",
    v.LEXML + "urn:lex:br:federal:decreto:1968;62934": "lexml_dec_62934.html",
    FICHA_12334: "camara_lei_12334_ficha.html",
    TEXTO_12334: "camara_lei_12334_atualizada.html",
    FICHA_62934: "camara_dec_62934_ficha.html",
}


class BaixadorFixo(v.Baixador):
    def __init__(self, paginas=PAGINAS):
        super().__init__(cache=Path("nao-usado"))
        self.paginas = dict(paginas)
        self.pedidos: list[str] = []

    def get(self, url):
        self.pedidos.append(url)
        if url not in self.paginas:
            raise v.ErroVigencia(f"{url}: HTTP 404")
        p = self.paginas[url]
        return p if p.startswith("<") else (FIX / p).read_text(encoding="utf-8")


def _ler(nome):
    return (FIX / nome).read_text(encoding="utf-8")


@pytest.fixture
def serra():
    conn = db.conectar(":memory:")
    demo.montar(conn, com_historico=False)
    return conn


# ------------------------------------------------------------------- endereços e leitura


@pytest.mark.parametrize("chave, esperado", [
    ("BR:LEI:12334/2010", "urn:lex:br:federal:lei:2010;12334"),
    ("BR:LCP:140/2011", "urn:lex:br:federal:lei.complementar:2011;140"),
    ("BR:DEL:227/1967", "urn:lex:br:federal:decreto.lei:1967;227"),
    ("BR:DEC:9406/2018", "urn:lex:br:federal:decreto:2018;9406"),
])
def test_urn_do_lexml_a_partir_da_chave_da_descoberta(chave, esperado):
    assert v.urn(chave) == esperado and v.suportada(chave)


@pytest.mark.parametrize("chave", ["BR:RES-ANM:95/2022", "MG:LEI:23291/2019", "lixo"])
def test_resolucao_da_anm_e_norma_estadual_nao_vao_para_a_camara(chave):
    assert not v.suportada(chave)
    with pytest.raises(v.ErroVigencia):
        v.urn(chave)


def test_lexml_aponta_a_ficha_da_camara_em_https_e_dominio_novo():
    assert v.ficha_no_lexml(_ler("lexml_lei_12334.html")) == FICHA_12334
    assert v.ficha_no_lexml(_ler("lexml_dec_62934.html")) == FICHA_62934
    assert v.ficha_no_lexml("<html><a href='https://outro.gov.br/x'>x</a></html>") is None


def test_ficha_da_lei_12334_traz_situacao_texto_atualizado_e_quem_alterou():
    f = v.ler_ficha(_ler("camara_lei_12334_ficha.html"), FICHA_12334, "BR:LEI:12334/2010")
    assert f.titulo == "LEI Nº 12.334, DE 20 DE SETEMBRO DE 2010"
    assert f.ementa.startswith("Estabelece a Política Nacional de Segurança de Barragens")
    assert f.situacao == "Não consta revogação expressa" and not f.revogada and f.revogada_por == []
    assert f.texto_url == TEXTO_12334
    assert f.original_url.endswith("-publicacaooriginal-129691-pl.html")
    nova = f.relacoes[0]
    assert (nova.chave, nova.data, nova.relacao, nova.artigos) == ("BR:LEI:15355/2026", "2026-03-11", "Alteração", ["3", "15"])
    assert nova.url == CAMARA + "lei/2026/lei-15355-11-marco-2026-798799-norma-pl.html"
    assert nova.muda_texto
    por_relacao = {(r.chave, r.relacao): r for r in f.relacoes}
    assert not por_relacao[("BR:DEC:11310/2022", "Regulamentação")].muda_texto
    assert por_relacao[("BR:LEI:14066/2020", "Acréscimo de Artigo")].artigos == ["2-A", "18-A", "18-B", "18-C"]


def test_ficha_do_decreto_62934_diz_revogado_e_por_quem():
    f = v.ler_ficha(_ler("camara_dec_62934_ficha.html"), FICHA_62934, "BR:DEC:62934/1968")
    assert f.revogada and f.situacao == "Revogada"
    assert [r.chave for r in f.revogada_por] == ["BR:DEC:9406/2018"]


def test_pagina_que_nao_e_ficha_e_erro_claro():
    with pytest.raises(v.ErroVigencia, match="não é uma ficha"):
        v.ler_ficha("<html><body>manutenção</body></html>", "https://x")


@pytest.mark.parametrize("texto, esperado", [
    ('Art. 3º, "caput", inciso I ; Art. 15, "caput", inciso VI', ["3", "15"]),
    ('Art. 2º-A, "caput", §§ 1º, 2º ; Art. 18-C', ["2-A", "18-C"]),
    ("art. 17, XXI", ["17"]),
    ("art. 2º-A, §2º", ["2-A"]),
    ("Capítulo V-A", []),
])
def test_artigos_citados(texto, esperado):
    assert v.artigos(texto) == esperado


def test_texto_atualizado_sem_as_notas_de_redacao():
    ps = v.paragrafos_do_texto(_ler("camara_lei_12334_atualizada.html"))
    inciso = next(p for p in ps if p.startswith("I - garantir a observância de padrões de segurança de barragens"))
    assert "afetem vidas humanas, animais e o meio ambiente;" in inciso
    assert "15.355" not in inciso and "Redação" not in inciso


# ------------------------------------------------------------------- o catálogo


def test_catalogo_confere_os_23_trechos_da_lei_12334_no_texto_de_2026(serra):
    [r] = v.revisar_catalogo(serra, BaixadorFixo())
    assert r.norma == "Lei 12.334/2010 (PNSB)" and r.chave == "BR:LEI:12334/2010"
    assert not r.revogada and r.erro is None
    assert r.trechos_conferidos == 23 and r.trechos_fora == [] and not r.precisa_curadoria
    recente = r.alteracoes[0]
    assert recente.chave == "BR:LEI:15355/2026" and recente.afeta == []   # art. 3º e 15 não estão no catálogo
    acrescimo = next(a for a in r.alteracoes if a.relacao == "Acréscimo de Artigo")
    assert acrescimo.afeta    # os art. 2º-A, 18-A e 18-C que a Lei 14.066 acrescentou estão no catálogo
    assert all(a.relacao != "Regulamentação" for a in r.alteracoes)
    guardada = v.lida(serra, "BR:LEI:12334/2010")
    assert guardada.texto_url == TEXTO_12334 and guardada.relacoes[0].chave == "BR:LEI:15355/2026"


def test_trecho_que_mudou_no_texto_atualizado_vai_para_a_curadoria(serra):
    serra.execute(
        "UPDATE obrigacao_versao SET trecho = 'texto que a lei não tem mais' WHERE status = 'vigente' AND obrigacao_id ="
        " (SELECT id FROM obrigacao WHERE codigo = 'L12-01')")
    [r] = v.revisar_catalogo(serra, BaixadorFixo())
    assert r.trechos_fora == ["L12-01"] and r.precisa_curadoria


def test_falha_na_camara_vira_pendencia_visivel(serra):
    [r] = v.revisar_catalogo(serra, BaixadorFixo({}))
    assert r.erro and "404" in r.erro and r.precisa_curadoria


# ------------------------------------------------------------------- a descoberta


def _candidata(conn, chave, status, titulo):
    c = d.Candidata(chave=chave, jurisdicao="BR", fonte="senado", tipo=chave.split(":")[1],
                    numero=chave.split(":")[2].split("/")[0], ano=int(chave[-4:]), titulo=titulo,
                    ementa="Aprova o Regulamento do Código de Mineração.", indexacao="", data=None, url="", situacao="")
    d.guardar(conn, [c])
    conn.execute("UPDATE norma_candidata SET status = ? WHERE chave = ?", (status, chave))
    conn.commit()


def test_candidata_revogada_sai_da_fila_com_a_fonte_na_nota(serra):
    _candidata(serra, "BR:DEC:62934/1968", "relevante", "Decreto 62.934/1968")
    _candidata(serra, "BR:LEI:12334/2010", "relevante", "Lei 12.334/2010")
    res = v.marcar_candidatas(serra, BaixadorFixo())
    assert (res.lidas, res.revogadas, res.descartadas, res.erros) == (2, 1, 1, {})
    r = serra.execute("SELECT * FROM norma_candidata WHERE chave = 'BR:DEC:62934/1968'").fetchone()
    assert r["status"] == "descartada" and r["decidida_por"] == "vigência (Câmara dos Deputados)"
    assert "Decreto nº 9406 de 12 de Junho de 2018" in r["nota"] and FICHA_62934 in r["nota"]
    assert r["situacao"].startswith("Revogada")
    viva = serra.execute("SELECT status FROM norma_candidata WHERE chave = 'BR:LEI:12334/2010'").fetchone()
    assert viva["status"] == "relevante"
    # já lidas não são pedidas de novo
    b = BaixadorFixo()
    assert v.marcar_candidatas(serra, b).lidas == 0 and b.pedidos == []


def test_aprovada_e_revogada_fica_para_a_curadoria_rever(serra):
    _candidata(serra, "BR:DEC:62934/1968", "aprovada", "Decreto 62.934/1968")
    res = v.marcar_candidatas(serra, BaixadorFixo())
    assert res.aprovadas_revogadas == ["BR:DEC:62934/1968"] and res.descartadas == 0
    assert serra.execute("SELECT status FROM norma_candidata").fetchone()["status"] == "aprovada"


def test_erro_numa_candidata_nao_para_as_outras(serra):
    _candidata(serra, "BR:LEI:99999/2020", "relevante", "Lei inexistente")
    _candidata(serra, "BR:DEC:62934/1968", "relevante", "Decreto 62.934/1968")
    res = v.marcar_candidatas(serra, BaixadorFixo())
    assert list(res.erros) == ["BR:LEI:99999/2020"] and res.revogadas == 1


def test_texto_atualizado_para_a_segunda_leitura(serra):
    t = v.texto_atualizado(serra, BaixadorFixo(), "BR:LEI:12334/2010")
    assert "Art. 1º Esta Lei estabelece a Política Nacional de Segurança de Barragens" in t
    assert v.texto_atualizado(serra, BaixadorFixo(), "MG:LEI:23291/2019") is None


def test_baixador_respeita_o_intervalo_do_lexml(tmp_path, monkeypatch):
    dormiu = []
    monkeypatch.setattr(v.time, "sleep", dormiu.append)

    class Resposta:
        status_code = 200
        text = "<html>ok</html>"

    class Http:
        def get(self, url):
            return Resposta()

    b = v.Baixador(cache=tmp_path, http=Http())
    b.get(v.LEXML + "urn:a")
    b.get(v.LEXML + "urn:b")
    b.get(v.LEXML + "urn:a")                  # do cache: não espera nem pede
    assert len(dormiu) == 1 and 4 < dormiu[0] <= 5


# ------------------------------------------------------------------- o Senado, quando a Câmara não tem a ficha

SENADO_10966 = v.SENADO_DETALHE.format(id="35488354")


def test_detalhe_do_senado_diz_revogado_e_por_quem():
    f = v.ler_senado_detalhe(_ler("senado_dec_10966.xml"), "BR:DEC:10966/2022", "https://legis.senado.leg.br/norma/35488354")
    assert f.revogada and f.situacao == "Revogada" and f.fonte == v.FONTE_SENADO
    assert [(r.chave, r.data, r.relacao) for r in f.revogada_por] == [("BR:DEC:11369/2023", "2023-01-01", "Revogação")]
    assert f.texto_url is None
    assert f.ementa.startswith("Institui o Programa de Apoio ao Desenvolvimento da Mineração Artesanal")


def test_detalhe_do_senado_da_lei_12334_bate_com_a_camara():
    f = v.ler_senado_detalhe(_ler("senado_lei_12334.xml"), "BR:LEI:12334/2010")
    assert not f.revogada
    assert (f.relacoes[0].chave, f.relacoes[0].relacao, f.relacoes[0].artigos) == ("BR:LEI:15355/2026", "Alteração", ["3", "15"])
    assert {r.relacao for r in f.relacoes} >= {"Alteração", "Regulamentação"}
    assert "2-A" in next(r for r in f.relacoes if r.chave == "BR:LEI:14066/2020").artigos


def test_sem_ficha_na_camara_o_lexml_leva_ao_senado(serra):
    paginas = {v.LEXML + "urn:lex:br:federal:decreto:2022;10966": "lexml_dec_10966.html",
               SENADO_10966: "senado_dec_10966.xml"}
    assert v.ficha_no_lexml(_ler("lexml_dec_10966.html")) is None
    assert v.senado_no_lexml(_ler("lexml_dec_10966.html")) == "35488354"
    _candidata(serra, "BR:DEC:10966/2022", "relevante", "Decreto 10.966/2022")
    res = v.marcar_candidatas(serra, BaixadorFixo(paginas))
    assert (res.lidas, res.descartadas, res.erros) == (1, 1, {})
    r = serra.execute("SELECT nota FROM norma_candidata WHERE chave = 'BR:DEC:10966/2022'").fetchone()
    assert "Decreto nº 11.369 de 01/01/2023" in r["nota"] and "legis.senado.leg.br/norma/35488354" in r["nota"]
    assert v.lida(serra, "BR:DEC:10966/2022").fonte == v.FONTE_SENADO
