# Análise de mercado e viabilidade: RegulaIA

Torre de controle regulatória por ativo, começando por barragens de mineração. Hackathon VX, Desafio 02. Versão de 05/11/2026.

Todo número deste documento tem fonte (lista no fim) ou é marcado como **premissa**. Os números do SIGBM vêm do export público de 05/11/2026, guardado em agregados em `data/mercado_sigbm.json`, e são conferidos por teste (`tests/test_documentacao.py`). O arquivo bruto não entra no repositório porque traz CPF de pessoas físicas.

## 1. Resumo

- **O problema existe e custa caro.** Das 461 barragens de mineração na Política Nacional de Segurança de Barragens (PNSB), 76 estão embargadas hoje e outras 147 já foram embargadas e liberadas: 223 (48%) passaram por embargo. Só em 2025 a ANM lavrou 85 autos de embargo em barragens. A multa da Lei 14.066/2020 vai de R$ 2 mil a R$ 1 bilhão, mas está suspensa desde março de 2026; o embargo continua, e é ele que para a estrutura (seção 2).
- **O volume é grande e muda de base em 2027.** Uma barragem na PNSB tem de 12 a 18 obrigações e cerca de 60 entregas com data por ano só pela Res. ANM 95/2022. Em 02/08/2027 a Res. ANM 220/2025 substitui a 95, e a 220 já foi alterada antes de valer (Res. ANM 245/2026).
- **O fiscal não vai achar o erro por você.** A ANM tem 53 servidores para fiscalizar cerca de 900 barragens, segundo a associação dos servidores. O controle é por declaração do próprio empreendedor: quem erra a data descobre no embargo.
- **Mercado inicial bem definido.** 125 grupos econômicos com barragem na PNSB; 64 deles têm barragem de dano potencial alto (243 barragens, 144 em Minas Gerais). Com as premissas de preço da seção 3: TAM de R$ 24,5 milhões por ano (908 barragens de mineração), SAM de R$ 12,4 milhões (as 461 da PNSB) e SOM de R$ 1,2 milhão em 3 anos (46 barragens, cerca de 13 grupos).
- **Expansão no mesmo motor: mesmo motor, outro cadastro.** Barragens de mineração são a porta de entrada; o mercado de verdade é compliance por ativo na mineradora inteira, e depois em todas as barragens do país. O SNISB tem 29.761 barragens cadastradas (água, energia, resíduos industriais), e 8.086 mineradoras recolheram CFEM em 2025. Vaso de pressão (NR-13), emergência (NR-22) e licença ambiental já rodam na demo.
- **Concorrência existe, mas olha de cima para baixo.** Plataformas como Sigalei e Verde Ghaia respondem "o que mudou na lei?". A RegulaIA responde "o que esta barragem precisa entregar, até quando, e já entregou?", e lê o documento de campo que comprova.

## 2. O problema

### Quem sofre

| Pessoa | O que precisa saber | Como faz hoje |
|---|---|---|
| Gerente de geotecnia (dono da barragem na operação) | Quais entregas vencem, por barragem, e se a inspeção de campo abriu alguma obrigação nova (ex.: ISE em 24 h) | Planilha por barragem, agenda pessoal, consultoria que faz a DCE |
| Compliance / jurídico regulatório | O que mudou na norma e o que isso muda nas obrigações já mapeadas | Clipping do DOU, notícia do site da ANM, leitura manual |
| Diretoria de operações | Quanto da operação está exposta a embargo, e onde | Relatório consolidado à mão, quando alguém pede |
| Consultoria de engenharia (DCE, RISR, RPSB) | O calendário de cada cliente e o que cada norma exige | Controle próprio, por cliente |

### O que dá errado

