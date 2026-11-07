"""Os campos do cadastro (regulaia/campos.py): conversão por tipo e a conferência da edição."""

from __future__ import annotations

import pytest

from regulaia import campos


def test_converter_numero_aceita_planilha_em_portugues():
    assert campos.converter("volume_m3", "2.980.000,5") == 2980000.5
    assert campos.converter("altura_m", "12") == 12
    assert campos.converter("dpa2", 9) == 9
    with pytest.raises(campos.ValorInvalido, match="não é número"):
        campos.converter("altura_m", "doze")
    with pytest.raises(campos.ValorInvalido, match="não é número"):
        campos.converter("dpa2", True)      # booleano não é número, mesmo sendo int em Python


def test_converter_booleano_opcoes_data_e_uf():
    assert campos.converter("trabalhadores_zas", "sim") is True
    assert campos.converter("trabalhadores_zas", "Não") is False
    assert campos.converter("trabalhadores_zas", False) is False
    with pytest.raises(campos.ValorInvalido, match="não é sim ou não"):
        campos.converter("trabalhadores_zas", "talvez")
    assert campos.converter("metodo_construtivo", "linha de centro") == "linha_de_centro"
    assert campos.converter("cri", "ALTO") == "alto"
    with pytest.raises(campos.ValorInvalido, match="não é uma das opções"):
        campos.converter("cri", "altíssimo")
    assert campos.converter("validade", "31/12/2027") == "2027-12-31"
    assert campos.converter("validade", "2027-12-31") == "2027-12-31"
    with pytest.raises(campos.ValorInvalido, match="não é data"):
        campos.converter("validade", "31/02/2027")
    assert campos.converter("uf", "mg") == "MG"
    with pytest.raises(campos.ValorInvalido, match="não é uma UF"):
        campos.converter("uf", "Minas")


def test_converter_vazio_e_none_ficam_de_fora():
    assert campos.converter("altura_m", "") is None
    assert campos.converter("altura_m", "   ") is None
    assert campos.converter("altura_m", None) is None


def test_conferir_estrito_recusa_campo_de_outro_tipo_e_junta_os_erros():
    with pytest.raises(campos.ValorInvalido) as e:
        campos.conferir("barragem", {"classe": "caldeira", "dpa2": "alto"})
    assert "não é campo do cadastro de barragem" in str(e.value) and "não é número" in str(e.value)
    ok = campos.conferir("barragem", {"dpa2": "9", "cri": "alto", "municipio": "Itabirito", "uf": "mg"})
    assert ok == {"dpa2": 9, "cri": "alto", "municipio": "Itabirito", "uf": "MG"}


def test_conferir_com_livres_deixa_passar_campo_fora_do_catalogo():
    ok = campos.conferir("barragem", {"nota_interna": "pilha ao lado", "dpa2": "9"}, livres=True)
    assert ok == {"nota_interna": "pilha ao lado", "dpa2": 9}
    with pytest.raises(campos.ValorInvalido):       # campo de outro tipo de ativo continua erro
        campos.conferir("barragem", {"classe": "caldeira"}, livres=True)


def test_do_tipo_e_pergunta():
    assert "lavra" in campos.do_tipo("unidade") and "lavra" not in campos.do_tipo("barragem")
    assert campos.pergunta("trabalhadores_zas") == "há trabalhadores na Zona de Autossalvamento?"
    assert campos.valor_legivel("linha_de_centro") == "linha de centro"
