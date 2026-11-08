# Avaliação do Assistente Mitra

Rodada com o **Claude Haiku 5.5** contra a demo (Mineradora Serra Azul), com o mesmo prompt (`mitra/pergunta_sistema.md`) e as mesmas ferramentas de leitura do chat. **9 de 10 casos passaram.**

Cada caso tem critérios objetivos em `tests/pergunta_avaliacao.toml`: o que a resposta precisa conter, o que não pode conter, que ferramenta precisa ter usado, e a conferência do Python (trecho entre aspas, data e código de obrigação ou ativo precisam estar no que as ferramentas devolveram). A nota sai do mesmo código do chat (`avaliar_resposta` e `conferir`, em `mitra/pergunta.py`).

## ✅ atrasadas-b3

**Pergunta:** O que está atrasado na B3 e por qual artigo?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias

<details><summary>Resposta</summary>

A B3 tem 2 obrigações atrasadas, as duas da Res. ANM 95/2022 (hoje: 2026-11-07).

- **R95-01 - Preencher as FIR quinzenalmente** (vence 2026-10-15). Res. ANM 95/2022, art. 19 I. Trecho: "I - preencher, quinzenalmente ou em menor período, a seu critério, as FIR". Período faltando: 1ª quinzena de outubro/2026. Área: barragem. Responsável: Gerência de Geotecnia.
- **R95-02 - Preencher o EIR no SIGBM até o fim da quinzena subsequente à inspeção** (vence 2026-10-30). Res. ANM 95/2022, art. 21. Trecho: "O preenchimento do EIR no SIGBM deverá ocorrer até o final da quinzena subsequente à inspeção em campo que gerou o preenchimento da FIR". Período faltando: 1ª quinzena de outubro/2026. Área: barragem. Responsável: Gerência de Geotecnia.

Onde agir: "Caixa de entrada" (o que precisa de ação) e "Entregas" (registrar a entrega e ver comprovantes).

</details>

## ✅ atrasadas-todas

**Pergunta:** Quais obrigações estão atrasadas hoje e o que eu faço primeiro?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias

<details><summary>Resposta</summary>

Há **4 obrigações atrasadas** na torre. Comece pelas duas que venceram em 2026-10-15: **L1 · LO-02** e **B3 · R95-01**. A torre usou 2026-11-07 como "hoje" (dia padrão dela).

**Atrasadas (mais antigas primeiro)**
- **L1 · LO-02**, "Monitorar os efluentes líquidos da estação de tratamento". LO 000/2023 (fictícia), Condicionante 2. Venceu em 2026-10-15; falta setembro/2026. Área: Gerência de Meio Ambiente.
- **B3 · R95-01**, "Preencher as FIR quinzenalmente". Res. ANM 95/2022, art. 19 I. Venceu em 2026-10-15; falta a 1ª quinzena de outubro/2026. Trecho: "I - preencher, quinzenalmente ou em menor período, a seu critério, as FIR". Área: Gerência de Geotecnia.
- **B3 · R95-02**, "Preencher o EIR no SIGBM até o fim da quinzena subsequente à inspeção". Res. ANM 95/2022, art. 21. Venceu em 2026-10-30; falta a 1ª quinzena de outubro/2026. Área: Gerência de Geotecnia.
- **E1 · N13-03**, "Exame externo periódico do vaso — categoria III sem SPIE". NR-13, 13.5.4.5. Venceu em 2026-10-30; falta 30/10/2026. Área: Manutenção da Usina.

**Dado faltando**
- **B4 · R95-08**, Res. ANM 95/2022, art. 18 §1. Falta saber se o B4 passou por modificação estrutural. Área: Gerência de Emergências.

**Vence logo**
- L1 · LO-06 (LC 140/2011, art. 14 §4): 2026-11-15.
- B4 · R95-05 (Res. ANM 95/2022, art. 18 I): 2026-11-20.
- B2 · R95-09 (Res. ANM 95/2022, art. 18 §2): 2026-12-01.

**Onde agir**
Comece pela Caixa de entrada, que mostra o que precisa de ação. Ao concluir uma entrega (FIR, EIR, monitoramento, exame do vaso), registre o comprovante em Entregas. A torre não registra entrega por você.

</details>

