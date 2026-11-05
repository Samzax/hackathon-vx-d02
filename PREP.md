# Hackathon VX, Desafio 02: prep notes

Checked on 2026-11-02. Scope: dam compliance for Brazilian mining companies.

## The demo case (verified in the official text)

| | |
|---|---|
| Act | Resolução ANM nº 245, de 31 de julho de 2026 |
| Published | DOU 04/08/2026, Edição 145, Seção 1, página 66 |
| Change | Art. 87 of Res. ANM 220/2025 gains item III: art. 7 §1 takes effect on **26 Dec 2029** |
| Before | 2 Aug 2027, with the rest of Res. 220 |
| Unchanged | Arts. 76 and 77 on 22 Apr 2027; everything else on 2 Aug 2027 |

Links:
- [Act in the DOU](https://www.in.gov.br/web/dou/-/resolucao-anm-n-245-de-31-de-julho-de-2026-723029571)
- [Res. 220 with amendments, ANMlegis](https://anmlegis.datalegis.net/action/ActionDatalegis.php?acao=abrirTextoAto&link=S&tipo=RES&numeroAto=00000220&seqAto=000&valorAno=2025&orgao=ANM%2FMME&cod_modulo=566&cod_menu=8303)

Use these two details in the pitch:
- **The press got the date wrong.** [ANM's own news post](https://www.gov.br/anm/pt-br/assuntos/noticias/novas-regras-para-zonas-de-autossalvamento-de-barragens-de-mineracao-devem-ser-implementadas-ate-2029) says 31 Dec 2029; the act says 26 Dec 2029. The product quotes the act, not the news.
- **Only art. 7 §1 moved.** Art. 7 caput still takes effect on 2 Aug 2027. A correct system changes one obligation and leaves the others alone.

Art. 86 revokes Res. 95/2022, 130/2023 and 175/2024 from 2 Aug 2027. Until then Res. 95/2022 still applies, so `seed_obligations.csv` is the register from that date. It is not today's calendar. Today's calendar needs rows from Res. 95/2022, which have not been checked.

## One real day, as a funnel

DOU Seção 1 regular edition, 4 Aug 2026: **339 acts → 23 from ANM → 1 that changes an obligation.**

This is one day, and the last step is the known answer, not a measured result. Re-run it over the full backtest window before quoting a general number.

Other days: 17 Oct 2025 had 295 acts (9 ANM), 24 Apr 2026 had 338 acts (13 ANM).

## Data access

> **5 Nov: `https://www.in.gov.br/robots.txt` is `User-agent: * / Disallow: /`.** Do not run an automated collector against the DOU listing or act pages. A `requests` call was also dropped by the server on 5 Nov while `curl` still answered, which looks like bot filtering. Use the official channels for machine access: INLABS (still in maintenance on 5 Nov) or the monthly open-data XML, downloaded by hand. Also confirmed on 5 Nov: the 4 Aug 2026 listing has 339 acts in `do1`, 23 from ANM, and 9 more in the extra edition `do1e`.

| Source | Status on 2026-11-02 |
|---|---|
| DOU daily listing | **Works without login.** Tested back to Oct 2025 |
| DOU act page | **Works without login** |
| ANMlegis | **Works.** Includes amended text and notes. Pages are cp1252, not UTF-8 |
| INLABS | **Down for scheduled maintenance.** Do not depend on it |
| DOU open data (monthly XML ZIPs) | Page loads and points to this as the INLABS alternative. Links are behind year and month selectors, so no file has been downloaded yet |

Listing: `https://www.in.gov.br/leiturajornal?secao=do1&data=DD-MM-YYYY`
- Acts are JSON inside `<script id="params">`, in `jsonArray`.
- Useful fields: `urlTitle`, `title`, `artType`, `hierarchyStr`, `numberPage`, `pubDate`, `content`, `editionNumber`.
- ANM filter: `hierarchyStr` contains `Agência Nacional de Mineração`.

Full text: `https://www.in.gov.br/web/dou/-/<urlTitle>`

Watch out for:
- `content` looks like an excerpt, so fetch the act page for the full text.
- Extra editions use other section codes (`do1a`, `do1e`, `do1esp`). Skipping them can miss an act.
- Listing completeness looks right (act pages run from 1 to the last page) but has not been checked against the official XML.
- Robots rules forbid crawling (see the note at the top of this section). Terms of use still not read.

## Seed obligations

`seed_obligations.csv` has 15 obligations. Article, deadline and scope were read from the ANMlegis text. Owners are fictional roles. OB-01 is the golden test: after processing Res. 245/2026, only that row should change.

## Organizer meeting (Meet, 5 Nov)

- **Pre-building is allowed and encouraged.** We can create the GitHub repo and put everything in it now.
- **The organizers will provide AWS integration.**
- They stressed the **pitch** and **technical viability**.

- **Judging is by criteria, not by challenge.** No challenge scores higher for being chosen. Weights remembered from the call, to confirm in the recording:

  | Criterion | Weight |
  |---|---|
  | Technical | 30% |
  | Pitch | 15% |
  | Market size and analysis | ? |
  | Others | ? |

  Market size counts, so the pitch needs a number: how many dams and companies the product serves (see the SIGBM task below).
- **AWS is optional.** Port to it only if we want or need to. The outbound-requests question matters less: the collector can run on our machines.

Still open, until the recording is released:
1. The full list of criteria and weights.
2. Which AWS services and limits we get.

## Before Saturday

- [ ] Create the GitHub repo and push the prep material
- [ ] Build the collector and the golden test (OB-01) before Saturday
- [ ] Draft the 5-minute pitch around the Res. 245 case
- [ ] Name one owner for data ingestion
- [ ] Talk to someone who works in mining compliance; ask the organizers for an intro
- [ ] Check with them that the seed list and the owner roles look realistic
- [ ] Refresh the dam count from SIGBM (the only figure found is 907, from March 2022)
- [ ] Send the organizers your challenge by Nov 6
- [ ] Re-check INLABS on Friday
