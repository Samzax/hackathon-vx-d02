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

cd front && npm ci                                # o front (Node 22.12+)
npm run dev                                       # http://localhost:3000, falando com a API na 8000
npm run build                                     # front/out: a API serve em http://localhost:8000
npm run tipos                                     # regera src/lib/api-tipos.ts depois do api.contrato
npm test && npm run e2e                           # vitest; Playwright contra a API real (depois do build)
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
- [x] 2A front Next.js em `front/`: substitui o Streamlit como interface principal, todas as telas do README.
      - Next.js 16 (App Router) + TypeScript + Tailwind 4, `output: "export"`: site estático que a própria API
        serve na mesma origem (`api/main.py` monta `front/out` se existir; `REGULAIA_FRONT` muda a pasta; rota
        `/api/v1/...` que não existe continua 404 em JSON). A imagem (`api/Dockerfile`) compila o front num
        estágio Node e copia o `out/`. Em dev, Next na 3000 e API na 8000 (CORS com credenciais).
      - Tipos gerados de `api/openapi.json` (`npm run tipos`, conferidos no CI com `--check`); cliente
        `openapi-fetch` com `credentials: "include"` e `X-CSRF-Token` (cookie `regulaia_csrf`) em toda escrita;
        React Query com chave `["torre", visão, empresa, hoje]`, e toda escrita invalida a torre.
      - Nada de regra no front: rótulos, períodos, campos do cadastro, quem decide, conferência e o que mudou
        vêm da API. Rotas novas para isso: `cadastro/campos`, `empresas/{id}/areas`, `resumo`, `vigencias`,
        `plano-transicao`, `obrigacoes`, `decisoes`, `ativos/{id}/obrigacoes/{codigo}/historico`,
        `entregas/periodo`, `comprovantes` (arquivo da entrega), `evidencias/exemplos`, `radar/exemplo`;
        `Ativo.posicao` (mapa, de `data/posicoes_demo.json`), `Eu.hoje`, e na versão de uma obrigação `mudou`
        (o que mudou em relação à anterior) e `corrigido` (proposto → aprovado por quem decidiu).
      - Marca própria, claro e escuro (segue o sistema, troca na barra lateral), cores de status da torre
        como variáveis CSS (`globals.css`), mapa Leaflet com ladrilhos do OpenStreetMap, Gantt em SVG,
        usável no celular (menu em gaveta, tabelas com rolagem).
      - Testes: vitest (formatação, cliente da API, status, markdown) e Playwright (`front/e2e/`): a API de
        verdade num SQLite novo servindo o `out/`, cinco cenários (entrar na demo e ver as 4 atrasadas,
        registrar uma entrega, gestor só com a área dele, curadoria aprovando a Res. 245, TI só com contas e
        auditoria). CI: jobs `front` (tipos, lint, typecheck, vitest, build) e `front-e2e`.
      - Em aberto: o Streamlit (`app.py`) continua na `main` até a troca; "Pergunte à torre" (2C) ainda não.
- [x] 2B AWS CDK (`infra/`, commit 49c404b): ALB + ECS Fargate (API e front na mesma origem, migração no start),
      RDS Postgres 16 isolado, S3 privado e versionado, Bedrock e Textract por IAM mínimo, EventBridge (radar
      06:00 BRT), Secrets Manager, CloudWatch com 3 alarmes, sem NAT. `tests/test_infra.py` confere a pilha;
      `npx aws-cdk@2 synth` sem aviso. Falta o deploy na conta do evento (IDs do Bedrock em `modelos.toml`).
- [x] 2C servidor MCP (`agente/`): 12 ferramentas de leitura sobre a API com o token de serviço,
      `REGULAIA_EMPRESA` prende o escopo numa cliente, erro da API vira erro de ferramenta legível; stdio e
      streamable HTTP. `tests/test_agente.py` contra a API real; conferido com um cliente MCP de verdade (stdio).
- [ ] 2C chat "Pergunte à torre" no front: rota na API (ex.: `POST /api/v1/pergunta`) que roda o Claude
      (Bedrock na AWS) com as mesmas ferramentas no escopo da sessão, e a tela no front (sessão do front).

### Descoberta de normas (produto, não a demo)
- [x] `regulaia/descoberta.py`: perfil da carteira (jurisdição x tipo de ativo), três fontes oficiais com dados
  abertos (Senado, ANMlegis, Assembleia de Minas), camada 0 sem IA (termos em `regulaia/temas.toml`, revogada e
  regra fora, segunda passada pela citação na ementa), triagem pela IA em paralelo (uma por vez com Bedrock),
  curadoria (aprovar/descartar com nome e nota) e cobertura por cliente com as lacunas conhecidas.
