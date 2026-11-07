"""Logs em JSON (um por requisição, prontos para o CloudWatch) com request_id e tempo."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("mitra.api")


class _Json(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        base = {"nivel": r.levelname, "msg": r.getMessage(), "logger": r.name}
        base.update(getattr(r, "extra_json", {}))
        if r.exc_info:
            base["erro"] = self.formatException(r.exc_info)
        return json.dumps(base, ensure_ascii=False)


def configurar_logs() -> None:
    if log.handlers:
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(_Json())
    log.addHandler(h)
    log.setLevel(logging.INFO)
    log.propagate = False


class RequestId(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = rid
        t0 = time.perf_counter()
        status = 500
        try:
            resposta = await call_next(request)
            status = resposta.status_code
            resposta.headers["X-Request-Id"] = rid
            return resposta
        finally:
            log.info("requisição", extra={"extra_json": {
                "request_id": rid, "metodo": request.method, "rota": request.url.path, "status": status,
                "ms": round((time.perf_counter() - t0) * 1000, 1),
                "usuario": getattr(request.state, "usuario", None)}})
