# Avaliação do Pergunte à torre

Gerado por `python -m mitra.pergunta avaliar` contra a demo (Mineradora Serra Azul), com o modelo de verdade. **10 de 10 casos passaram**; custo total US$ 0.1368; a mais lenta levou 14.5 s (o prazo é 45 s).

Cada caso tem critérios objetivos em `tests/pergunta_avaliacao.toml`: o que a resposta precisa conter, o que não pode conter, que ferramenta precisa ter usado, e a conferência do Python (trecho entre aspas, data e código de obrigação ou ativo precisam estar no que as ferramentas devolveram).

## ✅ atrasadas-b3

**Pergunta:** O que está atrasado na B3 e por qual artigo?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias · US$ 0.0068 · 6.8 s

<details><summary>Resposta</summary>

Na **B3** há 2 obrigações atrasadas, ambas da **Res. ANM 95/2022** e sob responsabilidade da Gerência de Geotecnia:

- **R95-01 – Preencher as FIR quinzenalmente** — art. 19, I: *"preencher, quinzenalmente ou em menor período, a seu critério, as FIR"*. Venceu em **2026-10-15**, falta a 1ª quinzena de outubro/2026.
- **R95-02 – Preencher o EIR no SIGBM até o fim da quinzena subsequente à inspeção** — art. 21: *"O preenchimento do EIR no SIGBM deverá ocorrer até o final da quinzena subsequente à inspeção em campo que gerou o preenchimento da FIR"*. Venceu em **2026-10-30**, mesmo período pendente (1ª quinzena de outubro/2026).

Hoje na torre é 2026-11-07. Registre as entregas em **Entregas** ou trate na **Caixa de entrada**.

</details>

## ✅ atrasadas-todas

**Pergunta:** Quais obrigações estão atrasadas hoje e o que eu faço primeiro?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias · US$ 0.0112 · 10.7 s

<details><summary>Resposta</summary>

**4 obrigações atrasadas hoje (07/11/2026)**, a mais antiga vencida há mais tempo primeiro:

1. **B3 — R95-01** "Preencher as FIR quinzenalmente" — Res. ANM 95/2022, art. 19 I — venceu **15/10/2026**, falta a 1ª quinzena de outubro/2026. Responsável: Gerência de Geotecnia.
   > "preencher, quinzenalmente ou em menor período, a seu critério, as FIR"

2. **L1 — LO-02** "Monitorar os efluentes líquidos da estação de tratamento" — LO 000/2023 (fictícia), Condicionante 2 — venceu **15/10/2026**, falta setembro/2026. Responsável: Gerência de Meio Ambiente.

3. **B3 — R95-02** "Preencher o EIR no SIGBM até o fim da quinzena subsequente à inspeção" — Res. ANM 95/2022, art. 21 — venceu **30/10/2026**, falta a 1ª quinzena de outubro/2026. Responsável: Gerência de Geotecnia.
   > "O preenchimento do EIR no SIGBM deverá ocorrer até o final da quinzena subsequente à inspeção em campo que gerou o preenchimento da FIR"

4. **E1 — N13-03** "Exame externo periódico do vaso — categoria III sem SPIE" — NR-13, 13.5.4.5 — venceu **30/10/2026**.
   > "A inspeção de segurança periódica, constituída por exames externo e interno, deve obedecer aos prazos máximos indicados na Tabela 2, com base na categoria do vaso"

**Prioridade de ação:**
- Primeiro resolver **B3** (duas pendências na barragem, mesmo vencimento 15/10 já acumulando) e **L1** (ambiental, mesma data 15/10) — são as mais antigas.
- Em seguida, **E1** (NR-13, equipamento), vencida em 30/10.

Há ainda **1 dado faltando** e **3 vence_logo** não detalhados aqui — posso trazer se quiser. Registre as entregas em **Entregas** e acompanhe o encerramento em **Caixa de entrada**.

</details>

## ✅ dado-faltando-b4

**Pergunta:** Tem algum dado faltando no cadastro que impede de saber se uma obrigação vale?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** instanciacao, pendencias · US$ 0.0066 · 7.4 s

