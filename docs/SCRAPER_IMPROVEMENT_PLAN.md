# Scraper improvement and source preservation plan

Prepared 15 October 2026. This is an implementation plan; the changes described below have not been applied to the production scraper, workflow or data.

## Overall assessment

Keep the existing dataset and build on it. Collection has produced 3,707 distinct advert IDs over almost a year, with substantial descriptions and useful employer/location/industry metadata. Deduplication in the final database works by ID. Most descriptions avoid the 10,000-character cap; excessive inclusion of interface text is usually repairable later. A damaged title is often still recoverable from the description or HTML.

The September estimate is [about 75 lost adverts, with a 40–90 sensitivity range](SEPTEMBER_2026_GAP_ESTIMATE.md), around 2% of an adjusted full total. This later gap does not affect the saved December 2025 sample. These findings justify clearer limits and targeted repairs; they do not establish that the earlier classification or survey comparison is invalid.

The priorities are **preserve source evidence now, improve future collection without discarding records, then backfill fields where evidence exists**. Keep raw captures, normalized records and later classifications separate.

## Phase 0 — preserve existing evidence before expiry

**First implementation task: download and preserve the retained successful-run artifacts.** The 20 September restart artifact is still available as of this plan, but its API metadata says it expires **20 October 2026 at 07:52 UTC**. Today's artifact expires 14 November. Raising retention later does not restore an expired object or automatically extend an existing one's expiry.

Preservation procedure:

1. Enumerate available run artifacts; download the ZIPs into a dated local archive outside the ordinary output paths.
2. Record each artifact ID, run ID, source commit, creation/expiry time, compressed size and SHA-256 digest. Verify the downloaded digest where possible.
3. Extract into a staging directory, never over the current data. Build a manifest of HTML files, job IDs, capture versions and hashes. Deduplicate identical payloads while preserving which runs contained them.
4. Retain the consolidated JSON snapshots and original text as well as HTML. A parser error must not destroy the only source used to diagnose it.
5. Mirror the preserved archive to Dropbox and include the archival inventory in Git. Confirm at least a few files can actually be restored and re-parsed.

Daily observation histories suggest that the retained post-restart artifacts may cover **490 distinct recently observed IDs**. Together with the 189 older local HTMLs, the potential union is **678 IDs**. This is an inferred recovery opportunity, not verified archive contents: successful artifact uploads and paths were checked, but the ZIPs have not been downloaded and inventoried. Preserve all available versions rather than just today's live adverts; some roles visible on 20 September have since disappeared.

## Phase 1 — durable HTML capture going forward

### Recommended initial design

**Continue using GitHub Actions for scraping. Store one original HTML version per advert and additional versions when advert evidence changes, as compressed immutable files in the repository.** This is a simple, practical starting point at the measured scale. Keep a local Dropbox copy as an independent recovery location. Review growth and move large archival payloads outside normal Git if necessary.

Use a layout such as:

```text
archive/
  html/2026/10/28836/<raw-sha256>.html.gz
  manifests/2026/10/2026-10-15.jsonl
```

The example partitions by capture month and job ID so a directory does not accumulate thousands of unrelated files. Manifests, rather than a single repeatedly overwritten `job_ID.html`, link each observation to the appropriate immutable source version.

Capture and save the original HTTP response bytes **before extraction**, including pages the parser cannot understand. A parser failure should produce a validation result and preserved source, not loss of the page. Preserve failed HTTP responses separately from the last known valid advert; a later 404 must not overwrite its successful HTML.

Each observation manifest should record:

- Job ID, requested URL, final URL, run ID and capture time in UTC.
- HTTP status, content type, encoding and selected response metadata.
- Raw-body SHA-256, compressed file location/hash and original byte count.
- Broad advert-content fingerprint, parser version/commit, extraction status and any warnings.
- Separate first observation, current observation and publication date fields.

**Do not use the current extracted JSON alone to decide whether HTML changed.** A broken extractor can hide changes in the very field that needs later repair. Compute a separate broad DOM fingerprint covering advert content, title, metadata, application targets and employer information, normalizing only known volatile material such as hidden application tokens. Keep the complete original raw HTML whenever that evidence fingerprint changes.

An exact raw hash proves integrity but can change daily because of tokens or page chrome. It should not force a new archived version of an otherwise unchanged advert. Conversely, retaining a version only on the first discovery would miss real edits, salary changes or renewed closing dates.

Continue retrieving or conditionally checking live adverts under an explicit refresh policy; an existing archive file must not mean “skip this ID forever.” Where raw bytes differ only in excluded volatile content and an older source version is reused, record the observed response hash and archived source hash separately, with an explicit flag that this day's exact bytes were not retained. Do not claim byte-for-byte daily retention under a first/changed-version policy.

