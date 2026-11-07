# Tarefa: cobertura de fontes, recall e verticais

Decisões do usuário em 7/11/2026, a partir da revisão dos fluxos. Objetivo: nenhum falso negativo
silencioso — ou a norma é capturada, ou a lacuna aparece com nome. Este documento junta tudo o que
está aberto; os itens 1 a 6 são novos, o item 7 consolida o resto.

## 1. Radar do DOU além da ANM (aprovado em 7/11)

Hoje o radar diário descarta tudo que não é ANM (`api/jobs.py` → `XmlAct.is_anm`). Isso joga fora,
por construção: portaria do MTE que altera NR (a Portaria 105/2026, que altera a NR-22, está no nosso
catálogo e **não passaria** no radar), lei federal que altera a 12.334 (como a 15.355/2026), atos de
ANA, Ibama e Conama.

Mudança — camada 0 em dois estágios, ainda sem IA:

- **Órgãos de interesse** (constante em `collector/dou.py`): ANM; MTE (inspeção do trabalho/SST);
  MMA, Ibama, ICMBio; ANA; Conama; Atos do Poder Legislativo e do Poder Executivo (leis, decretos, MPs).
- **Fora da lista**: o ato ainda entra se a ementa/identifica casar os termos do `mitra/temas.toml`
  (reaproveitar `descoberta.temas_da`), para a lista de órgãos nunca ser o único guarda.
- Tipos de ato: `NORMATIVE_TYPES` + identifica começando com "Lei", "Decreto", "Medida Provisória".
- Nada muda depois do filtro: a camada 1 (`mitra/triagem.candidatas`) continua o funil e o custo de IA
  segue perto de zero.

Arquivos: `collector/dou.py`, `collector/xml_dou.py`, `api/jobs.py`, `tests/test_dou.py`.
Validação: reprocessar `S01082026.zip` e comparar o funil (hoje 7.884 → 825); a Portaria MTE 105/2026
é o caso de teste canônico — tem de ser capturada.

## 2. Recall medido (eval de falso negativo) — hoje não existe

Três gabaritos, no padrão do `tests/pergunta_avaliacao.toml`:

- **Radar (camada 0):** fixtures de atos reais que DEVEM passar (Portarias MTE 105 e 261/2026,
  Res. ANM 245/2026, uma lei federal, um ato da ANA) e que devem ser descartados (crédito, homenagem,
  concessão de lavra individual). Roda no CI, sem IA.
- **Descoberta (busca + camada 0):** toda norma que o catálogo já tem (`mitra/fontes.py` +
  `cadastro/*.csv`) e que a fonte lista tem de sair como candidata — recall 100% no que conhecemos.
  Normas sem fonte (DN Copam 62/2002) ficam no gabarito marcadas como "lacuna conhecida": o teste
  prova que a cobertura informa, não que cobre.
- **Triagem IA (pela ementa):** `tests/descoberta_recall.toml` com ementas reais rotuladas
  (relevante/irrelevante + tipo de ativo); novo subcomando `python -m mitra.descoberta avaliar`
  medindo recall e precisão por modelo (DeepSeek × Haiku × Sonnet). Meta: recall 100% no gabarito;
  precisão é secundária (falso positivo custa só triagem humana). Mantidos: confiança mínima 0,7 +
  curadoria humana decide (aprovado em 7/11).
- `--revisar` (relê pelo texto os descartes duvidosos) deixa de ser manual: entra no job semanal
  para descartes com confiança < 0,85.

## 3. Descoberta pelo contexto da empresa (ex.: entra uma empresa do PR)

O que já existe: `descoberta.perfil()` monta (jurisdição × tipo de ativo) a partir dos ativos de
todas as clientes — ativo com UF=PR cria a necessidade "PR × barragem" sozinho — e a cobertura marca
"sem fonte automática" na instanciação (etapa 4). O que falta:

- **Disparo na instanciação:** ao gravar ativos de uma UF nova, rodar a descoberta daquela jurisdição
  na hora (não esperar domingo). Com conector → busca; sem conector → abrir automaticamente um item na
  fila da curadoria ("catalogar o estoque de PR à mão"). Hoje a lacuna aparece na tela mas não vira tarefa.
