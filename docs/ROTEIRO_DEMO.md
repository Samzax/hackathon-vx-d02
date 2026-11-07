# Roteiro da demo (3 minutos)

Antes de começar: `uv run streamlit run app.py`, clicar em **Entrar na demo** (conta de teste, sem senha), barra lateral com "Hoje" em 07/11/2026 e "Diretoria (todos os ativos)". Se alguém já mexeu, clicar em **Recriar demo**.

## 1. Caixa de entrada (60 s)

- **Fala:** "A Serra Azul tem 8 ativos e 131 obrigações vindas de 9 normas: a lei federal de segurança de barragens, a lei de Minas e seus dois decretos, as Res. 95 e 220 da ANM, a NR-13, a NR-22 e a licença ambiental. Ninguém aqui leu norma: a torre mostra o que precisa de ação, por ativo."
- Apontar os números do topo: 4 atrasadas, 1 dado faltando, 3 vencendo. Embaixo, a lista do que precisa de decisão ou ação: a mudança da Res. 245 aguardando aprovação, as atrasadas, o dado faltando e o que vence, cada linha com o botão que resolve (**Registrar entrega**, **Completar cadastro**, **Decidir →**).
- Em **Chegou um documento da operação?**, escolher `FIR_B3_2026-10-1Q.pdf` e clicar em **Ler documento**.
  - **Fala:** "A regra leu ativo, documento e data. A IA não foi chamada."
- Clicar em **Registrar evidência**. As atrasadas caem de 4 para 3, e a FIR da B3 sai da caixa.
- Opcional: `EIR_B3_2026-10-1Q_recibo_SIGBM.pdf` zera a B3 e mostra o aviso "enviado 7 dias depois do prazo". **Fala:** "comprova a quinzena, mas a torre não esconde o atraso."
- Escolher `FIR_B2_2026-11-1Q_anomalia.pdf` e clicar em **Ler documento**. Aparece o alerta vermelho: pontuação 10 obriga a ISE e o registro no SIGBM em 24 h.
  - **Fala:** "O documento da operação também dispara obrigações."
- Aba **Ativos**: clicar no ponto vermelho B3 do mapa (ou na linha **B3 · Barragem Córrego Fundo** da tabela). A ficha do ativo mostra as pendências com o trecho literal da Res. 95, todas as obrigações, o que comprova e o cadastro.
  - **Fala:** "Tudo de uma barragem numa tela só: o que deve, por quê, e o que já provou."
- Opcional: trocar "Quem está olhando" para *Manutenção da Usina*. O gestor vê só o vaso dele (NR-13). Abrir **Boletim da semana**: "é isso que ele recebe toda segunda, sem ler norma nenhuma."
- Opcional: **Sair** e entrar como `geotecnia@serraazul.demo` (senha em `data/usuarios_demo.json`). Não há seletor: a conta só vê B1 e B3. **Fala:** "quem decide o acesso é a TI; quem decide a área de cada barragem é a Diretoria."

## 2. Mudanças (45 s)

- Na caixa de entrada, clicar em **Decidir →** (abre **Regulatório**, **Mudanças**).
- **Fala:** "Em 31/7 saiu a Res. ANM 245. O radar achou o ato e propôs uma mudança. Ela não vale até alguém aprovar."
- Mostrar o antes/depois da OB-01 (art. 7 §1: quem trabalha na lavra e no beneficiamento sai da ZAS; prazo 2027 → 26/12/2029), o trecho do ato e a linha "conferido pelo Python".
- **Fala:** "Mudou uma obrigação. As outras 23 da Res. 220 ficaram iguais." (Está na linha em negrito do cartão, contada pelo Python, não pela IA.)
- Clicar em **Aprovar**.

## 3. Transição e linha do tempo (45 s)