## ✅ dado-faltando-b4

**Pergunta:** Tem algum dado faltando no cadastro que impede de saber se uma obrigação vale?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** instanciacao, pendencias, ficha_do_ativo

<details><summary>Resposta</summary>

Sim, um dado está faltando, e ele impede saber se uma obrigação vale. O dado é se a barragem **B4 (Barragem Vale do Cedro)** passou por modificação estrutural. Sem ele, a torre não sabe se vale a obrigação **R95-08** (Executar e concluir nova RPSB após modificação estrutural).

- **B4 / R95-08**: Res. ANM 95/2022, art. 18 §1. Status: dado_faltando. Vencimento: não definido. Área: barragem. Responsável: Gerência de Emergências.
- Trecho: "no prazo de 6 (seis) meses contados da conclusão da modificação, o empreendedor ficará obrigado a executar e concluir nova RPSB"

Outros pontos:
- Nas pendências desta empresa, esta é a única obrigação com dado faltando.
- A ficha de B4 traz o cadastro (UF MG, altura 37.0 m, DPA alto, entre outros), mas nenhum atributo aparece marcado como faltante.
- A consulta de instanciação não retornou etapas, porque a empresa entrou na torre por outro caminho. A lista de dados faltantes aparece na ficha de cada ativo.

Onde agir: preencher a informação no cadastro, em "Ativos" (ficha da B4). A torre não grava essa alteração por aqui.

</details>

## ✅ mudanca-245

**Pergunta:** Alguma norma mudou recentemente? O que eu preciso decidir?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** mudancas_pendentes, radar_do_dou

<details><summary>Resposta</summary>

Sim. Há uma mudança pendente: a Resolução ANM nº 245, de 31 de julho de 2026, propõe nova data para a OB-01 no ativo B2. Essa é norma pública, então a decisão é da curadoria Mitra. Até lá, a torre segue com a versão vigente.

- **Obrigação:** OB-01, "Retirar da ZAS os trabalhadores das áreas de lavra, beneficiamento e disposição de rejeitos e estéril" (ativo B2).
- **Antes e depois:** prazo e vigência passam de 2027-08-02 para 2029-12-26.
- **Trecho do ato:** "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º."
- **Conferência da torre:** a obrigação estava entre as candidatas, o trecho existe no ato e as datas propostas aparecem nele.
- **Quem decide:** curadoria Mitra. A data proposta só vale se for aprovada.
- **Resolução ANM nº 246, de 6 de agosto de 2026:** analisada, sem mudança no cadastro. Ela prorroga prazos processuais que não coincidem com as obrigações cadastradas.

O que você precisa acompanhar é a aprovação da mudança da OB-01, que aparece na página "Mudanças" da torre. A torre não tem informação sobre o que a empresa deve fazer enquanto a mudança não for decidida.

</details>

## ✅ transicao-220

**Pergunta:** O que passa a valer quando a Res. ANM 220/2025 entrar em vigor?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** linha_do_tempo, mudancas_pendentes, obrigacoes

<details><summary>Resposta</summary>

A torre mostra que a Res. ANM 220/2025 passa a ter obrigações para B1 a B4 em **2027-08-02**: 60 obrigações nessa data, todas com a norma "Res. ANM 220/2025". Uma mudança de data é proposta e só vale se for aprovada.

**Entram em 2027-08-02 (não são propostas):**
- **B1**: 16 obrigações, como OB-02 "Preencher a Ficha de Inspeção Regular (FIR)" (art. 38 I) e OB-22 "Manter sirenes com acionamento automatizado, manual e remoto, e outros mecanismos de alerta na ZAS" (art. 49).
- **B2**: 18 obrigações, como OB-10 "Executar RPSB a cada 10 metros alteados" (art. 44 §2).
- **B3**: 9 obrigações, como OB-07 "Concluir a RPSB com consultoria externa" (arts. 43 e 44 II).
- **B4**: 17 obrigações, como OB-09 "Concluir nova RPSB após modificação estrutural" (art. 44 §1).