- **Embargo.** No export do SIGBM de 05/11/2026, 76 das 461 barragens na PNSB estão embargadas e 147 aparecem como desembargadas. Na campanha de DCE de setembro de 2026, 15 barragens não enviaram a declaração e 19 não atestaram estabilidade; 34 ficaram embargadas (7% das obrigadas). O embargo suspende a atividade na estrutura: se é a barragem que recebe o rejeito, a produção passa a depender de outra saída.
- **Multa.** A Lei 14.066/2020 incluiu um capítulo de infrações na Lei 12.334/2010: advertência, multa simples ou diária de R$ 2 mil a R$ 1 bilhão, embargo, suspensão da atividade e apreensão de minério e equipamento.
- **Data errada por fonte errada.** A Res. 245/2026 adiou um parágrafo da Res. 220 para 26/12/2029. A notícia no site da ANM diz 31/12/2029. Quem acompanha norma por notícia erra a data; o ato publicado no DOU é o que vale (caso reproduzido na demo).
- **Transição de norma.** A Res. 220 substitui a Res. 95 em 02/08/2027. Cada uma das 461 barragens terá o mapa de obrigações refeito, e o que estava em andamento pela regra antiga precisa ser casado com a nova.
- **Evento que abre obrigação.** Uma anomalia na ficha de inspeção (pontuação 10 pela Res. 95, EC = 5 pela Res. 220) obriga Inspeção de Segurança Especial e registro no SIGBM em 24 horas. Se a informação fica no PDF da ficha, ninguém vê a tempo.

### Por que o empreendedor carrega o risco sozinho

- A ANM tem 53 servidores dedicados a cerca de 911 barragens, segundo a associação dos servidores (ASANM); dos 2.121 cargos da agência, 664 estão ocupados. Auditoria do TCU apontou quadro equivalente a 62% do necessário.
- O modelo é de autodeclaração: a DCE é emitida pelo próprio empreendedor duas vezes por ano. Sem fiscal suficiente, a falha aparece no embargo automático da campanha ou depois de um acidente.
- O custo de cauda é conhecido: R$ 37,7 bilhões no acordo de Brumadinho (2021) e R$ 170 bilhões na repactuação de Mariana (2024). Não tratamos isso como economia esperada do produto; é o contexto que explica por que o setor gasta com segurança e conformidade.

### Fiscalização e casos: o que pesa é o embargo

**Fiscalização da ANM em barragens em 2025** (relatório publicado em 10/03/2026; dados em `data/fiscalizacao_anm.json`):

| Indicador | 2025 |
|---|---|
| Vistorias em campo | 137 (126 em barragens da PNSB) |
| Autos de infração | cerca de 620 |
| Multas | 212 |
| Autos de embargo | 85 |

Comparado às 461 barragens da PNSB, dá cerca de 1 auto de embargo para cada 5 barragens em um ano. É só ordem de grandeza: auto não é barragem distinta (uma barragem pode receber mais de um) e parte dos autos pode ser de barragem fora da PNSB.

**A multa está suspensa; o embargo, não.** A Deliberação ANM nº 436, de 19/03/2026, suspendeu as multas das Resoluções ANM 122/2022 e 223/2025: novos autos com multa, processos em curso sobre a multa e a cobrança. Embargo, interdição e paralisação continuam. A ANM abriu a Consulta Pública nº 1/2026 (10/08 a 24/09/2026) para mudar a Res. 223 e não publicou data para o fim da suspensão. Antes de citar a suspensão como vigente, conferir o DOU do dia.

**Autuação chega a todos os portes.** A Relação nº 52/2026 (DOU de 10/08/2026) trouxe mais de 100 autos de infração contra 14 responsáveis por barragens de rejeito. Entre eles estão Vale, CSN Mineração, AngloGold Ashanti e Gerdau, mas a maior parte dos autos é de mineradoras pequenas e cooperativas, o nosso segmento de entrada. A relação não publica valores.

**Casos públicos:**

| Caso | O que aconteceu | Valor |
|---|---|---|
| Vale, barragem Maravilhas II (Itabirito, 2026) | Embargo publicado em 28/08/2026: o estudo de ruptura e o PAEBM não foram atualizados depois das obras de reforço concluídas em outubro de 2025. Não houve anomalia nova. A barragem foi para nível de alerta | Sem valor publicado |
| AngloGold Ashanti, Planta do Queiroz (Nova Lima, 2023) | O MPMG pediu a suspensão das atividades; o caso envolve declaração de estabilidade; produção parada desde dezembro de 2022 | Pedido de bloqueio de R$ 50 milhões |
| Vale, "barragens-fantasma" (2021) | O MPMG pediu multa por barragem que não estava no cadastro | Pedido de R$ 100 mil por dia e R$ 15 milhões por barragem nova declarada |
| Vale, minas Fábrica e Viga (Ouro Preto, 2026) | A Justiça mandou paralisar atividades | Multa de R$ 3,3 milhões, podendo chegar a cerca de R$ 13,7 milhões; bloqueio de R$ 846,6 milhões negado |
| Mina Casa Branca (Brumadinho, 2020) | Liminar proibiu lançar rejeito na barragem | R$ 50 mil por dia se descumprir |
| Emicon (Brumadinho, 2024) | Descumprimento de acordo com o MPMG sobre a segurança da barragem | R$ 5 mil por dia, até R$ 500 mil |