<details><summary>Resposta</summary>

Sim, há **1 pendência** nessa condição:

- **B4** — **R95-08** "Executar e concluir nova RPSB após modificação estrutural"
  - Norma: **Res. ANM 95/2022, art. 18 §1**
  - Trecho: *"no prazo de 6 (seis) meses contados da conclusão da modificação, o empreendedor ficará obrigado a executar e concluir nova RPSB"*
  - Dado faltando: **se o ativo passou por modificação estrutural**
  - Responsável: Gerência de Emergências

Sem essa informação a torre não consegue determinar se a obrigação se aplica ao B4. É preciso preencher esse dado no cadastro do ativo (aba **Ativos**, ficha da B4) para a obrigação ser corretamente classificada (passando a `em_dia`, `vence_logo` ou `atrasada`, conforme o caso).

</details>

## ✅ mudanca-245

**Pergunta:** Alguma norma mudou recentemente? O que eu preciso decidir?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** mudancas_pendentes, radar_do_dou · US$ 0.0090 · 10.4 s

<details><summary>Resposta</summary>

Sim, há **uma mudança aguardando decisão**, da Resolução ANM nº 245/2026 — e uma segunda análise que não gerou mudança.

## O que decidir: OB-01 (ZAS — retirada dos trabalhadores de lavra, beneficiamento e disposição de rejeitos/estéril)

- **Ativo afetado:** B2
- **Ato:** Resolução ANM nº 245, de 31 de julho de 2026
- **Antes → depois:** prazo e vigência de **2027-08-02** para **2029-12-26**
- **Trecho do ato:** "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º."
- **Conferência do Python:** obrigação estava entre as candidatas, o trecho existe no ato, e as datas propostas aparecem no trecho — tudo validado.
- **Quem decide:** curadoria Mitra (norma pública).
- Até a decisão, **vale a data atual (2027-08-02)**.

## O que não mudou

A Resolução ANM nº 246/2026 foi analisada mas **não gerou mudança no cadastro**: ela prorroga só prazos processuais ligados a sistemas específicos (Protocolo Digital, Dados Cadastrais, Dados Minerários) em uma janela que não coincide com nenhuma obrigação do cadastro, e exclui expressamente SIGBM, RAL e DIPEM — justamente onde estariam as obrigações relacionadas.

**Onde agir:** vá em **Mudanças** para aprovar ou recusar o ajuste de prazo da OB-01.

</details>

## ✅ transicao-220

**Pergunta:** O que passa a valer quando a Res. ANM 220/2025 entrar em vigor?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** linha_do_tempo · US$ 0.0135 · 12.4 s

<details><summary>Resposta</summary>

**Tudo isso já é dado como confirmado, não proposta** (a única marcada como "proposta" é uma linha específica da B2, abaixo). Em **2027-08-02**, a Res. ANM 220/2025 passa a gerar obrigações para as barragens B1, B2, B3 e B4 — substituindo o que hoje está na Res. ANM 95/2022.

**B1 — 13 obrigações novas**, entre elas:
- **OB-02** Preencher a FIR (art. 38 I); **OB-04** Elaborar o RISR/DCE (art. 39 I); **OB-06** Concluir a RPSB com consultoria externa (arts. 43 e 44 I); **OB-14/OB-15** RCO e DCO (art. 57); **OB-20/OB-21** monitoramento automatizado e vídeo-monitoramento 24h (art. 20 §2 e §3); **OB-22** sirenes na ZAS (art. 49).

**B2 — 15 obrigações**, inclui as de B1 mais:
- **OB-01** Retirar da ZAS os trabalhadores de lavra/beneficiamento/disposição (art. 7 §1); **OB-10** RPSB a cada 10 m alteados (art. 44 §2).

**B3 — 9 obrigações**, com particularidades:
- **OB-05** RISR/DCE (art. 39 II); **OB-07** RPSB (arts. 43 e 44 II); **OB-12** exercício simulado interno (art. 55); **OB-17** Seminário Orientativo quando a prefeitura/defesa civil pedir (art. 56 §1).

