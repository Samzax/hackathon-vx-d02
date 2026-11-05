"""Os números que a documentação e o roteiro da demo citam batem com o cadastro."""

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _linhas(caminho: Path) -> int:
    with open(caminho, encoding="utf-8", newline="") as f:
        return len(list(csv.DictReader(f)))


def test_numeros_do_cadastro_na_documentacao():
    res220 = _linhas(RAIZ / "seed_obligations.csv")
    total = res220 + sum(_linhas(p) for p in (RAIZ / "cadastro").glob("*.csv"))
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    roteiro = (RAIZ / "docs" / "ROTEIRO_DEMO.md").read_text(encoding="utf-8")
    arquitetura = (RAIZ / "docs" / "ARQUITETURA.md").read_text(encoding="utf-8")
    assert f"{total} obrigações cadastradas" in readme
    assert f"8 ativos e {total} obrigações" in roteiro
    assert f"Res. ANM 220/2025 (vale a partir de 2/8/2027) | {res220} |" in readme
    assert f"as {res220} da Res. 220/2025" in arquitetura
    assert f"Cada uma das {res220} obrigações" in arquitetura
    assert f"outras {res220 - 1} da Res. 220" in readme and f"outras {res220 - 1} da Res. 220" in roteiro


def test_numero_de_tipos_de_documento():
    from regulaia.evidencias import DOCUMENTOS

    tipos = len(DOCUMENTOS) + 1          # + exame interno do vaso, que sai do mesmo documento
    assert f"São {tipos} tipos de documento" in (RAIZ / "docs" / "ARQUITETURA.md").read_text(encoding="utf-8")
