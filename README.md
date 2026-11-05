# Torre de controle regulatória: barragens de mineração

Hackathon VX, Desafio 02. Rio de Janeiro, 7 e 8 de novembro de 2026.

O sistema lê o Diário Oficial da União todos os dias, separa os atos da ANM e mostra quais obrigações de uma mineradora mudaram, com o artigo e o prazo novos.

## Caso de demonstração

A Resolução ANM nº 245/2026 adiou o art. 7 §1 da Res. ANM 220/2025 de 2 ago. 2027 para 26 dez. 2029. Todo o resto da Res. 220 continua como estava. Um sistema correto muda uma obrigação e deixa as outras quatorze iguais.

## Conteúdo

| Arquivo | O que é |
|---|---|
| [PREP.md](PREP.md) | Pesquisa, fontes de dados, critérios de avaliação e pendências |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Decisões de arquitetura: banco, custo da IA, provedores |
| [seed_obligations.csv](seed_obligations.csv) | 15 obrigações da Res. 220/2025, no estado anterior à Res. 245. A OB-01 é o teste principal |
| `regulaia/` | Banco (SQLite), versionamento de obrigações e regras de aplicabilidade |
| `collector/` | Leitor do XML mensal do DOU (dados abertos) e das páginas já salvas em cache |
| [data/serra_azul.json](data/serra_azul.json) | A mineradora fictícia da demo: 4 barragens com perfis reais do SIGBM |
| [data/mercado_sigbm.json](data/mercado_sigbm.json) | Números de mercado com fonte: barragens e empresas no SIGBM |

## Como rodar

Requer o [uv](https://docs.astral.sh/uv/). Ele instala o Python 3.13 e as dependências na primeira execução.

```bash
uv sync
uv run pytest
uv run python -m regulaia.demo                                  # monta o banco da demo
uv run python -m collector.xml_dou data/raw/dou/S01082026.zip   # funil do mês
```

O ZIP mensal vem do [portal de dados abertos da Imprensa Nacional](https://www.in.gov.br/acesso-a-informacao/dados-abertos/base-de-dados) (Seção 1, ano e mês) e fica em `data/raw/dou/`, fora do Git.

O coletor lê só o que está em `cache/`. Ele não acessa o site do DOU, porque o `robots.txt` de www.in.gov.br proíbe robôs.
