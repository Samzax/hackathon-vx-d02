import pytest

from mitra.regras import RegraInvalida, aplica, faltantes, validar

B_ALTO = {"dpa": "Alto", "dpa2": 6, "trabalhadores_zas": True, "mapa_inundacao_validado": False}
B_BAIXO = {"dpa": "baixo", "dpa2": 2, "trabalhadores_zas": False}


@pytest.mark.parametrize(
    "regra, attrs, esperado",
    [
        ("*", {}, True),
        ("trabalhadores_zas", B_ALTO, True),
        ("trabalhadores_zas", B_BAIXO, False),
        ("dpa = alto", B_ALTO, True),          # sem diferença de maiúsculas
        ("dpa = alto", B_BAIXO, False),
        ("dpa2 > 4", B_ALTO, True),
        ("dpa2 <= 4", B_BAIXO, True),
        ("dpa2 > 4 e mapa_inundacao_validado", B_ALTO, False),
        ("dpa2 > 4 e trabalhadores_zas", B_ALTO, True),
    ],
)
def test_aplica(regra, attrs, esperado):
    assert aplica(regra, attrs) is esperado


def test_atributo_ausente_nao_aplica_e_aparece_como_faltante():
    assert aplica("alteamento_continuo", B_ALTO) is False
    assert faltantes("alteamento_continuo", B_ALTO) == ["alteamento_continuo"]
    assert faltantes("dpa2 > 4", B_ALTO) == []


def test_comparar_numero_com_texto_e_erro_de_cadastro():
    with pytest.raises(RegraInvalida):
        aplica("dpa2 > 4", {"dpa2": "alto"})


@pytest.mark.parametrize("regra", ["", "dpa2 >", "DPA = alto", "dpa2 > 4 ou", "ou dpa = alto", "dpa2 > 4 ou x y"])
def test_regra_mal_escrita(regra):
    with pytest.raises(RegraInvalida):
        validar(regra)


def test_verdadeiro_e_falso_comparam_com_booleanos():
    assert aplica("inserida_pnsb = verdadeiro", {"inserida_pnsb": True})
    assert not aplica("inserida_pnsb = verdadeiro", {"inserida_pnsb": False})
    assert aplica("inserida_pnsb = falso e cri = alto", {"inserida_pnsb": False, "cri": "alto"})


def test_maior_menor_so_com_numero():
    with pytest.raises(RegraInvalida):
        validar("categoria_vaso <= II")


@pytest.mark.parametrize(
    "regra, attrs, esperado",
    [
        ("dpa = alto ou dpa2 >= 4", {"dpa": "medio", "dpa2": 4}, True),     # Res. 220, art. 20 §3
        ("dpa = alto ou dpa2 >= 4", {"dpa": "alto", "dpa2": 2}, True),
        ("dpa = alto ou dpa2 >= 4", {"dpa": "baixo", "dpa2": 2}, False),
        ("dpa2 >= 4 e trabalhadores_zas ou dpa = alto", {"dpa": "baixo", "dpa2": 6, "trabalhadores_zas": False}, False),
        ("dpa2 >= 4 e trabalhadores_zas ou dpa = alto", {"dpa": "alto", "dpa2": 2}, True),
    ],
)
def test_ou(regra, attrs, esperado):
    assert aplica(regra, attrs) is esperado


def test_dado_faltando_so_quando_decide():
    """Falta o DPA2: se o DPA já é alto, a obrigação vale; se é baixo, o DPA2 decide e aparece como faltante."""
    assert faltantes("dpa = alto ou dpa2 >= 4", {"dpa": "alto"}) == []
    assert faltantes("dpa = alto ou dpa2 >= 4", {"dpa": "baixo"}) == ["dpa2"]
    # com "e", uma condição conhecida e falsa já decide: o dado que falta não importa
    assert faltantes("dpa2 >= 4 e mapa_inundacao_validado", {"dpa2": 2}) == []
    assert faltantes("dpa2 >= 4 e mapa_inundacao_validado", {"dpa2": 6}) == ["mapa_inundacao_validado"]