O que tiramos disso:

- **Maravilhas II é o caso que a torre resolve.** A estrutura não piorou; o documento ficou para trás de um fato da operação (a obra terminou e o estudo não foi refeito). É o tipo de obrigação por evento que a demo abre a partir de um documento de campo. E aconteceu numa empresa com time e orçamento, então o problema não é só de mineradora pequena.
- **Não calculamos "multa média evitada".** Os valores dos autos não são publicados, a faixa legal vai de R$ 2 mil a R$ 1 bilhão (antes da Lei 14.066 o teto do Código de Mineração era de cerca de R$ 3,2 mil) e a cobrança está suspensa. Uma média seria inventada.
- **O custo que pesa é o embargo**, que para a estrutura, e os pedidos judiciais de multa diária e bloqueio. Entram no argumento de compra como risco, não como economia garantida.

### Quanto trabalho é isso (estimativa)

- No cadastro da demo, feito a partir do texto oficial da Res. 95/2022, uma barragem tem de 12 a 18 obrigações e de 59 a 61 entregas com data por ano (FIR e extrato quinzenais, DCE e RISR semestrais, simulados, treinamentos, PAEBM, RCO), além das obrigações por evento e das plurianuais (RPSB).
- Em escala: 461 barragens × cerca de 60 entregas = **cerca de 27,7 mil entregas datadas por ano** só nas barragens de mineração da PNSB. É uma estimativa a partir do cadastro da demo, não um dado da ANM.
- Referência de custo de pessoal: engenheiro civil de geotecnia ganha em média R$ 13,9 mil por mês (CAGED, últimos 12 meses). A Prefeitura de Catalão (GO) estimou em R$ 424,8 mil um contrato de inspeções, DCE, RISR e revisão periódica de uma barragem de abastecimento.

### Quanto o problema custa para uma empresa (hipótese a validar)

Não há dado público do custo médio de controlar obrigações de barragem. A conta abaixo é um cenário ilustrativo, com cada premissa à vista, para ser trocada pelos números das entrevistas:

| Componente | Premissa | Grupo com 4 barragens |
|---|---|---|
| Entregas com data por ano | 4 × cerca de 60 (cadastro da demo) | cerca de 240 |
| Custo-hora de quem controla | Salário de R$ 13,9 mil (CAGED) × 1,8 de encargos (hipótese) ÷ 168 h | cerca de R$ 150 por hora |
| Triagem de norma, controle de prazo e cobrança | De 6 a 20 horas por semana (hipótese; 20 h é o número que a Nomos divulga para manter a lista de normas em dia) | De R$ 47 mil a R$ 156 mil por ano |
| Preço da RegulaIA nas premissas da seção 3 | 4 × R$ 27 mil | R$ 108 mil por ano |

O que a conta mostra: só com horas economizadas, o preço se paga perto do topo da faixa (20 h por semana), não embaixo. O argumento de compra precisa somar o que não entra nessa conta: consultoria chamada às pressas, uma estrutura embargada, retrabalho na troca 95 → 220. Esses custos são reais (casos na seção "Fiscalização e casos"), mas não tratamos multa ou embargo evitado como economia garantida. Por isso preço e horas são as duas primeiras perguntas das entrevistas (seção 8).

## 3. Tamanho do mercado

### Mercado inicial: barragens de mineração na PNSB (SIGBM, 05/11/2026)

