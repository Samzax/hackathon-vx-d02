# RegulaIA: torre de controle regulatória para mineração

Hackathon VX, Desafio 02. Rio de Janeiro, 7 e 8 de novembro de 2026.

A torre mostra, para cada ativo de uma mineradora, tudo o que ele precisa cumprir hoje: a obrigação, a norma, o artigo, o trecho literal que a cria, quando vence e se já foi comprovada. Os ativos podem ser:

- barragem;
- vaso de pressão;
- unidade de mineração;
- licença ambiental.

Ela se atualiza por dois caminhos:

- **norma nova:** o radar lê o Diário Oficial, acha o ato que mexe numa obrigação e propõe a mudança, que uma pessoa aprova;
- **documento da operação:** uma FIR, um laudo ou um boletim vira evidência, e a obrigação fica em dia.

Cada gestor vê só os seus ativos e ninguém precisa ler norma nenhuma.

## A demo

A Mineradora Serra Azul é fictícia, mas os perfis das quatro barragens vêm do SIGBM. A empresa tem 8 ativos e 63 obrigações cadastradas, em 7 de novembro de 2026:

| Aba | O que mostra |
|---|---|
| **Hoje** | Status de cada obrigação por ativo (🔴 atrasada, ⚪ dado faltando no cadastro, 🟡 vence em breve, 🟢 em dia, 🔵 por gatilho). Também recebe documentos: o PDF de uma FIR dá baixa na quinzena, e uma anomalia de pontuação 10 dispara o aviso de Inspeção de Segurança Especial |
| **Transição e linha do tempo** | O que muda quando a Res. ANM 220/2025 substitui a Res. 95/2022 (2/8/2027), por tema: o que continua, o que é novo, o que acaba. Mostra também as datas futuras de cada ativo |
| **Mudanças** | Versões propostas por atos novos, com antes/depois, o trecho do ato e a conferência do Python. Só valem depois de aprovadas |
| **Radar do DOU** | O funil de um mês do DOU (7.884 atos → 825 da mineração → 2 candidatos → 1 mudança) e o custo real da IA |

**Caso principal.** A Res. ANM 245/2026 adiou o art. 7 §1 da Res. 220/2025 (mapa de inundação com a ZAS) de 2/8/2027 para 26/12/2029. Um sistema correto muda essa obrigação e deixa as outras quatorze iguais. A NR-22 (Portaria MTE 105/2026, item 22.24.8) dá a mesma data para barragens não alteadas a montante. A linha do tempo mostra as duas normas, ANM e MTE, convergindo.

## O que está cadastrado

| Arquivo | Norma | Obrigações |
|---|---|---|
| [cadastro/res95_2022.csv](cadastro/res95_2022.csv) | Res. ANM 95/2022 (vale até 1/8/2027) | 21 |
| [seed_obligations.csv](seed_obligations.csv) | Res. ANM 220/2025 (vale a partir de 2/8/2027) | 15 |
| [cadastro/nr13.csv](cadastro/nr13.csv) | NR-13, vasos de pressão (Tabela 2, por categoria) | 10 |
| [cadastro/nr22.csv](cadastro/nr22.csv), [nr22_zas.csv](cadastro/nr22_zas.csv) | NR-22, mineração | 11 |
| [cadastro/lo_serra_azul.csv](cadastro/lo_serra_azul.csv) | Licença de operação fictícia e LC 140/2011 | 6 |

Cada obrigação tem três campos que a máquina lê:

- **regra:** a quais ativos se aplica (ex.: `dpa = alto`, `metodo_construtivo != montante e trabalhadores_zas`);
- **agenda:** quando vence (ex.: `quinzenal+15d`, `anos:3`, `unica`);
- **trecho:** o texto literal da norma.

O cadastro sai das normas assim: a IA propõe as obrigações a partir do texto (`regulaia/extrator.py`), uma pessoa escolhe e ajusta (`curadoria/*.csv`) e o script gera o CSV final (`regulaia/curadoria.py`). Repetir o processo dá o mesmo resultado.

## Conteúdo

| Caminho | O que é |
|---|---|
| [app.py](app.py) | A interface (Streamlit) |
| `regulaia/` | Banco, versões, regras, agenda, torre, extrator, impacto, leitor de evidência |
| `collector/` | Leitor do XML mensal do DOU (dados abertos) |
| [data/serra_azul.json](data/serra_azul.json), [data/historico_serra_azul.json](data/historico_serra_azul.json) | A empresa da demo e o histórico de entregas, com as falhas planejadas |
| `data/exemplos/` | PDFs fictícios para o leitor de evidência |
| [data/mercado_sigbm.json](data/mercado_sigbm.json) | Números de mercado com fonte: barragens e empresas no SIGBM |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Decisões de arquitetura e custos medidos |
| [PREP.md](PREP.md) | Pesquisa, fontes de dados, critérios de avaliação |

## Como rodar

Requer o [uv](https://docs.astral.sh/uv/). Ele instala o Python 3.13 e as dependências na primeira execução.

```bash
uv sync
uv run pytest
uv run streamlit run app.py                                     # a torre (interface)
uv run python -m regulaia.demo                                  # só monta o banco da demo
uv run python -m regulaia.exemplos                              # gera os PDFs de exemplo
uv run python -m collector.xml_dou data/raw/dou/S01082026.zip   # funil do mês
uv run python -m regulaia.impacto data/raw/dou/S01082026.zip    # impacto com IA (precisa de chave no .env)
RUN_IA=1 uv run pytest tests/test_ia_real.py -v                 # casos de ouro com o modelo real
uv run python -m regulaia.extrator ORIGEM NORMA TIPO DESTINO    # norma -> obrigações propostas (IA)
uv run python -m regulaia.curadoria ...                         # escolhas humanas -> cadastro/*.csv
```

A interface funciona sem chave e sem internet. As respostas da IA ficam em `data/cache_ia.db`, então a demo repete exatamente igual. Para chamar a IA de verdade, copie `.env.example` para `.env` e preencha ao menos uma chave.

O ZIP mensal vem do [portal de dados abertos da Imprensa Nacional](https://www.in.gov.br/acesso-a-informacao/dados-abertos/base-de-dados) (Seção 1, ano e mês) e fica em `data/raw/dou/`, fora do Git. O coletor não acessa o site do DOU, porque o `robots.txt` de www.in.gov.br proíbe robôs.