If complete raw evidence of **every daily response**, including otherwise irrelevant page changes, is required, add compressed daily bundles outside normal Git. Monthly GitHub Releases containing daily archive assets are an available GitHub-hosted option at this scale; object storage is the longer-term option for large archives or attachments. Keep a manifest in Git and mirror the payloads locally. Release storage is distinct from short-lived Actions artifacts and must be retrieved explicitly; it is not included in a normal clone.

### Measured scale and GitHub constraints

The 189 existing HTML pages average about 24.5 kB raw and 7.7 kB compressed. The eight recent sampled pages average about 27.6 kB raw and 8.7 kB compressed. These are sizing samples, not a measurement of every missing historical HTML file.

| Policy at approximately today's activity | Approximate HTML payload |
|---|---:|
| One version for all 3,707 adverts | 87–98 MiB raw; **27–31 MiB compressed** |
| One version for each additional year's roughly 4,000 new IDs | **29–33 MiB compressed**, before genuine revisions |
| Archive every response for 206 live IDs every day | **0.54–0.61 GiB compressed per year**, before attachments and manifests |

The existing Git object storage is about 54 MiB as inspected locally. Adding immutable first/changed HTML versions is therefore feasible without an immediate new storage service. Size estimates exclude images, PDFs, additional archives and Git overhead; monitor actual growth.

Current GitHub constraints, checked against official documentation:

| Mechanism | Practical constraint | Decision |
|---|---|---|
| Normal Git files | GitHub warns above 50 MiB and blocks files above 100 MiB. Individual compressed HTML pages are far smaller. [Large-file documentation](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). | Store small immutable versions, not one ever-growing archive file. |
| Repository health | GitHub recommends small repositories and advises storing generated payloads outside Git as they grow. Wide directories degrade performance. [Repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits). | Shard folders; review at 250 MiB, plan migration around 500 MiB–1 GiB. These are project guardrails, not hard GitHub caps. |
| Actions artifacts | Public-repository retention is at most 90 days. This workflow explicitly uses 30. [Retention settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository). | Useful temporary fallback; not the permanent archive. |
| Release assets | Up to 1,000 assets per release, each below 2 GiB; current documentation states no total release-size or bandwidth limit. [Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases). | Possible secondary daily-bundle store; monthly packaging stays well below those per-release limits. |
| Git LFS | Separate storage/bandwidth accounting and possible quota/billing blocks. [LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs). | Unnecessary for small HTML files; would introduce another billing dependency now. |
| Actions billing | Standard public-repository runners are free, but artifact storage still has plan allowances and usage restrictions. [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions). | Monitor storage and failed/stale runs. The September account lock's precise invoice component has not been established. |

A GitHub archive does not by itself eliminate the possibility of another billing/account interruption. That is why an independent local mirror, expected-run records and freshness monitoring remain worthwhile.

The current consolidated `all_jobs.json` is already about 19 MiB. Monitor its growth against the single-file limits too; partitioned historical exports and a compatible loader may eventually be needed. There is no immediate need to restructure it as part of the HTML fix.

### Acceptance checks for the archiver

- An archived page restores to exactly the saved response bytes and hash.
- A later 404 or parser exception leaves the earlier valid source intact.
- Unchanged advert evidence reuses its source version while still logging a new daily observation.
- A substantive content or metadata edit creates a new source version.
- A chosen historical version can be parsed with a corrected extractor without contacting the website.
- Failed extraction and publication are visible in run status; uploading an artifact or archive succeeds independently where possible even after extraction errors.

## Phase 2 — focused scraper repairs

These are targeted improvements to an already useful collector. Keep each source raw field, rather than replacing it with an uncertain normalized interpretation.

| Repair | Required behavior / verification |
|---|---|
| Complete title | Prefer `[itemprop="title"]` or the real advert heading. Preserve legitimate dashes and `X2`. Cover the Operator and Project Officer examples with fixtures. |
| Complete descriptions | Retain all available job text and optional source HTML. Remove the silent 10,000-character limit; record length and completeness status. Keep full and cleaned text as separate fields. |
| Interface cleanup | Remove application/share form text from the analysis field after preserving application URLs and source HTML. Do not delete substantive instructions, qualifications or closing dates. |
| Salary and job type | Read structured salary/currency and raw `jobtype` first. Only accept text-based salary when context supports it; unknown stays null. Preserve fixed-term wording separately from normalized contract categories. |
| ID-based discovery | Deduplicate URL aliases before detail requests. Retain final/canonical URL and alias history. Keep the existing successful final-ID deduplication. |
| Safe fresh start | Handle a missing database without `.get()` on null. |
| Page validation | Separate HTTP success from a valid advert; missing key selectors, blocked/error pages and zero/partial discovery must be detectable. |
| Honest reporting | Distinct new/updated/unchanged/successful/failed IDs for this run; unresolved historic 404s separately. Separate per-job retry attempts from aggregate counts. |
| Reliable publishing | Remove swallowed staging/push errors, serialize overlapping updates, and confirm archived sources and the current dataset were actually published. |
| Observation history | Update individual JSON and consolidated first/last observations consistently. Refresh cached adverts according to an explicit policy. |

