import pytest

from regulaia.regras import RegraInvalida, aplica, faltantes, validar

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


@pytest.mark.parametrize("regra", ["", "dpa2 >", "DPA = alto", "dpa2 > 4 ou x"])
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
