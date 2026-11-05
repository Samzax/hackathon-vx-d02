"""Monta o banco da demo: cadastro de obrigações + Mineradora Serra Azul + histórico.

Uso: uv run python -m regulaia.demo [caminho.db]
Recria o banco do zero a cada execução.

Cadastro: seed_obligations.csv (Res. ANM 220/2025) e todo cadastro/*.csv
(Res. ANM 95/2022, NR-13, NR-22, licença fictícia...).

Histórico (data/historico_serra_azul.json): a empresa cumpriu tudo desde `desde`,
menos as `falhas`; execuções de longo prazo (RPSB a cada 3 anos...) vêm de `ultimas`.
É o que faz a torre ter vermelho e amarelo de verdade na demo.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from . import agenda, db

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "seed_obligations.csv"
CADASTRO = ROOT / "cadastro"
SERRA_AZUL = ROOT / "data" / "serra_azul.json"
HISTORICO = ROOT / "data" / "historico_serra_azul.json"


def carregar_cadastro(conn) -> int:
    n = db.carregar_obrigacoes_csv(conn, SEED, norma="Res. ANM 220/2025")
    for csv in sorted(CADASTRO.glob("*.csv")):
        n += db.carregar_obrigacoes_csv(conn, csv)
    return n


def montar(conn, com_historico: bool = True) -> dict[str, int]:
    """Carrega obrigações, a empresa e o histórico; devolve {código do ativo: id}."""
    carregar_cadastro(conn)
    dados = json.loads(SERRA_AZUL.read_text(encoding="utf-8"))
    emp = db.criar_empresa(conn, dados["empresa"], ficticia=dados["ficticia"])
    ids = {}
    with conn:
        for a in dados["ativos"]:
            ids[a["codigo"]] = db.criar_ativo(
                conn, emp, a.get("tipo", "barragem"), a["codigo"], a["nome"], a["atributos"], a["responsavel"]
            )
    if com_historico and HISTORICO.exists():
        gerar_historico(conn, ids, json.loads(HISTORICO.read_text(encoding="utf-8")))
    return ids


def gerar_historico(conn, ids: dict[str, int], spec: dict) -> int:
    hoje = date.fromisoformat(spec["hoje"])
    desde = date.fromisoformat(spec["desde"])
    falhas = {(f["ativo"], f["obrigacao"], f["periodo"]) for f in spec.get("falhas", [])}
    ultimas = spec.get("ultimas", {})
    cumpridas = spec.get("cumpridas", {})
    n = 0
    for codigo_ativo, ativo_id in ids.items():
        for o in db.obrigacoes_do_ativo(conn, ativo_id, em=hoje.isoformat()):
            v = o.vigente
            if o.dados_faltando or not db.vale_em(v, hoje.isoformat()):
                continue
            ag, chave = v["agenda"], f"{codigo_ativo}:{o.codigo}"
            ini = max(desde, date.fromisoformat(v["vigencia_desde"])) if v["vigencia_desde"] else desde
            rotulos: list[str] = []
            if ag.startswith(("anos:", "meses:")):
                rotulos = [ultimas.get(chave, ultimas.get(f"*:{o.codigo}", desde.isoformat()))]
            elif ag.startswith(("data:", "unica")):
                if chave in cumpridas:
                    rotulos = [cumpridas[chave]]
            elif ag != "evento":
                rotulos = [p.rotulo for p in agenda.periodos(ag, ini, hoje) if p.vence < hoje]
            for r in rotulos:
                if (codigo_ativo, o.codigo, r) in falhas:
                    continue
                db.registrar_evidencia(conn, ativo_id, o.codigo, r, arquivo=f"demo/{codigo_ativo}/{o.codigo}/{r}.pdf")
                n += 1
    return n


AMOSTRA_DOU = ROOT / "tests" / "fixtures" / "dou" / "S01_amostra.zip"
RADAR = ROOT / "data" / "radar_demo.json"


def preparar(caminho: Path = db.DB_PADRAO, dou: Path = AMOSTRA_DOU) -> tuple:
    """Banco pronto para a interface: cadastro, empresa, histórico e o radar do DOU
    já rodado (Res. 245 e 246). Usa o cache de IA; sem chave, só o que está em cache."""
    from collector.xml_dou import load_month
    from . import impacto
    from .ia import Roteador

    if Path(caminho).exists():
        Path(caminho).unlink()
    conn = db.conectar(caminho)
    ids = montar(conn)
    roteador = Roteador(db.conectar(impacto.CACHE_IA))
    analises = []
    for a in load_month(dou):
        if not (a.is_anm and a.is_normative):
            continue
        an = impacto.analisar(conn, roteador, a.identifica, a.text)
        ato_id = db.registrar_ato(conn, "dou", a.id_materia, a.identifica, ementa=a.ementa,
                                  publicado_em=a.pub_date.isoformat(), texto=a.text)
        impacto.aplicar(conn, an, ato_id)
        analises.append(an)
    RADAR.write_text(json.dumps([
        {"ato": an.ato, "candidatas": [c.codigo for c in an.candidatas], "motivo": an.motivo,
         "confianca": an.confianca, "modelos": an.modelos, "custo_usd": an.custo_usd,
         "revisao_humana": an.revisao_humana,
         "mudancas": [{"obrigacao": m.obrigacao, "campo": m.campo, "valor_novo": m.valor_novo,
                       "reprovada": m.reprovada} for m in an.mudancas]}
        for an in analises], ensure_ascii=False, indent=1), encoding="utf-8")
    return conn, ids, analises


def main(argv: list[str]) -> int:
    from . import torre

    caminho = Path(argv[0]) if argv else db.DB_PADRAO
    if caminho.exists():
        caminho.unlink()
    conn = db.conectar(caminho)
    ids = montar(conn)
    spec = json.loads(HISTORICO.read_text(encoding="utf-8")) if HISTORICO.exists() else {}
    hoje = date.fromisoformat(spec.get("hoje", date.today().isoformat()))
    desde = date.fromisoformat(spec.get("desde", hoje.isoformat()))
    linhas = torre.painel(conn, 1, hoje, desde)
    for ativo, cont in torre.resumo(linhas).items():
        print(f"{ativo}: " + ", ".join(f"{k} {v}" for k, v in sorted(cont.items())))
    print(f"\nBanco em {caminho} (hoje = {hoje})")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
