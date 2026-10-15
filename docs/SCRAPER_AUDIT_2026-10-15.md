# PNGworkforce scraper audit — 15 October 2026

The daily scrape is operating again and the main job database is useful, but a successful GitHub Actions run does not establish that every extracted field is correct or every description is complete. The September billing interruption is confirmed. Important extraction and archiving defects should be addressed before another large classification run.

Follow-up: the [detailed gap estimate](SEPTEMBER_2026_GAP_ESTIMATE.md) puts additional lost adverts at **about 75, with a 40–90 sensitivity range**. The [improvement and source preservation plan](SCRAPER_IMPROVEMENT_PLAN.md) retains the existing dataset and previous analysis while prioritizing archiving, targeted repairs and evidence-based backfills. The known defects do not establish that prior analytical conclusions are invalid.

This audit examined repository commit `08612e154f5e977f7341d7ab11c6702052cb126c`, the database produced at `2026-10-15T02:36:40` UTC, all 351 recorded workflow runs, today's detailed execution log, all 3,707 stored records, eight selected live job pages, and both live listing sources. Only documentation and audit evidence were added. Production code, workflow configuration, scraped data and analysis files were unchanged. No production scrape, classification or analysis run was started, and no paid LLM requests were made.

Machine-readable evidence is in [audits/2026-10-15](audits/2026-10-15/): [workflow history](audits/2026-10-15/github-runs.json), [latest run](audits/2026-10-15/latest-run.json), [data quality](audits/2026-10-15/data-quality.json), and [live comparisons](audits/2026-10-15/live-checks.json).

## 1. Operational history and the September interruption

There are 351 recorded runs: 331 successes and 20 failures. Of these, 349 were scheduled daily runs and two were manual runs. The failures comprise one initial manual run on 31 October 2025 and the 19 scheduled runs from 1–19 September 2026. Every scheduled run outside that September interval succeeded in the returned history. There is one scheduled run per day from 1 November 2025 through 15 October 2026.

| Period | Evidence and outcome |
|---|---|
| 31 August 2026 | Last successful run before the interruption; database commit `4eb95fe`. |
| 1–19 September 2026 inclusive | Nineteen scheduled runs failed before any scraper steps ran. |
| 20 September 2026 | First successful scrape after the interruption; database commit `48d7691`. |
| 20 September–15 October 2026 inclusive | Twenty-six consecutive successful scheduled runs. |
| 15 October 2026 | Scraper step ran from 02:25:00 to 02:36:40 UTC; artifact upload and result push also succeeded. |

GitHub's annotation on both the [1 September run](https://github.com/juddormsby/png-job-scrape/actions/runs/33483131653) and the [19 September run](https://github.com/juddormsby/png-job-scrape/actions/runs/35428803916) states: “The job was not started because your account is locked due to a billing issue.” This confirms the reported payment problem; it was not a Python extraction failure. The job records have no executed steps and no assigned runner.

The database has no new `first_seen` dates during 1–19 September. It records 139 jobs first observed on 20 September, after scraping resumed. That is recovery of adverts still discoverable at resumption, not proof that all adverts from the interruption were recovered. An advert posted and removed entirely during the gap may be absent permanently. Daily availability and disappearance dates across the interruption are unknown, not zero. `first_seen` is the first successful observation, not necessarily the publication date.

For analysis, retain this interval as an explicit observation gap. Do not interpret the September decline in observations as a decline in vacancy demand, or the 20 September catch-up as one day's new demand. There are also 175 records whose last successful observation remains 31 August; their actual disappearance dates cannot be inferred from this gap.

## 2. What today's successful run actually did

