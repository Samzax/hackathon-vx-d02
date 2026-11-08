# Avaliação do Assistente Mitra

Rodada com o **Claude Haiku 5.5** contra a demo (Mineradora Serra Azul), com o mesmo prompt (`mitra/pergunta_sistema.md`) e as mesmas ferramentas de leitura do chat. **10 de 10 casos passaram.**

Cada caso tem critérios objetivos em `tests/pergunta_avaliacao.toml`: o que a resposta precisa conter, o que não pode conter, que ferramenta precisa ter usado, e a conferência do Python (trecho entre aspas, data e código de obrigação ou ativo precisam estar no que as ferramentas devolveram). A nota sai do mesmo código do chat (`avaliar_resposta` e `conferir`, em `mitra/pergunta.py`).

## ✅ atrasadas-b3

**Pergunta:** O que está atrasado na B3 e por qual artigo?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias

<details><summary>Resposta</summary>

Na B3 há 2 obrigações atrasadas, ambas da Res. ANM 95/2022 (data de referência da torre: 2026-11-07). Por ordem de vencimento, da mais antiga:

- **R95-01**, Preencher as FIR quinzenalmente. Norma: Res. ANM 95/2022, art. 19 I. Venceu em 2026-10-15; período faltando: 1ª quinzena de outubro/2026. Trecho: "I - preencher, quinzenalmente ou em menor período, a seu critério, as FIR". Responsável: Gerência de Geotecnia.
- **R95-02**, Preencher o EIR no SIGBM até o fim da quinzena subsequente à inspeção. Norma: Res. ANM 95/2022, art. 21. Venceu em 2026-10-30; período faltando: 1ª quinzena de outubro/2026. Trecho: "O preenchimento do EIR no SIGBM deverá ocorrer até o final da quinzena subsequente à inspeção em campo que gerou o preenchimento da FIR". Responsável: Gerência de Geotecnia.

Nesta consulta, a B3 não tem dado faltando nem obrigação vencendo logo.

Onde agir: registrar as entregas em "Entregas" (e ver os comprovantes lá). O que precisa de ação também aparece na "Caixa de entrada".

</details>

## ✅ atrasadas-todas

**Pergunta:** Quais obrigações estão atrasadas hoje e o que eu faço primeiro?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias

<details><summary>Resposta</summary>

**Há 4 obrigações atrasadas** (dia de referência da torre: 2026-11-07). Comece pelas duas que venceram em 2026-10-15 e depois pelas de 2026-10-30.

Atrasadas, da mais antiga:
- **B3, R95-01 "Preencher as FIR quinzenalmente"**: Res. ANM 95/2022, art. 19 I. Venceu 2026-10-15; falta 1ª quinzena de outubro/2026. Área: Gerência de Geotecnia. Trecho: "I - preencher, quinzenalmente ou em menor período, a seu critério, as FIR".
- **L1, LO-02 "Monitorar os efluentes líquidos da estação de tratamento"**: LO 000/2023 (fictícia), Condicionante 2. Venceu 2026-10-15; falta setembro/2026. Área: Gerência de Meio Ambiente.
- **B3, R95-02 "Preencher o EIR no SIGBM até o fim da quinzena subsequente à inspeção"**: Res. ANM 95/2022, art. 21. Venceu 2026-10-30; falta 1ª quinzena de outubro/2026. Área: Gerência de Geotecnia.
- **E1, N13-03 "Exame externo periódico do vaso — categoria III sem SPIE"**: NR-13, 13.5.4.5. Venceu 2026-10-30; falta 30/10/2026. Área: Manutenção da Usina.

Para não perder, também:
- **Dado faltando:** B4, R95-08 (Res. ANM 95/2022, art. 18 §1). A torre precisa saber se o B4 passou por modificação estrutural.
- **Vence logo:** L1, LO-06 (LC 140/2011, art. 14 §4) em 2026-11-15; B4, R95-05 (Res. ANM 95/2022, art. 18 I) em 2026-11-20; B2, R95-09 (Res. ANM 95/2022, art. 18 §2) em 2026-12-01.