- **Conectores estaduais sob demanda da carteira:** 1 conector por assembleia (lista anual + ementa +
  situação de vigência), no molde do da ALMG. Verificar dados abertos de ALEP (PR), ALESP (SP) e
  ALEPA (PA) primeiro; ~1 dia por conector. Estado sem conector continua lacuna declarada.
- **Cidade da empresa (decisão de 7/11):** legislação municipal e alvarás NÃO têm fonte automática —
  entram **no cadastro da empresa, na fase de consultoria/implantação**: checklist na etapa 5 da
  instanciação ("alvarás e exigências municipais da sede e de cada unidade enviados?"), virando
  obrigação própria pelo pipeline de licenças.
  **Feito (7/11):** tabela `exigencia_municipal` (migração 0007), `instanciacao.checklist_municipal` /
  `responder_municipal`, `GET/PUT /empresas/{id}/instanciacao/municipal` e a seção "Alvarás e exigências
  municipais" na tela Instanciação. Cada local (sede e cada unidade) fica confirmado ou "não se aplica";
  o alvará enviado em Licenças aparece como prova do local, confirmar sem ele pede nota e "não se aplica"
  sempre pede o porquê. A etapa 5 só fica pronta com todos os locais respondidos.

## 4. Alvará no cadastro (pequeno)

- Adicionar `"alvara"` a `TIPOS_LICENCA` (`mitra/instanciacao.py:65`) + rótulo na tela.
- O resto já funciona: `mitra/licencas.py` é agnóstico ao tipo — PDF → IA propõe condicionantes com
  trecho literal → Python confere → Regulatório aprova → vencimento e renovação viram obrigação da
  empresa. Ou seja: alvará entra no perfil da empresa, como as licenças.

## 5. Modelos (decisão de 7/11)

Para **ler os dados do catálogo** (extração de norma, dado público):

1. **Agora: Sonnet 5** (no evento, Bedrock `us.anthropic.claude-sonnet-5`; fora, `claude-sonnet-5-5`).
2. **Depois: medir o Haiku 5.5** no mesmo gabarito de extração (diff contra `data/extraido/*.json`).
3. **Então decidir:** delegar ao DeepSeek v4.1 **só dado não sensível** (norma publicada é pública),
   ou deixar tudo no Haiku 5.5. Custo do DeepSeek no OpenCode: US$ 10/mês dão US$ 100 de uso.

Implementação: hoje `mitra/modelos.toml` roteia só por camada (2/3). Criar roteamento **por tarefa com
flag de sensibilidade**: tarefas sensíveis (licenças, evidências, pergunta — texto de cliente) só
roteiam Anthropic/Bedrock; tarefas públicas (extrator, triagem da descoberta, impacto de norma pública)
podem cair para DeepSeek. `Roteador.pedir_json` já recebe `tarefa`; falta usá-la no roteamento.
Lembrete: a conta do evento não tem modelos 5.5 no allowlist do Bedrock (Sonnet 5 e Haiku 4.5 sim).

## 6. Vertical "obras em geral" — dá, em três fases

- **Fase A (destravar, horas):** prompt do analisador de impacto parametrizado por vertical
  (`mitra/impacto.py`, `SISTEMA` diz "barragens de mineração" fixo); tipo de ativo `obra` em
  `mitra/campos.py` + seção em `temas.toml` (canteiro, edificação, obra*...). O radar multi-órgão do
  item 1 já serve (MTE cobre NR-18/NR-35).
- **Fase B (conteúdo, dias):** catálogo NR-18, NR-35 e ART/CREA pelo pipeline extrator → curadoria
  que já existe; tipos de documento de evidência (diário de obra, ART, laudo estrutural) no
  dicionário de `mitra/evidencias.py`; gatilhos por norma no padrão existente (acidente/CAT → plano
  de ação; embargo/interdição → obrigação por evento). O mecanismo de gatilho (acionamento, agenda
  `evento`) é genérico; cada regra de detecção é pequena e por norma.
