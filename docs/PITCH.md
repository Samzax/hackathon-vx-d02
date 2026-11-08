# Pitch (5 minutos, sem perguntas)

Roteiro slide a slide para ensaiar e reescrever com a voz de quem apresenta. Todo número sai do repositório e é conferido por teste (`tests/test_documentacao.py`); o que é premissa está marcado como premissa.

## O formato que a organização definiu

- **5 minutos, sem perguntas.** O que a banca precisa saber tem de estar no slide ou no vídeo: não haverá chance de explicar depois.
- **Entrega até 13h do domingo:** link dos slides com o vídeo da demo funcionando, a análise de mercado ([ANALISE_MERCADO.md](ANALISE_MERCADO.md)) e o repositório.
- **Notas de 0 a 5 em cada critério, todos os jurados avaliam todos os times:** execução técnica 30%, resolução do problema 20%, análise de mercado e viabilidade 20%, inovação 15%, pitch 15%.
- **Banca:** cofundador da Visagio, consultor de tecnologia da Visagio que veio da AWS, chefe do BNDES Garagem, investidor-anjo e scout da a16z, co-CEO da Cortex. Metade da banca investe ou constrói empresas: mercado e modelo de negócio pesam tanto quanto a técnica.

Como o tempo está dividido, e qual critério cada parte carrega:

| Tempo | Slide | Critério |
|---|---|---|
| 0:00 – 0:25 | 1. Metade já foi embargada | Resolução do problema |
| 0:25 – 0:55 | 2. Sessenta entregas por barragem, e a norma muda | Resolução do problema |
| 0:55 – 1:15 | 3. Por que agora | Mercado |
| 1:15 – 1:30 | 4. A torre em uma frase | Inovação |
| 1:30 – 3:15 | 5. Vídeo da demo | Execução técnica |
| 3:15 – 3:45 | 6. Por que dá para confiar | Execução técnica, inovação |
| 3:45 – 4:15 | 7. Mercado e modelo | Mercado e viabilidade |
| 4:15 – 4:35 | 8. Concorrência | Mercado, inovação |
| 4:35 – 4:55 | 9. Próximos passos | Viabilidade |
| 4:55 – 5:00 | 10. Fechamento | Pitch |

## 1 · Metade já foi embargada (0:00 – 0:25)

- **Na tela:** "223 de 461" em letra grande. Embaixo: "barragens de mineração na Política Nacional de Segurança de Barragens que já foram embargadas. Fonte: SIGBM, 05/11/2026". Numa segunda linha, menor: "2025: 85 autos de embargo. Fonte: ANM".
- **Fala:** "Das 461 barragens de mineração que a lei de segurança de barragens cobre, 223 já foram embargadas, quase metade. 76 estão embargadas hoje, e só em 2025 a ANM lavrou 85 autos de embargo. Embargo quer dizer estrutura parada. Em agosto, uma barragem da Vale foi embargada sem anomalia nenhuma: a obra terminou e o estudo de ruptura não foi refeito."
- **Por que não falamos de multa:** as multas da ANM estão suspensas desde março de 2026 (Deliberação 436), e o embargo continua. Citar "multa de até R$ 1 bilhão" sem dizer isso é número que a banca pode derrubar. Detalhe e casos na [análise de mercado](ANALISE_MERCADO.md), seção "Fiscalização e casos".

## 2 · Sessenta entregas por barragem, e a norma muda (0:25 – 0:55)

- **Na tela:** uma barragem no centro com as entregas do ano em volta (FIR e extrato a cada quinzena, DCE e relatório de inspeção a cada semestre, simulado, treinamento). Ao lado, o recorte da notícia da ANM ("31/12/2029") e o do ato no DOU ("26/12/2029").
- **Fala:** "Cada barragem tem cerca de 60 entregas com data por ano. A norma muda pelo Diário Oficial, misturada a milhares de atos. Em julho, a Resolução 245 adiou um prazo: a notícia no site da ANM diz 31 de dezembro, o ato diz 26. E a ANM tem 53 servidores para fiscalizar cerca de 900 barragens. A empresa descobre o erro no embargo."

## 3 · Por que agora (0:55 – 1:15)