| Recorte | Barragens | Empresas / grupos |
|---|---|---|
| Barragens de mineração cadastradas | 908 | 235 empresas |
| Na PNSB | 461 | 126 empresas (125 grupos pela raiz do CNPJ) |
| Na PNSB com dano potencial alto | 243 | 64 grupos |
| Na PNSB em Minas Gerais | 189 | 41 empresas |
| Dano potencial alto em Minas Gerais | 144 | — |
| Em nível de alerta ou emergência | 77 | — |
| Embargadas hoje | 76 | — |

Situação das 461: 288 ativas, 111 em descaracterização (inclui as 37 de alteamento a montante, que a Lei 14.066/2020 mandou descaracterizar) e 62 inativas. As que estão em descaracterização seguem com obrigações e acrescentam as do projeto de descaracterização.

### Como as barragens se distribuem entre os grupos

| Barragens por grupo | Grupos | Barragens | O que isso significa |
|---|---|---|---|
| 1 | 61 | 61 | Pequenas mineradoras: preço baixo, venda por canal (consultoria) |
| 2 a 4 | 48 | 136 | **Alvo inicial**: várias barragens, pouca estrutura de compliance |
| 5 a 9 | 11 | 72 | **Alvo inicial**: dor de consolidar entre unidades |
| 10 ou mais | 5 | 192 | Grandes grupos: venda longa, sistemas próprios, maior contrato |

- Concentração: o maior grupo tem 88 barragens (19%); os 10 maiores têm 230 (50%).
- O segmento de 2 a 9 barragens soma 59 grupos e 208 barragens: grande o bastante para pagar, pequeno o bastante para não ter um time de sistemas fazendo isso internamente.

### Receita potencial (premissas, ajustáveis na aba Mercado da demo)

Cobrança por ativo: R$ 1.500 por barragem por mês e R$ 150 por mês para cada outro ativo ligado a ela (vaso de pressão, licença, unidade), com 5 outros ativos por barragem. Conta: 461 × (R$ 1.500 + 5 × R$ 150) × 12 = **R$ 12,4 milhões por ano** se todas as barragens da PNSB usassem; com 10% de adoção, R$ 1,2 milhão.

| Preço por barragem por mês | 5% de adoção | 10% de adoção | 25% de adoção | 100% |
|---|---|---|---|---|
| R$ 1.000 | R$ 0,48 mi | R$ 0,97 mi | R$ 2,42 mi | R$ 9,68 mi |
| R$ 1.500 | R$ 0,62 mi | R$ 1,24 mi | R$ 3,11 mi | R$ 12,45 mi |
| R$ 2.500 | R$ 0,90 mi | R$ 1,80 mi | R$ 4,49 mi | R$ 17,98 mi |

Valores anuais, sempre com os 5 outros ativos a R$ 150. Por que esse preço é defensável (hipótese a validar com clientes): R$ 27 mil por ano por barragem com os ativos ligados a ela é menos de 7% do contrato de inspeção e declarações estimado por Catalão, e menos de dois meses do salário médio de um engenheiro de geotecnia, sem encargos.

### TAM, SAM e SOM

Mesma premissa de preço em todas as linhas: R$ 27 mil por barragem por ano, com os 5 ativos ligados a ela. Os números de barragens vêm do SIGBM; o preço é hipótese.

| Recorte | Definição | Barragens | Receita por ano |
|---|---|---|---|
| **TAM** (mercado total do produto como ele é hoje) | Todas as barragens de mineração cadastradas no SIGBM | 908 | R$ 24,5 milhões |
| **SAM** (o que o MVP atende) | Barragens de mineração na PNSB, que têm as obrigações da Res. 95 e da Res. 220 | 461 | R$ 12,4 milhões |
| Segmento de entrada | Barragens dos 59 grupos com 2 a 9 barragens na PNSB | 208 | R$ 5,6 milhões |
| **SOM** (meta em 3 anos) | 10% do SAM, vindo do segmento de entrada: cerca de 13 dos 59 grupos | 46 | R$ 1,2 milhão |

A tabela de expansão abaixo não entra no TAM: barragens de água e energia e as normas de toda a mineradora pedem cadastro de normas novas, e o preço para esses ativos ainda não foi pensado.

### Expansão no mesmo motor

