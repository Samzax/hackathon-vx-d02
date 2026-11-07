"""Textos oficiais das normas do cadastro: de onde vêm e como baixar.

Uso: uv run python -m regulaia.fontes [--forcar]

Salva em data/raw/normas/ (fora do Git). Arquivo que já existe não é baixado de novo.
Com os textos baixados, tests/test_trechos.py confere cada trecho citado no cadastro.
O ANMlegis serve as páginas em cp1252 sem dizer; todas são gravadas em UTF-8.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .db import ROOT

DESTINO = ROOT / "data" / "raw" / "normas"
_ANMLEGIS = ("https://anmlegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&link=S&tipo=RES"
             "&numeroAto={numero:08d}&seqAto=000&valorAno={ano}&orgao=ANM%2FMME&cod_modulo=566&cod_menu=8303")
_MTE = "https://www.gov.br/trabalho-e-emprego/pt-br"
_NRS = _MTE + ("/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/"
               "comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes/")
_PORTARIAS = _MTE + "/assuntos/inspecao-do-trabalho/seguranca-e-saude-no-trabalho/sst-portarias/2026-1/"

# arquivo local -> (norma, URL oficial)
FONTES: dict[str, tuple[str, str]] = {
    "res95_2022.html": ("Res. ANM 95/2022 (texto consolidado)", _ANMLEGIS.format(numero=95, ano=2022)),
    "res220_2025.html": ("Res. ANM 220/2025 (texto consolidado, com a Res. 245/2026)", _ANMLEGIS.format(numero=220, ano=2025)),
    # O Planalto derruba conexões que não vêm de navegador; a Câmara serve o mesmo texto consolidado, com as
    # notas de redação (regulaia/vigencia.py tira as notas e o que está riscado antes de conferir)
    "lei_12334_2010_camara.html": ("Lei 12.334/2010 (PNSB, texto atualizado da Câmara, com a Lei 15.355/2026)",
                                   "https://www2.camara.leg.br/legin/fed/lei/2010/"
                                   "lei-12334-20-setembro-2010-608607-normaatualizada-pl.html"),
    "lei_mg_23291_2019.html": ("Lei MG 23.291/2019 (política estadual de segurança de barragens, texto atualizado)",
                               "https://www.almg.gov.br/legislacao-mineira/texto/LEI/23291/2019/"),
    "dec_mg_48078_2020.html": ("Decreto MG 48.078/2020 (PAE, texto atualizado)",
                               "https://www.almg.gov.br/legislacao-mineira/texto/DEC/48078/2020/"),
    "dec_mg_48140_2021.html": ("Decreto MG 48.140/2021 (regulamenta a Lei 23.291, texto atualizado)",
                               "https://www.almg.gov.br/legislacao-mineira/texto/DEC/48140/2021/"),
    "nr-13-atualizada-2023-b.pdf": ("NR-13", _NRS + "nr-13-atualizada-2023-b.pdf"),
    "nr-22-atualizada-2026.pdf": ("NR-22", _NRS + "nr-22-atualizada-2026.pdf"),
    "portaria-mte-no-105-altera-a-nr-22-anexo-iii-nr-09-e-aprova-o-anexo-v-poeiras-minerais-ii.pdf": (
        "Portaria MTE 105/2026 (altera a NR-22)",
        _PORTARIAS + "portaria-mte-no-105-altera-a-nr-22-anexo-iii-nr-09-e-aprova-o-anexo-v-poeiras-minerais-ii.pdf"),
    "portaria-mte-no-261-ajusta-port-105_26-que-altera-a-nr-22.pdf": (
        "Portaria MTE 261/2026 (ajusta a Portaria 105)",
        _PORTARIAS + "portaria-mte-no-261-ajusta-port-105_26-que-altera-a-nr-22.pdf/@@download/file"),
}


def baixar(forcar: bool = False, destino: Path = DESTINO) -> list[str]:
    import httpx

    destino.mkdir(parents=True, exist_ok=True)
    feitos = []
    with httpx.Client(follow_redirects=True, timeout=60, headers={"User-Agent": "RegulaIA/0.1"}) as http:
        for nome, (norma, url) in FONTES.items():
            alvo = destino / nome
            if alvo.exists() and not forcar:
                continue
            try:
                r = http.get(url)
                r.raise_for_status()
            except httpx.HTTPError as e:
                feitos.append(f"{nome}: FALHOU ({type(e).__name__}); abra {url} no navegador e salve em {alvo}")
                continue
            if nome.endswith(".html"):
                # o ANMlegis não declara o charset (é cp1252); quem declara (a ALMG, em UTF-8) é respeitado
                texto = r.text if "charset" in r.headers.get("content-type", "") else r.content.decode(
                    "cp1252", errors="replace")
                alvo.write_text(texto, encoding="utf-8")
            else:
                if not r.content.startswith(b"%PDF"):
                    raise ValueError(f"{url} não devolveu um PDF")
                alvo.write_bytes(r.content)
            feitos.append(f"{nome} ({norma})")
    return feitos


def main(argv: list[str]) -> int:
    feitos = baixar(forcar="--forcar" in argv)
    print("\n".join(feitos) if feitos else "Todos os textos já estavam em " + str(DESTINO))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
