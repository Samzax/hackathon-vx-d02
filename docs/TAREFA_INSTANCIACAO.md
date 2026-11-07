# Tarefa: instanciação de uma empresa (da base padrão à torre personalizada)

A RegulaIA tem a **base padrão**, que vale para todo cliente: o catálogo de normas públicas, o SIGBM
público (só CNPJ), a descoberta e a vigência das normas. Falta a **base personalizada** de cada
empresa e de cada operação: os ativos que o SIGBM não traz, as licenças e condicionantes, os
responsáveis técnicos (com dado pessoal), quem vê o quê dentro da empresa e as regras próprias dela.
Instanciar é levar uma cliente nova do zero até a torre funcionando, sem ninguém editar CSV à mão.

Ler antes: `docs/PLATAFORMA.md` (Multiempresa, Descoberta), `regulaia/sigbm.py`, `regulaia/descoberta.py`
(`cobertura`), `regulaia/extrator.py`, `api/rotas/admin.py` (`/sigbm/busca`, `/sigbm/importar`),
`api/rotas/evidencias.py` (`/leitura`), `api/seguranca.py`, `regulaia/usuarios.py`.

## Regras da sessão

- Checkout principal, branch `plataforma`. Commits sem linha de coautoria. Ruff e a suíte inteira antes de
  cada commit; empurre a cada parte pronta (uma parte = um commit verde) e confira o CI.
- **Não mexa em `infra/`.** Outra sessão está montando a AWS agora. Variável de ambiente nova (a chave de
  criptografia, por exemplo) vai documentada em `docs/PLATAFORMA.md`, seção "Para a infra", com nome, para
  que serve e de onde vem em produção (Secrets Manager); quem cuida da infra liga.
- Não mexa em `regulaia/vigencia.py` (outra sessão está nele). A próxima migração é a `0005`.
- O Docker desta máquina não sobe: Postgres se confere no CI (ou num cluster local sem Docker, como a
  sessão anterior fez na porta 55432).
- Mantenha em `docs/PLATAFORMA.md` uma seção "Instanciação" com a lista do que está pronto e do que falta,
  atualizada a cada commit: se o limite de uso acabar no meio, outra sessão continua dali.

## 1. Domínio: `regulaia/instanciacao.py`

O estado da instanciação de cada empresa, em etapas, cada uma com quem fez e quando:

1. **Cadastro**: CNPJ, razão social, UFs. A partir do SIGBM (`sigbm.buscar`) a plataforma vê as barragens
   do CNPJ (todas, não só as da PNSB) e escolhe quais entram. Empresa sem barragem no SIGBM também entra
   (só CNPJ e nome).
2. **Ativos**: além das barragens, minas, usinas, pilhas e equipamentos, por formulário ou por planilha
   (modelo CSV baixável, validado linha a linha, com o erro na linha). Cada ativo pertence a uma **unidade**
   (a operação: "Mina Serra Azul", com as barragens e equipamentos dela).
3. **Dados que faltam**: para cada ativo, o que as regras do catálogo pedem e ninguém informou
   (`sigbm.FALTAM_NO_SIGBM` e os atributos que hoje viram "dado faltando"). É uma lista de tarefas para a
   empresa, não um bloqueio.
4. **Cobertura normativa**: roda `descoberta.cobertura` assim que há ativos, para mostrar desde o primeiro
   dia o que vale e o que ainda não está no catálogo.
5. **Licenças e condicionantes** (seção 2).
6. **Responsáveis técnicos** (seção 3).
7. **Contas e acessos**: a primeira conta da cliente (TI da empresa, senha provisória trocada no primeiro
   acesso), e as demais pela própria cliente, com escopo por unidade (seção 4).
8. **Revisão e entrada em operação**: um resumo do que está pronto e do que falta; "entrar em operação"
   grava `monitorado_desde` e a torre passa a valer. Dá para entrar com pendências; elas continuam visíveis.

Cada etapa tem estado (`pendente`, `em_andamento`, `pronta`) e o percentual vem das etapas, não de um
número inventado.

## 2. Licenças e condicionantes (obrigações próprias)

- A empresa envia o PDF da licença (LP, LI, LO, outorga, autorização). A leitura reaproveita o que existe
  (`/evidencias/leitura`, OCR, `extrator`): a IA propõe as condicionantes como obrigações próprias
  (título, prazo, periodicidade, evidência, ativo ou unidade a que se aplica) **com o trecho literal da
  licença**, e o Python confere que o trecho está, palavra por palavra, no texto do PDF (a mesma regra
  do catálogo: sem trecho conferido, não entra).
- As propostas ficam pendentes; quem aprova é o Regulatório **da própria empresa** (a plataforma só lê,
  como já ficou decidido). Aprovada, vira obrigação com `empresa` preenchida e versão vigente.
