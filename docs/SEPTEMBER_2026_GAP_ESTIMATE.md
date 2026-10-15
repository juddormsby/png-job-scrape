# September 2026 observation gap: estimated loss of adverts

Prepared 15 October 2026. This is a missing-data estimate, not a reconstruction of adverts that were never observed.

## Working conclusion

Use **approximately 75 additional advert IDs lost because of the interruption**, with **40–90** as a deliberately broad sensitivity range. The range is not a confidence interval or a guaranteed lower/upper bound. It combines publishing rates, ID allocation and historical visibility evidence; these methods share data and are not statistically independent.

About **140 adverts from the bracketing interval were recovered** at or after resumption. The working estimate therefore describes roughly **215 otherwise capturable adverts: 140 recovered and 75 lost**, or approximately **65% recovered and 35% lost**. The 40–90 range implies roughly 22–39% loss within this affected cohort. It does not imply that 19 days' entire output was lost.

Against the full 3,707-record dataset, 75 missing adverts imply around **2.0% missing from an adjusted total of 3,782**. The 40–90 sensitivity range corresponds to approximately 1.1–2.4% of that adjusted full total. This is an aggregate estimate; missing short-lived adverts may differ systematically from retained adverts.

This estimates the **additional loss from the interruption relative to ordinary daily collection**. It does not establish 98% coverage of everything ever published on the website; normal collection errors and adverts too brief to be observed by a daily scraper remain separate questions.

The unit is **distinct website advert IDs**, not positions, people recruited, or unique underlying vacancies. An advert can cover several positions, and different IDs can be reposts of similar recruitment.

## 1. Exact interruption and available evidence

