# Revisão de código da base (07/11/2026)

Revisão somente leitura antes da tarefa de instanciação ([TAREFA_INSTANCIACAO.md](TAREFA_INSTANCIACAO.md)),
atrás de erro de verdade: isolamento entre empresas, papéis, auditoria, SQL, Postgres x SQLite, regra de
negócio, front chamando rota errada. Lidos: `regulaia/` (menos `vigencia.py`, em obra noutra sessão),
`api/`, `agente/` e `front/src/` (lib, moldura e componentes de escrita), com segunda opinião de workers
do DeepSeek (Hermes) em paralelo, um por área; cada achado deles foi conferido no código antes de entrar
aqui. Achados do mais grave ao menos; os marcados **[corrigido]** têm teste que falhava antes e o commit
da correção.

## 1. Um PATCH de cadastro com tipo errado derruba a torre inteira da empresa **[corrigido]**

- `api/rotas/torre.py:735` (`PATCH /ativos/{id}/atributos`) aceita qualquer valor sem conferir o tipo, e
  `regulaia/regras.py:99-101` levanta `RegraInvalida` quando uma regra numérica encontra texto.
- Cenário: a Diretoria (ou qualquer chamada direta à API; o front restringe o input, mas a API é aberta)
  salva `{"dpa2": "alto"}` num ativo. O PATCH responde 200 e grava. A partir daí **toda** chamada de
  `painel`, `ficha`, `boletim`, `calendario`, `planilha` e `transicao` da empresa estoura 500
  (`RegraInvalida: dpa2: 'alto' não se compara com '4'` dentro de `db.obrigacoes_do_ativo`): uma edição
  errada deixa a torre da cliente fora do ar até alguém adivinhar e corrigir o campo.
- Correção: os campos do cadastro saíram de `api/cadastro.py` para o domínio (`regulaia/campos.py`, o
  rascunho da sessão anterior) com `converter`/`conferir`: valor que não é do tipo do campo volta 422 com
  o erro ("Pontuação de perda de vidas do DPA: 'alto' não é número"), valor válido entra convertido
  (número vira número, "sim" vira booleano), campo fora do catálogo continua texto livre, como já dizia o
  contrato da rota. Teste: `tests/test_api.py::test_cadastro_recusa_tipo_errado_e_a_torre_sobrevive` e
  `tests/test_campos.py`.

## 2. Escrita com código de obrigação inexistente (ou de outra cliente) estoura 500 ou grava lixo **[corrigido]**

- `api/rotas/torre.py` (`POST /atribuicoes:720`, `POST /comentarios:728`, `DELETE /entregas:710`): o
  código vai direto a `db._obrigacao_id` (`regulaia/db.py:244`), que levanta `ErroCadastro` — nenhuma das
  rotas trata, vira 500.
- Pior: `_obrigacao_id` busca o código **global**, sem empresa. Cenário: a Morro Alto chama
  `POST /atribuicoes {ativo_id: <B3 dela>, codigo: "LO-01"}` com o código da condicionante da licença da
  Serra Azul — responde 200, grava `responsavel_obrigacao` apontando para a obrigação de outra cliente e
  confirma a existência do código (o resto da API responde 404 justamente para não revelar). O mesmo em
  `POST /comentarios`, que ainda liga o evento à obrigação alheia no histórico do ativo.
- Correção: as três rotas resolvem o código no escopo de quem chama (`e.ve_obrigacao`): inexistente ou de
  outra cliente responde 404, e `ErroCadastro` remanescente vira 422. Teste:
  `tests/test_api.py::test_codigo_de_obrigacao_inexistente_ou_alheio_nao_estoura_nem_grava`.

## 3. `GET /auditoria` com `limite` negativo estoura 500 no Postgres **[corrigido]**

- `api/rotas/admin.py:179`: `limite: int = 200` sem piso; `min(limite, 1000)` deixa passar negativo, e
  `LIMIT -1` é erro no Postgres (no SQLite devolve a trilha inteira, ignorando o teto). Correção:
  `Query(200, ge=1, le=1000)`. Teste no mesmo commit do achado 2.

## Observações (não são erro, ou têm correção planejada em outra tarefa)

- **Código de obrigação é UNIQUE global** (`regulaia/schema.sql`, `db._obrigacao_id`, `db.versao`,
  `db.historico`, rotas que buscam por código): duas clientes não podem ter cada uma a sua "LO-01". Já
  documentado em PLATAFORMA.md; a migração 0005 da tarefa de instanciação troca por único em
  (empresa, código) e leva a empresa a toda busca.
- `db.entregar` grava o evento com `em` = data sem hora (`regulaia/db.py:417`), e o histórico ordena por
  `em DESC`: a entrega do dia aparece antes de eventos com hora do mesmo dia. Cosmético.
- `db.registrar_ato` (`regulaia/db.py:184`): `ON CONFLICT DO NOTHING` por identificador — um segundo ato
  com o mesmo identificador e texto diferente é ignorado em silêncio. Hoje só entra identificador com
  hash do texto (upload) ou id de matéria do DOU; vale atenção se entrar outra fonte.
- CSRF por double submit sem vínculo com a sessão (`api/seguranca.py`): padrão aceito (o cookie de
  sessão é HttpOnly + SameSite=lax); um subdomínio hostil poderia plantar o cookie legível, mas não há
  subdomínios no produto.
- Front: `EditorCadastro` (`front/src/components/cadastro.tsx:81`) filtra `v !== ""`, então não dá para
  limpar um campo preenchido pela interface (a API aceita `null`). UX, não erro.
- Front: `deTexto` numérico faz `Number(...)` sem conferir `NaN` (`cadastro.tsx:44`); o input
  `type=number` segura o caso no navegador e, depois do achado 1, a API recusa o que passar.