Primeiro passo: B3 R95-01 e L1 LO-02, que venceram há mais tempo. Veja o que precisa de ação na **Caixa de entrada** e registre a entrega do comprovante em **Entregas**.

</details>

## ✅ dado-faltando-b4

**Pergunta:** Tem algum dado faltando no cadastro que impede de saber se uma obrigação vale?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias, instanciacao, ficha_do_ativo

<details><summary>Resposta</summary>

Sim, falta um dado, e ele impede saber se uma obrigação vale. A torre marca um único caso de `dado_faltando`:

- **B4** (Barragem Vale do Cedro), **R95-08** "Executar e concluir nova RPSB após modificação estrutural". Norma: Res. ANM 95/2022, art. 18 §1. Dado faltando: "se passou por modificação estrutural". Área: barragem. Responsável: Gerência de Emergências. Vencimento: não calculado.
- Trecho da norma: "no prazo de 6 (seis) meses contados da conclusão da modificação, o empreendedor ficará obrigado a executar e concluir nova RPSB"

Na ficha do B4 não aparece outro dado faltando; as demais obrigações do ativo têm outro status (em dia, vence logo ou gatilho). A consulta de instanciação da empresa não trouxe etapas, porque a torre informou que a empresa entrou por outro caminho.

Onde agir: confirme se o B4 passou por modificação estrutural e corrija o cadastro em "Ativos" (ficha e cadastro do ativo).

</details>

## ✅ mudanca-245

**Pergunta:** Alguma norma mudou recentemente? O que eu preciso decidir?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** mudancas_pendentes, radar_do_dou, historico_da_obrigacao

<details><summary>Resposta</summary>

Sim. Há uma mudança aguardando decisão: a Resolução ANM nº 245, de 31 de julho de 2026, propõe mudar para 26/12/2029 o prazo da OB-01. Hoje o prazo é 02/08/2027. Até a decisão, a torre continua com a versão vigente. Quem decide esta norma é a curadoria Mitra, não a empresa.

**Mudança pendente**
- **OB-01** (Res. ANM 220/2025, art. 7 §1), ativo B2: "Retirar da ZAS os trabalhadores das áreas de lavra, beneficiamento e disposição de rejeitos e estéril".
- Antes: prazo e vigência desde 02/08/2027. Depois (proposto): 26/12/2029, nos dois campos.
- Trecho do ato: "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º."
- Conferência da torre: a obrigação estava entre as candidatas, o trecho existe no ato e as datas aparecem nele.

**Sem mudança no cadastro**
- Resolução ANM nº 246, de 6 de agosto de 2026: a torre não encontrou obrigação do cadastro afetada.

**O que você precisa decidir**
- Nesta mudança, nenhuma decisão cabe à empresa: a curadoria Mitra decide. A data proposta só vale se for aprovada.
- Até lá, use 02/08/2027 como prazo de referência.
- Acompanhe o status na aba "Mudanças".

</details>

## ✅ transicao-220

**Pergunta:** O que passa a valer quando a Res. ANM 220/2025 entrar em vigor?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** linha_do_tempo, mudancas_pendentes, obrigacoes

<details><summary>Resposta</summary>

Pela torre, a Res. ANM 220/2025 começa a cobrar obrigações em **2027-08-02**: são 60 entradas nos ativos B1 a B4 nessa data (B1: 16, B2: 18, B3: 9, B4: 17). Exemplos: OB-02 "Preencher a Ficha de Inspeção Regular (FIR)" (Res. ANM 220/2025, art. 38 I) e OB-19 "Realizar Inspeção de Segurança Especial (ISE) ao detectar anomalia com EC1, EC3, EC4 ou EC5 = 5" (art. 42). Nenhuma dessas aparece com marca de proposta.

Pontos de atenção:

- **Proposta pendente:** o OB-01 do B2 ("Retirar da ZAS os trabalhadores das áreas de lavra, beneficiamento e disposição de rejeitos e estéril", Res. ANM 220/2025, art. 7 §1) aparece também com data **2029-12-26**, marcada como proposta. A mudança vem da Resolução ANM nº 245, de 31 de julho de 2026, com o trecho: "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º." Ela aguarda a curadoria Mitra; até a aprovação, a torre mantém 2027-08-02. A data proposta só vale se for aprovada.
- **Outra data, de outra norma:** N22-ZAS2 (NR-22, 22.24.8) no B2 em 2029-12-26, sem marca de proposta.
- **O que deixa de valer:** a torre não mostrou nesta consulta até quando valem as obrigações da Res. ANM 95/2022. Estão cadastradas 20 obrigações dessa norma, mas sem data de fim na consulta. Também não sei a data de entrada em vigor da 220 além da data de início das obrigações.

Onde agir: na aba Transição e linha do tempo, para o quadro completo; na aba Mudanças, para aprovar ou recusar a mudança do OB-01.

</details>

## ✅ cobertura-mg

**Pergunta:** Que normas valem para as minhas barragens em Minas Gerais? Estou coberto?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** cobertura_normativa

<details><summary>Resposta</summary>

**Resposta curta:** a torre tem cobertura **verificada** em Minas Gerais para barragens (ativos B1, B2, B3 e B4), mas com lacunas conhecidas e dezenas de normas estaduais ainda sem obrigação cadastrada. Pelos dados da torre, você não está totalmente coberto.

**No catálogo (geram obrigação):**
- Lei MG 23.291/2019
- Decreto MG 48.078/2020 (PAE)
- Decreto MG 48.140/2021

**Fonte lida:** Assembleia de Minas (leis, leis complementares e decretos de Minas Gerais), 1989–2026, lida em 2026-11-07 00:52 UTC.

**Lacunas conhecidas:** "Deliberações Normativas do Copam e resoluções da Semad e da Feam (sem dados abertos)".

**Esperando curadoria da Mitra (não geram obrigação ainda):** a torre listou 34 normas estaduais que podem atingir barragens, entre elas decretos de caução ambiental (48.747/2023 e alterações), de auditoria técnica extraordinária (46.993/2016 e 47.158/2017), de licenciamento (47.383/2018 e alterações, e 49.298/2026) e a Lei MG 23.795/2021 (Peab). Não há mudança aprovada aguardando extração.

**Limite desta consulta:** a pergunta foi filtrada só para MG e barragens. A cobertura federal não foi consultada aqui.

**Onde acompanhar:** "Cobertura normativa" para ver as lacunas e as normas em curadoria. Obrigações da empresa aparecem em "Caixa de entrada" e "Entregas".

</details>

## ✅ equipamento-nr13

**Pergunta:** Como está o vaso de pressão VP-101?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** ficha_do_ativo, pendencias

<details><summary>Resposta</summary>

O VP-101 (código E1, "VP-101 Reservatório de ar comprimido da usina") tem **1 obrigação atrasada**: o exame externo periódico do vaso.

- **N13-03**, "Exame externo periódico do vaso — categoria III sem SPIE", atrasada. Vencimento: 2026-10-30 (período faltando: 30/10/2026). Fonte: NR-13, 13.5.4.5. Vale porque o cadastro tem categoria III e spie false.
  Trecho: "A inspeção de segurança periódica, constituída por exames externo e interno, deve obedecer aos prazos máximos indicados na Tabela 2, com base na categoria do vaso"
- **N13-04**, exame interno periódico: em dia, vence 2027-10-30.
- Seis obrigações (N13-01, 02, 07, 08, 09 e 10) estão em "gatilho": dependem de evento e não têm data.

Última evidência recebida: N13-03 referente ao período 30/10/2023 e N13-04 referente ao período 30/10/2021, ambas recebidas em 2026-11-07 (origem "histórico da demo").