**B4 — 14 obrigações**, inclui as de B1 mais:
- **OB-09** Nova RPSB após modificação estrutural (art. 44 §1).

Comuns a todos os 4 ativos nessa data: **OB-02, OB-03, OB-18, OB-19, OB-24** (FIR, EIR, reporte de anomalia em 24h, ISE, cópias do PAEBM à defesa civil).

**Além disso — ainda como proposta (não aprovada)**: em **2029-12-26**, para a **B2**, aparece de novo **OB-01** (retirada da ZAS) junto com **N22-ZAS2** da **NR-22, 22.24.8** ("Restringir a permanência na ZAS aos trabalhadores estritamente necessários"). Essa data só vale se a mudança for aprovada — hoje a torre segue com a versão vigente. Decisão fica em **Mudanças**.

</details>

## ✅ cobertura-mg

**Pergunta:** Que normas valem para as minhas barragens em Minas Gerais? Estou coberto?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** cobertura_normativa · US$ 0.0375 · 12.4 s

<details><summary>Resposta</summary>

A cobertura em MG para barragens é **verificada**, mas ainda tem muita coisa esperando curadoria — não dá para dizer que você está "coberto" em sentido pleno.

**O que já está no catálogo (gera obrigação hoje):**
- **Lei MG 23.291/2019** — Política Estadual de Segurança de Barragens
- **Decreto MG 48.078/2020** — regulamenta o PAE (Plano de Ação de Emergência)
- **Decreto MG 48.140/2021** — regulamenta a classificação de potencial de dano

Isso vale para os ativos **B1, B2, B3 e B4**.

**Fonte lida:** Assembleia de Minas (leis, leis complementares e decretos de MG), 1989–2026, lida em 2026‑11‑07.

**Lacuna conhecida:** Deliberações Normativas do Copam e resoluções da Semad e da Feam — essas não têm dados abertos, então não são rastreadas automaticamente. Se algo relevante de segurança de barragens estiver nelas, a torre não vê.

**Esperando curadoria (ainda não geram obrigação):** ~30 decretos e leis estaduais que podem afetar suas barragens, entre os mais relevantes:
- **Decreto MG 48.747/2023 e alterações** (48.795/2024, 48.848/2024, 48.977/2024) — caução ambiental para barragens, com atualização a cada 5 anos
- **Decretos 48.133/2021, 48.149/2021, 48.190/2021, 48.454/2022, 48.759/2024** — todos alterando o regime do PAE (prazos, CCPAE, obrigações para barragens nível 2/3)
- **Decreto 48.460/2022** — altera critérios de classificação de potencial de dano
- **Decreto 46.993/2016 e 47.158/2017** — Auditoria Técnica Extraordinária de Segurança de Barragem
- **Lei MG 12.488/1997** — escada para peixes em barragem
- **Decreto MG 49.298/2026** — regras de transição para a Lei Federal 15.190/2025

Nenhuma dessas 30 gera obrigação enquanto não passar pela curadoria Mitra (fica em **Cobertura normativa** aguardando triagem). Se quiser, posso detalhar as pendências já ativas de B1 a B4 nas normas que já estão no catálogo.

</details>

## ✅ equipamento-nr13

**Pergunta:** Como está o vaso de pressão VP-101?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** ficha_do_ativo · US$ 0.0154 · 10.4 s

<details><summary>Resposta</summary>

**VP-101 (E1 – Reservatório de ar comprimido da usina)** tem uma pendência atrasada e o restante em dia ou dependente de evento.

**Cadastro:** vaso de pressão, categoria III, sem SPIE, em operação, responsável Manutenção da Usina.

