"""Camada 0: a regra que lê norma e artigo citados decide quais obrigações vão para a IA.
Ler a menos manda a obrigação errada (ou nenhuma); ler a mais gasta IA à toa."""

import pytest

from mitra import triagem


@pytest.mark.parametrize("texto, normas", [
    ("Resolução ANM nº 95/2022", {"95"}),
    ("Resolução nº 95, de 7 de fevereiro de 2022", {"95"}),
    ("RESOLUÇÃO ANM Nº 220, DE 2025", {"220"}),
    ("Resolução DC/ANM nº 245", {"245"}),
    ("Res. ANM 95", {"95"}),
    ("Res. ANM nº 95", {"95"}),
    ("Res. ANM n.º 95/2022", {"95"}),
    ("Resolução ANM n.º 95", {"95"}),
    ("Res. 95/2022", {"95"}),
    ("Resolução ANM nº 95, de 2022, e Resolução ANM nº 130", {"95", "130"}),
    ("resoluções anteriores", set()),
    ("Resolução de Diretoria Colegiada", set()),
])
def test_norma_citada_em_varios_formatos(texto, normas):
    assert triagem.referencias(texto).normas == normas


@pytest.mark.parametrize("texto, artigos", [
    ("art. 27", {"27"}),
    ("art. 1º", {"1"}),
    ("artigo 27", {"27"}),
    ("arts. 17 e 18", {"17", "18"}),
    ("Arts. 17, 18 e 19", {"17", "18", "19"}),           # todos da lista, não só o primeiro
    ("os artigos 3 e 4 da Resolução", {"3", "4"}),
    ("art. 27, § 2º", {"27"}),                           # o parágrafo não vira artigo
    ("art. 87, III", {"87"}),
])
def test_artigos_citados_em_varios_formatos(texto, artigos):
    assert triagem.referencias(texto).artigos == artigos


def test_citar_o_artigo_por_extenso_soma_os_pontos_do_artigo():
    obrigacoes = [{"codigo": "X", "fonte": "Res. ANM 95/2022", "artigo": "art. 27", "titulo": "Inspeção especial",
                   "evidencia": "", "aplica_se_a": "barragem"}]
    curto, = triagem.candidatas("Altera o art. 27 da Res. ANM nº 95", obrigacoes)
    longo, = triagem.candidatas("Altera o artigo 27 da Resolução ANM n.º 95", obrigacoes)
    assert curto.pontos == longo.pontos == 9 and "cita o art. 27" in longo.motivos
