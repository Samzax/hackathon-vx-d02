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
- **Multiempresa:** a RegulaIA é a plataforma; cada mineradora (a Serra Azul inclusive) é uma cliente
  que só vê o que é dela. Decisão do usuário (06/11): mudança de **norma pública** (Res. ANM, NR...) é
  aprovada pela **curadoria da plataforma**, uma vez para todas as clientes (a cliente vê "aguardando
  curadoria RegulaIA"); **obrigação própria** da empresa (condicionante de licença, TAC, procedimento
  interno) é aprovada pelo Regulatório ou pela Diretoria **da própria empresa**.

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
- [x] `tests/test_api.py`: 31 testes (sessão, CSRF, papéis, escopo, fluxos, isolamento entre empresas, contrato)
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

### Multiempresa
- [x] Esquema: `obrigacao.empresa` (vazio = norma pública), `usuario.empresa` e `usuario.plataforma`
      (equipe da RegulaIA), `auditoria.empresa`; migração Alembic `0002_multiempresa`. A ligação é pelo
      **nome** da empresa (UNIQUE), não pelo id: o "Recriar demo" recria as empresas e as contas ficam.
      `tests/test_banco.py` confere que 0001 + 0002 dão o `schema_pg.sql`.
- [x] Domínio: `db.obrigacoes_do_ativo` só traz norma pública ou obrigação da dona do ativo (a L1 de
      outra empresa não recebe as condicionantes LO-xx da Serra Azul); busca de ativo sempre com a
      empresa (`db.ativo_por_codigo`: evidências, transição); `torre.mudancas` e `_comecam_em` só com o
      que é público ou da empresa; `impacto.analisar(..., empresa=)` analisa o ato de uma cliente só
      contra o catálogo dela; contas e áreas por empresa (`usuarios.listar/areas(conn, empresa=)`).
- [x] API (`api/seguranca.py`): o `Escopo` leva `empresa_id`, `empresa` e `plataforma`. Conta de cliente
      vê só a empresa dela; conta da plataforma e o token de serviço veem todas; conta sem empresa: 403.
      O que é de outra cliente devolve **404** (não revela que existe): empresa, ativo, histórico de
      obrigação própria, mudança, leitura de evidência, conta. `/mudancas` diz `escopo` ("norma pública"
      ou "empresa"), `decide` e `quem_decide`; a decisão segue a regra do usuário acima.
      `/radar/propor` e `/sigbm/importar`: só a curadoria. TI cria e edita só contas da própria empresa
      (a TI da plataforma escolhe a empresa no campo `empresa`; vazio cria conta da plataforma).
      Auditoria grava a empresa de quem agiu e cada cliente vê só a própria trilha.
- [x] Conta da curadoria na demo: `curadoria@regulaia.demo` (Regulatório da plataforma). A conta de teste
      ganhou a visão "Curadoria RegulaIA (plataforma)".
- [x] Testes de isolamento em `tests/test_api.py` (segunda cliente com B1, B3 e L1 e a mesma área).
- [ ] Em aberto: a plataforma (curadoria, token de serviço) ainda pode registrar entrega, comentar e
      mexer no cadastro de qualquer cliente, como suporte. Se isso deve ser só leitura, fechar nas rotas
      de escrita da torre.
- [ ] O Streamlit (`app.py`) continua de uma empresa só e com as regras antigas de decisão (é a demo).
- [ ] Obrigação própria ainda tem código global (`obrigacao.codigo` UNIQUE): duas clientes não podem
      ter cada uma a sua "LO-01". Quando entrar a segunda cliente com licença própria, prefixar o código
      ou trocar o UNIQUE por (empresa, codigo).

## CI (run 42281176074, commit ae998d9)

- lint, imagem: ok.
- testes-sqlite: 2 falhas que não apareciam no Windows, corrigidas depois:
  - `test_ocr.py::test_exemplo_escaneado_esta_nos_exemplos_e_e_igual_ao_gerado`: os pixels são os mesmos,
    o que muda é o zlib do Python (zlib-ng no 3.14 e em builds do Linux, zlib 1.3 no Windows) e com ele
    os bytes do PDF. O teste agora compara a imagem descomprimida, pixel a pixel.
  - `test_app.py::test_ato_ficticio_vira_mudanca_pendente`: a resposta da IA para o ato fictício só estava
    no `data/cache_ia.db` local. Entrou no `data/cache_ia_demo.json`, e os testes do Streamlit passam a usar
    um cache novo, semeado só com o que está no Git (como num clone novo).
- testes-postgres: passou dos 40 minutos rodando a suíte (no SQLite ela leva 1 minuto no CI) e o log só sai
  quando o job termina. Causa provável: o `DROP SCHEMA ... CASCADE` da limpeza de cada teste espera para
  sempre por uma conexão que ficou aberta com transação (a do `st.cache_resource` do Streamlit, ou a de
  um teste que falhou, presa no traceback). O `conftest.py` agora fecha as conexões do teste antes e usa
  `lock_timeout`; o `test_app.py` limpa o `st.cache_resource` a cada teste; o job tem `timeout-minutes: 45`
  e mostra as 15 durações mais longas. Ainda não conferido no Postgres (o Docker daqui não respondeu):
  ver no próximo CI.

## Próximo

1. **Mais normas de verdade no catálogo**, pelo mesmo caminho das atuais: `regulaia/fontes.py` baixa o
   texto oficial, `regulaia/extrator.py` propõe (com IA), `curadoria/*.csv` escolhe, `regulaia/curadoria.py`
   gera, `tests/test_trechos.py` confere o trecho literal; norma curta pode ser curada à mão, como
   `cadastro/nr22_zas.csv`. Pedidos do usuário: Lei 12.334/2010 (PNSB), lei estadual de MG de barragens,
   outras resoluções da ANM, outras NRs aplicáveis à mineração; sempre com o trecho literal conferido
   contra o texto oficial. Em 06/11 o Planalto derrubou a conexão do `regulaia.fontes` (connection reset)
   e o normas.leg.br só serve a página com JavaScript: falta uma fonte oficial que baixe sem navegador.
   Antes de pôr norma nova, conferir que as candidatas da triagem dos atos em cache (Res. 245, 246 e o ato
   fictício) não mudam: o prompt da IA leva as candidatas, e se mudar o cache da demo deixa de valer.
2. Conferir o `testes-postgres` no próximo CI (acima).