- Ainda em **Regulatório**, aba **Transição e linha do tempo**. Mostrar a contagem regressiva para 02/08/2027, quando a Res. 220 substitui a 95, e os pares por tema: o que continua (FIR, RPSB), o que é novo e o que acaba.
- Opcional: clicar em **Res. 220** (barra lateral, "Viagem no tempo"). A torre vira para 02/08/2027 e já cobra pela norma nova. **Fala:** "a RPSB não zera: a torre conta a última feita pela norma antiga." Voltar com **Demo**.
- Na linha do tempo (uma barra por norma em cada ativo), clicar no losango de **26/12/2029** na linha B2 · NR-22: a data abre logo abaixo. No mesmo dia vencem duas obrigações sobre a ZAS: a da ANM (OB-01, já aprovada: lavra e beneficiamento deixam de contar como estruturas da barragem) e a do MTE (NR-22, item 22.24.8: só os trabalhadores estritamente necessários dentro da ZAS).
  - **Fala:** "Dois reguladores, a mesma data. A torre cruza os dois sem ninguém ler as duas normas."

## 4. Radar do DOU (30 s)

- Funil de agosto/2026: 7.884 atos → 825 da ANM → 2 normativos para a IA → 1 muda o cadastro.
- **Fala:** "Regra antes de IA: 99,97% do volume nunca chega ao modelo. Cada análise custou menos de meio centavo de dólar, e a resposta fica em cache. A empresa pode usar a própria conta de IA (Bedrock, Anthropic), então os documentos dela não saem de casa."

## Se perguntarem

| Pergunta | Resposta curta |
|---|---|
| E se a IA errar? | O Python confere o trecho, o dispositivo e as datas. Uma pessoa aprova. Nada muda sozinho |
| Funciona sem internet? | Sim. A demo roda do cache (`data/cache_ia_demo.json`) e sem chave |
| Serve para outra coisa além de barragem? | O motor é "ativo + obrigação + agenda + evidência": já roda vaso de pressão, unidade e licença |
| Quanto custa cadastrar uma norma nova? | A extração da Res. 95 inteira custou US$ 0,065. A NR-13, US$ 0,045 |
| Qual o tamanho do mercado? | **Sobre**, **Mercado**: 461 barragens de 126 empresas na PNSB (SIGBM). Preço e adoção são premissas que dá para mudar na hora |
| Como sei que o cadastro está certo? | Cada obrigação da Res. 220 cita o parágrafo que a cria, e um teste confere o trecho contra o texto oficial. A conferência achou um "≥" que virava ">" no site da ANM e nove obrigações que faltavam |
| E se a pessoa fechar a tela depois do alerta? | A torre não esquece. Registrar a FIR com anomalia abre a ISE da B2 com prazo de 24 h, e ela fica vermelha no painel e no boletim. Só o relatório da ISE (`Relatorio_ISE_B2_2026-11-06.pdf`) a encerra |
| Quando a norma muda, o leitor de documentos muda junto? | Sim. Botão **Res. 220** na barra lateral, depois `FIR_B2_2027-08-1Q_Res220_EC3.pdf`. Pela Res. 95 a ISE vinha de pontuação 10. Pela Res. 220 (art. 42) vem de EC1, EC3, EC4 ou EC5 = 5. O alerta cita o artigo novo, e EC2 = 5 sozinho não dispara |
| Por que em 2027 há tantas atrasadas? | As entregas da demo vão até 07/11/2026; depois disso ninguém registrou nada, então o que venceu aparece atrasado (a tela avisa). O que importa nessa data é o que a torre passa a cobrar, e de qual norma |
| A ANM não divulgou 31/12/2029? | A notícia no site da ANM diz 31/12; o ato publicado no DOU diz 26/12 (art. 87, III). A torre usa o ato e mostra o trecho, não a notícia |
| Um gestor pode dar baixa no ativo de outro? | Não. Na visão *Manutenção da Usina*, `FIR_B3_2026-10-1Q.pdf` é lido, mas a tela diz que a B3 não é dele e não mostra o botão de registrar. Quem registra é a Geotecnia ou a Diretoria |
| Dá para testar com outro ato? | Sim: **Regulatório**, **Radar do DOU**, "Teste com um ato seu". Cole qualquer texto; se nenhuma obrigação for tocada, a IA nem é chamada |
