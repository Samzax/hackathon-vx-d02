# Backlog de trabalho autônomo (noite de 5 para 6/11/2026)

Autorizado pelo usuário: seguir sozinho com o escopo combinado (torre com Hoje / Transição /
Mudanças, Res. 95 + Res. 220 + NRs + licença fictícia), fazendo commit e push no repositório
privado, sem linhas de coautoria. Nada fora do repositório (sem mensagens, compras, contas).

Regras: rodar `uv run pytest` antes de cada commit; IA só com DeepSeek V4.1 Flash (OpenCode Go)
ou Haiku/Sonnet; nada de Opus; chaves só no `.env`; o CSV bruto do SIGBM (tem CPF) nunca vai pro Git.

## Fila (marcar [x] ao terminar)

- [x] Curadoria da Res. 95/2022 -> `curadoria/res95_2022.csv` -> `cadastro/res95_2022.csv`
      (códigos R95-01..; ver `data/historico_serra_azul.json`, que já usa R95-01, -02, -05, -06, -09, -16;
      vigência 2022-02-07 a 2027-08-01; incluir obrigações de emergência/PAEBM dos arts. 23-45)
- [x] Curadoria da NR-13 -> `cadastro/nr13.csv` (tipo equipamento; N13-03 = exame externo periódico,
      N13-04 = exame interno periódico, conforme a Tabela 2 e a categoria do vaso; conferir no texto)
- [x] Testes da torre (`tests/test_torre.py`): B3 com FIR atrasada, B4 com dado faltando,
      L1 com renovação vencendo, transição 95 -> 220, Res. 245 pendente só na B2
- [x] Teste de fumaça da interface com `streamlit.testing.v1.AppTest`
- [x] Revisar a interface rodando de verdade (preview) e corrigir o que estiver feio ou confuso
- [x] Transição: mostrar as obrigações equivalentes (ex.: RPSB na 95 e na 220) em vez de só "sai/entra"
- [x] Mudanças: ao aprovar a Res. 245, a OB-01 da B2 sai da transição de 2027 e vai para 2029
- [x] NR-22 Portaria MTE 105/2026: não serve como mudança pendente (é de jan/2026, já no texto da NR-22),
      mas mostra MTE e ANM com a mesma data para a ZAS (26/12/2029): virou cadastro N22-ZAS1/2 e linha do tempo
- [x] Leitor de evidência (FIR em PDF -> período e campos): regra + IA conferida, gatilho de ISE, envio na aba Hoje
- [x] Atualizar README e docs/ARQUITETURA.md com a torre, agenda, curadoria e custos medidos

## Extras feitos na mesma noite

- [x] Demo roda num clone novo sem `.env` (cache da IA versionado em `data/cache_ia_demo.json`, com teste)
- [x] Radar mostra o custo original de cada análise mesmo vinda do cache
- [x] PDFs/zips como binário no Git (`.gitattributes`)
- [x] Roteiro da demo de 3 minutos: `docs/ROTEIRO_DEMO.md`
- [x] Teste da interface para o envio de evidência (FIR comum e FIR com anomalia)
- [x] Boletim da semana por gestor (Markdown) e períodos em linguagem de gente
- [x] Calendário .ics com os vencimentos de cada gestor
- [x] Aba Mercado (SIGBM com fonte + premissas ajustáveis)
- [x] Leitor de evidência para relatório de vaso NR-13 (externo/interno); PDF escaneado com aviso
- [x] Histórico de cada obrigação (versões, origem, quem decidiu)
- [x] Visão por norma e órgão na aba Hoje
- [x] Aba Como funciona (diagrama com números vivos)
- [x] Recibo do EIR com aviso de entrega fora do prazo; upload de arquivo inválido sem quebrar a tela
- [x] Plano de transição para download (o que continua, o que é novo, o que não tem equivalente)
- [x] Troca de norma não zera a contagem de RPSB (herda a última execução equivalente)
- [x] Viagem no tempo com botões (Demo, Res. 220, ZAS)
- [x] Varredura da interface: 8 visões x 3 datas sem erro; condicionantes da licença não somem após a validade
- [x] Dockerfile para AWS (App Runner/ECS/EC2); app conferido só com dependências de produção
- [x] Tema claro conferido; diagrama legível nos dois temas
- [x] Cada ativo mostra o que comprova (últimas evidências)
- [x] Radar: teste com um ato colado (regra -> IA -> Python -> aprovação), com exemplo fictício no cache
- [x] Agenda semanal; mudança de periodicidade aprovada leva a agenda junto (regra, não IA)
- [x] Cadastro da Res. 220 conferido contra o texto oficial: trecho literal em cada obrigação, ≥ sublinhado do ANMlegis, 9 obrigações que faltavam (arts. 20 §2 e §3, 38 §4, 42, 46 §4, 49, 54 §2, 56 §1, 59)
- [x] ISE pela norma do dia: pontuação 10 (Res. 95) ou EC1/EC3/EC4/EC5 = 5 (Res. 220), com FIR de exemplo no modelo novo
- [x] Todos os trechos do cadastro (Res. 95, Res. 220, NR-13, NR-22) conferidos por teste contra o texto oficial; `regulaia.fontes` baixa os textos
- [x] Leitor de evidência cobre todas as obrigações periódicas do cadastro (RCO, PGRBM, PAEBM, NR-22, condicionantes da licença); tipo pelo título
- [x] Anomalia registrada abre a ISE do ativo (prazo de 24 h) até o relatório da inspeção encerrar; na Res. 220 abre também o registro no SIGBM (recibo do EIE encerra)
- [x] Código sem avisos do ruff (F, E9, B); teste de que a curadoria regera o cadastro da Res. 95, NR-13 e NR-22
- [x] Regras com "ou"; plano de transição diz quando o tema existe na norma nova mas não vale para o ativo
- [x] ISE aberta aparece no calendário .ics e no boletim com o motivo; citações da Res. 220 sem a norma repetida
- [x] Teste confere os números do topo citados no roteiro da demo
- [x] Documentação descreve certo o art. 7 §1 da Res. 220 (quem pode ficar na ZAS), não "mapa de inundação"
- [x] Boletim e tabela da torre dizem "sem evidência registrada" em vez de repetir a data de vencimento; coluna Dispositivo sem a norma repetida
- [x] Pendência de entrega única mostra a data da última evidência (ex.: PGRBM de 30/06/2025 vira atrasado na Res. 220)
- [x] Transição: coluna da Res. 220 sem a norma repetida; plano (.md) cita a norma dos dois lados; RPSB por alteamento com periodicidade legível (curadoria)
- [x] Mudanças e Radar: nome do ato sem as maiúsculas do DOU, custo com vírgula, data da decisão em DD/MM/AAAA, "vale a partir de"; teste garante a linha "Conferido pelo Python"
