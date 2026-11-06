"""Jobs que rodam fora da requisição (na AWS: task do Fargate disparada pelo EventBridge).

    python -m api.jobs radar [arquivo.zip]   # radar do DOU: triagem -> IA nas candidatas -> fila de decisão

O arquivo é o XML mensal do DOU (dados abertos da Imprensa Nacional); sem argumento, a amostra
de agosto/2026 que está no repositório. Cada ato vira registro único (idempotente): rodar de
novo não duplica nada nem paga a IA de novo (cache)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from regulaia import db, demo, impacto
from regulaia.ia import Roteador

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


def main(argv: list[str]) -> int:
    configurar_logs()
    if not argv or argv[0] != "radar":
        print(__doc__)
        return 2
    alvo = Path(argv[1]) if len(argv) > 1 else demo.AMOSTRA_DOU
    print(json.dumps(radar(alvo, Config()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
