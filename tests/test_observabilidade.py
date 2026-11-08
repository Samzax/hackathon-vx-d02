"""Logs da API: os módulos do domínio (mitra.ia) saem no mesmo JSON do CloudWatch que as requisições."""

from __future__ import annotations

import io
import json
import logging

from api.observabilidade import configurar_logs, raiz


def test_aviso_do_dominio_sai_no_log_json_da_api():
    configurar_logs()
    configurar_logs()                       # chamar de novo (várias apps no mesmo processo) não duplica
    nossos = [h for h in raiz.handlers if getattr(h, "mitra_json", False)]
    assert len(nossos) == 1
    saida = io.StringIO()
    anterior = nossos[0].setStream(saida)
    try:
        logging.getLogger("mitra.ia").warning("modelo %s recusado pelo provedor", "bedrock:x")
        logging.getLogger("mitra.ia").info("modelo %s responde", "bedrock:y")
        logging.getLogger("mitra.api").info("requisição")
    finally:
        nossos[0].setStream(anterior)
    linhas = [json.loads(linha) for linha in saida.getvalue().splitlines()]
    assert [(r["logger"], r["nivel"]) for r in linhas] == [
        ("mitra.ia", "WARNING"), ("mitra.ia", "INFO"), ("mitra.api", "INFO")]
    assert linhas[0]["msg"] == "modelo bedrock:x recusado pelo provedor"