- **Na tela:** contagem regressiva até 02/08/2027 e "Res. 95 → Res. 220".
- **Fala:** "Em 2 de agosto de 2027 a Resolução 220 substitui a 95. As 126 empresas com barragem na política nacional, 461 barragens, vão refazer o mapa de obrigações, e a regra nova já mudou antes de valer. Hoje, 77 dessas barragens estão em nível de alerta ou emergência."
- Fonte: SIGBM público, exportado em 05/11/2026 (`data/mercado_sigbm.json`).

## 4 · A torre em uma frase (1:15 – 1:30)

- **Na tela:** duas setas chegando no mesmo ativo. De cima: "Diário Oficial → obrigação". De baixo: "PDF da operação → baixa ou alerta". No meio: "uma pessoa aprova".
- **Fala:** "A Mitra é uma torre de controle por ativo. De cima, lê o Diário Oficial e atualiza as obrigações. De baixo, lê o documento da operação e dá baixa ou dispara o alerta. Nada muda sem uma pessoa aprovar."

## 5 · Vídeo da demo (1:30 – 3:15)

Vídeo sem som, gravado seguindo o [roteiro](ROTEIRO_DEMO.md); a narração é ao vivo. Cada linha abaixo é um corte do vídeo.

- **0:00 Caixa de entrada.** 8 ativos, 131 obrigações de 11 normas; 4 atrasadas, 1 dado faltando, 3 vencendo, cada pendência com o botão que resolve. **Narração:** "Uma mineradora fictícia, com barragens, vasos de pressão e licença. O que precisa de ação, por ativo, sem ninguém ler norma."
- **0:20 Documento de campo.** Ler `FIR_B2_2026-11-1Q_anomalia.pdf`: aparece o alerta vermelho. **Narração:** "A ficha de inspeção chega em PDF. A regra lê barragem, documento e data, sem IA. A anomalia obriga uma inspeção especial em 24 horas, e a torre abre essa obrigação."
- **0:45 Mudança de norma.** **Revisar alteração** na caixa abre **Mudanças**: antes e depois da OB-01. Na Diretoria não há botão de aprovar, porque norma pública é decidida pela curadoria da Mitra: trocar a persona para **Curadoria Mitra** e clicar em **Aprovar**. **Narração:** "O radar achou a Resolução 245 e propôs a mudança, com o trecho do ato. Mudou uma obrigação; as outras 23 ficaram iguais. A curadoria da Mitra aprova uma vez, e vale para todas as clientes."
- **1:10 Transição.** Botão **Res. 220**: a torre vira para 02/08/2027 e cobra pela norma nova. **Narração:** "No dia da troca, a torre já cobra pela norma nova e não perde o que foi feito pela antiga."
- **1:30 Radar e gestor.** Funil 7.884 atos → 825 da ANM → 2 para a IA → 1 muda o cadastro; trocar para *Manutenção da Usina*. **Narração:** "Um mês inteiro do Diário Oficial virou duas chamadas de IA. E cada gestor vê só os ativos dele."

## 6 · Por que dá para confiar (3:15 – 3:45)

- **Na tela:** quatro números: 99,97% · US$ 0,065 · 66 trechos · mais de 500 testes.
- **Fala:** "Regra antes de IA: 99,97% do Diário Oficial nunca chega ao modelo. Quando chega, a IA propõe, uma conferência automática verifica se o trecho existe no ato e se a data está no trecho, e uma pessoa aprova. Cada análise custou menos de meio centavo de dólar; cadastrar a Resolução 95 inteira custou US$ 0,065. Um teste confere os 66 trechos do cadastro contra o texto oficial. No ar, a IA roda no Amazon Bedrock, dentro da conta AWS: a mineradora pode usar a própria conta, e os documentos dela não saem de casa."

## 7 · Mercado e modelo (3:45 – 4:15)