**Status das obrigações:**
- 🔴 **Atrasada** — **N13-03** (Exame externo periódico do vaso — categoria III sem SPIE), **NR-13, item 13.5.4.5**: venceu em **30/10/2026**, período faltando 30/10/2026. Trecho: *"A inspeção de segurança periódica, constituída por exames externo e interno, deve obedecer aos prazos máximos indicados na Tabela 2, com base na categoria do vaso"*.
- 🟢 **Em dia** — **N13-04** (Exame interno periódico, mesmo dispositivo 13.5.4.5): vence 30/10/2027.
- ⚪ **Gatilho** (sem calendário, dependem de evento) — todas sob área documentação/equipamento/emergência:
  - N13-01: manter registro de segurança (NR-13, 13.5.1.7)
  - N13-02: manter prontuário atualizado (NR-13, 13.5.1.5)
  - N13-07: inspeção extraordinária quando ocorrer situação prevista (NR-13, 13.5.4.10)
  - N13-08: relatório de inspeção em até 60 dias após o evento (NR-13, 13.3.8)
  - N13-09: comunicar autoridade/sindicato em caso de vazamento, incêndio ou explosão grave (NR-13, 13.3.11)
  - N13-10: sinalizar categoria e número do vaso em local visível (NR-13, 13.5.1.4)

**Última evidência registrada:** exame externo de 30/10/2023 (N13-03) e exame interno de 30/10/2021 (N13-04) — ambas vindas do histórico de demonstração, sem novos registros desde então.

A obrigação N13-03 está atrasada; recomendo registrar a inspeção na **Caixa de entrada** ou anexar o comprovante em **Entregas** assim que for feita.

</details>

## ✅ licenca

**Pergunta:** Tem condicionante da licença de operação vencida ou vencendo?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias · US$ 0.0118 · 7.7 s

<details><summary>Resposta</summary>

Sim — há duas obrigações ligadas à licença de operação, ambas no ativo **L1**:

- **LO-02** — "Monitorar os efluentes líquidos da estação de tratamento" (LO 000/2023 (fictícia), Condicionante 2) — **atrasada**, venceu em **2026-10-15**, falta o período de **setembro/2026**. Responsável: Gerência de Meio Ambiente.
- **LO-06** — "Requerer a renovação da licença de operação" (LC 140/2011, art. 14 §4) — **vence_logo**, vence em **2026-11-15**. Responsável: Gerência de Meio Ambiente.

Hoje na torre é **2026-11-07**. Nenhuma outra pendência da lista (B2, B3, B4, E1) é condicionante de licença — são obrigações de Res. ANM 95/2022 e NR-13.

Para regularizar o monitoramento atrasado e tratar a renovação antes do vencimento, use a **Caixa de entrada** (ação) e registre os comprovantes em **Entregas**.

</details>

## ✅ ativo-inexistente

**Pergunta:** O que está atrasado na barragem B9?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias, ativos · US$ 0.0226 · 14.5 s

<details><summary>Resposta</summary>

Não existe ativo **B9** na torre. Consultando a lista oficial de ativos, temos: **B1** (Barragem Serra I), **B2** (Barragem Serra II), **B3** (Barragem Córrego Fundo), **B4** (Barragem Vale do Cedro), **E1** (VP-101 Reservatório de ar comprimido da usina), **E2** (VP-205 Vaso do sistema hidráulico do britador), **L1** (Licença de Operação nº 000/2023), **U1** (Complexo Minerário Serra Azul).

Das barragens, há pendências atrasadas em:
- **B3** (Barragem Córrego Fundo): 2 obrigações atrasadas.

As demais barragens não têm atrasos: **B1** e **B2** sem atrasadas; **B4** sem atrasadas (mas com 1 dado_faltando e 1 vence_logo).

Quer que eu detalhe as 2 pendências atrasadas da **B3**?

</details>

## ✅ fora-da-torre

**Pergunta:** Qual é a multa máxima que a ANM pode aplicar por barragem sem PAEBM?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** nenhuma · US$ 0.0025 · 2.9 s

<details><summary>Resposta</summary>

Essa é uma dúvida de direito/sanção administrativa fora do que a torre registra — ela mostra obrigações, vencimentos e status por ativo, não valores de multa. Posso te dizer, por exemplo, se alguma das suas barragens está com o PAEBM atrasado ou com dado faltando: quer que eu confira isso?

</details>
