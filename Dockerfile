# Mitra: imagem da torre para rodar na nuvem (AWS App Runner, ECS ou EC2).
#
#   docker build -t mitra .
#   docker run -p 8501:8501 mitra                      # demo: sem chave, roda do cache
#   docker run -p 8501:8501 --env-file .env mitra      # com IA de verdade (chaves no .env)
#
# A demo não precisa de internet nem de chave: as respostas de IA usadas nela estão em
# data/cache_ia_demo.json. As chaves, quando houver, entram por variável de ambiente,
# nunca na imagem (.env está no .dockerignore).

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# dependências primeiro (camada reaproveitada quando só o código muda)
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN uv sync --locked --no-dev

# usuário sem privilégio; o banco da demo é recriado em data/ a cada início
RUN useradd --create-home mitra && chown -R mitra /app
USER mitra

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

ENV PATH="/app/.venv/bin:$PATH"
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
