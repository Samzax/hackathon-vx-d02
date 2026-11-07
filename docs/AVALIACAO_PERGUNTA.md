# Avaliação do Pergunte à torre

Gerado por `python -m regulaia.pergunta avaliar` contra a demo (Mineradora Serra Azul), com o modelo de verdade. **10 de 10 casos passaram**; custo total US$ 0.1144; a mais lenta levou 13.2 s (o prazo é 45 s).

Cada caso tem critérios objetivos em `tests/pergunta_avaliacao.toml`: o que a resposta precisa conter, o que não pode conter, que ferramenta precisa ter usado, e a conferência do Python (trecho entre aspas, data e código de obrigação ou ativo precisam estar no que as ferramentas devolveram).

## ✅ atrasadas-b3

**Pergunta:** O que está atrasado na B3 e por qual artigo?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias · US$ 0.0076 · 8.2 s

<details><summary>Resposta</summary>

Na **B3** há 2 obrigações **atrasadas**, ambas da Res. ANM 95/2022, responsabilidade da Gerência de Geotecnia:

- **R95-01** – Preencher as FIR quinzenalmente
  - **Res. ANM 95/2022, art. 19, I**: *"preencher, quinzenalmente ou em menor período, a seu critério, as FIR"*
  - Venceu em **2026-10-15**; falta o período da **1ª quinzena de outubro/2026**.

- **R95-02** – Preencher o EIR no SIGBM até o fim da quinzena subsequente à inspeção
  - **Res. ANM 95/2022, art. 21**: *"O preenchimento do EIR no SIGBM deverá ocorrer até o final da quinzena subsequente à inspeção em campo que gerou o preenchimento da FIR"*
  - Venceu em **2026-10-30**; falta o período da **1ª quinzena de outubro/2026**.

Hoje na torre é **2026-11-07**, então ambas estão atrasadas há mais de uma semana. Para regularizar, registre a entrega em **Entregas** ou trate a pendência na **Caixa de entrada**.

</details>

## ✅ atrasadas-todas

**Pergunta:** Quais obrigações estão atrasadas hoje e o que eu faço primeiro?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias · US$ 0.0111 · 9.8 s

<details><summary>Resposta</summary>

**4 obrigações atrasadas hoje (07/11/2026)**, a mais antiga primeiro:

1. **B3 — R95-01** "Preencher as FIR quinzenalmente" — Res. ANM 95/2022, art. 19 I — vencida em **15/10/2026**, falta a 1ª quinzena de outubro/2026. Responsável: **Gerência de Geotecnia**.
   > "I - preencher, quinzenalmente ou em menor período, a seu critério, as FIR"

2. **L1 — LO-02** "Monitorar os efluentes líquidos da estação de tratamento" — LO 000/2023 (fictícia), Condicionante 2 — vencida em **15/10/2026**, falta setembro/2026. Responsável: **Gerência de Meio Ambiente**.

3. **B3 — R95-02** "Preencher o EIR no SIGBM até o fim da quinzena subsequente à inspeção" — Res. ANM 95/2022, art. 21 — vencida em **30/10/2026**, falta a 1ª quinzena de outubro/2026. Responsável: **Gerência de Geotecnia**.
   > "O preenchimento do EIR no SIGBM deverá ocorrer até o final da quinzena subsequente à inspeção em campo que gerou o preenchimento da FIR"

4. **E1 — N13-03** "Exame externo periódico do vaso — categoria III sem SPIE" — NR-13, item 13.5.4.5 — vencida em **30/10/2026**, data faltando: 30/10/2026. Responsável: **Manutenção da Usina**.
   > "A inspeção de segurança periódica, constituída por exames externo e interno, deve obedecer aos prazos máximos indicados na Tabela 2, com base na categoria do vaso"

**Prioridade:** começar pela B3 (R95-01, vencida há mais tempo, 15/10), em paralelo com L1 (LO-02, mesma data), depois B3 (R95-02) e E1 (N13-03).

Também há 1 pendência de **dado_faltando** e 3 **vence_logo** não listadas aqui — posso detalhar se quiser. Registre as entregas em **Entregas** e trate tudo pela **Caixa de entrada**.

