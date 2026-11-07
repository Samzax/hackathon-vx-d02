# Tarefa: descoberta de normas na API e no front

Ler antes: `regulaia/descoberta.py` (o módulo, com a explicação no topo), `regulaia/temas.toml`,
`tests/test_descoberta.py`, `docs/PLATAFORMA.md`. Branch `plataforma`. Commits sem linha de coautoria.
`api/` e `front/` são seus; o domínio (`regulaia/`) já está pronto e testado. Se precisar mudar algo
em `regulaia/descoberta.py`, mude e acrescente o teste.

## O que já existe

- Tabelas `norma_candidata` e `descoberta_busca` (migração `0003_descoberta`, `schema.sql`, `schema_pg.sql`).
- `descoberta.cobertura(conn, empresa_id)`: por jurisdição e tipo de ativo da empresa, o que está no
  catálogo, as fontes lidas (até qual ano, quando), as lacunas conhecidas, o que espera triagem,
  curadoria ou extração, e o `estado` (`ROTULOS_ESTADO` tem o texto para a tela).
- `descoberta.fila(conn, status, jurisdicao)`: a fila da curadoria (relevantes primeiro pela menor confiança).
- `descoberta.decidir(conn, chave, "aprovar"|"descartar", quem, nota)`: decisão da curadoria.
- `descoberta.candidata(conn, chave)`: uma norma, com a triagem da IA (`deveres`, `motivo`, `confianca`, `modelo`).
- A demo carrega `data/descoberta_demo.json` (a fila real, gerada com as fontes de verdade) em `demo.preparar`.
- CLI: `uv run python -m regulaia.descoberta buscar|triar|cobertura|decidir|exportar`.

## O que entregar

**API** (contrato em `api/openapi.json`, testes em `tests/test_api.py`):

- `GET /api/v1/empresas/{id}/cobertura`: a cobertura da empresa. Cliente vê só a dela (404 para outra,
  como o resto); a plataforma vê qualquer uma.
- `GET /api/v1/normas-candidatas?status=relevante&jurisdicao=MG`: a fila. **Só plataforma** (é trabalho
  da curadoria RegulaIA; cliente recebe 403).
- `GET /api/v1/normas-candidatas/{chave}`: uma norma (a chave tem `:` e `/`: usar `{chave:path}` ou
  query string).
- `POST /api/v1/normas-candidatas/{chave}/decisao` `{"decisao": "aprovar"|"descartar", "nota": "..."}`:
  só a curadoria (`seguranca.curadoria`), `quem` = e-mail da sessão, com auditoria (`acao = "descoberta.decidir"`,
  `empresa` vazio).
- Busca e triagem **não** viram rota: são job (`python -m api.jobs descoberta`, como o radar), porque leem
  dezenas de milhares de normas e chamam a IA. Acrescentar ao `api/jobs.py` e ao compose, se quiser.

**Front:**

- Na ficha da empresa (ou na aba Regulatório, para cliente): "Cobertura normativa". Uma linha por
  jurisdição e tipo de ativo, com o estado em cor (coberta verde, mas sempre com as lacunas conhecidas ao lado; curadoria/triagem pendente amarelo;
  sem fonte automática cinza com o texto "cobertura não verificada", **nunca verde**), as normas do
  catálogo, as fontes lidas ("Assembleia de Minas, 1989–2026, lida em ...") e as lacunas conhecidas.
- Para a plataforma, "Normas candidatas": a fila com título, ementa, o que a IA disse (deveres, motivo,
  confiança, modelo, e se leu o texto oficial ou só a ementa: `leu_texto`), link para o texto oficial, o aviso `cita_catalogo` ("altera a Res. ANM 95/2022:
  conferir se o texto consolidado já tem") e Aprovar / Descartar com nota. Filtro por jurisdição
  e status (relevante, aprovada, descartada, irrelevante: a curadoria pode reabrir o que a IA descartou).
- Teste e2e: a curadoria entra, abre "Normas candidatas", aprova uma, e a cobertura da Serra Azul muda
  de "esperando curadoria" para "aprovada, falta extrair".

**Agente MCP** (`agente/servidor.py`, depois da rota): ferramenta de leitura `cobertura_normativa(empresa)`
sobre `GET /empresas/{id}/cobertura`, com teste em `tests/test_agente.py`. Pergunta que ela responde:
"que normas valem para as minhas barragens em MG e quais ainda não estão no catálogo?".
