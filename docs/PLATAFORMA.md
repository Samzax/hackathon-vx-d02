# Plataforma: da demo em Streamlit para o produto

Branch `plataforma`. A `main` continua com a demo em Streamlit funcionando até o front novo
cobrir todas as telas. Este arquivo é o plano e o estado: quem continuar (outra sessão, outra
conta) começa por aqui.

## Decisões

- **Domínio intocado:** as regras ficam em `regulaia/`, com os mesmos testes. Tudo novo é camada em volta.
- **Banco:** Postgres em produção (AWS RDS), SQLite nos testes rápidos e na demo offline. O mesmo SQL
  portátil roda nos dois; as diferenças ficam em `regulaia/banco.py`. Esquema do Postgres em
  `regulaia/schema_pg.sql` (texto com `COLLATE "C"` para ordenar igual ao SQLite).
- **API:** FastAPI em `api/`. Sessão por cookie HttpOnly (só o hash do token no banco), CSRF por
  double submit, papéis (TI, Diretoria, Regulatório, gestor), escopo por área, auditoria de toda
  escrita, logs JSON com request_id, contrato OpenAPI versionado em `api/openapi.json`.
- **Front:** Next.js + Tailwind (fase 2A). **Infra:** AWS CDK em Python (fase 2B). **Agente:** servidor
  MCP + chat "Pergunte à torre" com Bedrock (fase 2C). **CI:** GitHub Actions (fase 3).

## Como rodar

```bash
uv sync
uv run uvicorn api.main:app --reload            # http://localhost:8000/docs (SQLite em data/regulaia.db)
REGULAIA_DATABASE_URL=postgresql://... uv run uvicorn api.main:app
uv run python -m api.contrato                    # regera api/openapi.json depois de mudar a API
docker compose up --build                         # Postgres + API, igual à AWS
REGULAIA_DATABASE_URL=postgresql://... uv run alembic upgrade head
REGULAIA_TESTE_PG=postgresql://... uv run pytest # a suíte inteira no Postgres
```

## Estado

### Fase 1: núcleo e API
- [x] SQL portátil (sem `datetime('now')`, `INSERT OR ...`, `IS NOT ?`); 328 testes passam no SQLite
- [x] `regulaia/banco.py`: conexão Postgres com a cara do sqlite3; `schema_pg.sql`
- [x] `tests/conftest.py`: `REGULAIA_TESTE_PG` roda a suíte inteira no Postgres (schema isolado por teste)
- [x] API: auth (login, demo, logout, me, visão), torre (empresas, painel, ativos, ficha, histórico,
      calendário, transição, linha do tempo, boletim md/pdf, .ics, planilha), escrita (entregas,
      desfazer, atribuições, comentários, atributos, responsável), mudanças (listar, decidir com
      correção), radar (funil, análise de ato, propor), evidências (leitura de PDF, registro),
      contas (TI), auditoria, SIGBM (busca, importação), mercado, recriar demo, /health
- [x] `tests/test_api.py`: 21 testes (sessão, CSRF, papéis, escopo, fluxos, contrato)
- [ ] Rodar a suíte no Postgres de verdade (Docker Desktop não subiu na primeira tentativa)
- [x] Alembic (`migrations/`, 0001 = `schema_pg.sql` congelado, lock para tasks em paralelo);
      `tests/test_banco.py` confere que SQLite e Postgres têm as mesmas tabelas e colunas
- [x] `docker compose`: postgres + api + job do radar (`python -m api.jobs radar`); `api/Dockerfile`
- [x] CI em `.github/workflows/ci.yml`: ruff, suíte no SQLite, suíte no Postgres (com migração 2x),
      build das imagens e compose subindo com a API respondendo
- [ ] Pool de conexões (psycopg_pool) no lugar de uma conexão por requisição

### Fase 2 (paralelo, depois da fase 1)
- [ ] 2A front Next.js (tipos gerados de `api/openapi.json`)
- [ ] 2B AWS CDK: ECS Fargate, RDS, S3, Bedrock, Textract, EventBridge (radar diário), SQS, Secrets, CloudWatch
- [ ] 2C servidor MCP + chat

### Fase 3
- [ ] GitHub Actions: ruff, pytest (SQLite e Postgres), front, docker build, cdk synth