</details>

## ✅ dado-faltando-b4

**Pergunta:** Tem algum dado faltando no cadastro que impede de saber se uma obrigação vale?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias · US$ 0.0066 · 6.2 s

<details><summary>Resposta</summary>

Sim, há **1 caso** de dado faltando no cadastro:

- **B4** — obrigação **R95-08** (Executar e concluir nova RPSB após modificação estrutural), **Res. ANM 95/2022, art. 18 §1**.
  - Trecho da norma: *"no prazo de 6 (seis) meses contados da conclusão da modificação, o empreendedor ficará obrigado a executar e concluir nova RPSB"*
  - Dado que falta: **se o ativo passou por modificação estrutural**. Sem essa informação, a torre não consegue determinar se a obrigação se aplica (e, se aplicar, a partir de quando contar o prazo de 6 meses).
  - Área responsável: Gerência de Emergências.

Para resolver, é preciso completar esse atributo no cadastro do ativo B4 — isso se corrige na seção **Ativos** (ficha do ativo/cadastro). Depois de preenchido, a torre recalcula o status automaticamente.

</details>

## ✅ mudanca-245

**Pergunta:** Alguma norma mudou recentemente? O que eu preciso decidir?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** mudancas_pendentes, radar_do_dou · US$ 0.0087 · 10.2 s

<details><summary>Resposta</summary>

**Sim, uma mudança está aguardando decisão:** a Resolução ANM nº 245/2026 propõe adiar o prazo do item III do art. 7º, § 1º, da Res. ANM 220/2025, usado na obrigação **OB-01** (retirar da ZAS os trabalhadores das áreas de lavra, beneficiamento e disposição de rejeitos e estéril), afetando o ativo **B2**.

- **Antes:** prazo/vigência em 2027-08-02
- **Depois (proposto):** prazo/vigência em 2029-12-26
- **Trecho do ato:** "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º."
- **Conferência Python:** obrigação estava entre as candidatas, o trecho existe no ato, e as datas propostas aparecem no trecho — tudo confirmado.
- **Quem decide:** curadoria RegulaIA (é norma pública, não decisão da empresa).

Até a aprovação, a torre continua considerando o prazo atual (2027-08-02) para a OB-01 no ativo B2.

Outro ato analisado neste mês (Res. ANM 246/2026, sobre prorrogação de prazos processuais) **não gerou mudanças** — ele exclui explicitamente SIGBM, RAL, DIPEM e obrigações de risco à saúde/vida/ambiente, e nenhuma obrigação do cadastro caía na janela coberta.

Para aprovar ou recusar a mudança da OB-01, vá em **Mudanças** na torre.

</details>

## ✅ transicao-220

**Pergunta:** O que passa a valer quando a Res. ANM 220/2025 entrar em vigor?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** linha_do_tempo · US$ 0.0145 · 13.2 s

<details><summary>Resposta</summary>

Em **02/08/2027** a Res. ANM 220/2025 entra em vigor e substitui a Res. ANM 95/2022 para as barragens B1, B2, B3 e B4 — todas já com datas confirmadas (não é "proposta"). Entram ao todo 60 obrigações novas (da 220) distribuídas assim:

**B1** (18 obrigações) — ex.: **OB-02** Preencher a FIR (art. 38 I), **OB-06** Concluir a RPSB com consultoria externa (arts. 43 e 44 I), **OB-20** Monitoramento automatizado de instrumentação 24h (art. 20 §2), **OB-22** Sirenes de alerta na ZAS (art. 49).

**B2** (19 obrigações) — as mesmas linhas de B1, mais **OB-01** Retirar da ZAS os trabalhadores de lavra/beneficiamento/disposição (art. 7 §1) e **OB-10** RPSB a cada 10 m alteados (art. 44 §2).

**B3** (10 obrigações) — ex.: **OB-05** Elaborar o RISR e enviar a DCE (art. 39 II), **OB-07** Concluir a RPSB (arts. 43 e 44 II), **OB-12** Exercício simulado interno (art. 55), **OB-17** Seminário Orientativo quando a prefeitura pedir (art. 56 §1).

