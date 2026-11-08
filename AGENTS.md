## Summary

Mitra is a regulatory-control platform for operational assets. It organizes obligations, deadlines, supporting evidence, regulatory changes and audit records in one workspace so each responsible person can act on what requires attention.

The application serves multiple personas:

- **Diretoria** oversees all assets and assigns responsibility.
- **Regulatório** reviews and approves regulatory changes.
- **Gestor de área** works with the assets and obligations assigned to the area.
- **Curadoria Mitra** manages platform-wide regulatory content.
- **TI** manages accounts and access.

The primary user experience is the **Caixa de Entrada**, which brings together pending reviews, deliveries, documents and status indicators. The main application is in `front/` (Next.js and TypeScript); the API is in `api/`; regulatory and domain logic is in `mitra/`; and `infra/` contains infrastructure definitions.

## Language and content

- Use professional, business-oriented Portuguese in every user-facing message.
- Prefer concise, direct wording. For example, use **“A partir de”** instead of **“Começa a valer em”**.
- Describe unavailable features as **“Esse recurso está desativado”**, not as **“IA está desligado”**.
- Do not expose implementation details or technical vocabulary in product copy. Do not write messages such as “validado pelo Python” or “a IA pesquisou”. Describe the business outcome instead.
- Write for different professional personas. Text must be understandable without technical knowledge.
- Keep system behavior, security and implementation details in documentation or internal code comments, not in the product interface.

## Interface guidance

- Use the **Caixa de Entrada** as the reference for visual hierarchy and density.
- Keep titles short and focused on the user task. Do not place explanatory paragraphs in titles.
- Subtitles must fit within two lines at the intended layout width. If more explanation is necessary, place it in contextual help or a dedicated section.
- Preserve clear actions, accessible labels and responsive behavior when changing the interface.
- Reuse existing components and visual tokens before introducing new patterns.

## Engineering guidance

- Keep changes within the requested scope and preserve existing role-based access rules.
- Frontend checks: from `front/`, run `npm run lint`, `npm run typecheck`, and the relevant tests or build.
- Backend checks: from the repository root, run relevant tests with `uv run pytest`.
- Do not edit generated API types manually; regenerate them from the API schema when needed.
- Update tests whenever a visible label, accessibility label or access rule changes.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<optional scope>): <description>`, with type one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert` (description may be in Portuguese). Enable the local check once per clone with `git config core.hooksPath .githooks`; CI runs the same check on new commits.