Responsável: Manutenção da Usina (área equipamento). Hoje, para a torre: 2026-11-07.

Onde agir: registrar o comprovante do exame externo em "Entregas". O item aparece na "Caixa de entrada".

</details>

## ✅ licenca

**Pergunta:** Tem condicionante da licença de operação vencida ou vencendo?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias, obrigacoes

<details><summary>Resposta</summary>

Sim. Para a licença de operação do ativo L1 há uma condicionante atrasada e um pedido de renovação que vence logo (dia de referência da torre: 2026-11-07).

- **LO-02 - Monitorar os efluentes líquidos da estação de tratamento** (L1). Status: atrasada, vencimento 2026-10-15, período faltando: setembro/2026. Norma: LO 000/2023 (fictícia), Condicionante 2. Área: Gerência de Meio Ambiente.
- **LO-06 - Requerer a renovação da licença de operação** (L1). Status: vence_logo, vencimento 2026-11-15. Norma: LC 140/2011, art. 14 §4. Área: Gerência de Meio Ambiente.

A torre não trouxe o trecho literal dessas duas obrigações, então não cito texto de norma. Também não há data de validade da própria licença na resposta, só as datas das obrigações acima.

Onde agir: registrar a entrega do monitoramento em "Entregas" e acompanhar o que precisa de ação na "Caixa de entrada".

</details>

## ✅ ativo-inexistente

**Pergunta:** O que está atrasado na barragem B9?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias

<details><summary>Resposta</summary>

Não encontrei a barragem B9 na torre: ela não está cadastrada nesta empresa, então não há pendências para mostrar.

A torre respondeu: "Ativo 'B9' não encontrado nessa empresa."

As barragens cadastradas são:
- **B1** (Barragem Serra I)
- **B2** (Barragem Serra II)
- **B3** (Barragem Córrego Fundo)
- **B4** (Barragem Vale do Cedro)

Se o código B9 estiver certo, o ativo pode estar fora do acesso desta conta ou ainda não ter sido cadastrado. Essa confirmação cabe ao Regulatório ou à área que cuida do cadastro, na aba "Ativos".

Se quiser, consulto agora o que está atrasado em uma das barragens acima, por exemplo B3 ou B1.

</details>

## ✅ fora-da-torre

**Pergunta:** Qual é a multa máxima que a ANM pode aplicar por barragem sem PAEBM?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** obrigacoes, cobertura_normativa

<details><summary>Resposta</summary>

A torre não tem essa informação. Não sei qual é a multa máxima: nenhuma ferramenta trouxe valor de multa para barragem sem PAEBM, e a busca por "multa" nas obrigações voltou vazia.

O que a torre tem sobre o PAEBM são obrigações de treinamento e entrega, não de sanção:
- **R95-11**: "Realizar treinamentos internos semestrais do PAEBM com a equipe externa de ACO/DCO, aprovando-os" (Res. ANM 95/2022)
- **R95-20**: "Entregar cópias físicas atualizadas do PAEBM à defesa civil municipal" (Res. ANM 95/2022)
- **OB-11**: "Executar os treinamentos internos do PAEBM" (Res. ANM 220/2025)
- **OB-24**: "Entregar cópias físicas atualizadas do PAEBM à defesa civil dos municípios do mapa de inundação" (Res. ANM 220/2025)

Sobre multas, a torre tem na lista de normas fora do catálogo, aguardando curadoria, as Resoluções ANM 132/2023, 150/2024, 196/2025 e 230/2026, que atualizam os valores das multas minerárias. Essas normas ainda não estão no catálogo e não geram obrigação na torre. A torre também não trouxe os valores nem o trecho que os fixa.

Para essa resposta, consulte o texto oficial da norma que prevê a sanção e a área Regulatório da empresa.

Se quiser, posso consultar a ficha de uma barragem para ver quais obrigações PAEBM valem para ela.

</details>