A escada em uma frase: **mesmo motor, outro cadastro.** Primeiro as barragens de mineração da PNSB (o mercado inicial acima), depois a mineradora inteira (vasos de pressão, NR-22, licenças: o degrau que a demo já roda), depois as barragens de água, energia e resíduos. Cada degrau pede o cadastro de normas novas, não um produto novo.

| Camada | Tamanho | Fonte |
|---|---|---|
| Barragens de mineração fora da PNSB | 447 | SIGBM |
| Todas as barragens do país (água, energia, resíduo industrial) | 29.761 cadastradas no SNISB em 2025, 48% sem classificação definida | ANA, RSB 2026 |
| Mineradoras ativas (licença, NR-22, NR-13, CFEM) | 8.086 recolheram CFEM em 2025 | ANM |
| Faturamento do setor mineral | R$ 298,8 bilhões em 2025 | IBRAM |
| Software de EHS no mundo | US$ 2,2 a 7,1 bilhões em 2025, conforme a definição de cada relatório | Mordor, Custom Market Insights |
| Gestão de mudança regulatória no mundo | US$ 1,4 a 2,8 bilhões em 2025 | DIResearch, Market Intelo |
| Barragens de rejeito sob o padrão global GISTM (membros do ICMM) | 836 | ICMM, 2025 |

O modelo de dados não fala "barragem", fala **ativo**: uma obrigação tem norma, dispositivo, trecho literal, agenda e evidência. Por isso a mesma torre já cobre na demo um vaso de pressão (NR-13), a unidade (NR-22) e uma licença de operação.

## 4. Concorrência

| Quem | O que faz | Onde é forte | O que não cobre (no que divulga) |
|---|---|---|---|
| **Sigalei** | Monitoramento de DOU, diários estaduais e municipais, agências e SEI; triagem em três camadas com validação humana; tarefas e evidência de aplicabilidade | Amplitude de fontes; clientes como Petrobras e Raízen; foco em seguros, farma, agro e alimentos | Não organiza por ativo nem por período de entrega; não lê o documento operacional que comprova a obrigação |
| **Verde Ghaia (SOGI)** | Gestão de requisitos legais e riscos ligada a ISO e ESG | Base grande: 2.300 clientes declarados, 12 milhões de normas captadas | Requisito legal por empresa e sistema de gestão, não calendário de entregas por estrutura |
| **Ius Natura** (+ Onegreen) | Requisitos legais ESG e licenciamento ambiental | Licenciamento; pertence à Vela LatAm (grupo Constellation Software), que comprou a Onegreen e a juntou à Ius Natura em 2026 | Barragem e as normas da ANM não aparecem no que divulga |
| **LegisMap** | Monitoramento, impacto, inventário e calendário regulatório | Setores financeiro e de saúde (SUSEP, ANS, PREVIC, Bacen, ANPD) | Mineração fora do escopo divulgado |
| **Stance** (Sistema de Requisitos Legais) | Requisitos legais de qualidade, meio ambiente, saúde e segurança nas três esferas; avisa documento perto de vencer; licenças, checklist e multi-site | Mais de 590 clientes declarados; apoio a auditorias ISO 14001 e 45001 | Barragem e ANM não aparecem no que divulga; o vencimento é de documento, não de entrega periódica por estrutura |
| **Nomos** | Agentes de IA monitoram fontes oficiais e normas internas e mandam a nota de impacto, com prazo, obrigação e citação da fonte, como tarefa para a área; API e servidor MCP | Clientes como Braskem, LATAM, Nubank e Mercado Livre; promete ler o ato na fonte, não a notícia | Mineração e ANM fora do que divulga; a tarefa nasce da norma, não do calendário de cada ativo |
| **Legalbot** | Do ato novo à evidência: classifica com IA, distribui a tarefa com prazo e responsável e registra a evidência com rastreabilidade | Financeiro, energia, saneamento, telecom, saúde, infraestrutura; mais de 350 fontes | ANM não está entre os reguladores que lista; a evidência é a de que a área tratou a norma, não o documento de campo que comprova a entrega do período |
| **ProcTracker** | Citado no documento de apoio da equipe | — | Não achamos fonte pública sobre ele; fica fora da comparação até confirmar o que é |
| **GreenLegis**, **Inteligov** | Requisitos legais (BH, desde 1999); inteligência governamental | Nichos estabelecidos | Mesmo limite: norma, não ativo |
| **EHS globais** (Intelex, Enablon, Sphera, Cority) | Suítes de saúde, segurança e meio ambiente | Grandes grupos multinacionais | Caros, em inglês, sem as normas da ANM; implantação longa |
| **Monitoramento geotécnico** (instrumentação, radar, piezômetros) | Dado físico da barragem | Engenharia | Não é concorrente: é fonte de evidência e parceiro de integração |
| **Consultorias de engenharia** | Fazem DCE, RISR, RPSB | Confiança técnica do cliente | **Canal**: atendem muitas barragens e precisam do mesmo calendário |
| **Planilha + e-mail + clipping** | Status quo | Custo zero aparente | É onde a data errada da notícia vira embargo |

