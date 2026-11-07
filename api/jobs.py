"""Jobs que rodam fora da requisição (na AWS: task do Fargate disparada pelo EventBridge).

    python -m api.jobs radar [arquivo.zip]   # radar do DOU: triagem -> IA nas candidatas -> fila de decisão
    python -m api.jobs descoberta [--desde ANO] [--fontes senado,anm,almg] [--limite N] [--paralelo N]
                                  [--sem-triagem]
        # descoberta de normas: lê as fontes oficiais (Senado, ANMlegis, Assembleia de Minas) e passa
        # pela IA as candidatas novas; o que for relevante vai para a fila da curadoria Mitra

Radar: o arquivo é o XML mensal do DOU (dados abertos da Imprensa Nacional); sem argumento, a amostra
de agosto/2026 que está no repositório. Cada ato vira registro único (idempotente): rodar de novo não
duplica nada nem paga a IA de novo (cache).

Descoberta: lê dezenas de milhares de normas e chama a IA, por isso é job e não rota. Rodar de novo não
apaga triagem nem decisão; a IA só vê as candidatas novas (e o cache evita pagar duas vezes). `--desde`
lê só a partir daquele ano (e a cobertura passa a dizer isso). Sai com código 1 se uma fonte falhou ou se
a triagem parou (sem provedor de IA, teto do dia): o que foi feito fica gravado."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from mitra import db, demo, impacto
from mitra.ia import Roteador

from .config import Config
from .observabilidade import configurar_logs, log


def radar(zip_dou: Path, cfg: Config) -> dict:
    from collector.xml_dou import load_month

    conn = db.conectar(cfg.banco)
    rot = Roteador(db.conectar(cfg.cache))
    atos = load_month(zip_dou)
    anm = [a for a in atos if a.is_anm and a.is_normative]
    propostas = 0
    for a in anm:
        an = impacto.analisar(conn, rot, a.identifica, a.text)
        ato_id = db.registrar_ato(conn, "dou", a.id_materia, a.identifica, ementa=a.ementa,
                                  publicado_em=a.pub_date.isoformat(), texto=a.text)
        try:
            propostas += len(impacto.aplicar(conn, an, ato_id))
        except db.ErroCadastro as e:        # já havia proposta pendente desse ato: rodar de novo não duplica
            log.info("radar: proposta já existe", extra={"extra_json": {"ato": a.identifica, "motivo": str(e)}})
    resumo = {"atos": len(atos), "anm_normativos": len(anm), "propostas": propostas, "custo_usd": rot.custo_total()}
    log.info("radar concluído", extra={"extra_json": resumo})
    return resumo


def descoberta(cfg: Config, *, desde: int | None = None, fontes: tuple[str, ...] | None = None,
               limite: int | None = None, triar: bool = True, paralelo: int = 4,
               baixador=None, roteador: Roteador | None = None) -> dict:
    """Busca nas fontes e triagem pela IA. `baixador` e `roteador` trocam a internet e a IA (testes)."""
    from mitra import descoberta as d

    conn = db.conectar(cfg.banco)
    try:
        baixador = baixador or d.Baixador()
        busca = d.buscar(conn, baixador, fontes or tuple(d.FONTES), desde)
        resumo: dict = {"busca": [asdict(r) for r in busca]}
        if triar:
            rot = roteador or Roteador(db.conectar(cfg.cache))
            # um Roteador (e uma conexão de cache) por linha de execução; com Bedrock, a triagem é uma por vez
            novo = None if roteador is not None else (lambda: Roteador(db.conectar(cfg.cache)))
            resumo["triagem"] = d.triar(conn, rot, limite, paralelo=paralelo, novo_roteador=novo, texto=baixador.texto)
        resumo["fila"] = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM norma_candidata GROUP BY status ORDER BY status")}
        conn.commit()
    finally:
        conn.close()
    log.info("descoberta concluída", extra={"extra_json": resumo})
    return resumo


def falhou(resumo: dict) -> bool:
    """Fonte fora do ar ou triagem interrompida: o job sai com erro para o alarme ver."""
    return any(r["falhas"] for r in resumo.get("busca", [])) or bool((resumo.get("triagem") or {}).get("erro"))


def _opcao(argv: list[str], nome: str) -> str | None:
    return argv[argv.index(nome) + 1] if nome in argv and argv.index(nome) + 1 < len(argv) else None


def main(argv: list[str]) -> int:
    configurar_logs()
    if not argv or argv[0] not in ("radar", "descoberta"):
        print(__doc__)
        return 2
    if argv[0] == "radar":
        alvo = Path(argv[1]) if len(argv) > 1 else demo.AMOSTRA_DOU
        print(json.dumps(radar(alvo, Config()), ensure_ascii=False))
        return 0
    from mitra.descoberta import FONTES

    resto = argv[1:]
    desde, fontes, limite, paralelo = (_opcao(resto, o) for o in ("--desde", "--fontes", "--limite", "--paralelo"))
    if fontes and (desconhecidas := set(fontes.split(",")) - set(FONTES)):
        print(f"fonte desconhecida: {', '.join(sorted(desconhecidas))} (há: {', '.join(FONTES)})")
        return 2
    resumo = descoberta(Config(), desde=int(desde) if desde else None,
                        fontes=tuple(fontes.split(",")) if fontes else None, limite=int(limite) if limite else None,
                        triar="--sem-triagem" not in resto, paralelo=int(paralelo) if paralelo else 4)
    print(json.dumps(resumo, ensure_ascii=False))
    return 1 if falhou(resumo) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