**Em 2029-12-26 (B2):**
- N22-ZAS2 "Restringir a permanência na ZAS aos trabalhadores estritamente necessários", NR-22, 22.24.8. Não é da Res. 220.
- OB-01 "Retirar da ZAS os trabalhadores das áreas de lavra, beneficiamento e disposição de rejeitos e estéril" (Res. ANM 220/2025, art. 7 §1) tem data proposta de 2029-12-26 pela Resolução ANM nº 245, de 31 de julho de 2026. O trecho do ato diz "III - em 26 de dezembro de 2029, quanto ao § 1º do art. 7º.". Quem decide é a curadoria Mitra. Até a aprovação, vale 2027-08-02.

**O que deixa de valer:** a torre não informa a data em que a Res. ANM 95/2022 deixa de valer. A consulta lista 21 obrigações R95 (por exemplo, R95-05 "Executar a RPSB a cada 3 anos") sem data de saída. Não consegui confirmar esse ponto pela torre.

</details>

## ✅ cobertura-mg

**Pergunta:** Que normas valem para as minhas barragens em Minas Gerais? Estou coberto?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** cobertura_normativa

<details><summary>Resposta</summary>

A torre marca a cobertura de Minas Gerais e a federal como verificadas, mas não dá para afirmar que você está coberto: há normas relevantes esperando a curadoria da Mitra e lacunas conhecidas. Os ativos consultados são B1, B2, B3 e B4.

**No catálogo (geram obrigações):**
- Minas Gerais: Lei MG 23.291/2019; Decreto MG 48.078/2020 (PAE); Decreto MG 48.140/2021.
- Federal: Lei 12.334/2010 (PNSB); Res. ANM 95/2022; Res. ANM 220/2025; NR-22.

**Fora do catálogo, esperando curadoria (não geram obrigação ainda):** entre outros, Decreto MG 46.993/2016 (auditoria de segurança), Decreto MG 48.747/2023 (caução ambiental), Decreto MG 48.759/2024 (PAE), Decreto federal 11.310/2022 e Lei 14.066/2020.

**Lacunas conhecidas:**
- MG: "Deliberações Normativas do Copam e resoluções da Semad e da Feam (sem dados abertos)".
- Federal: "Resoluções do Conama, do Ibama e da ANA (sem conector)".

**Fontes lidas:** Assembleia de Minas (1989–2026, lida em 2026-11-07 00:52 UTC); Senado Federal (1967–2026, mesma data); ANMlegis (2018–2026, mesma data); MTE, NRs vigentes (2026, lida em 2026-11-07 20:46 UTC).

Não consultei as datas de entrada em vigor de cada norma nesta conversa, então não sei dizer quando a Res. ANM 220/2025 e as demais passam a valer. Para ver quais obrigações valem para cada barragem e quando vencem, a consulta de ficha do ativo traz isso.

</details>

## ✅ equipamento-nr13

**Pergunta:** Como está o vaso de pressão VP-101?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** ficha_do_ativo, pendencias

<details><summary>Resposta</summary>

O VP-101 (código E1) tem **uma obrigação atrasada**: o exame externo periódico, com vencimento em 2026-10-30. Pela torre, são 1 atrasada, 1 em dia e 6 que dependem de gatilho.

- **N13-03, Exame externo periódico do vaso, categoria III sem SPIE:** atrasada, vence em 2026-10-30. Fonte: NR-13, 13.5.4.5. Trecho: "A inspeção de segurança periódica, constituída por exames externo e interno, deve obedecer aos prazos máximos indicados na Tabela 2, com base na categoria do vaso". Área: Manutenção da Usina. Última evidência recebida: período 30/10/2023, em 2026-11-07.
- **N13-04, Exame interno periódico do vaso, categoria III sem SPIE:** em dia, vence em 2027-10-30. Mesma norma e dispositivo. Última evidência recebida: período 30/10/2021.
- **Por gatilho (sem calendário):** N13-01, N13-02, N13-07, N13-08, N13-09 e N13-10.

Cadastro: classe vaso_pressao, categoria III, sem SPIE, em operação.

Para agir, registre a entrega do exame externo em **Entregas** e acompanhe o item em **Caixa de entrada**.

</details>

## ✅ licenca

**Pergunta:** Tem condicionante da licença de operação vencida ou vencendo?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias, obrigacoes, ficha_do_ativo

<details><summary>Resposta</summary>

