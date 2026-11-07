# Tarefa 2 da CLI: conexões em pool e plataforma só leitura nos dados do cliente

Roda em paralelo com outra sessão da CLI que faz a descoberta (`docs/TAREFA_DESCOBERTA.md`, rotas
`api/rotas/descoberta.py` e telas de cobertura e normas candidatas). Para não pisar nela: trabalhe no
worktree `../hackathon-vx-d02-cli2`, branch `plataforma-cli2`, e não mexa em descoberta nem em `infra/`.
Commits sem linha de coautoria. Ruff e a suíte inteira antes de cada commit; empurre o branch e deixe o CI
verde. O Docker desta máquina não sobe (a "Plataforma de Máquina Virtual" do Windows está desligada): o
que depende de Docker e Postgres se confere no CI, que tem os dois.

Ler antes: `docs/PLATAFORMA.md` (seções Multiempresa e Fase 1), `api/seguranca.py`, `api/banco.py`.

## 1. Pool de conexões (psycopg_pool)

Hoje `api/banco.py` abre e fecha uma conexão por requisição. No Postgres, trocar por um
`psycopg_pool.ConnectionPool` criado no `lifespan` do app (tamanho por variável de ambiente, com padrão
pequeno), devolvendo a conexão ao pool no fim da requisição, com rollback se ficou transação aberta. No
SQLite (testes e demo) continua uma conexão por requisição. `regulaia/banco.py` tem a conexão Postgres
com a cara do sqlite3: o pool precisa entregar esse mesmo embrulho. `psycopg[binary]` já está nas
dependências de execução; acrescentar `psycopg-pool`. Teste: várias requisições em sequência e em
paralelo no Postgres (`REGULAIA_TESTE_PG`) sem vazar conexão (o pool volta ao tamanho mínimo) e uma
requisição que falha no meio não deixa transação aberta para a próxima.

## 2. Plataforma só lê os dados operacionais do cliente

Hoje a curadoria e o token de serviço (plataforma) podem registrar entrega, desfazer entrega, anexar
comprovante, atribuir, comentar e mexer no cadastro e no responsável de ativo de qualquer cliente.
Decisão: **nos dados operacionais do cliente a plataforma só lê.** Quem entrega, comenta e corrige o
cadastro é a própria empresa. A plataforma continua escrevendo o que é dela: decisão de mudança de
norma pública, radar, descoberta e curadoria, contas (TI da plataforma) e importação do SIGBM.

- Fechar com 403 e mensagem clara ("a equipe RegulaIA só lê os dados da empresa") as rotas de escrita da
  torre e de evidências: `POST /comprovantes`, `POST /entregas`, `DELETE /entregas`, `POST /atribuicoes`,
  `POST /comentarios`, `PATCH /ativos/{id}/atributos`, `PUT /ativos/{id}/responsavel`, `POST /evidencias/registro`.
  `POST /evidencias/leitura` (ler PDF sem gravar) continua aberta.
- Decisão de mudança de obrigação **própria** da empresa (condicionante) é da empresa: a plataforma não
  aprova nem rejeita (`POST /mudancas/{id}/decisao` em obrigação com `empresa` preenchida → 403 para
  a plataforma). Norma pública continua só com a plataforma.
- O front esconde os botões de escrita para a plataforma (não só confia no 403) e mostra um aviso
  discreto "visão da plataforma: só leitura".
- O servidor MCP (`agente/`) já é só leitura: conferir que nenhuma ferramenta escreve.
- Testes em `tests/test_api.py` para cada rota (plataforma 403, cliente 2xx), e o e2e de um fluxo do
  cliente continua passando. Atualizar `api/openapi.json` e marcar os itens em `docs/PLATAFORMA.md`.

## 3. Depois de 1 e 2

Avise no fim, com o que ficou de fora. A próxima tarefa (instanciação de empresa: cadastro a partir do
CNPJ, dados privados por empresa e por unidade) vai sair em outro arquivo quando o domínio estiver pronto.