- Licença tem validade: o vencimento e o prazo de renovação (em geral 120 dias antes, conforme a licença)
  viram obrigação também.
- **Código da obrigação por empresa**: hoje `obrigacao.codigo` é UNIQUE global, e duas clientes não podem
  ter cada uma a sua "LO-01". Trocar por único em (empresa, código), com a norma pública (empresa vazia)
  também única entre si (índice sobre `COALESCE(empresa, '')`), e fazer toda busca por código levar a
  empresa (`db._obrigacao_id`, `versao`, `historico`, `propor_versao`, as entregas, a rota que busca
  `obrigacao` por código). Migração `0005`. Teste: duas clientes com "LO-01", cada uma vê e entrega só a
  dela, e a norma pública continua igual para as duas.

## 3. Responsáveis técnicos e dado pessoal

- Por ativo ou unidade: responsável técnico (nome, CPF, registro no conselho, número da ART, vigência da
  ART), coordenador do PAEBM, etc. ART vencendo vira obrigação.
- **CPF criptografado por campo** (biblioteca `cryptography`, chave em `REGULAIA_CHAVE_DADOS`, nunca no
  Git; em produção vem do Secrets Manager). A API devolve mascarado (`***.456.789-**`); ver o CPF
  inteiro é do Regulatório e da TI da própria empresa, e cada visualização vai para a auditoria.
- Dado pessoal **nunca** vai para a IA (a extração da licença recebe o texto com CPF trocado por
  marcador), nunca para o Git, nunca para a demo (na demo, só CPF fictício e marcado como fictício) e
  nunca para a conta AWS do evento (que só roda a demo).
- LGPD: exportar e apagar os dados pessoais de uma empresa (rota da TI da empresa, com auditoria).
- Empreendedor pessoa física (as linhas do SIGBM com CPF, que ficam fora da base pública): pode virar
  cliente informando os próprios dados, com o consentimento registrado (quem, quando, para quê).

## 4. Escopo por unidade (operação)

- `unidade` por empresa; `ativo` ganha a unidade; conta pode ser restrita a uma ou mais unidades.
- Gestor restrito vê só os ativos e as obrigações das unidades dele, em todas as rotas, no boletim, no
  calendário e no servidor MCP (`agente/`). Diretoria e Regulatório da empresa continuam vendo tudo.
- Testes de isolamento como os de empresa: conta da Unidade A não vê, não entrega e não comenta nada da B.

## 5. Personalização da empresa

- **Prazo interno**: a empresa pode adiantar o prazo de uma obrigação (pública ou própria), por exemplo
  "entregar 15 dias antes do prazo legal". A torre mostra os dois (interno e legal) e atrasa pelo interno,
  sem mudar a norma.
- **Normas internas**: obrigação própria sem licença (padrão corporativo, política interna), cadastrada
  pela empresa, com a mesma aprovação.
- **Responsável padrão por área** para obrigação nova.

## 6. API e front

- API: rotas para cada etapa (criar instanciação, escolher barragens do SIGBM, ativos e planilha, dados que
  faltam, licença e propostas, responsáveis, unidades e acessos, entrar em operação, LGPD), com papéis e
  escopo, auditoria e o contrato em `api/openapi.json` (regenerar `front/src/lib/api-tipos.ts`).
- Front: assistente "Nova empresa" (plataforma); página "Instanciação" da empresa com as etapas e o que
  falta; envio da licença e aprovação das condicionantes (com o trecho e a página do PDF); responsáveis
  técnicos (CPF mascarado, botão "ver" auditado); unidades e acessos. Visual igual ao resto do front.
- e2e: a curadoria cria uma empresa a partir de um CNPJ real do SIGBM (só dado público de PJ), sobe uma
  licença fictícia (gerar o PDF no teste ou em `data/exemplos/`), a TI da cliente entra, o Regulatório
  dela aprova duas condicionantes, um gestor restrito a uma unidade só vê aquela unidade, e a empresa
  entra em operação com as pendências visíveis.
- Agente MCP: ferramenta de leitura `instanciacao(empresa)` (etapas e o que falta).

## 7. Fim

Atualize README (seção nova curta, com o fluxo), `docs/ARQUITETURA.md` e `docs/PLATAFORMA.md`. No fim,
diga o que ficou de fora e por quê.

## Continuação (7 nov): sessão no Bedrock

A sessão anterior parou no limite semanal antes do primeiro commit. Esta roda no Claude Code com o
Bedrock da conta do evento (Fable 5, perfil `vx`, us-east-1).

**Estado que ficou no checkout, sem commit e sem teste** (rascunho da sessão anterior; confira antes de
aproveitar, refaça o que não estiver bom): `regulaia/campos.py` (novo), `migrations/versions/0005_instanciacao.py`
e `.sql` (novos), e mudanças em `regulaia/schema.sql`, `regulaia/schema_pg.sql`, `regulaia/db.py`,
`regulaia/banco.py` e `api/cadastro.py`.

