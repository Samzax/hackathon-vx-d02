"""Casos de ouro contra um modelo de verdade.

Só rodam com RUN_IA=1 e uma chave no .env (custam frações de centavo):
    RUN_IA=1 uv run pytest tests/test_ia_real.py -v
"""

import os
from pathlib import Path

import pytest

from collector.xml_dou import load_month
from regulaia import db, demo, impacto
from regulaia.ia import Roteador

pytestmark = pytest.mark.skipif(os.environ.get("RUN_IA") != "1", reason="defina RUN_IA=1 para chamar a IA")

AMOSTRA = Path(__file__).parent / "fixtures" / "dou" / "S01_amostra.zip"


@pytest.fixture(scope="module")
def ambiente():
    conn = db.conectar(":memory:")
    ids = demo.montar(conn)
    atos = {a.identifica.split(",")[0]: a for a in load_month(AMOSTRA) if a.is_anm and a.is_normative}
    return conn, ids, Roteador(conn), atos


def test_res_245_real(ambiente):
    conn, ids, rot, atos = ambiente
    ato = atos["Resolução ANM Nº 245"]
    an = impacto.analisar(conn, rot, ato.identifica, ato.text)
    assert not an.revisao_humana, an.motivo
    assert {m.obrigacao for m in an.aprovadas} == {"OB-01"}
    assert any(m.campo in ("prazo", "vigencia_desde") and m.valor_novo == "2029-12-26" for m in an.aprovadas)

    novas = set(impacto.aplicar(conn, an, db.registrar_ato(conn, "dou", "245", ato.identifica, texto=ato.text)))
    afetadas = {c for c, a in ids.items()
                if any(o.pendente and o.pendente["id"] in novas for o in db.obrigacoes_do_ativo(conn, a))}
    assert afetadas == {"B2"}


def test_res_246_real_nao_muda_nada(ambiente):
    conn, _, rot, atos = ambiente
    ato = atos["Resolução ANM Nº 246"]
    an = impacto.analisar(conn, rot, ato.identifica, ato.text)
    assert not an.revisao_humana, an.motivo
    assert an.aprovadas == []