- **O que o slide faz:** carrega o critério de mercado e viabilidade (20% da nota) em 30 segundos, respondendo três perguntas: quem compra primeiro, quanto vale e como a empresa ganha dinheiro. Risco de embargo não entra aqui: é dor, e fica no slide 1. Multa evitada não entra como receita nem como economia.
- **Na tela:**
  - à esquerda, o funil 908 → 461 → 208 → 46 barragens (cadastradas → na política nacional → grupos de 2 a 9 barragens → meta em 3 anos), com "R$ 24,5 mi · R$ 12,4 mi · R$ 1,2 mi por ano" ao lado das etapas que viram receita (TAM, SAM, SOM);
  - à direita, o modelo em três linhas: assinatura por ativo; implantação; licença para consultoria, que também é canal de venda;
  - embaixo, a escada numa faixa só, com o título "Mesmo motor, outro cadastro": 461 barragens da PNSB (a porta de entrada) → a mineradora inteira, 8.086 pagam CFEM (NR-13, NR-22 e licença já rodam na demo) → 29.761 barragens do país (água, energia, resíduos; SNISB);
  - acima do rodapé, a conta de quem compra (hipótese da [análise de mercado](ANALISE_MERCADO.md), seção 2): "um grupo com 4 barragens gasta de R$ 47 mil a R$ 156 mil por ano em horas só para controlar prazos; a Mitra custa R$ 108 mil, sem contar consultoria às pressas nem estrutura embargada";
  - no rodapé: "preço a validar com 10 entrevistas e 3 pilotos pagos".
- **Fala:** "Começamos pelos 59 grupos que têm de 2 a 9 barragens: dor de consolidar, pouco time de sistemas. Cobrando por ativo, só as 461 barragens da PNSB dão R$ 12,4 milhões por ano; com 10% de adoção, R$ 1,2 milhão. Mas o motor é por ativo, não por barragem: mesmo motor, outro cadastro. Depois vêm as outras 447 barragens de mineração, a mineradora inteira, em 8.086 mineradoras que pagam royalty, e as 29.761 barragens do país."
- **Por que a escada:** o SAM de R$ 12,4 milhões é pequeno para quem investe; o mercado de verdade é compliance por ativo na mineradora inteira. A demo prova o degrau do meio: vaso de pressão (NR-13), unidade (NR-22) e licença rodam no mesmo motor das barragens.
- **Premissas, não dados** (dá para mudar ao vivo na aba **Mercado**): R$ 1.500 por barragem por mês, 5 outros ativos por barragem a R$ 150 por mês cada, 10% de adoção. Conta: 461 × (R$ 1.500 + 5 × R$ 150) × 12.

## 8 · Concorrência (4:15 – 4:35)

- **Na tela:** duas colunas. "Monitoramento legal (Sigalei, Verde Ghaia, Ius Natura): o que mudou na lei?" · "Mitra: o que esta barragem precisa entregar, até quando, e já entregou?"
- **Fala:** "Monitoramento legal já existe, e é bom em dizer o que mudou na lei. Nós respondemos o que esta barragem precisa entregar, até quando, e se já entregou, lendo o documento que comprova. As consultorias que fazem a declaração de estabilidade não são concorrentes: são o nosso canal."

## 9 · Próximos passos (4:35 – 4:55)

- **Na tela:** linha do tempo até 02/08/2027 com três marcos: pilotos, preço validado, troca da norma. Embaixo, o time: Daniel Couto, Larissa Albuquerque, Monique Cardoso, Rildo Parasio e Samuel Araujo.
- **Fala:** "Até a troca da norma, em agosto de 2027: três pilotos pagos em Minas Gerais, uma consultoria parceira e o preço validado em dez entrevistas. Depois, barragens de água e energia e as normas de toda a mineradora, no mesmo motor."

## 10 · Fechamento (4:55 – 5:00)

- **Fala:** "A norma muda, a torre muda junto, e uma pessoa decide."

## Ensaio

- As falas e a narração somam cerca de 610 palavras: perto de 4 min a 150 palavras por minuto. O slide 7 ficou no limite dos 30 s: se apertar, a escada fica só na tela. O resto do tempo é o vídeo mostrando a tela entre uma narração e outra, e uma pausa depois do número de abertura. Um teste conta as palavras e falha se passar de 750.
- Cronometrar duas vezes com o vídeo rodando. Se passar de 5 min, cortar primeiro o corte "Transição" do vídeo e depois o slide 9 para uma frase.
- O vídeo é gravado antes, com a barra lateral em 07/11/2026, "Diretoria (todos os ativos)" e **Recriar demo**. Ter o arquivo do vídeo local, além do link, caso a internet falhe.
- Não há perguntas: as respostas que mais importam já estão nos slides 6 (a IA errar), 7 (premissas de preço) e 8 (concorrência). A tabela "Se perguntarem" do [roteiro](ROTEIRO_DEMO.md) fica para as mentorias e para conversas depois do pitch.