Use normal-range and outlier fixtures: multi-location adverts, a valid absent salary, a structured salary, a long advert, a short external teaser, legitimate hyphenated roles, URL aliases, a 200 error page, changed content and a cold start. Long or short text should be flagged when appropriate rather than automatically discarded. Preserve rare valid observations.

Additional inexpensive source fields are raw closing date, country, actual Apply URL/external requisition ID, attachment/image links, and an explicit vacancy-count hint. Keep listed region tags distinct from a specific worksite or roster extracted from the description. Agency and client employer should remain distinct when the evidence identifies them.

## Phase 3 — recover and improve historical fields

### Salary recovery is worthwhile, with a source hierarchy

1. **Preserved HTML:** re-extract structured salary, currency, job type and title. This is the strongest route for the existing 189 files and any recovered artifact pages.
2. **Stored descriptions:** look for explicit currency/amount/pay-period evidence in salary context. The descriptions are already in consolidated JSON even when individual HTML files are absent.
3. **Live or externally linked adverts:** retrieve when useful, but label the new capture time. A current version is not guaranteed to be identical to the original publication.
4. **No surviving evidence:** mark salary unknown. Do not turn the old comma or an arbitrary number into a pay estimate.

A preliminary text screen finds salary/remuneration/wage terms in **1,112 descriptions** and simple explicit PGK/Kina/K-number patterns in **367**. These are candidate-review counts, not 1,112 or 367 validated salary observations. Context may describe benefits, fees, allowances, company turnover or something else.

Full descriptions make later recovery possible for many fields, but they are not guaranteed to contain salary. The audited Education Program Manager salary appears in structured page metadata outside its short description. Without source HTML or a surviving page, that particular value would not be recoverable from the description alone.

For repaired values retain raw evidence, normalized amount/range, currency, period if specified, source type, capture/version identifier, extraction version and a quality flag. Preserve the original scraped value in historical versions. Keep inferred/model-produced values separate from explicitly advertised pay.

### Other historical repairs

- Recover full titles and normalize dates from available HTML. With description-only evidence, retain a reconstructed-title field and provenance rather than silently inventing an exact original heading.
- Recover complete text for capped records when source evidence survives. There are 72 capped records. Where expired originals and artifacts are gone, the missing tail cannot be reconstructed reliably.
- Clean repeated interface text from a derived description while retaining the stored original. This can improve token efficiency without losing evidence.
- Preserve observation history and flag the September gap. Do not rewrite `first_seen` as if the scraper had run during it.
- Flag likely source reposts/duplicates for analysis; do not automatically collapse different IDs with identical descriptions into one vacancy.

Every backfill should report record count, unique IDs, source coverage, fields changed, ambiguous/unrecoverable cases and extraction provenance. Require a preview and compare old/new values before publishing changed data. Keep parser changes and backfilled data in separate commits from later classification and survey analysis.

## Phase 4 — analysis continuity and classification

The previous 503-job classification sample predates the September interruption. The salary field is not separately supplied to the classifier. Full descriptions and employer context provide substantial classification evidence despite some title cuts. Retain the prior outputs as versioned analysis results.

Before a larger refresh, perform a targeted comparison on records affected by title/description repairs. Check whether corrected inputs materially change category shares or individual codes; do not infer that every old classification must be wrong. This plan does not include a paid rerun now.

For subsequent classification, store input hash, source/parser version, model, prompt version, run time and success/error status. Reprocess changed inputs deliberately; do not treat a cached error as a successful finished job. Bound parallelism, use retries/backoff and save progress frequently.

For September aggregates use the observed dataset plus the documented +75 central and +40/+90 sensitivity where relevant. Do not manufacture missing job descriptions or distribute all inferred missing adverts across industries using unsupported weights.

## Proposed implementation sequence and commit boundaries

1. **Preserve artifacts and source inventory immediately**, before the earliest confirmed expiry on 20 October. Confirm recovered file coverage.
2. **Add durable versioned raw HTML capture and manifests**, then verify restore behavior. Start with compressed first/changed versions in Git and a local mirror; add daily bundles if required.
3. **Repair extraction and run validation** using focused fixtures for demonstrated failures. Archive evidence before all parsing.
4. **Publish a separately reviewed historical backfill**, with measurable changes and provenance. Recalculate data quality and ensure IDs/old analytical outputs are preserved.
5. **Refresh classification and analysis separately**, with a targeted sensitivity check first.

The current work delivers the estimate, evidence and this plan. It does not enable new storage services, modify GitHub settings, download the artifact archive, change production collection, rewrite historical data or incur classification charges.