- **Fase C (prova):** 1 obra fictícia na carteira da demo mostrando que torre, boletim e Pergunte à
  torre são os mesmos.

## 7. Consolidado — tudo que está aberto em 7/11

| # | Item | Dono |
|---|---|---|
| 1 | Radar multi-órgão (item 1) | código |
| 2 | Evals de recall (item 2) | código |
| 3 | Descoberta na instanciação + conectores estaduais (item 3) | código |
| 4 | `"alvara"` em TIPOS_LICENCA (item 4) | código, 1 linha |
| 5 | Roteamento por tarefa/sensibilidade + Sonnet 5 na extração (item 5) | código |
| 6 | Vertical obras, fases A→C (item 6) | código |
| 7 | Decidir: 22 tipos de documento (código) × "23" (docs/ARQUITETURA.md) | usuário |
| 8 | Re-rodar o eval do Pergunte à torre pós-rename (prompt mudou, cache invalidou) | código |
| 9 | Tela "Nova empresa" no front (instanciação; API pronta) | código |
| 10 | Push `main` + papel IAM `github-deploy` → auto-deploy (comandos em `infra/README.md`) | usuário |
| 11 | CI verde e remover o worktree `plataforma-pergunta` | código |
| 12 | IA na AWS (MITRA_BEDROCK=1 + IAM Sonnet 5/Haiku 4.5) | usuário dá o go |
| 13 | Vídeo da demo | usuário + código |
| 14 | Revisão por IA no aceitar/rejeitar norma | aguarda o go |

## 8. Anti-NR-3: nenhuma lacuna depende de alguém lembrar dela (implementado em 7/11, à noite)

O caso NR-3 (gatilho de embargo planejado sem a norma no catálogo, descoberto por acaso no meio da
implementação) expôs três buracos. Fecharam assim — a decisão humana continua onde sempre esteve
(curadoria), o que acabou foi a dependência de memória:

1. **Conector de estoque para as NRs** (`descoberta.ler_nrs`, fonte `mte`): a página oficial das NRs
   vigentes é lida a cada rodada; NR vigente vira candidata sem depender de termo (universo pequeno e
   curado) e a revogada fica marcada. A lacuna "NRs catalogadas à mão" saiu do temas.toml.
2. **Grafo de citações do catálogo** (`python -m mitra.descoberta lacunas`, também no job semanal):
   varre cadastro/ + data/extraido/ atrás de normas citadas (lei, decreto, resolução, NR, CLT) que não
   estão nem no catálogo nem na fila; cada uma vira candidata relevante com a proveniência
   ("NR-1 — citada por NR-13, NR-18, NR-22"). Na primeira rodada real achou 7, inclusive a NR-1 (GRO).
3. **Integridade gatilho↔obrigação por teste** (`tests/test_eventos_cobertos.py` + mapa `[eventos]` no
   temas.toml + registro `GATILHOS` em evidencias.py): gatilho sem obrigação no cadastro, evento sem
   dono ou termo dessincronizado são teste vermelho (o próprio teste pegou uma dessincronia ao nascer).
4. **Extração automática na aprovação** (`api/rotas/descoberta.py::_extrair_aprovada`): candidata
   aprovada dispara a extração em segundo plano (texto baixável -> IA propõe -> Python confere ->
   data/extraido/); a pessoa continua escolhendo o que entra. Sem texto baixável ou sem IA, fica no
   caminho manual, com log.
5. **A própria NR-3 catalogada** (cadastro/nr3.csv, trechos literais conferidos por teste contra o PDF
   oficial): termo de embargo/interdição agora abre por gatilho as obrigações 3.5.4 e 3.5.5 (segurança
   na correção e salários na paralisação) — e o termo só abre, não dá baixa em nada (`apenas_aciona`).

Pendências desse bloco: conector de alterações das NRs pelas páginas de portarias SST (hoje a mudança
de NR chega pelo radar do DOU, órgão MTE); triagem pela ementa continua fraca para título curto de NR
(a NR-3 seria descartada pela IA se não estivesse catalogada — mitigada porque NR entra sem termo e a
curadoria lê a fila completa).
