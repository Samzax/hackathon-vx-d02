# Tarefa: front em Next.js (fase 2A)

Ler antes: `docs/PLATAFORMA.md` (plano e estado), `README.md` (o que a torre faz e as abas),
`api/openapi.json` (o contrato). Branch `plataforma`. Commits sem linha de coautoria.
Outra sessão está fazendo a infra AWS em `infra/` ao mesmo tempo: **não mexa em `infra/`**.
Quem mexe em `api/` e no front é você.

## O que entregar

Um front de produto (não protótipo) em `front/`, que substitui o Streamlit como interface
principal, falando só com a API.

- **Stack:** Next.js (App Router) + TypeScript + Tailwind; `output: "export"` (estático). Em
  produção a própria API serve `front/out` na mesma origem (montar `StaticFiles` em `api/main.py`
  quando a pasta existir), então o cookie de sessão e o CSRF funcionam sem CORS. Em dev, Next na
  3000 e API na 8000 (CORS já liberado para `http://localhost:3000` com credenciais).
- **Tipos:** gerados do `api/openapi.json` com `openapi-typescript` (script `npm run tipos`); cliente
  fetch com `credentials: "include"` e o cabeçalho `X-CSRF-Token` (cookie `mitra_csrf`) em toda escrita.
- **Visual:** marca própria (`assets/marca.svg`, `assets/logo_claro.svg`, `assets/logo_escuro.svg`),
  claro e escuro, português, responsivo (desktop primeiro, mas usável no celular). Cores de status
  iguais às da torre: atrasada vermelho, dado faltando lilás, vence em breve amarelo, em dia verde,
  por gatilho azul. Nada de dado inventado: tudo vem da API.
- **Telas** (seguem as abas do README):
  - Entrar: botão "Entrar na demo" (POST /auth/demo) e e-mail/senha.
  - Moldura: menu lateral por papel, seletor "Quem está olhando" para a conta de teste
    (PUT /auth/visao, inclui "Curadoria Mitra (plataforma)"), seletor de empresa para a
    plataforma, data "hoje" com os atalhos de viagem no tempo (Demo 07/11/2026, Res. 220
    02/08/2027, ZAS 27/12/2029) passados como `hoje` nas consultas.
  - Caixa de entrada: os 5 números (cada um filtra), pendências com o botão que resolve
    (registrar entrega em diálogo com comprovante opcional, completar cadastro, decidir mudança),
    envio de documento (PDF -> /evidencias/leitura -> conferência -> /evidencias/registro, com os
    gatilhos e avisos), boletim (md/pdf) e .ics.
  - Ativos: mapa (posições de `data/posicoes_demo.json`; criar rota na API se precisar),
    tabela com contagem por status, ficha do ativo (pendências com trecho literal e dispositivo,
    todas as obrigações, evidências, histórico, cadastro editável, área responsável para a Diretoria).
  - Entregas: filtros (status, ativo, norma, responsável, texto, prazo), seleção múltipla
    (entregar, passar para outra área, comentar), calendário do mês, exportar Excel e .ics.
  - Regulatório: Mudanças (antes/depois, trecho do ato, conferência do Python, aprovar, corrigir e
    aprovar, rejeitar, conforme `decide`/`quem_decide`; histórico da obrigação), Radar do DOU
    (funil, custo real da IA, "teste com um ato seu"), Transição e linha do tempo (Gantt por ativo).
  - Sobre: Mercado (SIGBM) e Como funciona.
  - Usuários e acessos (TI) e Auditoria.
- **Testes:** vitest nos utilitários (formatação, cliente da API) e Playwright ponta a ponta contra
  a API real com SQLite (`uv run uvicorn api.main:app`): entrar na demo, ver 4 atrasadas, registrar
  uma entrega, gestor vendo só a área dele, curadoria aprovando a Res. 245.
- **CI:** job `front` em `.github/workflows/ci.yml` (npm ci, tipos conferidos contra o openapi,
  lint, typecheck, vitest, build) e o Playwright num job que sobe a API.
- Atualizar `docs/PLATAFORMA.md` (2A) e o README (como rodar o front). Rodar `uv run pytest -q`
  antes de commitar se mexer em `api/`, e `uv run python -m api.contrato` se o contrato mudar.
