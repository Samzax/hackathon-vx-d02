# RegulaIA API: a imagem que roda no ECS Fargate (e no docker compose local).
#
#   docker build -f api/Dockerfile -t regulaia-api .
#   docker run -p 8000:8000 -e REGULAIA_DATABASE_URL=postgresql://... regulaia-api
#
# A mesma imagem roda a API (padrão) e o job do radar do DOU:
#   docker run regulaia-api python -m api.jobs radar
# Segredos (URL do banco, chaves de IA, token do agente) entram por variável de ambiente,
# vindos do Secrets Manager na AWS; nunca na imagem (.env está no .dockerignore).

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN uv sync --locked --no-dev

RUN useradd --create-home regulaia && mkdir -p /app/data/uploads && chown -R regulaia /app
USER regulaia

ENV PATH="/app/.venv/bin:$PATH" \
    REGULAIA_COOKIE_SEGURO=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# migração antes de subir: idempotente, várias tasks podem rodar ao mesmo tempo (lock do Alembic no Postgres)
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --workers 2"]