Nineteen scheduled runs, 1–19 September inclusive, were blocked by a GitHub billing lock. The [first failure](https://github.com/juddormsby/png-job-scrape/actions/runs/33483131653) and [last failure](https://github.com/juddormsby/png-job-scrape/actions/runs/35428803916) explicitly identify the billing issue. No scraper steps ran on those dates.

| Boundary | Successful database snapshot | Maximum captured ID |
|---|---|---:|
| Last successful scrape | 31 August, 08:44:17 UTC; commit `4eb95fea89d36cf0840bec9dadc8cb31d925c191` | 28332 |
| First successful restart | 20 September, 07:52:18 UTC; commit `48d76911f5e1a4e4d0f265a8060e50a33aeefae0` | 28564 |
| Audit follow-up | 15 October; data commit `6020b3f4e245e8f485f3f9e1b191050a4a1acc28` | 28898 |

The elapsed time between successful observations was **19.964 days**. The models use a 20-day interval: 19 missed runs and observation again on day 20. This also includes part of 31 August and the morning of 20 September, so the modeled cohort is slightly broader than publication dates 1–19 September alone.

The restart added **139 genuinely new IDs**, measured by comparing cumulative ID sets in the two committed snapshots. These adverts had not been measured before the gap but remained discoverable at restart. Of those 139, the historical restart records label 136 as published 1–19 September, two as 31 August and one as 20 September.

Two other IDs in the numeric span were captured later:

- **28486:** first captured 28 September, with a 10 September publication date. This is an additional confirmed recovery from September.
- **28474:** first captured 9 October, with a 9 October publication date. It is a recovered allocation slot, but it is not established as an advert published during the interruption; it might have been a held draft or a later publication.

Accordingly, arrival/visibility models use **140 confirmed bracketing-cohort recoveries**: 139 at restart plus 28486. The ID accounting uses **141 successful IDs** in the numeric span, because both later successes are already accounted for and cannot be counted as wholly unmeasured IDs. There are **137 recovered records with a documented original publication date of 1–19 September**.

Publication dates can change when adverts are edited or re-advertised. Using the latest database's publication dates would yield only 123 in that last category. The original restart snapshot and first-observation dates are therefore essential; current publication dates alone should not be used to reconstruct September's original flow.

## 2. Three estimates

| Method | Main calculation | Estimated lost IDs |
|---|---|---:|
| Nearby publishing/capture rate | Approximately 11 distinct first captures/day × 20 days, minus 140 recoveries | **80** |
| ID gaps calibrated against unaffected periods | 232 slots × 94.45% ordinary capture coverage, minus 141 successful IDs in the span | **78** |
| Advert visibility / simulated outage | Remove the same 19 runs from earlier daily histories; use the loss/recovery ratio, matching restart weekday | **64** |

These point estimates support an order of **70–80 missing adverts**. A rounded working number of 75 is appropriate for planning and sensitivity analysis, rather than a claim that exactly 75 adverts disappeared.

### Method A: nearby publishing rates

Daily counts use **distinct IDs first captured**, not the scraper's inflated request-level `new_jobs_scraped` counter. First captures in unaffected periods proxy the flow ordinarily measurable by the scraper. Zero-arrival days are included, and 20 September's catch-up is excluded from the baseline.

| Unaffected baseline | Captured IDs / days | Daily rate | Expected in 20 days | Less 140 recovered |
|---|---:|---:|---:|---:|
| August | 338 / 31 | 10.90 | 218.1 | 78.1 lost |
| 21 September–14 October | 266 / 24 | 11.08 | 221.7 | 81.7 lost |
| These two nearby periods pooled | 604 / 55 | 10.98 | 219.6 | **79.6 lost** |
| July, as a sensitivity check | 384 / 31 | 12.39 | 247.7 | 107.7 lost |

July's higher rate gives a substantially larger estimate and exceeds the 91 unobserved allocation slots in the principal ID bracket. This shows why a stationary rate from any arbitrary month should not be treated as the answer. Seasonal variation, publication timing, ID gaps and sampling variability matter. The closest pre/post periods agree more closely.

A weekday-stratified resampling check of the wider July/August/post-restart baseline is included in the evidence. It is a descriptive sensitivity exercise, not a formal interval: independently resampling days does not account for serial dependence or seasonality.

### Method B: the ID evidence

The sequence from **28333 through 28564 inclusive contains 232 allocation slots**. Successful records exist for 139 at restart and 141 by the audit. Thus **91 slots remain unobserved**, with no successful body or separate failed-job metadata record for those IDs.

Those 91 are **candidate missing IDs, not 91 confirmed published adverts**. IDs can be allocated to drafts, withdrawn adverts, test/deleted entries or later publications. Ordinary uninterrupted periods also have holes.

The primary calibration uses 37 unaffected 20-day ID windows ending 1 July–6 August. Every window is followed for the same 25 days available after the real restart; none crosses the real billing interruption. Their pooled coverage is **94.45%**, and their median coverage is 94.59%. Applying that ordinary coverage gives:

```text
Expected ordinarily capturable IDs = 232 × 0.9445 ≈ 219
Already successfully recorded in the span = 141
Additional lost because of the interruption ≈ 219 − 141 = 78
```

The control estimates range roughly 72–85, with a middle 80% range of 75–81. These controls overlap heavily and do not provide 37 independent observations or a confidence interval.

Adjacent windows provide additional checks: the 11–31 August ID span has 90.6% eventual coverage, implying 69 lost if transferred to the gap. The 20 September–10 October span has 84.9% coverage, implying 56. Post-restart windows have shorter follow-up and more not-yet-published slots at the audit date, so they are supplementary sensitivities rather than the primary matched-follow-up calibration.

The holes are concentrated toward the beginning of the interval, as expected if early adverts expired before resumption:

| ID allocation band | Successful records by audit | Unobserved slots |
|---|---:|---:|
| 28333–28372 | 5 / 40 | 35 |
| 28373–28412 | 16 / 40 | 24 |
| 28413–28452 | 32 / 40 | 8 |
| 28453–28492 | 25 / 40 | 15 |
| 28493–28532 | 35 / 40 | 5 |
| 28533–28564 | 28 / 32 | 4 |

The 91-slot ceiling is conditional on the ID bracket. It is not an unconditional mathematical bound on all missing published adverts: older IDs can be published late or reissued. In the nearby unaffected baseline, 18 of 988 new captures had IDs at or below the previous day's maximum. This appears uncommon, but it is another reason to report a range and preserve the missing-slot list as candidates rather than known missing jobs.

### Method C: model the jobs that expire before restart

This method directly addresses the survival mechanism. The repository retains daily cumulative JSON versions. For each successful historical date, an ID was counted as observed that day only when its `last_seen` date matched the snapshot date. This avoids assuming that a job was continuously visible between its first and last observations.

Using 149 committed daily snapshots, the analysis constructs **78 hypothetical interruptions** in May–July:

1. Keep a last successful observation on day zero.
2. Pretend the next 19 scheduled runs did not happen.
3. Resume observation on day 20.
4. Identify the adverts actually first captured during that 20-day interval under normal daily scraping.
5. Count how many would still be observed on restart or in the following 25 days, and how many would never enter the dataset under that simulated interruption.

All simulations and follow-up finish before 1 September, so the actual interruption does not contaminate the comparison. The use of 25 days' follow-up matches the real 20 September–15 October observation period.

Across all 78 overlapping windows, **28.4%** of ordinarily capturable arrivals would have been lost. Applying the loss/recovery ratio to 140 observed recoveries gives:

```text
Lost / recovered = 0.2844 / (1 − 0.2844)
Estimated missing = 140 × that ratio ≈ 56
```

For the **11 windows with a Sunday restart**, matching 20 September, loss is 31.3%, giving approximately **64 missing**. Individual windows vary materially. The middle 80% of all-window estimates is about 37–86; the weekday-matched middle 80% is about 44–96. Their overlap means these are descriptive historical ranges, not independent-sample prediction intervals.

Two fixed examples illustrate the mechanism:

| Last scrape / pretend restart | Actually captured arrivals | Eventually recoverable after pretend restart | Lost |
|---|---:|---:|---:|
| 1 June / 21 June | 176 | 134 | 42 |
| 1 July / 21 July | 249 | 190 | 59 |

A simpler first-to-last visibility-span approximation gives about 53 lost. It is secondary because a long span can bridge temporary absences or reposting. The daily-observation experiment is preferable.

## 3. Interpretation and uncertainty

The three main estimates are approximately 80, 78 and 64. They support **75 as a central working estimate**, with **40–90** as a practical sensitivity range. No method sees the missing adverts themselves, so none can identify an exact count.

The principal uncertainties are changing publication rates, differences in advert duration by employer/role, draft and delayed ID allocation, edited publication dates, ordinary scraper misses, and possible changes in site indexing. Historical outage windows overlap. The broad range represents those model choices and observed variation; it is not a 95% confidence interval.

Most importantly, this estimate concerns adverts **never obtaining a record because they appeared and disappeared while collection was interrupted**. Different losses must be kept separate:

- A captured advert's exact daily presence and disappearance time during the gap remain unknown even if its description was later recovered.
- An older captured advert may have been edited during the interruption; that missed historical version is not counted as a wholly missing advert here.
- Reposts and adverts covering several positions make website ID counts different from unique recruitment opportunities or vacancy totals.

Short-lived adverts are more likely to be missing. A blanket weighting factor applied to every industry or occupation is therefore not justified without further evidence. Do not fabricate individual missing records, descriptions or job categories.

## 4. How to use the data

The interruption does **not** make the dataset unusable. There are almost a year's worth of observations and 3,707 distinct advert IDs with substantial stored descriptions. Around 98% are below the known description cap, though that is not proof that every one is complete. The main deduplication by ID already works; nine repeated requests on the audit day did not create duplicate IDs in the consolidated database.

The saved 503-job classification/analysis sample dates from December 2025, **before** the September 2026 interruption. This later gap cannot explain or invalidate those earlier results. Salary is not read as a separate input by the current classifier. The older title and description defects merit targeted sensitivity checks, but the audit establishes no grounds for discarding the previous analysis wholesale.

For future work:

- Retain the actual observed records unchanged as the primary data.
- Annotate 1–19 September as unobserved, and identify the 20 September backlog separately from genuine new daily recruitment.
- Report aggregate counts with a central +75 and +40/+90 sensitivity where that correction is relevant. Clearly distinguish observed from estimated totals.
- Use original captured publication dates, observation dates and snapshot provenance when constructing flows. Do not assign all recovered adverts to 20 September or treat missing scrape days as zero publication.
- Treat activity duration, daily vacancy stocks and fine September timing more cautiously than broad descriptive analyses across the full dataset.

## 5. Reproduction and files

From the repository root:

```bash
python3 -B code/estimate_september_gap.py
```

The script uses only Python's standard library and immutable commits already in local Git. It makes no network requests, changes no production scraper/data, and calls no LLM. It generates:

- [estimates.json](audits/2026-10-15/september-gap/estimates.json): all calculations, window estimates and assumptions.
- [daily-observations.json](audits/2026-10-15/september-gap/daily-observations.json): compact evidence from 149 daily snapshots, with source commits and observed/new ID sets.
- [missing-id-candidates.json](audits/2026-10-15/september-gap/missing-id-candidates.json): the 91 unobserved allocation slots, explicitly not a list of proven missing published jobs.
- [artifact-inspection.json](audits/2026-10-15/september-gap/artifact-inspection.json): retention metadata for the restart and audit-day artifacts; contents have not yet been downloaded or verified.

The separate [improvement and archiving plan](SCRAPER_IMPROVEMENT_PLAN.md) covers preservation, parser repairs and cautious retrospective backfilling. The original [scraper audit](SCRAPER_AUDIT_2026-10-15.md) contains live-page comparisons and code findings.
