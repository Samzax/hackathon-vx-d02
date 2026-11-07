"""Monta o banco da demo: cadastro de obrigações + Mineradora Serra Azul + histórico.

Uso: uv run python -m mitra.demo [caminho.db]
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

from . import banco, agenda, db, descoberta, usuarios

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
CACHE_DEMO = ROOT / "data" / "cache_ia_demo.json"     # respostas da IA usadas na demo (vai pro Git)
_COLUNAS_CACHE = ("chave", "tarefa", "provedor", "modelo", "resposta", "tokens_in", "tokens_out", "custo_usd")


def exportar_cache(cache, destino: Path = CACHE_DEMO, tarefas=("impacto", "extrator")) -> int:
    """Copia do cache local (fora do Git) as respostas que a demo precisa."""
    marcas = ",".join("?" * len(tarefas))
    linhas = [dict(r) for r in cache.execute(
        f"SELECT {', '.join(_COLUNAS_CACHE)} FROM analise_ia WHERE tarefa IN ({marcas}) ORDER BY chave",
        tarefas)]
    destino.write_text(json.dumps(linhas, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(linhas)


def semear_cache(cache, origem: Path = CACHE_DEMO) -> int:
    """Num clone novo o cache está vazio: carrega as respostas da demo, sem sobrescrever nada."""
    if not origem.exists():
        return 0
    linhas = json.loads(origem.read_text(encoding="utf-8"))
    with cache:
        # data fixa no passado: a resposta da demo não conta no teto de gasto do dia (MITRA_TETO_DIA_USD)
        cache.executemany(
            f"INSERT INTO analise_ia ({', '.join(_COLUNAS_CACHE)}, criada_em) "
            f"VALUES ({', '.join('?' * len(_COLUNAS_CACHE))}, '2026-11-01 00:00:00') ON CONFLICT DO NOTHING",
            [tuple(l[c] for c in _COLUNAS_CACHE) for l in linhas])
    return len(linhas)


def preparar(caminho: Path | None = None, dou: Path = AMOSTRA_DOU, cache: Path | None = None) -> tuple:
    """Banco pronto para a interface: cadastro, empresa, histórico e o radar do DOU
    já rodado (Res. 245 e 246). Usa o cache de IA; sem chave, só o que está em cache."""
    conn = db.conectar(caminho if caminho is not None else db.DB_PADRAO)
    pg = banco.eh_url_postgres(caminho)
    if pg:
        # Vários processos podem preparar ao mesmo tempo (os workers do uvicorn, as tasks do ECS): um
        # apagaria o que o outro está gravando. Um de cada vez; quem esperou um banco vazio e o encontra
        # pronto não refaz. Quem pediu para recriar uma demo que já existia recria.
        vazio_antes = _empresas(conn) == 0
        conn.execute("SELECT pg_advisory_lock(?)", (_LOCK_DEMO,))
        conn.commit()
        if vazio_antes and _empresas(conn) > 0:
            conn.execute("SELECT pg_advisory_unlock(?)", (_LOCK_DEMO,))
            conn.commit()
            return conn, {}, []
    try:
        return _preparar(conn, caminho, dou, cache)
    except Exception:
        if pg:
            conn.rollback()         # transação abortada: sem isso, o unlock abaixo também falharia
        raise
    finally:
        if pg:
            conn.execute("SELECT pg_advisory_unlock(?)", (_LOCK_DEMO,))
            conn.commit()


_LOCK_DEMO = 724100246       # o Alembic usa 724100245


def _empresas(conn) -> int:
    n = conn.execute("SELECT COUNT(*) FROM empresa").fetchone()[0]
    conn.commit()
    return n


def _preparar(conn, caminho, dou: Path, cache: Path | None) -> tuple:
    from collector.xml_dou import load_month
    from . import impacto
    from .ia import Roteador

    conn_cache = db.conectar(cache if cache is not None else (caminho if banco.eh_url_postgres(caminho) else impacto.CACHE_IA))
    semear_cache(conn_cache)
    roteador = Roteador(conn_cache)
    analises = []
    with db.sem_sincronizar(conn):
        db.limpar(conn)     # no Windows o arquivo pode estar aberto pela interface
        ids = montar(conn)
        usuarios.semear(conn)       # contas ficam fora do limpar(): só entram as que faltam
        descoberta.semear(conn)     # a fila de normas candidatas também (trabalho da curadoria, não da cliente)
        for a in load_month(dou):
            if not (a.is_anm and a.is_normative):
                continue
            an = impacto.analisar(conn, roteador, a.identifica, a.text)
            ato_id = db.registrar_ato(conn, "dou", a.id_materia, a.identifica, ementa=a.ementa,
                                      publicado_em=a.pub_date.isoformat(), texto=a.text)
            impacto.aplicar(conn, an, ato_id)
            analises.append(an)
    RADAR.write_text(json.dumps([registro_radar(an) for an in analises], ensure_ascii=False, indent=1),
                     encoding="utf-8")
    return conn, ids, analises


def registro_radar(an) -> dict:
    """O que a interface mostra de uma análise de ato: candidatas, motivo, modelo, custo e mudanças."""
    return {"ato": an.ato, "candidatas": [c.codigo for c in an.candidatas], "motivo": an.motivo,
            "confianca": an.confianca, "modelos": an.modelos, "custo_usd": an.custo_usd,
            "custo_original_usd": an.custo_original_usd,
            "revisao_humana": an.revisao_humana,
            "mudancas": [{"obrigacao": m.obrigacao, "campo": m.campo, "valor_novo": m.valor_novo,
                          "reprovada": m.reprovada} for m in an.mudancas]}


def main(argv: list[str]) -> int:
    from . import torre

    if argv[:1] == ["--exportar-cache"]:
        from . import impacto
        print(f"{exportar_cache(db.conectar(impacto.CACHE_IA))} respostas em {CACHE_DEMO}")
        return 0
    caminho = Path(argv[0]) if argv else db.DB_PADRAO
    conn = db.conectar(caminho)
    with db.sem_sincronizar(conn):
        db.limpar(conn)
        montar(conn)
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
