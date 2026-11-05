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

Art. 86 revokes Res. 95/2022, 130/2023 and 175/2024 from 2 Aug 2027. Until then Res. 95/2022 still applies, so `seed_obligations.csv` is the register from that date, not today's calendar. Today's calendar comes from `cadastro/res95_2022.csv` (21 obligations, valid until 1 Aug 2027). Both registers quote the paragraph that creates each obligation, and `tests/test_trechos.py` checks every quote against the official text.

## Findings on 5 Nov

- **The full month, measured.** August 2026, DOU Seção 1 open-data XML (`S01082026.zip`, regular and extra editions): **7,884 acts → 825 from ANM → 2 normative** (Res. 245 and Res. 246). The 4 Aug numbers match the site listing exactly: 339 in DO1 plus 9 in DO1E, 23 from ANM.
- **Res. ANM 246/2026 is the second golden case.** It extends ANM procedural deadlines, but §1 excludes obligations whose breach risks life or the environment, and §2 II excludes SIGBM deadlines. Correct answer for dam obligations: **no change**. A naive system would flag it.
- **"DPA2" is real.** It is the loss-of-life sub-score of DPA in Res. 220. The text writes the threshold as an underlined ">", which means **≥ 4**. The seed had "> 4", which left DPA2 = 4 dams in neither art. 39 I nor II. Fixed.
- **Market, with a source** (SIGBM public export, 5 Nov 2026): **908 mining dams from 235 companies; 461 under the PNSB from 126 companies; 189 PNSB dams in MG from 41 companies.** Details in `data/mercado_sigbm.json`.
- **SIGBM moved** to `sigbm.anm.gov.br` (no robots.txt). The old `app.anm.gov.br` resets the connection. The page has an official "Exportar CSV" button. The raw export stays out of Git because it includes CPFs of individual owners.

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
| DOU open data (monthly XML ZIPs) | **Works (5 Nov).** `S01082026.zip` (August 2026, Seção 1) downloaded by hand and parsed by `collector/xml_dou.py`: 7,884 acts. A small sample of it is in `tests/fixtures/dou/S01_amostra.zip` |

Listing: `https://www.in.gov.br/leiturajornal?secao=do1&data=DD-MM-YYYY`
- Acts are JSON inside `<script id="params">`, in `jsonArray`.
- Useful fields: `urlTitle`, `title`, `artType`, `hierarchyStr`, `numberPage`, `pubDate`, `content`, `editionNumber`.
- ANM filter: `hierarchyStr` contains `Agência Nacional de Mineração`.

Full text: `https://www.in.gov.br/web/dou/-/<urlTitle>`

Watch out for:
- `content` looks like an excerpt, so fetch the act page for the full text.
- Extra editions use other section codes (`do1a`, `do1e`, `do1esp`). Skipping them can miss an act.
- Listing completeness checked against the official XML for 4 Aug 2026 (5 Nov): 339 acts in `do1` plus 9 in `do1e`, 23 from ANM, same as the site listing.
- Robots rules forbid crawling (see the note at the top of this section). Terms of use still not read.

## Seed obligations

`seed_obligations.csv` has 24 obligations from Res. 220/2025 (it started with 15; a check against the official text found 9 missing). Article, deadline and scope were read from the ANMlegis text. Owners are fictional roles. OB-01 is the golden test: after processing Res. 245/2026, only that row should change.

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

- [x] Create the GitHub repo and push the prep material (private repo, `main`)
- [x] Build the collector and the golden test (OB-01) before Saturday (`collector/`, `tests/test_impacto.py`)
- [ ] Draft the 5-minute pitch around the Res. 245 case: first draft in `docs/PITCH.md` (numbers checked by test), still to rehearse and rewrite in the presenter's voice
- [ ] Name one owner for data ingestion
- [ ] Talk to someone who works in mining compliance; ask the organizers for an intro
- [ ] Check with them that the seed list and the owner roles look realistic
- [x] Refresh the dam count from SIGBM (908 dams, 5 Nov 2026)
- [ ] Send the organizers your challenge by Nov 6
- [ ] Re-check INLABS on Friday
