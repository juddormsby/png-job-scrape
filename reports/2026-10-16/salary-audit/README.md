# Salary disclosure and recoverability audit — 16 October 2026

The saved descriptions contain **58 confirmed adverts with an explicit monetary salary/wage amount or range: 1.56% of 3,712 advert IDs**. Preserved HTML adds **30** further adverts, making **88 known cases, or 2.37% of the full database**, recoverable from sources already held. This is observed source coverage, not an LLM accuracy estimate.

## Definition and denominator

“Salary available” means an explicit monetary amount or range offered for the advertised role, including hourly wages, monthly pay, fortnightly pay and expatriate packages. A currency or pay period may still need clarification; this is not a count of fully normalized annual salaries. Salary grades such as NC12 or N14, “competitive”, “negotiable”, unspecified commissions and benefits alone do not count. Neither do employer revenue, project budgets, assets, procurement prices, tax rates, leave days or superannuation percentages.

The unit is a distinct advert ID. Reposts remain separate, and one advert may cover several positions, levels or salary bands. Results therefore describe adverts, rather than independently verified individual vacancies.

Database snapshot: `json_output/all_jobs.json`, updated 15 October 2026, SHA-256 `7b0b330f6d999c29de5ddf3d6ce57e46e138944b5c871bb9d2f5c4f6314d5285`. The 48 entries in the separate failed-jobs list are excluded.

## Measured results

| Evidence available | Numeric pay found | Denominator | Percent |
|---|---:|---:|---:|
| Saved description, full database | 58 | 3,712 | 1.56% |
| Description or currently preserved HTML, full database | 88 | 3,712 | 2.37% |
| Saved description, only the HTML-available subset | 14 | 684 | 2.05% |
| Description or HTML, same HTML-available subset | 44 | 684 | 6.43% |
| Saved description, first seen Sep–Oct 2026 | 7 | 423 | 1.65% |
| Description or HTML, first seen Sep–Oct 2026 | 11 | 423 | 2.60% |

All 423 adverts first seen in September–October have preserved HTML. In this recent cohort, including the full page increases the count from 7 to 11: **4 additional adverts, a 0.95 percentage-point gain**. Descriptions alone contain 7/11 (63.6%) of the numeric-pay disclosures found in that cohort's available page text; this is a small denominator and not a general extraction recall estimate.

Within the same 684-advert HTML subset, the existing `salary` field provides **0 confirmed usable monetary salaries (0%)**. All 684 fields are nonempty, but 652 contain only a comma and the remaining 32 contain incidental numbers. In particular, **all 44 confirmed salary-disclosing adverts have a comma in the existing salary field**. Thus the matched comparison is 0/684 in the existing salary field, 14/684 (2.05%) recoverable from descriptions, and 44/684 (6.43%) recoverable using full-page evidence. Field presence is not salary availability.

Across all 684 paired cases, HTML adds 30 adverts, a 4.39 percentage-point gain, and descriptions contain 14/44 (31.8%) of disclosures found in the paired evidence. This larger gap is strongly affected by the archive's employer and time composition.

## Why 6.43% cannot simply be extrapolated

The 684 preserved adverts are not a random sample. They include all 150 initial-stock adverts first captured in October 2025, all 423 first captured in September–October 2026, and only 111 from other first-seen months. Among the 30 extra HTML-only disclosures:

- 26 are Glory Estate Limited adverts from the initial stock;
- 3 are ChildFund PNG adverts;
- 1 is a Media Metro advert.

The initial stock contains 33 salary-disclosing adverts out of 150 (22.0%), versus 11/423 (2.6%) in the recent cohort. Almost all of the difference is concentrated in a particular employer's older listings. Of Glory Estate's 176 records, only 56 have HTML, leaving 120 without it. The available 26 older Glory Estate pages disclose salary, while the other 30 available Glory Estate pages do not. We cannot tell whether the 120 missing pages followed the older or newer practice.

## Practical estimates

- **Careful description extraction:** plan around **1.5–2% coverage**. The measured figure is 1.56%; a better model cannot recover amounts absent from the input. The 2% endpoint is a planning judgement, not a statistical upper confidence limit.
- **Descriptions plus currently held HTML:** **2.37% is already evidenced**, before any external retrieval or model run.
- **Hypothetically having HTML for every advert:** use **roughly 3–6% as a provisional planning range**, with about 4% as a working assumption if a single figure is required. This is a sensitivity scenario, not a representative estimate or confidence interval.

For transparency, one simple scenario applies the recent cohort's additional HTML-only rate (4/423) to the 2,908 non-Glory adverts missing HTML, and varies additional salary availability among the 120 missing Glory Estate adverts. Including the 88 already known cases gives:

