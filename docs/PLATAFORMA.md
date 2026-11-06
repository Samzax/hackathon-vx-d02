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

## Próximo: multiempresa (pedido do usuário em 06/11, ainda não feito)

A RegulaIA é o sistema; a Serra Azul é uma cliente (tenant) que usa o sistema. Hoje o código
mistura os dois. Rastros achados:

1. `usuario` sem `empresa_id`: conta de uma mineradora vê as outras pela API. Conta ganha
   `empresa_id` (nulo só para a equipe da plataforma); a API filtra tudo pela empresa da sessão.
2. Obrigação própria no catálogo global: as condicionantes da licença (`cadastro/lo_serra_azul.csv`,
   regra `*`) valem para licença de qualquer empresa. `obrigacao` ganha escopo opcional
   (`empresa_id`/`ativo_id`, vazio = norma pública); `db.obrigacoes_do_ativo` filtra por ele.
3. Código de ativo não é único entre empresas (B1 existe em várias), mas há busca só por código:
   `regulaia/evidencias.py:310` (registrar), `regulaia/torre.py:523` (pares), `api/rotas/evidencias.py:58`.
4. Áreas globais: `usuarios.areas()` e o escopo do gestor comparam só o nome da área
   ("Gerência de Geotecnia" de uma empresa casa com a de outra).
5. `auditoria` sem empresa: cada cliente deve ver só a própria trilha.
6. **Decisão em aberto (perguntar ao usuário):** aprovar uma mudança de norma hoje muda a versão
   global, ou seja, a Regulatório da Serra Azul decide por todas as clientes; e o "teste com um ato
   seu" (`/radar/propor`) de uma cliente altera o catálogo de todas. Opções: (a) adoção por empresa
   (tabela `adocao(empresa_id, versao_id, status, decidida_por, correcao)`; cada cliente aprova a
   leitura da norma para si); (b) curadoria da plataforma aprova a versão global e as clientes só veem.
   Recomendação: (a), porque quem responde perante a ANM é a empresa.
7. Testes de isolamento: duas empresas com ativos de mesmo código e mesma área; nenhuma rota
   devolve dado da outra.

## CI (run 42281176074, commit ae998d9)

- lint, imagem: ok. testes-postgres: rodando quando esta nota foi escrita.
- testes-sqlite falhou em 2 testes que passam no Windows e dependem do ambiente:
  `tests/test_ocr.py::test_exemplo_escaneado_esta_nos_exemplos_e_e_igual_ao_gerado` (PDF gerado
  difere no Linux, provavelmente fonte) e `tests/test_app.py::test_ato_ficticio_vira_mudanca_pendente`
  (a análise do ato fictício não aparece; conferir se depende do `data/cache_ia.db` local, fora do Git).
