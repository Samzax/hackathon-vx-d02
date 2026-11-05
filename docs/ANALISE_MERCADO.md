# Análise de mercado e viabilidade: RegulaIA

Torre de controle regulatória por ativo, começando por barragens de mineração. Hackathon VX, Desafio 02. Versão de 05/11/2026.

Todo número deste documento tem fonte (lista no fim) ou é marcado como **premissa**. Os números do SIGBM vêm do export público de 05/11/2026, guardado em agregados em `data/mercado_sigbm.json`, e são conferidos por teste (`tests/test_documentacao.py`). O arquivo bruto não entra no repositório porque traz CPF de pessoas físicas.

## 1. Resumo

- **O problema existe e custa caro.** Das 461 barragens de mineração na Política Nacional de Segurança de Barragens (PNSB), 76 estão embargadas hoje e outras 147 já foram embargadas e liberadas: 223 (48%) passaram por embargo. A multa da Lei 14.066/2020 vai de R$ 2 mil a R$ 1 bilhão.
- **O volume é grande e muda de base em 2027.** Uma barragem na PNSB tem de 12 a 18 obrigações e cerca de 60 entregas com data por ano só pela Res. ANM 95/2022. Em 02/08/2027 a Res. ANM 220/2025 substitui a 95, e a 220 já foi alterada antes de valer (Res. ANM 245/2026).
- **O fiscal não vai achar o erro por você.** A ANM tem 53 servidores para fiscalizar cerca de 900 barragens, segundo a associação dos servidores. O controle é por declaração do próprio empreendedor: quem erra a data descobre no embargo.
- **Mercado inicial bem definido.** 125 grupos econômicos com barragem na PNSB; 64 deles têm barragem de dano potencial alto (243 barragens, 144 em Minas Gerais). Com as premissas de preço da seção 4, as 461 barragens valem R$ 12,4 milhões por ano.
- **Expansão no mesmo motor.** O SNISB tem 29.761 barragens cadastradas (água, energia, resíduos industriais), e 8.086 mineradoras recolheram CFEM em 2025. Vaso de pressão (NR-13), emergência (NR-22) e licença ambiental já rodam na demo.
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

### Quanto trabalho é isso (estimativa)

- No cadastro da demo, feito a partir do texto oficial da Res. 95/2022, uma barragem tem de 12 a 18 obrigações e de 59 a 61 entregas com data por ano (FIR e extrato quinzenais, DCE e RISR semestrais, simulados, treinamentos, PAEBM, RCO), além das obrigações por evento e das plurianuais (RPSB).
- Em escala: 461 barragens × cerca de 60 entregas = **cerca de 27,7 mil entregas datadas por ano** só nas barragens de mineração da PNSB. É uma estimativa a partir do cadastro da demo, não um dado da ANM.
- Referência de custo de pessoal: engenheiro civil de geotecnia ganha em média R$ 13,9 mil por mês (CAGED, últimos 12 meses). A Prefeitura de Catalão (GO) estimou em R$ 424,8 mil um contrato de inspeções, DCE, RISR e revisão periódica de uma barragem de abastecimento.

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

### Expansão no mesmo motor

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
| **GreenLegis**, **Inteligov** | Requisitos legais (BH, desde 1999); inteligência governamental | Nichos estabelecidos | Mesmo limite: norma, não ativo |
| **EHS globais** (Intelex, Enablon, Sphera, Cority) | Suítes de saúde, segurança e meio ambiente | Grandes grupos multinacionais | Caros, em inglês, sem as normas da ANM; implantação longa |
| **Monitoramento geotécnico** (instrumentação, radar, piezômetros) | Dado físico da barragem | Engenharia | Não é concorrente: é fonte de evidência e parceiro de integração |
| **Consultorias de engenharia** | Fazem DCE, RISR, RPSB | Confiança técnica do cliente | **Canal**: atendem muitas barragens e precisam do mesmo calendário |
| **Planilha + e-mail + clipping** | Status quo | Custo zero aparente | É onde a data errada da notícia vira embargo |

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
3. **Produto:** Bedrock na conta do cliente; OCR (Textract) para ficha escaneada; importação direta do SIGBM; boletim enviado por e-mail ou WhatsApp.
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
