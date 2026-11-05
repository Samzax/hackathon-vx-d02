"""O cadastro é reproduzível: extração da IA (versionada) + escolhas da pessoa = o CSV do cadastro."""

import csv
import json
from pathlib import Path

import pytest

from regulaia import curadoria

RAIZ = Path(__file__).resolve().parent.parent

CASOS = [   # extração, escolhas, cadastro, norma, tipo de ativo, vigência
    ("res95_2022", "res95_2022", "res95_2022", "Res. ANM 95/2022", "barragem", "2022-02-07", "2027-08-01"),
    ("nr13", "nr13", "nr13", "NR-13", "equipamento", "", None),
    ("nr22", "nr22", "nr22", "NR-22", "unidade", "", None),
]


@pytest.mark.parametrize("extracao, escolhas, cadastro, norma, tipo, desde, ate", CASOS, ids=[c[0] for c in CASOS])
def test_curadoria_regera_o_cadastro(extracao, escolhas, cadastro, norma, tipo, desde, ate):
    ext = json.loads((RAIZ / "data" / "extraido" / f"{extracao}.json").read_text(encoding="utf-8"))
    with open(RAIZ / "curadoria" / f"{escolhas}.csv", encoding="utf-8", newline="") as f:
        linhas = curadoria.montar(ext, list(csv.DictReader(f)), norma, tipo, desde, ate)
    with open(RAIZ / "cadastro" / f"{cadastro}.csv", encoding="utf-8", newline="") as f:
        esperado = list(csv.DictReader(f))
    gerado = [{k: ("" if v is None else str(v)) for k, v in l.items()} for l in linhas]
    assert gerado == esperado