Nomos e Legalbot mostram que "norma vira tarefa com prazo e evidência" já é oferta conhecida. Por isso a RegulaIA não se posiciona como a única a fazer isso: o que ela faz e eles não divulgam é organizar por estrutura (cada barragem com suas entregas por período, pela norma que vale no dia) e dar baixa lendo o documento de campo que comprova a entrega.

Sinal de interesse de investidor no tema: a RegDoor (inteligência regulatória com IA) levantou R$ 4,2 milhões em pré-seed com a Antler; a Sigalei levantou R$ 1,3 milhão com GVAngels; a consolidação de Ius Natura e Onegreen pelo grupo Constellation mostra que o setor compra empresas desse tipo.

## 5. Diferencial

1. **Por ativo, não por norma.** Cada barragem tem a lista de obrigações que valem para ela no dia, com responsável, período e status. É o que o gerente de geotecnia usa; o "o que mudou na lei" vem junto, não no lugar.
2. **Fecha o ciclo de baixo para cima.** O PDF da ficha de inspeção dá baixa no período certo, e uma anomalia abre a ISE com prazo de 24 h pela regra da norma que vale naquele dia (Res. 95 ou 220). Plataformas de monitoramento legal param na tarefa.
3. **Vigência como dado.** Cada obrigação tem versões com data de início e fim. A troca 95 → 220 em 02/08/2027 e o adiamento da Res. 245 aparecem como linha do tempo, não como planilha refeita.
4. **Trecho literal e conferência.** Cada obrigação cita o parágrafo que a cria, e um teste confere 66 trechos contra o texto oficial. A conferência achou um "≥" que virava ">" no site da ANM.
5. **Regra antes de IA.** Em agosto de 2026, 7.884 atos do DOU viraram 2 chamadas de IA. Cada análise custou menos de meio centavo de dólar, e cadastrar a Res. 95 inteira custou US$ 0,065. Um cliente novo com as mesmas normas não custa cadastro de novo.
6. **Pessoa decide.** Nenhuma mudança vale sem aprovação, e a IA propõe só o que o Python consegue conferir no texto do ato.
7. **Dado do cliente na conta do cliente.** Provedor e modelo de IA são configuração. O próximo passo é o Bedrock na conta AWS da mineradora, com os documentos sem passar pela nossa.

## 6. Modelo de negócio

| Linha | Como cobra | Para quem |
|---|---|---|
| Assinatura por ativo | Por barragem por mês, mais um valor menor por ativo ligado (vaso, licença, unidade) | Mineradora com 2 a 50 barragens |
| Implantação | Valor único: importar o cadastro do SIGBM, ligar normas, responsáveis e histórico de entregas | Todo cliente novo |
| Licença multiempresa | Por carteira de barragens | Consultoria de engenharia que faz DCE e RISR para vários clientes |
| Enterprise | Contrato anual com integração (SIGBM, ERP, monitoramento) e IA na conta do cliente | Os 5 grupos com 10 barragens ou mais |

Custos que o produto já mede: chamada de IA abaixo de US$ 0,005 por análise; cadastro de uma norma nova de US$ 0,045 (NR-13) a US$ 0,065 (Res. 95); infraestrutura de uma aplicação web pequena. O custo que pesa é humano: curadoria jurídica de cada norma nova e implantação. Uma norma curada serve a todos os clientes sujeitos a ela.

