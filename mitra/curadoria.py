"""Curadoria: da extração da IA (JSON) para o cadastro (CSV), com escolhas de uma pessoa.

A IA propõe dezenas de obrigações por norma; a pessoa escolhe as que entram e
completa o que a máquina precisa (a agenda, às vezes a regra). Escolhas ficam
num CSV pequeno e versionado, então o cadastro é reproduzível:

  curadoria/res95_2022.csv  ->  cadastro/res95_2022.csv

Colunas das escolhas:
  codigo, artigo, titulo_contem (desempata quando o artigo tem mais de uma), agenda
  opcionais (substituem o que a IA propôs): titulo, aplica_se_a, regra, periodicidade,
  prazo, area, evidencia, responsavel
Comuns a todas as linhas, na linha de comando: norma, tipo_ativo, vigencia_desde, vigencia_ate.

Uso:
  uv run python -m mitra.curadoria data/extraido/res95_2022.json curadoria/res95_2022.csv \
      cadastro/res95_2022.csv "Res. ANM 95/2022" barragem 2022-02-07 2027-08-01
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from . import agenda, regras
from .triagem import normalizar

SAIDA = ["id", "tipo_ativo", "norma", "area", "artigo", "obrigacao", "aplica_se_a", "regra",
         "periodicidade", "agenda", "prazo", "vigencia_desde", "vigencia_ate",
         "responsavel_ficticio", "evidencia", "fonte", "trecho"]


class EscolhaInvalida(ValueError):
    pass


def _achar(propostas: list[dict], artigo: str, contem: str) -> dict:
    achadas = [p for p in propostas if p["reprovada"] is None
               and normalizar(p["artigo"]) == normalizar(artigo)
               and normalizar(contem) in normalizar(p["titulo"])]
    if len(achadas) != 1:
        raise EscolhaInvalida(f"{artigo!r} / {contem!r}: {len(achadas)} propostas encontradas")
    return achadas[0]


def montar(extracao: dict, escolhas: list[dict], norma: str, tipo: str,
           desde: str, ate: str | None) -> list[dict]:
    out = []
    for e in escolhas:
        p = _achar(extracao["propostas"], e["artigo"], e.get("titulo_contem") or "")
        def campo(nome, padrao=None, e=e):
            return (e.get(nome) or "").strip() or padrao
        linha = {
            "id": e["codigo"], "tipo_ativo": tipo, "norma": norma,
            "area": campo("area", p["area"]), "artigo": p["artigo"],
            "obrigacao": campo("titulo", p["titulo"]), "aplica_se_a": campo("aplica_se_a", p["aplica_se_a"]),
            "regra": campo("regra", p["regra"]), "periodicidade": campo("periodicidade", p["periodicidade"]),
            "agenda": e["agenda"], "prazo": campo("prazo", p["prazo"]),
            "vigencia_desde": desde, "vigencia_ate": ate or "",
            "responsavel_ficticio": campo("responsavel", ""), "evidencia": campo("evidencia", p["evidencia"]),
            "fonte": f"{norma} {p['artigo']}", "trecho": p["trecho"],
        }
        regras.validar(linha["regra"])
        agenda.validar(linha["agenda"])
        out.append(linha)
    codigos = [l["id"] for l in out]
    if len(set(codigos)) != len(codigos):
        raise EscolhaInvalida("código repetido nas escolhas")
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 6:
        print(__doc__)
        return 2
    origem, escolhas_csv, destino, norma, tipo, desde = argv[:6]
    ate = argv[6] if len(argv) > 6 else None
    desde = "" if desde == "-" else desde
    extracao = json.loads(Path(origem).read_text(encoding="utf-8"))
    with open(escolhas_csv, encoding="utf-8", newline="") as f:
        escolhas = list(csv.DictReader(f))
    linhas = montar(extracao, escolhas, norma, tipo, desde, ate)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, SAIDA, lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    print(f"{len(linhas)} obrigações de {len(extracao['propostas'])} propostas -> {destino}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
