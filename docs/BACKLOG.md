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
- [x] Quem aprova vê a agenda em português ("quinzenal, até o fim de cada quinzena"), não o código; confiança com vírgula; título do ato colado legível
- [x] Hoje: dado faltando em português (com o nome do campo entre parênteses); entrega única mostra a última evidência
- [x] Muitos períodos pendentes viram um intervalo no boletim e na tabela; obrigação herdada da Res. 95 não repete a data
- [x] Leitor de evidência: acionamento diz o nome da obrigação aberta e o documento que a encerra; aviso de atraso com maiúscula
- [x] Leitor de evidência diz por que não achou o ativo (código não cadastrado, dois ativos citados); problemas com maiúscula
- [x] .streamlit/config.toml: upload até 20 MB e sem estatística de uso também fora do Docker
- [x] ARQUITETURA lista os 8 documentos de exemplo com o que cada um mostra; teste impede a lista de ficar velha
- [x] Teste confere o funil de agosto (7.884 → 825) da tela e dos documentos contra o ZIP do DOU
- [x] "Por norma" explica por que a Res. 220 ainda não aparece; comandos do README conferidos
- [x] Viagem no tempo avisa que o histórico da demo para em 07/11/2026 (explica os atrasos de 2027); pergunta no roteiro
- [x] Teste: aprovada a Res. 245, OB-01 e NR-22 vencem juntas no painel (26/12/2029); sem aprovação, nada muda
- [x] Clone novo conferido de novo: 184 passam (10 pulados); com os textos oficiais, 190 (4 pulados); README atualizado
- [x] OB-01 com título de ação ("Retirar da ZAS os trabalhadores das áreas de lavra..."); análise da Res. 245 refeita com a IA (US$ 0,0011, mesmo resultado) e cache da demo exportado
- [x] Cartão da mudança diz, pelos dados, quantas obrigações mudam e quantas ficam (não depende do texto da IA)
- [x] PREP.md atualizado (24 obrigações da Res. 220, 21 da Res. 95 conferidas); teste dos números inclui o PREP
- [x] Roteiro: pergunta sobre a data da notícia da ANM (31/12) contra o ato (26/12)
- [x] uv.lock conferido; teste do .dockerignore: a imagem leva o que a demo lê ao iniciar e deixa de fora .env, dados brutos e bancos
- [x] Ato colado ganha o mesmo cartão em Mudanças (porquê, conferência, escopo); a conferência só lista o que o Python checou de fato
- [x] README: tabela "O que os testes garantem", com teste que impede citar teste inexistente
- [x] Mapa dos ativos cabe inteiro num projetor de 1280 px (colunas de texto com largura fixa)
- [x] Conferidas todas as abas em 1280 px: rótulo do Mercado encurtado ("Empresas na PNSB", com explicação no ícone de ajuda)
- [x] README com duas capturas da torre (Hoje e Mudanças), teste que confere toda imagem citada; sem botão "Deploy" do Streamlit na tela; botão "Res. 220" não corta em 1280 px
- [x] Conferidas as seis abas no tema escuro (tudo legível); no Mercado, rótulo "Outros ativos por barragem" encurtado (detalhe no ícone de ajuda) para os três campos ficarem alinhados
- [x] Teste do roteiro: todo botão/aba em negrito existe no app e todo PDF citado existe nos exemplos; fala de abertura nomeia as 5 normas
- [x] PDF que não abre vira frase para o operador ("protegido por senha: mande uma cópia sem senha" / "não parece um PDF válido"), sem nome de exceção na tela; PDF só com senha de dono abre normalmente (teste)
- [x] Montagem da demo 2x mais rápida (2,7 s -> 1,4 s; suíte 73 s -> 52 s): banco recriável montado sem esperar o disco a cada commit, padrão restaurado depois (teste)
- [x] Colunas de status do mapa e da tabela "Por norma" com o nome ao passar o mouse (não depender só da cor); cabeçalho com texto foi testado e cortava os nomes em 1280 px
- [x] Calendário .ics: lembrete no dia em que a obrigação fica amarela na torre (5 dias antes para quinzenal/mensal, 30 para o resto), sem lembrete para atrasada; prazos não marcam o gestor como ocupado; validado com a biblioteca icalendar
- [x] Boletim não contradiz a torre: a seção de 30 dias mostra quantas já estão em amarelo (3, igual ao topo da aba Hoje) e marca cada uma com 🟡 (teste)
- [x] Custos citados (ARQUITETURA e roteiro: Res. 95 US$ 0,065, NR-13 US$ 0,045, NR-22 US$ 0,009; análise por ato entre US$ 0,0005 e 0,002) conferidos contra o que a IA cobrou, com teste
- [x] Boletim e plano de transição em PDF (regulaia/pdf.py, reportlab já no projeto): emoji vira palavra ou sai, travessão e acentos ficam, rodapé com página; PDF em cache na interface (sem custo por clique); "1 obrigação" no singular
- [x] Corrigido antes de chegar à nuvem: reportlab era só de dev e a imagem (uv sync --no-dev) quebraria o boletim em PDF; agora é dependência de produção, pandas declarado, e um teste confere que tudo o que o app importa está em [project].dependencies. Imagem reconstituída sem Docker num diretório limpo: seis abas sem erro e os dois PDFs baixam
- [x] Preparo para o Linux da imagem: teste confere que todo caminho citado no código bate letra por letra com o disco (Windows não distingue maiúscula), sem nomes que só diferem na caixa e sem acento em nome de arquivo
- [x] Fins de linha: tudo LF no Git (o Linux da imagem lê igual); PNG marcado como binário no .gitattributes
- [x] Boletim junta a mesma obrigação com o mesmo prazo em vários ativos numa linha ("B1, B2, B4 · Preencher as FIR…"): a seção de 30 dias da diretoria cai de 9 para 5 linhas; as contagens seguem por ativo
- [x] Res. 95: monitoramento automatizado e vídeo-monitoramento (R95-17, R95-18) marcados como "Contínua" (eram "Por evento"), igual às equivalentes da Res. 220 na transição. Mudou o prompt da Res. 245: análise refeita com o modelo (mesmo resultado, só a OB-01; US$ 0,0023), cache exportado e conferido sem chave num diretório limpo; o "por quê" novo cita 22/04/2027, que está no ato (art. 87, I). Faixa de custo por ato na documentação atualizada para US$ 0,0005 a 0,003; captura de Mudanças refeita
- [x] Decisões e histórico com horário de Brasília (dd/mm/aaaa hh:mm), não UTC cru; a data muda junto perto da meia-noite (teste). Conferido no navegador: aprovar a Res. 245 mostra a decisão e as duas versões da OB-01
- [x] Botão e aviso de registro em português ("Registrar evidência: FIR de B3 · 1ª quinzena de outubro/2026"); o código da obrigação e do período ficam na dica. Fluxo da FIR com anomalia conferido no navegador: abre a ISE da B2 (atrasadas 4 -> 5)
- [x] Ato colado no Radar: título para no ano ("Portaria nº 123, de 3 de novembro de 2026"), sem engolir o começo do texto nem rebaixar nomes próprios; sem candidata, um aviso só (custo zero). Conferido no navegador
- [x] Teste da promessa "cada gestor vê só os seus ativos": para cada gestor, nenhuma aba cita ativo de outro (texto, tabelas, títulos); conferido também no navegador (Usina e Geotecnia) e com mutação (mostrar todos os ativos faz o teste falhar)
- [x] Rejeitar conferido no navegador (versão 1 continua vigente, a 2 fica registrada como rejeitada); histórico diz "veio do cadastro inicial" em vez de "decidida por carga inicial"
- [x] Celular (390 px): sem rolagem lateral; os 5 números do topo em duas linhas (antes ocupavam a tela inteira), rótulo sem corte e título menor. CSS só abaixo de 640 px: o desktop fica igual (conferido nas duas larguras)
- [x] PREP.md em dia: XML mensal do DOU baixado e lido (7.884 atos), listagem conferida contra o XML, repositório e teste-ouro marcados como feitos; o pitch de 5 min continua em aberto (roteiro da demo de 3 min pronto)
- [x] Rascunho do pitch de 5 min (docs/PITCH.md): problema com a Res. 245 (notícia diz 31/12, ato diz 26/12), por que agora, demo curta, viabilidade, mercado e premissas; teste confere cada número contra o SIGBM, as premissas da aba Mercado e a demo
- [x] PDFs gerados só no clique (download_button com partial): mudar a data ou o gestor não paga mais reportlab; rerun estável em 0,34-0,36 s. Downloads conferidos no navegador
- [x] Histórico inteiro do Git (114 commits) varrido: nenhum .env, export bruto do SIGBM, banco, chave de API ou CPF; .env.example sempre com valores vazios. Teste impede versionar isso daqui em diante
- [x] Leitor de evidência aceita mais formatos de data: 03.11.2026, 03-11-2026, 3/11/2026 e "realizada em"; ano com 2 dígitos e data impossível não são adivinhados (11 casos de teste). A mesma leitura vale para a data de envio (aviso de atraso) e para a conferência de datas do radar
- [x] Leitor de evidências reconhece o ativo também pelo código depois de rótulo ("Barragem B3", "Ativo: B3"), pelo nome sem o tipo ("Córrego Fundo") e pela tag do vaso ("VP-101"); código solto continua sem valer
- [x] Código desconhecido depois de rótulo ("Barragem B9") também é apontado como "não é ativo cadastrado"; a mensagem genérica passa a mostrar o formato "Ativo: B3"
- [x] Gatilho de ISE lê mais formatos: "EC 3 = 5", "EC-3 = 5", "EC3 (5)" e "Maior pontuação: 10" (antes passavam em branco, e a ISE obrigatória não abria); "pontuação 6" solta continua sem valer
- [x] ARQUITETURA descreve as regras atuais do leitor: jeitos de citar o ativo, formatos de data e de colunas EC aceitos e o que não é adivinhado
- [x] Gestor não registra documento de ativo de outro gestor (aviso diz quem registra; sem botão nem prévia do que abriria); a leitura mostra as colunas EC lidas do Quadro I.8 para conferência
- [x] README e roteiro contam que um gestor não dá baixa no ativo de outro (pergunta pronta para a banca, com o PDF de exemplo)
- [x] Quando a IA deduz o ativo (o documento não cita código nem nome inteiro), a leitura avisa e o aviso fica gravado na evidência; ícone 🤖 em vez do relógio de atraso
- [x] Triagem lê mais jeitos de citar norma e artigo: "Res. ANM nº 95", "n.º 95", "Res. 95/2022", "artigo 27" e listas ("arts. 17, 18 e 19" viram os três); o § não vira artigo. Conferido: os 14 atos da amostra do DOU e o ato fictício mantêm as mesmas candidatas, então o cache de IA continua valendo
- [x] Análise de mercado densa (docs/ANALISE_MERCADO.md, entrega do hackathon): embargos, multas, déficit de fiscalização, segmentação do SIGBM por grupo e dano potencial, receita com sensibilidade, expansão (SNISB, CFEM), concorrência (Sigalei, Verde Ghaia, Ius Natura, LegisMap, EHS globais), diferencial, modelo de negócio, riscos e 20 fontes. Números do SIGBM em data/mercado_sigbm.json (só agregados) e conferidos por teste; PDF sai por python -m regulaia.pdf, que agora entende tabela, subseção e lista numerada
- [x] Pitch reescrito (docs/PITCH.md) para 5 min sem perguntas: 10 slides com tela, fala e tempo; abre com 223 de 461 barragens da PNSB já embargadas, vídeo da demo no meio com narração ao vivo, mercado pelos 59 grupos de 2 a 9 barragens, concorrência e próximos passos; teste confere embargo, grupos, funil 908 → 461 → 243, número de testes e limite de 750 palavras
- [x] Lacunas do documento complementar (04/11) que não dependem da AWS: quem aprova pode corrigir a proposta da IA antes de aprovar (fica registrado proposto x aprovado); PDF escaneado detectado por página, com OCR pelo Textract quando ligado e aviso claro quando não (exemplo FIR_B3_2026-10-1Q_escaneada.pdf); adaptadores Bedrock (Converse, < 1 req/s), Textract e S3 prontos e testados com clientes falsos, ligados só por .env; diagrama da arquitetura AWS no README com o que falta fazer no evento; análise de mercado com TAM/SAM/SOM, custo do problema por empresa e Stance, Nomos e Legalbot (ProcTracker sem fonte pública)