Sim. Uma condicionante da licença de operação está atrasada, e o requerimento de renovação vence em 15/11/2026. A validade cadastrada da licença do ativo L1 é 2027-03-15, então a licença em si não aparece como vencida.

- **LO-02, atrasada, vence em 2026-10-15**: "Monitorar os efluentes líquidos da estação de tratamento". Norma: LO 000/2023 (fictícia), Condicionante 2. Falta o período de setembro/2026. Responsável: Gerência de Meio Ambiente.
- **LO-06, vence logo, 2026-11-15**: "Requerer a renovação da licença de operação". Norma: LC 140/2011, art. 14 §4. Responsável: Gerência de Meio Ambiente. A torre não trouxe o trecho deste dispositivo.
- **Em dia**: LO-01 (2027-01-30), LO-03 (2027-01-30), LO-04 (2027-01-30) e LO-05 (2027-03-15), todas da LO 000/2023 (fictícia).

Onde agir: registre a entrega de setembro/2026 do LO-02 em "Entregas" e acompanhe os itens na "Caixa de entrada". A data de validade da própria licença só aparece no cadastro do ativo L1.

</details>

## ❌ ativo-inexistente

**Pergunta:** O que está atrasado na barragem B9?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** pendencias

**Falhas:** conferência: trechos citados que não estão nos resultados: ErroTorre: Ativo 'B9' não encontrado nessa empresa.; códigos que não estão nos resultados: B1, B2, B3, B4, E1, E2, L1, U1, VP-101, VP-205

<details><summary>Resposta</summary>

A torre não encontrou o ativo B9 nesta empresa, então não consigo dizer o que está atrasado nele.

A consulta respondeu: "ErroTorre: Ativo 'B9' não encontrado nessa empresa." Os ativos que a torre lista para esta empresa são:

- B1 (Barragem Serra I)
- B2 (Barragem Serra II)
- B3 (Barragem Córrego Fundo)
- B4 (Barragem Vale do Cedro)
- E1 (VP-101 Reservatório de ar comprimido da usina)
- E2 (VP-205 Vaso do sistema hidráulico do britador)
- L1 (Licença de Operação nº 000/2023 (fictícia))
- U1 (Complexo Minerário Serra Azul)

Próximos passos:
- Se você quis dizer um destes ativos, informe o código e eu consulto as pendências dele.
- Se a B9 deveria constar, confira o cadastro em "Ativos". A torre só mostra os ativos que esta conta pode ver; se ela não aparece, pode estar fora do seu acesso ou não ter sido cadastrada.

</details>

## ✅ fora-da-torre

**Pergunta:** Qual é a multa máxima que a ANM pode aplicar por barragem sem PAEBM?

**Modelo:** `claude-haiku-5-5` · **ferramentas:** obrigacoes, cobertura_normativa

<details><summary>Resposta</summary>

A torre não tem o valor da multa máxima que a ANM pode aplicar por barragem sem PAEBM. Nenhuma obrigação do catálogo traz valor de sanção: as buscas por "multa" e "penalidade" não retornaram nada.

O que a torre tem sobre o PAEBM (obrigações, não penalidades):
- **OB-11**: "Executar os treinamentos internos do PAEBM" (Res. ANM 220/2025)
- **OB-24**: "Entregar cópias físicas atualizadas do PAEBM à defesa civil dos municípios do mapa de inundação" (Res. ANM 220/2025)
- **R95-11**: "Realizar treinamentos internos semestrais do PAEBM com a equipe externa de ACO/DCO, aprovando-os" (Res. ANM 95/2022)
- **R95-20**: "Entregar cópias físicas atualizadas do PAEBM à defesa civil municipal" (Res. ANM 95/2022)

Na cobertura normativa aparecem resoluções da ANM sobre multas, como a Res. ANM 230/2026, cuja ementa diz: "Atualiza os valores dos emolumentos, da Taxa Anual por Hectare (TAH), das multas previstas na legislação minerária, das vistorias de fiscalização e dos demais serviços prestados pela Agência Nacional de Mineração (ANM)." O texto que veio não informa o valor por barragem.

Para o valor, consulte o texto oficial da norma de penalidades e da resolução de multas vigente. Se quiser, posso verificar as obrigações de PAEBM de uma barragem específica (ex.: "B1").

</details>