**B4** (13 obrigações) — as comuns, mais **OB-09** Nova RPSB após modificação estrutural (art. 44 §1).

Comuns a várias barragens: **OB-03** Enviar o EIR no SIGBM (art. 38 II), **OB-11/16** Treinamentos e simulado anual do PAEBM, **OB-14/15** RCO e DCO (art. 57), **OB-18/19** Reporte em 24h e ISE para anomalias graves (arts. 38 §4 e 42), **OB-23** Atualização do PGRBM a cada 2 anos (art. 59, parágrafo único), **OB-24** Entrega do PAEBM às defesas civis (art. 46 §4).

⚠️ Há também um item marcado **"proposta"** (ainda não aprovado): em **26/12/2029**, para **B2**, a **OB-01** (retirada de trabalhadores da ZAS, art. 7 §1) ganharia nova data, junto com **N22-ZAS2** da NR-22 (22.24.8) sobre restringir a permanência na ZAS. Essa data só vale se a mudança for aprovada em **Mudanças**.

A lista completa de obrigações que a Res. 95/2022 deixa de gerar não veio nesta consulta — recomendo olhar a ficha de cada ativo ou **Transição e linha do tempo** na torre para o comparativo obrigação a obrigação.

</details>

## ✅ cobertura-mg

**Pergunta:** Que normas valem para as minhas barragens em Minas Gerais? Estou coberto?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** cobertura_normativa · US$ 0.0134 · 11.2 s

<details><summary>Resposta</summary>

**Cobertura em MG não é total: está catalogada parcialmente, com várias normas relevantes ainda esperando curadoria.** Para as 4 barragens em MG (**B1, B2, B3, B4**):

**No catálogo hoje:**
- **Decreto MG 48.078/2020** (PAE)
- **Decreto MG 48.140/2021**
- **Lei MG 23.291/2019** (Política Estadual de Segurança de Barragens)

**Fonte oficial lida:** Assembleia de Minas (leis, leis complementares e decretos de MG), período 1989–2026, lida em 2026-11-07.

**Lacunas conhecidas** (fora do alcance da fonte automática):
- Deliberações Normativas do Copam e resoluções da Semad e da Feam — **não têm dados abertos**, então não são verificadas por aqui.

**Esperando curadoria da RegulaIA** (já identificadas pela IA, ainda não entraram no catálogo — portanto **não geram obrigação** na torre hoje): são **27 normas**, entre as mais relevantes para barragens:
- **Decreto MG 46.993/2016** — institui a Auditoria Técnica Extraordinária de Segurança de Barragem (declaração de estabilidade)
- **Decreto MG 48.747/2023** e alterações (48.795/2024, 48.848/2024, 48.977/2024) — caução ambiental para barragens
- **Decretos 48.133/2021, 48.149/2021, 48.190/2021, 48.454/2022, 48.759/2024** — todos alterando o regime do PAE (Plano de Ação de Emergência)
- **Decreto 48.460/2022** — altera critérios de classificação do potencial de dano de barragens de rejeitos
- **Lei MG 23.795/2021** — Política Estadual dos Atingidos por Barragens
- **Lei MG 12.488/1997** — escadas para peixes em barragens
- entre outras (licenciamento geral, TFAMG, APAs específicas)

Nenhuma das 27 gerou obrigação ainda — não estão no catálogo. Se quiser, posso detalhar por ativo (B1–B4) o que já vale hoje via **Obrigações**, ou você pode acompanhar a fila de curadoria em **Cobertura normativa** na torre.

</details>

## ✅ equipamento-nr13

**Pergunta:** Como está o vaso de pressão VP-101?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** ficha_do_ativo · US$ 0.0137 · 8.7 s

<details><summary>Resposta</summary>

**VP-101 (E1 – Reservatório de ar comprimido da usina)** tem uma obrigação atrasada que pede atenção imediata.

- **Cadastro**: vaso de pressão, categoria III, sem SPIE, em operação, responsável: Manutenção da Usina.

**Pendência crítica:**
- **N13-03** – Exame externo periódico (categoria III sem SPIE) — **NR-13, item 13.5.4.5** — status **atrasada**, vencia em 30/10/2026. Trecho da norma: *"A inspeção de segurança periódica, constituída por exames externo e interno, deve obedecer aos prazos máximos indicados na Tabela 2, com base na categoria do vaso"*.

