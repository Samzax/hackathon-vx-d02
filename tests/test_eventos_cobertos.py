"""O mapa de eventos regulatórios fecha o ciclo contra o falso negativo de dependência (o caso NR-3).

Dois lados, conferidos aqui: (1) todo evento declarado em temas.toml [eventos] acha obrigação no
cadastro pelo termo — ou declara `lacuna` com o motivo; (2) todo gatilho do leitor de evidências
(mitra/evidencias.GATILHOS) está no mapa, com o mesmo termo e a mesma norma. Gatilho órfão ou evento
sem dono viram teste vermelho, nunca uma descoberta silenciosa no meio de uma implementação."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from mitra import descoberta
from mitra.evidencias import GATILHOS
from mitra.triagem import normalizar

RAIZ = Path(__file__).resolve().parent.parent


def _titulos_por_tipo() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for arq in sorted((RAIZ / "cadastro").glob("*.csv")):
        for linha in csv.DictReader(arq.open(encoding="utf-8")):
            if linha.get("tipo_ativo") and linha.get("obrigacao"):
                out.setdefault(linha["tipo_ativo"], []).append(normalizar(linha["obrigacao"]))
    # a Res. 220 vive em seed_obligations.csv, sem coluna de tipo: é toda de barragem
    for linha in csv.DictReader((RAIZ / "seed_obligations.csv").open(encoding="utf-8")):
        if linha.get("obrigacao"):
            out.setdefault("barragem", []).append(normalizar(linha["obrigacao"]))
    return out


def test_todo_evento_do_mapa_tem_obrigacao_no_cadastro_ou_lacuna_declarada():
    eventos = descoberta.temas().get("eventos", {})
    assert eventos, "o mapa [eventos] sumiu do temas.toml"
    titulos = _titulos_por_tipo()
    for tipo, do_tipo in eventos.items():
        for nome, ev in do_tipo.items():
            if ev.get("lacuna"):
                continue        # lacuna declarada: aparece, não quebra
            termo = ev["obrigacao"]
            acha = [t for t in titulos.get(tipo, []) if re.search(rf"\b{termo}", t)]
            assert acha, (f"o evento {tipo}.{nome} aponta o termo {termo!r} e nenhuma obrigação do "
                          f"cadastro casa: catalogue a norma ({ev['norma']}) ou declare `lacuna`")


def test_todo_gatilho_do_leitor_esta_no_mapa_com_o_mesmo_termo_e_norma():
    eventos = {nome: ev for do_tipo in descoberta.temas().get("eventos", {}).values()
               for nome, ev in do_tipo.items()}
    for nome, g in GATILHOS.items():
        assert nome in eventos, f"o gatilho {nome!r} não está no mapa [eventos] do temas.toml"
        assert eventos[nome]["obrigacao"] == g["obrigacao"], nome
        assert eventos[nome]["norma"] == g["norma"], nome


def test_tipos_de_ativo_nao_engolem_o_mapa_de_eventos():
    cfg = descoberta.temas()
    assert "eventos" not in descoberta.tipos_de_ativo(cfg)
    assert "barragem" in descoberta.tipos_de_ativo(cfg)