## 7. Riscos e como tratamos

| Risco | Tratamento |
|---|---|
| Responsabilidade técnica: o cliente achar que a ferramenta substitui o responsável técnico | A torre organiza e lembra; a DCE e o relatório continuam assinados pelo engenheiro. Toda mudança passa por aprovação humana |
| IA errar uma data | O Python confere se o trecho existe no ato e se a data está no trecho; leitura incompleta não é registrada |
| A ANM melhorar o próprio SIGBM | O SIGBM registra o que foi entregue; a torre organiza o que falta entregar, junta outras normas (MTE, ambiental) e trata a transição |
| Venda longa em grandes mineradoras | Começar pelo meio (2 a 9 barragens) e por consultorias, que já atendem várias barragens |
| Dados pessoais | O export bruto do SIGBM tem CPF e fica fora do repositório e da nuvem; a análise usa só agregados |

## 8. Próximos passos

1. **Agora até 02/08/2027 (janela da troca 95 → 220):** três pilotos pagos em Minas Gerais, no segmento de 2 a 9 barragens, mais uma consultoria de engenharia como parceira de canal.
2. **Validar preço e disposição a pagar:** dez entrevistas com gerentes de geotecnia e compliance; testar R$ 1.000, R$ 1.500 e R$ 2.500 por barragem.
3. **Produto:** ligar na conta AWS do cliente o Bedrock, o Textract (ficha escaneada) e o S3 (original das evidências), cujos adaptadores já estão no código e testados sem AWS; importação direta do SIGBM; boletim enviado por e-mail ou WhatsApp.
4. **Expansão:** barragens de água e energia (ANA, ANEEL e órgãos estaduais), licenças ambientais estaduais e NRs para toda a mineradora.

## Fontes

Acessadas em novembro de 2026.