**Em dia:**
- **N13-04** – Exame interno periódico — NR-13, 13.5.4.5 — próximo vencimento 30/10/2027.

**Por gatilho (sem calendário, dependem de evento):**
- N13-01 (registro de segurança), N13-02 (prontuário atualizado), N13-07 (inspeção extraordinária), N13-08 (relatório de inspeção em até 60 dias), N13-09 (comunicação de incidente grave) e N13-10 (sinalização de categoria/número) — todas sob Manutenção da Usina.

**Últimas evidências recebidas**: exame interno em 30/10/2021 (N13-04) e exame externo em 30/10/2023 (N13-03) — ambas registradas no histórico da demo em 2026-11-07.

Não há histórico recente de entregas ou mudanças de responsável registrado na ficha. Para regularizar o exame externo atrasado, registre a entrega em **Entregas** ou veja o item na **Caixa de entrada**.

</details>

## ✅ licenca

**Pergunta:** Tem condicionante da licença de operação vencida ou vencendo?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias · US$ 0.0117 · 6.8 s

<details><summary>Resposta</summary>

Sim — no ativo **L1**, há condicionante da licença de operação atrasada e uma obrigação ligada a ela vencendo logo:

**Atrasada**
- **LO-02** – Monitorar os efluentes líquidos da estação de tratamento
  Norma: **LO 000/2023 (fictícia), Condicionante 2**
  Vencida em **2026-10-15**, falta o período **setembro/2026**
  Responsável: Gerência de Meio Ambiente

**Vence logo**
- **LO-06** – Requerer a renovação da licença de operação
  Norma: **LC 140/2011, art. 14 §4**
  Vence em **2026-11-15**
  Responsável: Gerência de Meio Ambiente
  *(obs.: esta não é uma condicionante da LO em si, mas decorre da proximidade do vencimento da licença)*

Hoje na torre é **2026-11-07**. Para regularizar o monitoramento de setembro e acompanhar o pedido de renovação, vá em **Entregas** (registrar o comprovante) e na **Caixa de entrada** para tratar a prioridade.

</details>

## ✅ ativo-inexistente

**Pergunta:** O que está atrasado na barragem B9?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** pendencias, ativos · US$ 0.0201 · 12.8 s

<details><summary>Resposta</summary>

Não existe um ativo chamado **B9** nesta empresa. A torre confirma estes ativos no escopo:

- **B1** – Barragem Serra I
- **B2** – Barragem Serra II
- **B3** – Barragem Córrego Fundo
- **B4** – Barragem Vale do Cedro
- **E1** – VP-101 Reservatório de ar comprimido da usina
- **E2** – VP-205 Vaso do sistema hidráulico do britador
- **L1** – Licença de Operação nº 000/2023 (fictícia)
- **U1** – Complexo Minerário Serra Azul

Olhando a contagem de pendências de cada um, os que têm itens **atrasados** agora são:

- **B3** – Barragem Córrego Fundo: 2 atrasadas
- **E1** – VP-101 Reservatório de ar comprimido da usina: 1 atrasada
- **L1** – Licença de Operação nº 000/2023 (fictícia): 1 atrasada

Quer que eu detalhe as pendências atrasadas de algum desses (norma, dispositivo e vencimento)?

</details>

## ✅ fora-da-torre

**Pergunta:** Qual é a multa máxima que a ANM pode aplicar por barragem sem PAEBM?

**Modelo:** `bedrock:us.anthropic.claude-sonnet-5` · **ferramentas:** nenhuma · US$ 0.0071 · 6.9 s

<details><summary>Resposta</summary>

A torre não traz valores de multas aplicadas pela ANM — ela registra obrigações, vencimentos e status (atrasada, dado faltando, vence logo, em dia, gatilho), com a norma e o dispositivo de origem, não penalidades em reais. Não tenho essa informação para responder.

Se quiser, posso consultar a torre sobre pendências relacionadas a PAEBM em algum ativo específico, ou quais obrigações de uma norma valem para uma barragem específica — me diga o ativo e eu busco.

</details>