- [x] Tabelas `norma_candidata` e `descoberta_busca` (migração 0003); a fila real vai para a demo em
  `data/descoberta_demo.json` e entra no `demo.preparar`, fora do "Recriar demo".
- [x] `tests/test_descoberta.py` com trechos reais das três fontes em `tests/fixtures/descoberta/`.
- [x] API e front ([docs/TAREFA_DESCOBERTA.md](TAREFA_DESCOBERTA.md)):
  - `api/rotas/descoberta.py`: `GET /empresas/{id}/cobertura` (cliente só a dela, 404 para outra; gestor só as
    linhas dos ativos da área; a plataforma vê qualquer uma), `GET /normas-candidatas?status=&jurisdicao=` e
    `GET /normas-candidatas/{chave}` (só a plataforma, `seguranca.plataforma`; cliente 403), `POST
    /normas-candidatas/{chave}/decisao` (só a curadoria; `quem` = e-mail da sessão; auditoria
    `descoberta.decidir` com empresa vazia, e a recusada também). A chave tem `:` e `/`: rota `{chave:path}`, e o
    front manda codificada (`%3A`, `%2F`). Rótulos (estado, status, fonte, jurisdição) vêm do domínio.
  - Domínio: o estado `extracao_pendente` ("aprovada, falta extrair") separado de `curadoria_pendente`;
    `VERIFICADOS` (o que não foi lido nunca é verificado), `ROTULOS_STATUS`, `NOMES_FONTES`, `nome_jurisdicao`.
  - Job `python -m api.jobs descoberta [--desde] [--fontes] [--limite] [--paralelo] [--sem-triagem]` e o serviço
    `descoberta` no compose (perfil `jobs`, volume com o cache das fontes). Falta o agendamento na AWS
    (EventBridge, em `infra/`), que não entrou aqui.
  - Front: Regulatório → "Cobertura normativa" (todos menos a TI; cores em `src/lib/cobertura.ts`: verde só se
    verificada, cinza com "cobertura não verificada") e "Normas candidatas" (só a plataforma, com contador das
    relevantes; filtro por jurisdição e status na URL, busca, Aprovar / Descartar com nota). E2E: a curadoria
    aprova o Decreto MG 48.747/2023 e ele passa de "esperando curadoria" para "aprovada, falta extrair" na
    cobertura da Serra Azul; a cliente não abre a fila e a B4 levada para o Pará sai cinza.
  - Agente: `cobertura_normativa(empresa, jurisdicao, tipo_ativo)`.
- [ ] Mais conectores: outros estados (PA, BA, GO...) sem o LexML, que bloqueia robô; Copam/Semad em MG; Conama.

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

1. **Mais normas de verdade no catálogo.** Entraram, curadas à mão com trecho literal conferido por
   `tests/test_trechos.py`:
   - `cadastro/lei12334.csv`: Lei 12.334/2010 (PNSB) compilada com a Lei 14.066/2020, 23 obrigações do
     empreendedor (art. 17, PAE do art. 12, PSB do art. 8º, art. 18, 18-A e 2º-A). O Planalto derruba conexão
     que não vem de navegador: o texto foi salvo do navegador, sem os trechos riscados (revogados).
   - `cadastro/lei_mg_23291.csv`: Lei MG 23.291/2019 (texto atualizado da ALMG, baixa sem navegador),
     18 obrigações, só para `uf = MG`. A auditoria técnica de segurança depende do novo atributo
     `potencial_dano_ambiental` (classificação estadual), que o SIGBM não traz: em empresa importada, dado faltando.
   - `cadastro/dec_mg_48078.csv` (PAE, 9) e `cadastro/dec_mg_48140.csv` (classificação, auditoria, descaracterização,
     obras emergenciais, 7): os decretos que regulamentam a lei mineira, texto atualizado da ALMG.
   Total: 129 obrigações, 123 trechos conferidos. Os números da demo (4 atrasadas, 1 dado faltando,
   3 vencendo) e o cache de IA dos atos da demo não mudaram. Próximas candidatas: Deliberações Normativas do Copam sobre
   barragens, NR-01 (GRO) para a unidade, leis estaduais de barragens de outros estados (PA, BA, GO).
2. Conferir o `testes-postgres` no próximo CI (acima).