| Assumed additional salary availability in 120 missing Glory Estate pages | Projected total salary adverts | Percent of full database |
|---|---:|---:|
| 0% | about 115 | 3.11% |
| 25% | about 145 | 3.92% |
| 50% | about 175 | 4.73% |
| 100% | about 235 | 6.34% |

This scenario assumes similar hidden-header disclosure for other missing pages and cannot account for unknown employer/time differences. The endpoints are not hard bounds. It illustrates why current evidence supports “a few percent” while not determining a precise historical population rate.

## Method and manual review

1. Screened all 3,712 descriptions using inclusive currency, numeric pay-period, and pay-keyword/nearby-number patterns. This produced 521 currency/period candidates and 385 additional broad candidates, or 906 flagged descriptions.
2. Manually inspected currency/period evidence and numerical pay-related passages. Repeated match profiles and employer boilerplate were grouped for review. K92 Mining, K9 dogs, K1 school grades, Kina Haus addresses, AUD80 million project budgets and procurement amounts were explicitly rejected. All 385 additional broad-candidate records' relevant passages were inspected; none added a numeric salary beyond the 58 currency/period positives.
3. Selected 150 descriptions at random, without replacement, from the 2,806 screen-negative descriptions using seed 20261016. Inspected numeric and compensation-relevant excerpts for unusual formats and missed disclosures. Found no additional monetary salary. This was a focused passage review, not a blinded full-text gold-standard annotation; it does not establish perfect recall or justify a narrow confidence interval.
4. Ran a second independent screen for unprefixed decimal/thousands amounts and alternative pay vocabulary, reviewing its additional passages; no further numeric salary was identified.
5. Parsed one selected available HTML source for each of 684 database IDs, preferring the database's explicit source reference, then a successful `job_html` index, then legacy HTML. Inspected every nonempty structured base-salary value, full-page currency/period evidence, and pay/number passages beyond the description cap. Only 32 of 96 nonempty structured base-salary fields give monetary pay: 2 repeat description pay and 30 add pay absent from the description. Salary grades and “Negotiable (PGK)” were excluded. Another 12 paired adverts disclose pay in the body without a numeric structured base-salary field, giving 44 in total.
6. Confirmed that archived description text agrees with the saved description, allowing whitespace normalization and the 10,000-character cap, for all 14 description-positive paired cases. No additional numerical pay was found beyond the cap in available full descriptions.

The original broad scan deliberately generated false positives. The 58/88 counts are reviewed evidence counts, not raw regex-hit counts. The manual review used evidence passages and template groups rather than reading all 3,712 complete adverts. Some salary formats could still have been missed. No paid model APIs, live source fetches, OCR, linked PDFs, external application sites or pay-scale lookups were used.

The description field separately flags 102 adverts mentioning a salary grade/level (2.75%). That is potentially useful supplementary data, but it should not be silently converted into a monetary salary without the relevant dated pay scale.

## Examples

| Advert | Evidence | Description alone? |
|---|---|---|
| 28517, Senior Lecturer | PGK53,663–65,586 per annum base salary; market allowance separately stated | Yes |
| 27502, TB Nursing Officer | K49,920–60,736 per annum, pro rata | Yes |
| 25090, All Rounder Mechanic | K14 per hour starting rate | Yes |
| 28825, Education Program Manager | PGK120,000 in page salary header | No |
| 24979, Senior Mechanic | K7,500–12,000 gross monthly in page salary header | No |

For a future extraction run, use deterministic HTML selectors to recover structured pay where available, then an LLM to interpret body text and distinguish base salary, allowances, currency, period and multiple levels. Require a source quote. Use “not stated in available text” separately from “source incomplete.”

## Files and reproduction

- [summary.json](summary.json): counts and limitations.
- [confirmed_salary_evidence.json](confirmed_salary_evidence.json): all 88 confirmed adverts, source references and supporting passages.
- [reviewed_description_candidates.json](reviewed_description_candidates.json): 906 flagged descriptions' evidence passages and review labels.
- [manual_review.json](manual_review.json): saved positive IDs and decision rules.
- [negative_review_sample.json](negative_review_sample.json): reproducible random check IDs.

From the repository root, run `venv/bin/python code/audit_salary_coverage.py --finalize`. Full-text working files are written to `/private/tmp/pngworkforce-salary-audit-20261016`; compact reviewed evidence remains in this report folder. The command reapplies the saved manual decisions to the screened snapshot; a changed dataset requires renewed review. Production job data and classification files are unchanged.