**Mudanças de outra sessão (AWS), sem commit, que não são suas**: `infra/`, `api/Dockerfile` e
`tests/test_infra.py`. Não reverta nem inclua nos seus commits: faça `git commit -- <seus caminhos>`.
`pyproject.toml` e `uv.lock` estão livres: a dependência `cryptography` entra normalmente (`uv add`).

**Ordem**
1. **Revisão de código da base** (só leitura primeiro): `regulaia/`, `api/`, `agente/`, `front/src/`.
   Procure erro de verdade (isolamento entre empresas, papéis, auditoria, SQL, Postgres x SQLite, regra de
   negócio, front chamando rota errada), não estilo. Escreva os achados em `docs/REVISAO_CODIGO.md`, do
   mais grave ao menos, cada um com arquivo:linha e o cenário que quebra. Corrija os que forem erro de
   verdade, com teste que falha antes e passa depois, um commit por correção (ou por grupo pequeno).
2. **Instanciação**, seções 1 a 7 acima, a partir do rascunho.

**Chave de dados**: em produção `REGULAIA_CHAVE_DADOS` chega do Secrets Manager como texto alfanumérico
de 64 caracteres, não como chave Fernet. Derive a chave no código, para qualquer texto valer:
`Fernet(base64.urlsafe_b64encode(hashlib.sha256(chave.encode()).digest()))`. Sem a variável, a API sobe,
mas guardar CPF dá erro claro (nada de chave padrão no código).

**Ritmo do Bedrock**: a conta do evento pede menos de 1 pedido por segundo. Nada de subagentes do Bedrock
em paralelo: um de cada vez, ou nenhum (o paralelo fica com o DeepSeek, abaixo).

**Delegar ao DeepSeek (Hermes), em paralelo**: o DeepSeek V4.1 Flash roda pelo Hermes desta máquina, pelo
plano OpenCode Go, fora da AWS: o limite de 1 pedido por segundo é só do Bedrock, então **vários workers do
DeepSeek podem rodar ao mesmo tempo**. Você (Fable) continua sem subagentes do Bedrock em paralelo.

Chamada (cada worker em segundo plano, com a saída num arquivo de log fora do repositório):

    hermes -z "<tarefa>" --in . -m deepseek-v4.1-flash --provider opencode-go --reasoning max [--worktree]

- **Modelo fixo**: a config do Hermes tem fallback para outro modelo (`mimo-v2.6-flash`) quando o
  DeepSeek falha. Passe sempre `-m` e `--provider`, e confira no log qual modelo respondeu; trabalho de outro
  modelo você descarta ou refaz. Se o OpenCode Go limitar as chamadas, diminua o número de workers.
- **Quem faz o quê**
  - **Revisão de código: em paralelo, só leitura**, sem `--worktree`. Um worker por área (`regulaia/`, `api/`,
    `agente/`, `front/src/`), cada um devolvendo os achados com arquivo:linha e o cenário que quebra, sem
    mudar nada. Você confere cada achado no código antes de ele entrar em `docs/REVISAO_CODIGO.md`: o que
    não se confirmar, sai.
  - **Base da instanciação: só você.** Esquema, migração 0005 e o núcleo de `regulaia/instanciacao.py`;
    todo o resto depende disso, e em paralelo daria conflito.
  - **Partes sensíveis: só você.** CPF criptografado, isolamento por empresa e por unidade, papéis,
    auditoria, LGPD (exportar e apagar).
  - **Folhas: em paralelo, com `--worktree`**, depois que a base estiver com commit (a worktree sai do
    último commit, então o que não tiver commit não vai junto). Exemplos: páginas do front, validação do
    modelo CSV, a ferramenta MCP `instanciacao`, rascunhos de teste. Uma tarefa fechada por worker, com os
    arquivos nomeados e o que entregar; dois workers nunca no mesmo arquivo (`api/openapi.json` e
    `front/src/lib/api-tipos.ts` você regenera no fim).
- **Regras em toda tarefa**: não fazer commit nem push, não mexer em `infra/`, não ler `.env` nem nada em
  `data/raw/` (lá está o CSV do SIGBM com CPF), não mandar dado pessoal para lugar nenhum.
- **Aceitar**: você lê o diff de cada worker, traz para o checkout principal (uma worktree por vez), roda
  ruff e a suíte, e só então faz o commit. Worktree aproveitada ou descartada, você remove
  (`git worktree remove`). Quem faz commit é sempre você.

**Migração 0005**: quando estiver com commit, empurrada e com o CI verde, escreva isso na seção
"Instanciação" de `docs/PLATAFORMA.md` (a sessão AWS espera para refazer a imagem e o deploy).
