# Review como jurado: Mitra (Desafio 02)

Data: 08/11/2026, 12h. Revisado: o código no commit `d65ce84` (`main` = `plataforma`), as verificações rodadas na máquina e o site no ar (<https://d1wj3tlr6ee301.cloudfront.net>), percorrido com cada persona a partir da Caixa de entrada.

## Verificações (resultado real)

| Verificação | Resultado |
|---|---|
| `uv run pytest` (raiz) | **684 passaram, 10 pulados**, 2 min 31 s |
| `npm run lint` (front) | 0 erros, 1 aviso, num arquivo **não versionado** (`front/e2e/timelapse/roteiro.mjs`, `writeFileSync` sem uso). O CI roda com `--max-warnings 0`: quem versionar esse arquivo precisa tirar o import |
| `npm run typecheck` | passou |
| `npm test` (vitest) | **42 passaram** (7 arquivos) |
| `npm run build` | passou, 21 rotas estáticas |
| `npm run tipos:conferir` | falha **só no Windows**: o arquivo gerado tem CRLF (`core.autocrlf=true`); sem o `\r` é idêntico. No CI (Linux) passa |
| CI no GitHub (`d65ce84`) | CI e Deploy verdes em `main` e `plataforma` |
| Site no ar | todas as páginas respondem 200. A API leva de 0,14 a 0,9 s (o painel, com 344 KB, é o mais lento). O Assistente respondeu em 7 s pelo Bedrock, US$ 0,024, com a conferência ok |

## Nota de hoje

| Critério | Peso | Nota | Por quê |
|---|---|---|---|
| Execução técnica | 30% | **4,5** | Engenharia acima da média de hackathon: 684 testes, CI com SQLite, Postgres, e2e e imagem, deploy por OIDC em ECS Fargate, RDS e CloudFront, Bedrock no ar com troca automática de modelo, teto de gasto, CSRF, auditoria e CPF cifrado. Perde ponto porque a tela central mostra `opencode:deepseek-v4.1-flash@high` e "Conferido pelo Python": um jurado técnico lê DeepSeek por gateway de terceiro num produto que promete Claude no Bedrock |
| Resolução do problema | 20% | **4,5** | O golden test aparece de verdade: Res. 245 na Caixa, antes e depois da OB-01, trecho literal, "as outras 23 ficam iguais", e a FIR com anomalia que abre a ISE de 24 h. Perde ponto porque o roteiro manda aprovar na visão Diretoria, onde não há botão Aprovar: o apresentador trava no momento-chave |
| Mercado e viabilidade | 20% | **3,5** | Números com fonte (SIGBM 05/11/2026, 85 autos de embargo, Deliberação 436) e premissas declaradas. É frágil em três pontos: o SAM de R$ 12,4 mi é pequeno para investidor, o preço não foi validado com cliente (nenhuma entrevista feita, PREP.md) e não há economia da unidade (por que R$ 1.500 por barragem) |
| Inovação | 15% | **4,0** | Regra antes de IA, trecho literal conferido, obrigação por ativo com versão e aprovação, curadoria que aprova uma vez para todas as clientes, documento da operação que dispara obrigação. É diferente de GRC e de monitoramento legal, mas a tela fala "IA" e "Python" onde deveria mostrar o resultado de negócio |
| Pitch | 15% | **3,5** | Roteiro bem amarrado aos critérios, cronometrado e com números testados. Mas está desatualizado: diz "72 obrigações de 5 normas" (hoje são 101 de 9), "mais de 170 testes" (hoje 547 funções e 694 casos), ainda condiciona a frase do Bedrock a "se estiver pronto no domingo" e manda clicar em Aprovar numa tela sem o botão |

**Nota ponderada hoje: 4,08.** (0,30 × 4,5 + 0,20 × 4,5 + 0,20 × 3,5 + 0,15 × 4,0 + 0,15 × 3,5)

## Achados, por ganho de nota por hora

### Bloqueia a demo (corrigir já)

| # | Achado | Critério | Evidência | Correção | Esforço | Risco para a demo |
|---|---|---|---|---|---|---|
| D1 | O roteiro manda aprovar a Res. 245 na visão Diretoria, mas norma pública só a Curadoria Mitra decide: na Diretoria não há botão Aprovar | Pitch, Problema | No ar, `/regulatorio/mudancas/` na Diretoria mostra "Quem decide esta mudança: curadoria Mitra" e nenhum botão; na Curadoria aparecem Aprovar, Rejeitar e Corrigir e aprovar. `docs/PITCH.md:74`, `docs/ROTEIRO_DEMO.md:22-25` | O roteiro troca a persona para **Curadoria Mitra** antes de aprovar, e a narração vira argumento: "a curadoria aprova uma vez e vale para todas as clientes" | 10 min | Nenhum (só docs) |
| D2 | A tela mostra o ID do modelo: `opencode:deepseek-v4.1-flash@high (cache)` em Mudanças e no Radar, e o ID cru do Bedrock (`us.anthropic.claude-…`) no Assistente, que não é o modelo que README e pitch citam (Haiku 5.5). Um ID de provedor não é texto de produto | Execução, Inovação | `front/src/app/(torre)/regulatorio/mudancas/page.tsx:92`, `radar/page.tsx:200`, `pergunte/page.tsx:39` | Tirar o ID do modelo da interface; o registro medido fica no banco e nos docs. Manter custo e confiança | 20 min | Baixo |
| D3 | "Conferido pelo Python" no cartão da Res. 245, e "Python conferindo", "conferida pelo Python" e "o Python confere" no Radar, no Leitor, em Licenças e em Como funciona. O AGENTS.md proíbe exatamente isso | Execução, Pitch | `mudancas/page.tsx:86`, `radar/page.tsx:78-79,138,164`, `components/leitor.tsx:87`, `licencas/page.tsx` (8 lugares), `sobre/como-funciona/page.tsx:67,95` | Trocar por "Conferência automática" e pelo resultado: "o trecho existe no ato", "as datas aparecem no trecho" | 20 min | Baixo |
| D5 | Todo deploy apaga a análise da Res. 245 no ar: o cartão perde o "Por quê", a conferência e a linha "Muda 1 obrigação… as outras 23 ficam iguais" até alguém clicar em **Recriar demo**. Achado depois do deploy de `32c36fe`: `/empresas/7/mudancas` passou a devolver `tamanho: null` | Execução, Problema | `api/rotas/regulatorio.py:207-208` lê `data/radar_demo.json`, que só `demo.preparar` grava (`mitra/demo.py:201`), e o arquivo está fora do Git e da imagem (`.gitignore:31`, `.dockerignore`). O container novo nasce sem ele | Na hora: **Recriar demo** depois de cada push em `main`. De vez: guardar a análise no banco (ou no S3 da pilha) em vez de um arquivo do container, ou regenerá-la do cache ao subir, numa thread, só na AWS | 5 min (operacional); 1 h (de vez) | Nenhum (operacional); médio (de vez, mexe na subida da API) |
| D4 | O pitch tem números que a tela e o repositório desmentem: "72 obrigações de 5 normas" (hoje 101 obrigações de 9 normas, contadas pela mesma função do teste), "mais de 170 testes" (547 funções e 694 casos no pytest, mais 42 no front e 11 de ponta a ponta) e a frase do Bedrock condicionada ("só se o adaptador estiver pronto"), que já está no ar | Pitch, Execução | `docs/PITCH.md:73,84,87`, `docs/ROTEIRO_DEMO.md:7`, `tests/test_documentacao.py:196,219-222` (o 72 está escrito à mão no teste) | Atualizar PITCH e ROTEIRO, e fazer o teste calcular obrigações e normas em vez de conferir um literal | 15 min | Nenhum |

### Sobe nota

| # | Achado | Critério | Evidência | Correção | Esforço | Risco |
|---|---|---|---|---|---|---|
| S1 | "Começa a valer em" (o AGENTS.md pede "A partir de") no cartão da Caixa, na tabela de Mudanças e em Responsáveis | Pitch (texto) | `api/rotas/regulatorio.py:28`, `mitra/torre.py:283,419`, `responsaveis/page.tsx:224` | Rótulo "A partir de"; atualizar testes que conferem o texto | 15 min | Baixo |
| S2 | "IA ligada · gasto hoje…" (o AGENTS.md cita "IA está desligado" como o que não fazer), "Foram à IA 6 candidatas", "Obrigações enviadas à IA", "a IA nem foi chamada", "O que cobra, pela IA" | Execução, Inovação | `components/moldura.tsx:268`, `radar/page.tsx:22,31,63,183,200`, `regulatorio/cobertura/page.tsx:35,93,99`, `normas-candidatas/page.tsx:63,74`, `api`/`mitra` (texto "Foram à IA") | Falar do resultado: "Análise automática ativa", "6 obrigações analisadas", "nenhuma obrigação é afetada: sem custo de análise" | 30 min | Baixo |
| S3 | A persona Regulatório não está no seletor da conta de teste. No ar as senhas ficam no Secrets Manager, então o jurado só alcança Diretoria, gerências, TI e Curadoria: uma das 5 personas do produto fica invisível | Execução, Problema | `api/rotas/auth.py:53` (lista de visões), `api/seguranca.py:167-188` (`escopo_da_conta`); o seletor no ar não tem "Regulatório" | Incluir "Regulatório (todos os ativos)" nas visões da conta de teste, com o mesmo escopo do papel `regulatorio`, e testes de acesso | 25 min | Médio-baixo (regra de acesso, coberta por teste) |
| S4 | Assistente: datas em ISO no meio do português ("venceu em 2026-10-15") e custo com ponto ("US$ 0.0236") | Execução, Pitch | No ar, resposta à pergunta "O que está atrasado na B3…"; `pergunte/page.tsx:39` | Formatar no front: data DD/MM/AAAA no texto exibido, custo com vírgula (a conferência roda antes, no servidor) | 15 min | Baixo |
| S5 | O README não diz ao jurado o que clicar: não tem um caminho de 2 minutos com as personas e o golden test | Pitch, primeira impressão | `README.md:1-12` | Seção curta "Avaliar em 2 minutos" no topo: Entrar na demo, Caixa, Ler documento, Mudanças (Curadoria aprova), Assistente, Regulatório e Gestor no seletor | 10 min | Nenhum |
| S6 | Subtítulos longos e técnicos passam de duas linhas (Licenças, Radar, Usuários), e os tipos de licença aparecem sem acento ("autorizacao", "alvara") | Pitch (texto) | No ar, `/licencas/`, `/regulatorio/radar/`, `/usuarios/` | Subtítulos de uma ou duas linhas; rótulo de exibição para cada tipo | 20 min | Baixo |
| S7 | No slide de mercado falta a economia da unidade: por que R$ 1.500 por barragem por mês e quem paga | Mercado | `docs/PITCH.md:78-91`; a hipótese de custo já existe em `docs/ANALISE_MERCADO.md` (seção "Quanto o problema custa para uma empresa") | Uma linha no slide 7 ligando o preço ao custo do trabalho manual e ao risco de embargo, marcada como hipótese | 15 min | Nenhum |

### Polimento

| # | Achado | Evidência | Correção | Esforço |
|---|---|---|---|---|
| P1 | Rótulos em caixa de título na Caixa ("Cadastro Incompleto", "Revisões Pendentes") e "Atrasada" no singular com 4 itens | No ar, `/caixa/` | Caixa de frase e plural | 10 min |
| P2 | "Por gatilho 225" no topo da Caixa confunde: 225 das 290 linhas são obrigações que só valem se algo acontecer | No ar, `/caixa/` | Rótulo "Sob condição", com a dica explicando | 10 min |
| P3 | `tipos:conferir` falha no Windows por CRLF | Verificações acima | `.gitattributes`: `front/src/lib/api-tipos.ts text eol=lf` | 5 min |
| P4 | O seletor de arquivo nativo aparece cortado ("Nenhum ar...vo escolhido") | No ar, `/caixa/` | Esconder o input nativo atrás do botão | 10 min |
| P5 | O Assistente mostra a citação "> …" com o sinal literal dentro de item de lista | No ar, `/pergunte/` | Tratar citação dentro de item no renderizador | 15 min |
| P6 | As telas Licenças e Responsáveis estão vazias na demo da Serra Azul e parecem inacabadas | API no ar: `/empresas/7/licencas` e `/responsaveis` devolvem lista vazia | Semear uma licença e dois responsáveis na demo, sem mudar os números do pitch (exige rever os testes de números) | 45 min |
| P7 | Em Mudanças, o selo "visão da plataforma: só leitura" começa em minúscula | No ar, Curadoria | Caixa de frase | 2 min |
| P8 | O README está em inglês e o produto e o pitch em português; a banca é brasileira | `README.md` | Decisão do time; se trocar, o README vira português | 30 min |

## As 5 perguntas mais difíceis (e a resposta sugerida)

O pitch não tem perguntas, mas estas aparecem na mentoria, na conversa depois do pitch ou na cabeça do jurado enquanto ele assiste.

1. **"A tela mostra DeepSeek, o README diz Claude. Para onde vão os dados da mineradora?"** O provedor é configuração, não código. Na AWS a análise roda no Amazon Bedrock, dentro da conta, e no ar já responde por Claude; o que está gravado na demo foi medido em desenvolvimento com um modelo mais barato e ficou como registro. A mineradora pode usar a própria conta (traga sua chave), e CPF nunca vai para a IA: fica cifrado por campo.
2. **"Se a torre errar um prazo e a barragem for embargada, de quem é a culpa?"** A torre não substitui o responsável técnico. Cada obrigação cita o trecho literal, um teste confere os 66 trechos contra o texto oficial, e nada muda sem uma pessoa aprovar, com trilha de auditoria. A conferência já achou um "≥" que virava ">" no site da ANM e nove obrigações que faltavam no cadastro.
3. **"R$ 12,4 milhões de SAM é pequeno. Por que isso vira uma empresa grande?"** As barragens são a porta de entrada, não o teto. O motor é por ativo e já roda vaso de pressão (NR-13), unidade (NR-22), licença, saúde e obra. A escada vai das 461 barragens da PNSB para as 8.086 mineradoras que pagam CFEM e para as 29.761 barragens do país, e as consultorias que assinam a declaração de estabilidade são o canal.
4. **"Vocês falaram com algum cliente? De onde sai R$ 1.500 por barragem?"** É premissa, e o pitch diz isso. A conta parte do custo do trabalho de hoje (cerca de 60 entregas com data por barragem por ano, em planilha) e do custo de um embargo. A validação é o próximo passo: 10 entrevistas e 3 pilotos pagos antes de 02/08/2027, quando a Res. 220 entra em vigor.
5. **"O que impede a Sigalei, a Verde Ghaia ou um GRC de fazer isso?"** Eles respondem o que mudou na lei. A Mitra responde, por ativo, o que entregar, até quando e se já foi entregue, lendo o documento que comprova. O fosso é o catálogo curado com trecho literal, o modelo de ativo, o leitor de evidência e a aprovação que vale para todas as clientes; refazer isso é trabalho de curadoria, não de software.

## Nota projetada

Com "Bloqueia a demo" e "Sobe nota" feitos:

| Critério | Hoje | Projetada |
|---|---|---|
| Execução técnica (30%) | 4,5 | 4,8 |
| Resolução do problema (20%) | 4,5 | 4,7 |
| Mercado e viabilidade (20%) | 3,5 | 3,8 |
| Inovação (15%) | 4,0 | 4,3 |
| Pitch (15%) | 3,5 | 4,2 |
| **Ponderada** | **4,08** | **4,42** |

O teto do critério de mercado depende de uma coisa que código não resolve: falar com uma mineradora ou com uma consultoria de barragem antes do pitch, nem que seja por telefone, e citar isso no slide 7.

## Andamento das correções

Atualizado a cada commit, pela ordem da lista.

| # | Situação |
|---|---|
| D1 | Feito (`439b294`): pitch e roteiro trocam para a Curadoria Mitra antes de aprovar |
| D2 | Feito (`914613b`): nenhum ID de modelo na interface (Mudanças, Radar, Assistente, Licenças) |
| D3 | Feito (`914613b`): "Conferência automática" no lugar de "Python" em todas as telas |
| D4 | Feito (`439b294`): 131 obrigações de 11 normas e "mais de 500 testes", calculados pelo teste; frase do Bedrock firme. O teste que conta as palavras do pitch, citado no PITCH.md mas apagado num commit anterior, voltou |
| D5 | Feito: o resumo de cada análise vai para a tabela `analise_ato` (migração 0009), e o job do radar guarda o dele também, então um ato real ganha o mesmo "Por quê" no cartão. O arquivo `data/radar_demo.json` saiu. Depois do primeiro deploy com a tabela, um **Recriar demo** a preenche, e os deploys seguintes não apagam mais |
| S1 | Feito (`914613b`): "A partir de" e "Até" nos rótulos da API, no boletim e em Responsáveis; "Entra em vigor" no .ics |
| S2 | Feito (`914613b`): "Análise automática ativa", "Das 6 obrigações analisadas", triagem em vez de "a IA achou" |
| S3 | Feito (`8821004`): "Regulatório" no seletor da conta de teste, com teste de acesso |
| S4 | Feito (`914613b`): datas DD/MM/AAAA e custo com vírgula no Assistente |
| S5 | Feito: seção "Try it in two minutes" no README |
| S6 | Feito (`914613b`): subtítulos curtos em Licenças, Radar, Usuários e Normas candidatas; "Outorga", "Autorização", "Alvará" |
| S7 | Feito: a conta de quem compra no slide 7, marcada como hipótese |
| P1 | Feito em parte (`914613b`): "Cadastro incompleto" e "Revisões pendentes". "Atrasada" fica no singular porque é também o status de cada obrigação |
| P2 | Não feito: "Por gatilho" é o nome do status em toda a torre e nos docs; trocar só o cartão criaria dois nomes para a mesma coisa |
| P3 | Feito (`be9f652`): `.gitattributes` com `eol=lf` para `api-tipos.ts`; `tipos:conferir` passa no Windows |
| P4 | Feito (`be9f652`): botão "Escolher arquivo" e o nome do arquivo, sem o texto nativo cortado |
| P5 | Feito (`be9f652`): citação "> …" do Assistente vira citação, no item da lista ou solta |
| P6 | Não feito: responsável com ART vira obrigação (`mitra/responsaveis.py`) e licença nova cria condicionantes, então semear os dois muda os números da Caixa que o pitch cita e o teste confere. Fica para depois do evento |
| P7 | Feito (`be9f652`): "Visão da plataforma: só leitura" |
| P8 | Decisão do time (README em inglês) |
