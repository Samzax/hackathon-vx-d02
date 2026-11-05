"""Todo trecho citado no cadastro existe, palavra por palavra, no texto oficial da norma.

Os textos oficiais ficam em data/raw/normas (fora do Git): sem eles, o teste é pulado.
"""

import csv
from pathlib import Path

import pytest

from regulaia import normas
from regulaia.impacto import _limpo

RAIZ = Path(__file__).resolve().parent.parent
NORMAS = RAIZ / "data" / "raw" / "normas"
NR22 = "nr-22-atualizada-2026.pdf"

FONTES = {
    "seed_obligations.csv": ["res220_2025.html"],
    "cadastro/res95_2022.csv": ["res95_2022.html"],
    "cadastro/nr13.csv": ["nr-13-atualizada-2023-b.pdf"],
    "cadastro/nr22.csv": [NR22],
    "cadastro/nr22_zas.csv": [NR22,
                              "portaria-mte-no-105-altera-a-nr-22-anexo-iii-nr-09-e-aprova-o-anexo-v-poeiras-minerais-ii.pdf",
                              "portaria-mte-no-261-ajusta-port-105_26-que-altera-a-nr-22.pdf"],
}


def _paragrafos(nome: str) -> list[str]:
    caminho = NORMAS / nome
    if not caminho.exists():
        pytest.skip(f"{nome} não baixado")
    return normas.paragrafos_anmlegis(caminho) if nome.endswith(".html") else normas.paragrafos_pdf_nr(caminho)


@pytest.mark.parametrize("cadastro", sorted(FONTES))
def test_trecho_existe_no_texto_oficial(cadastro):
    with open(RAIZ / cadastro, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert all(l["trecho"].strip() for l in linhas), "obrigação sem trecho"
    texto = _limpo(" ".join(p for nome in FONTES[cadastro] for p in _paragrafos(nome)))
    fora = [l["id"] for l in linhas if _limpo(l["trecho"]) not in texto]
    assert not fora, fora


def test_toda_fonte_tem_url_oficial():
    """Quem clona o repositório baixa os textos com `uv run python -m regulaia.fontes`."""
    from regulaia import fontes

    usados = {nome for nomes in FONTES.values() for nome in nomes}
    assert usados <= set(fontes.FONTES)
    assert all(url.startswith("https://") for _, url in fontes.FONTES.values())
