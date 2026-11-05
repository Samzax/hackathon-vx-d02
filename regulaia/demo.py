"""Monta o banco da demo: obrigações da Res. 220 + Mineradora Serra Azul.

Uso: uv run python -m regulaia.demo [caminho.db]
Recria o banco do zero a cada execução.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import db

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "seed_obligations.csv"
SERRA_AZUL = ROOT / "data" / "serra_azul.json"


def montar(conn) -> dict[str, int]:
    """Carrega obrigações e a empresa; devolve {código do ativo: id}."""
    db.carregar_obrigacoes_csv(conn, SEED)
    dados = json.loads(SERRA_AZUL.read_text(encoding="utf-8"))
    emp = db.criar_empresa(conn, dados["empresa"], ficticia=dados["ficticia"])
    ids = {}
    with conn:
        for a in dados["ativos"]:
            ids[a["codigo"]] = db.criar_ativo(
                conn, emp, "barragem", a["codigo"], a["nome"], a["atributos"], a["responsavel"]
            )
    return ids


def main(argv: list[str]) -> int:
    caminho = Path(argv[0]) if argv else db.DB_PADRAO
    if caminho.exists():
        caminho.unlink()
    conn = db.conectar(caminho)
    ids = montar(conn)
    for codigo, ativo_id in ids.items():
        obs = db.obrigacoes_do_ativo(conn, ativo_id)
        falta = [f"{o.codigo} ({', '.join(o.dados_faltando)})" for o in obs if o.dados_faltando]
        print(f"{codigo}: {len(obs)} obrigações -> {', '.join(o.codigo for o in obs)}")
        if falta:
            print(f"    dado faltando: {'; '.join(falta)}")
    print(f"\nBanco em {caminho}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