The [15 October execution](https://github.com/juddormsby/png-job-scrape/actions/runs/38670839013) provides stronger evidence than the green workflow status alone:

| Quantity | Interpretation |
|---|---|
| 206 homepage URLs across 21 AJAX pages | Homepage pagination reached its final partial page. |
| 150 latest-page URLs | The second source was also retrieved. |
| 215 detail requests, 206 distinct job IDs | Nine jobs were requested twice through different URL slugs. |
| 14 reported new jobs | The database actually gained 13 distinct IDs: 3,694 to 3,707. One new ID was counted twice. |
| 199 reported updates | Request-level counter; it is not a count of distinct jobs with changed content. |
| Two previously failed jobs recovered | These were successfully retried during this run. |
| No current detail-fetch failures found in the log | All 215 requests produced records; this does not independently validate their contents. |
| 48 remaining failures | Historical backlog; all 48 saved errors are 404s. This is not 48 failures on 15 October. |

The duplicate requests arise because discovery deduplicates on URL, while the final database deduplicates on numeric job ID. For example, `/jobs/view/it-support-specialist-/28896` and `/jobs/view/it-support-specialist/28896` are treated as different discoveries. The database itself has 3,707 unique IDs; this particular defect inflates request counters and wastes requests rather than creating duplicate IDs in `all_jobs.json`.

The failed-job backlog is retained across runs. Jobs that disappear from the listings are not automatically retried every day merely because they remain in that backlog. Most old 404s should be distinguished from current extraction or network failures.

## 3. Live HTML checks

Eight pages were deliberately selected to cover different employers, a short advert, two long adverts and known edge cases. All eight returned HTTP 200. The raw HTML was inspected directly, alongside re-extraction using the current parser without invoking its download/save pipeline. This is a targeted diagnostic sample, not a random estimate of accuracy across the whole database.

For all eight, employer, listed region, industry and posting date agreed between the saved record and the inspected page. The independent structured-title and salary checks revealed errors that repeating the same parser alone would not detect.

| Live advert | Description characters: saved / page container | Finding |
|---|---:|---|
| [28898 — Project Officer - X2](https://www.pngworkforce.com/jobs/view/project-officer-x2/28898) | 4,593 / 4,593 | Text matches. Saved title loses the `X2` suffix. Saved salary is `2`, not evidence of pay. |
| [28855 — HVAC-R SERVICE SUPERVISOR](https://www.pngworkforce.com/jobs/view/hvac-r-service-supervisor/28855) | 10,000 / 12,137 | Exact first 10,000 characters only. Even after removing application forms, the advert body has 11,157 characters. |
| [28825 — Education Program Manager](https://www.pngworkforce.com/jobs/view/education-program-manager/28825) | 725 / 725 | Onsite text matches. The page explicitly lists PGK120,000.00, but saved salary is a comma. Most role detail may require following its external application link. |
| [28836 — Operator - Power Station Control Room](https://www.pngworkforce.com/jobs/view/operator-power-station-control-room/28836) | 3,915 / 3,915 | Text matches. Saved title is only `Operator`. |
| [28860 — Engineer, Structural](https://www.pngworkforce.com/jobs/view/engineer-structural/28860) | 5,449 / 5,449 | Text matches. The site's broad region tags differ in purpose from the specific Lihir worksite and roster discussed in the advert. |
| [28889 — Laboratory Technician](https://www.pngworkforce.com/jobs/view/laboratory-technician/28889) | 5,499 / 5,499 | Text matches, but 976 characters are application/share interface text. |
| [28773 — Nurse Specialist Supervisor](https://www.pngworkforce.com/jobs/view/nurse-specialist-supervisor-banz-jiwaka-province/28773) | 10,000 / 12,875 | Exact first 10,000 characters only. Body without application forms is 11,870 characters. |
| [28824 — Translator](https://www.pngworkforce.com/jobs/view/translator/28824) | 4,732 / 4,732 | Text matches. Structured job type is `Fixed Term Contract`; the saved field reduces it to `Contract`. |

Thus six sampled descriptions match the full text extracted from the page's description container; two are truncated. Matching the container does not mean that the text is clean job content: this container also includes application and sharing interfaces.

The short Education Program Manager advert is genuinely short on PNGworkforce. It links to BambooHR. A direct HTTP check of that external URL returned a JavaScript application shell, so this audit did not recover or validate its full external job description. The current scraper does not follow that link. Its complete capture of the onsite teaser should not be confused with complete capture of the employer's full specification.

During the later listing check, the homepage contained 211 distinct IDs across 22 pages, and the latest page contained 150 IDs; their union was 212. Independent enumeration of the HTML links agreed with the parser's homepage count and latest-page ID set. Six current IDs were not yet in the 02:36 database: `28899`, `28900`, `28902`, `28903`, `28904`, `28905`. One old ID, `28312`, had returned to the live listings while its saved `last_seen` remained 31 August. Direct checks of `28312` and `28905` showed live pages dated 15 October.

These listings were fetched after the scheduled scrape and changed during the audit. Publication dates are not precise insertion timestamps. Consequently this is a watch list for the next run, not proof that all seven were missed by the morning scraper. The audit did not update the production database with them.

## 4. Whole-database quality checks

The database contains 3,707 records with unique job IDs. All records have nonempty titles, descriptions, employer names, industries, publication dates and observation timestamps. Location is nonempty in 3,706. Presence alone is not a correctness test.

| Check | Result | Implication |
|---|---:|---|
| Description length exactly 10,000 | 72 records (1.94%); two observed today | Strong truncation candidates; both sampled live cases are confirmed truncated. |
| Description contains sharing-form phrase | 3,638 records (98.14%) | Site interface text is included in most stored descriptions. |
| Salary equals a single comma | 3,526 records (95.12%) | Salary must not be used analytically in its current form. Other values also require validation. |
| Median stored description length | 3,674 characters | Most adverts have substantial text, but length includes interface material. |
| Legacy publication dates outside DD/MM/YYYY format | 150 records | JSON mixes formats. CSV generation normalizes dates separately; normalize and retain raw dates explicitly in a repair. |
| Individual archived HTML files present | 189, versus 3,707 database records | Most referenced HTML files are not available in a fresh repository checkout. |
| Individual archived job JSON files present | 189 | The consolidated JSON is substantially more complete than the individual-file collection. |

An additional comparison of the 189 available archived pages found 47 titles that were exactly the structured title cut at its first ` - `. This extends the evidence for the title defect beyond the two selected live examples. Another 18 title differences involved other differences, including whitespace; they should not all be classified as title truncation without further review.

There are 169 groups of exactly matching stored descriptions involving 433 records with different IDs. Some are genuine source duplicates or reposts, such as the two current Boiler Operator adverts. These should be flagged for analysis, not automatically deleted or treated as one vacancy: identical adverts can represent reposting, multiple positions, or separate recruitment rounds.

Phone/address completeness also overstates usefulness when an employer supplies placeholders such as `--` or `..`. Preserve raw values and add validation flags rather than assuming every nonempty field is informative.

## 5. Confirmed code defects and operational weaknesses

### Fix before the next classification refresh

1. **Title truncation.** In [`code/scraper.py`, lines 564–578](../code/scraper.py#L564), splitting the document title at the first ` - ` removes legitimate role text and vacancy-count suffixes. Prefer `[itemprop="title"]` or the actual advert heading. The current fallback expects an `h1`, although most sampled pages use an `h3` with the structured title span.
2. **Description truncation and interface pollution.** Lines 786–797 impose a silent 10,000-character limit and retain `.apply-forms` descendants. Store the complete source body, create a separate cleaned text field, and record lengths and extraction version. Keep application targets as separate metadata before removing interface elements. A simple character cap should not determine what evidence reaches the classifier.
3. **Salary extraction.** Lines 807–816 scan the whole page, and the fallback regular expression accepts a comma or any number without a salary label, currency or pay period. It also misses structured values beginning with `PGK`. Use `[itemprop="baseSalary"]` and `[itemprop="salaryCurrency"]` first; require evidence for textual fallbacks and use null when unknown. The Education Program Manager example demonstrates an actual missed advertised salary.
4. **Durable source retention.** The workflow commits only the three consolidated outputs. Individual HTML and job JSON are uploaded as artifacts with 30-day retention. HTML saved in the repository stops at 189 files. A checkout therefore cannot reliably follow most `html_file_rel` references. Preserve source snapshots in durable storage or a deliberate archive policy before artifacts expire. The saved HTML is a BeautifulSoup serialization, not the original response bytes; linked documents and images are not downloaded.

### Make run status and counters trustworthy

5. **Deduplicate by job ID before requesting details.** Preserve URL aliases and a canonical URL, but use numeric ID as the discovery identity. Today's 215 requests for 206 IDs and 14 reported versus 13 actual new IDs are direct evidence.
6. **A green run can hide missing work.** A failed AJAX page ends pagination; zero total discoveries prints a warning, saves a diagnostic page and returns normally. Individual fetch failures are collected rather than causing failure. The workflow has no minimum discovery count, required-field validation, truncation checks or dataset freshness gate. Add explicit partial/failure states and sensible thresholds with historical comparisons.
7. **Push errors are masked.** In [`.github/workflows/scrape.yml`, line 54](../.github/workflows/scrape.yml#L54), `git push || echo "No changes to commit"` exits successfully after a rejected or failed push. This can label an unpublished scrape successful. Today's push did succeed; this is a future failure mode. The preceding `git add ... || true` similarly masks staging errors. Handle an actual no-change result separately and let unexpected publishing errors fail.
8. **Separate today's failures from the backlog.** Report unique discovered/attempted/succeeded/failed IDs for this run, plus separately tracked unresolved historic failures. `retry_count` is also reused for aggregate retries and individual failure-attempt counts, so later failures can reset the aggregate. These should be different variables. Most existing 404s are not retried unless the job is discovered again.
9. **Add an outage record outside the scraper's successful-run output.** A billing lock prevents the script from running at all, so it cannot log its own missing observations. Track expected versus actual run dates and latest successful publication, and enable notifications for failures and stale output. Do not infer completeness from a recently updated file alone.

### Other verified or directly reproducible weaknesses

10. **Fresh-database startup fails.** With no existing `all_jobs.json`, `load_existing_summary()` returns null, but lines 1126–1127 call `.get()` on it outside the existence guard. A mocked, offline invocation reproduced `AttributeError: 'NoneType' object has no attribute 'get'` before any network call. The existing database avoids this path today.
11. **HTTP 200 is not sufficient page validation.** The code does not require job-page selectors or a useful description before counting a result as successful. An offline synthetic 200 error page still yielded an ID and a `Job not found` title; `scrape_job_detail` has no corresponding semantic rejection gate. No such stored record was established in the live sample, so this is a confirmed validation weakness, not a claim of measured soft-error contamination.
12. **Cached files prevent refresh.** `is_job_already_scraped` checks for an HTML file, readable JSON and a non-generic title, then skips the page without comparing current content. It does not actually require a description despite the comment. In Actions, most new individual files are absent from each clean checkout, so most current jobs are downloaded again; a local run with a fuller archive could instead retain old descriptions or dates indefinitely. Make refresh policy explicit, with source hashes or conditional retrieval where appropriate.
13. **Individual-file observation dates differ from the consolidated history.** Each detail JSON is written with `first_seen = now` before the consolidation merge restores historical `first_seen`. Thus re-downloaded individual JSON artifacts can have misleading first-observation dates even though the consolidated JSON preserves them. Update tracking consistently before saving either representation.
14. **Configuration is disconnected.** `code/config.yaml` is not loaded by the scraper. Its `github_actions.enabled: false` and `commit_changes: false` do not control the active workflow. Treat it as stale documentation or wire it into one explicit configuration mechanism.
15. **Routine maintenance.** The latest log warns that older action versions target deprecated Node.js 20, with GitHub forcing them onto Node.js 24. They succeeded today. Update supported action versions in a separate maintenance change; this warning did not cause the September interruption.

All five Python source files parsed successfully with Python's AST parser. There are no syntax errors in those files. That check does not establish runtime correctness or extraction accuracy. The two offline reproductions above did not write scraper outputs or contact the website.

## 6. Suitability for later LLM classification

The classifier includes the stored description verbatim in its prompt, alongside title, employer, employer website, location and the site's informal industry label. It does not retrieve HTML or follow employer/application URLs. Therefore it inherits the scraper's missing title suffixes, 10,000-character cuts, interface noise and short onsite teasers. Most records contain enough job text to be useful, but “full descriptions captured” is currently too strong a claim.

The industry's informal tag and the employer profile are useful context but can describe a recruitment agency rather than the eventual employing organization. Preserve agency and client-employer evidence separately when identifiable. Similarly, a multi-region search tag is not automatically the role's actual worksite. These distinctions matter for industry classification and geographical analysis.

The saved final classification run has 503 records and is from December 2025; this audit did not refresh it. Before another run:

- Repair and backfill the input fields first. Historical repairs need provenance; a current version of an advert is not necessarily identical to its original version.
- Track input content hash, extraction version, model, prompt version, classification time and success/error status. The current resume logic skips any saved job ID, including an error result, and will also skip an old classification after its input has changed.
- Add classifier-specific `openai` and `pydantic` dependencies to a suitable environment definition; they are absent from the scraper's `requirements.txt`.
- Review the configured 500 concurrent workers and add bounded retry/backoff and more frequent checkpointing. This audit made no API calls and did not measure rate limits. Currently results are saved after a batch completes, so interruption can lose that batch's completed work.
- Align input/output naming deliberately: the scripts default to unsuffixed `LLM_processed_jobs.json/.csv`, whereas Stata reads saved run `LLM_processed_jobs6.csv`.
- Align the schema with persisted output: `classification_summary` is requested from the model but omitted from the saved result. This is a small efficiency/consistency issue, not a reason to change prior analytical conclusions.

These are preparation and reproducibility issues; this audit does not assess the substantive accuracy of the old ISIC/ISCO classifications or rerun the survey comparison.

## 7. Additional fields worth capturing

Prioritize evidence already in the source page, with raw values and separate normalized fields:

| Field | Source and purpose |
|---|---|
| Complete structured title and vacancy-count hint | Structured title span; retain explicit counts such as `X2` and distinguish adverts from positions. |
| `description_text_full`, `description_text_clean`, source HTML/hash, lengths | Preserve all role evidence and make truncation/cleanup measurable. Retain structured paragraphs/lists or their HTML as well. |
| Salary raw value, numeric range, currency and pay period | Existing structured salary/currency plus carefully validated body text. Do not invent a pay period if none is given. |
| Raw employment type | Existing `jobtype` field, then a separate normalized category. Preserve distinctions such as fixed-term versus permanent. |
| Closing date raw/ISO and extraction evidence | Often in the advert body, including the sampled Education Program Manager deadline. Useful for active-advert analysis. |
| Application URL and external requisition ID | Actual external Apply target, not just the employer homepage. Enables a separately scoped external-description retrieval step. |
| Attachment and image URLs, content type and extraction status | Flag adverts whose substantive specification is in a PDF or image. No embedded description images were found in the eight-page sample; this is a coverage safeguard. |
| Listed region/country and specific worksite/roster separately | Country is already structured; worksite, FIFO/roster and remote/onsite detail may occur in the body. Keep explicit values separate from inferred values. |
| Agency, advertised employer and client employer | Avoid treating a recruiting intermediary as the economic activity of every advertised role. |
| Run ID, expected/actual observation dates, HTTP status, validation status, content hash and change history | Distinguish a successful response, a usable advert, an unchanged advert, a disappearance and an observation gap. |

Education, required experience, skills, certifications, contract duration and eligibility restrictions are useful later classification/extraction outputs. Their evidence should remain tied to the preserved advert text; avoid making the raw scraper depend on an LLM for basic collection.

## 8. Recommended sequence

1. Keep the September gap documented and incorporate it into any time-series interpretation.
2. In a separate implementation change, fix structured titles, salary, full clean descriptions, ID-based discovery and page validation. Add focused fixtures for these demonstrated failures and for fresh-database startup.
3. Make source retention durable and reporting honest: current versus historic failures, distinct-ID counts, explicit partial scrapes and publishing errors. Add workflow freshness checks and failure notifications.
4. Re-extract current/live records and any available historical HTML, retaining old values and repair provenance. Many older source pages are not present locally and artifacts expire; expired adverts with truncated stored text may not be fully recoverable.
5. Verify the six newly listed IDs and returned ID `28312` on a subsequent scheduled run before diagnosing a persistent coverage issue.
6. Refresh classification only after the input repair and versioning policy are agreed; keep resulting classification and analysis updates in separate commits.

Limits: only eight existing records received detailed live-page validation, two additional listing discrepancies received a detail-page check, and one external ATS link was checked without obtaining its JavaScript-rendered specification. The historical billing gap has no scrape snapshots for the missing days. This audit did not download old artifact archives, test paid classification calls, change the scrape schedule, or establish completeness against every job ever published on PNGworkforce.