1. ANM, SIGBM público, export CSV de 05/11/2026: https://sigbm.anm.gov.br/Publico/ClassificacaoNacionalDaBarragem (agregados em `data/mercado_sigbm.json`).
2. ANM, resumo da campanha de entrega de DCE de setembro de 2026 e de setembro de 2025: https://www.gov.br/anm/pt-br/assuntos/barragens/dce-e-dco
3. Senado Notícias, "Brasil tem nova lei de segurança de barragens" (Lei 14.066/2020, multas): https://www12.senado.leg.br/noticias/materias/2020/10/01/brasil-tem-nova-lei-de-seguranca-de-barragens
4. Machado Meyer, alterações na PNSB (sanções do capítulo V-A): https://www.machadomeyer.com.br/pt/inteligencia-juridica/publicacoes-ij/ambiental/alteracoes-na-politica-nacional-de-seguranca-de-barragens
5. Brasil de Fato, déficit de servidores da ANM (dados da ASANM e da auditoria do TCU): https://brasildefato.com.br/?p=635940 ; Gran Cursos, inquérito do MPF sobre o déficit: https://blog.grancursosonline.com.br/concurso-anm-mpf-instaura-inquerito/
6. IBRAM, "Setor Mineral 2025": https://ibram.org.br/wp-content/uploads/2026/02/02.02.2026-Setor-Mineral-2025.pdf
7. Agência iNFRA, CFEM 2025 (8.086 titulares arrecadadores): https://agenciainfra.com/blog/mineradoras-pagam-r-798-bilhoes-em-royalties-em-2025-aponta-anm/
8. ANA, Relatório de Segurança de Barragens 2024/2025 e RSB 2026: https://static.poder360.com.br/2025/07/Relatorio-Seguranca-Barragens-2024-2025.pdf e https://cenarioenergia.com.br/wp-content/uploads/2026/07/rsb-2026-1.pdf
9. TRF6, acordo de repactuação de Mariana: https://portal.trf6.jus.br/acordo-de-repactuacao-de-mariana-e-assinado-em-brasilia/
10. Salário de engenheiro civil de geotecnia (CAGED): https://www.salario.com.br/profissao/engenheiro-civil-geotecnica-cbo-214230/
11. Edital de Catalão (GO), Concorrência 12/2026: https://alertalicitacao.com.br/!licitacao/PNCP-04750108000152-1-000023-2026
12. Sigalei: https://www.sigalei.com.br e aporte: https://www.baguete.com.br/noticias/sigalei-recebe-aporte-de-r-13-milhao
13. Verde Ghaia: https://www.verdeghaia.com.br
14. LegisMap: https://legismap.com.br
15. Vela LatAm, Onegreen e Ius Natura: https://itforum.com.br/?p=9617197
16. RegDoor, pré-seed: https://startups.com.br/negocios/rodada-de-investimento/nova-startup-de-ia-regulatoria-levanta-pre-seed-de-r-42m/
17. Mordor Intelligence, EHS software: https://marketresearch.com/Mordor-Intelligence-LLP-v4018/EHS-Software-Share-Trends-Statistics-36231302 ; Custom Market Insights: https://www.custommarketinsights.com/?p=75970
18. Gestão de mudança regulatória: https://www.marketresearch.com/Deep-Insights-Research-Co-DIR-v4285/Global-Regulatory-Change-Management-Solutions-41707602 ; https://marketintelo.com/report/regulatory-change-management-software-market
19. ICMM, Tailings Progress Report 2025: https://www.icmm.com/en-gb/research/tailings-management/2025/tailings-progress-report
20. Res. ANM 95/2022, 220/2025 e 245/2026, e os casos da demo: este repositório (`cadastro/`, `curadoria/`, `docs/ARQUITETURA.md`).
21. Stance, Sistema de Requisitos Legais: https://stancebrasil.com.br/solucao/requisitos-legais/
22. Nomos: https://nomos.pro/
23. Legalbot: https://www.legalbot.com.br/
24. ANM, "Relatório destaca melhora no cenário de segurança das barragens de mineração em 2025" (10/03/2026): https://www.gov.br/anm/pt-br/assuntos/noticias/relatorio-destaca-melhora-no-cenario-de-seguranca-das-barragens-de-mineracao-em-2025 (números em `data/fiscalizacao_anm.json`).
25. Demarest, suspensão das multas das Resoluções 122/2022 e 223/2025: https://www.demarest.com.br/anm-suspende-a-aplicacao-das-multas-previstas-nas-resolucoes-122-2022-e-223-2025/ ; consulta pública sobre a Res. 223: https://www.demarest.com.br/anm-inicia-consulta-publica-sobre-proposta-de-alteracao-da-resolucao-anm-no-223-2025/
26. Atlas Público, Relação nº 52/2026: https://atlaspublico.com.br/noticias/anm-lavra-mais-de-100-autos-de-infracao-contra-14-77892
27. Mais Minas, embargo de Maravilhas II: https://maisminas.com.br/anm-embarga-barragem-maravilhas-ii-da-vale-em-itabirito/
28. AngloGold, Planta do Queiroz: https://agenciabrasil.ebc.com.br/geral/noticia/2023-04/anglogold-e-alvo-de-acao-do-mpmg-que-pede-interdicao-de-barragens ; https://www.otempo.com.br/cidades/mpmg-pede-suspensao-das-atividades-da-mineradora-anglogold-em-nova-lima-1.2857803
29. Estado de Minas, paralisação em mina da Vale em Ouro Preto: https://www.em.com.br/gerais/2026/02/7351221-justica-determina-paralisacao-de-atividades-em-mina-da-vale-em-ouro-preto.html
30. "Barragens-fantasma": https://atilalemos.com.br/2021/05/06/barragens-fantasma-mp-pede-que-vale-declare-todas-as-barragens-em-minas/
31. Mina Casa Branca: https://noticias.ambientebrasil.com.br/clipping/2020/04/15/158801-justica-proibe-mineradora-de-lancar-rejeitos-em-barragem-de-brumadinho.html
32. MPMG, Emicon: https://www.mpmg.mp.br/portal/menu/comunicacao/noticias/justica-acata-pedido-do-mpmg-e-determina-adocao-de-medidas-emergenciais-para-garantir-a-seguranca-de-barragem-da-emicon-em-brumadinho.shtml
33. O Tempo, teto de multa antes da Lei 14.066: https://www.otempo.com.br/politica/congresso-se-omite-e-multa-maxima-da-anm-a-vale-e-de-r-3-2-mil-1.2129581
