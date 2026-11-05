# Pitch (5 minutos): rascunho

Rascunho para ensaiar e reescrever com a voz de quem apresenta. Todo número aqui sai do repositório e é conferido por teste (`tests/test_documentacao.py`); o que é premissa está marcado como premissa. A demo do meio segue o [roteiro de 3 minutos](ROTEIRO_DEMO.md), encurtado.

Critérios que a organização citou: técnica (30%), pitch (15%) e tamanho de mercado. O tempo abaixo segue esse peso: metade é a torre funcionando.

## 0:00 – 0:40 · O problema, num caso real

- **Fala:** "Em 31 de julho a ANM publicou a Resolução 245. Ela adia um único parágrafo da norma de barragens, o que tira da Zona de Autossalvamento quem trabalha na lavra e no beneficiamento: de 2 de agosto de 2027 para 26 de dezembro de 2029. A notícia no site da própria ANM diz 31 de dezembro. O ato diz 26. Quem acompanha norma por notícia e planilha erra a data; quem muda a planilha inteira erra o resto, porque as outras 23 obrigações da norma não mudaram."
- Na tela: a aba **Mudanças**, com o antes/depois da OB-01 e o trecho do ato.

## 0:40 – 1:10 · Por que agora

- **Fala:** "Em 2 de agosto de 2027 a Resolução 220 substitui a 95. As 126 empresas com barragem na Política Nacional de Segurança de Barragens, 461 barragens, vão refazer o mapa de obrigações, e a regra nova já mudou antes de valer. Hoje, 77 dessas barragens estão em nível de alerta ou emergência."
- Fonte: SIGBM público, exportado em 05/11/2026 (`data/mercado_sigbm.json`).

## 1:10 – 3:40 · A torre funcionando

Seguir o [roteiro](ROTEIRO_DEMO.md) em versão curta:

1. **Hoje (40 s):** 8 ativos, 72 obrigações de 5 normas; 4 atrasadas, 1 dado faltando, 3 vencendo. Ler `FIR_B2_2026-11-1Q_anomalia.pdf`: a regra lê ativo, documento e data sem IA, e a anomalia de pontuação 10 abre a ISE com prazo de 24 h.
2. **Mudanças (40 s):** "Mudou uma obrigação. As outras 23 ficaram iguais." Clicar em **Aprovar**: nada muda sem uma pessoa.
3. **Transição (40 s):** contagem até 02/08/2027 e, em 26/12/2029, ANM e MTE (NR-22) vencendo no mesmo dia sobre a ZAS.
4. **Radar (30 s):** agosto de 2026 inteiro, 7.884 atos → 825 da ANM → 2 para a IA → 1 muda o cadastro.

## 3:40 – 4:20 · Por que funciona (viabilidade técnica)

- **Fala:** "Regra antes de IA: 99,97% do Diário Oficial nunca chega ao modelo. Quando chega, a IA propõe, o Python confere se o trecho existe no ato e se a data está no trecho, e uma pessoa aprova. Cada análise custou menos de meio centavo de dólar; cadastrar a Resolução 95 inteira custou US$ 0,065. A empresa pode usar a própria conta de IA, inclusive Bedrock na AWS, e a demo roda sem internet a partir do cache."
- Se perguntarem como se sabe que o cadastro está certo: cada obrigação cita o parágrafo que a cria, e um teste confere os 66 trechos contra o texto oficial.

## 4:20 – 4:50 · Mercado e modelo

- **Fala:** "Cobrando por barragem e por ativo, só as 461 barragens da PNSB dão R$ 12,4 milhões por ano; com 10% de adoção, R$ 1,2 milhão. Fora dessa conta ficam as outras 447 barragens de mineração e setores com o mesmo problema: energia, saneamento, óleo e gás."
- **Premissas, não dados** (dá para mudar ao vivo na aba **Mercado**): R$ 1.500 por barragem por mês, 5 outros ativos por barragem a R$ 150 por mês cada, 10% de adoção. Conta: 461 × (R$ 1.500 + 5 × R$ 150) × 12.

## 4:50 – 5:00 · Fechamento

- **Fala:** "Cada gestor vê só os ativos dele, com o artigo e o trecho que criam cada obrigação, e ninguém precisa ler norma. A norma muda, a torre muda junto, e uma pessoa decide."

## Ensaio

- Cronometrar duas vezes; se passar de 5 min, cortar primeiro o passo 3 da demo (Transição).
- Antes de subir: barra lateral em 07/11/2026, "Diretoria (todos os ativos)", **Recriar demo**.
- Perguntas prováveis e respostas curtas: tabela "Se perguntarem" do [roteiro](ROTEIRO_DEMO.md).
