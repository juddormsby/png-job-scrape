# Vacancy analysis plan

Scope: data preparation, tables and charts. Presentation narratives and personal examples remain with Judd. Unit: distinct advert IDs; an advert can contain several vacancies.

## Storage and workflow

Use **Python plus Stata**. Python handles JSON/HTML, deterministic text extraction, AI calls, joins and basic descriptive figures. Stata retains the existing survey comparison and handles duration/survival analysis. Keep each calculation in one language: do not maintain competing Python and Stata versions. No notebooks are needed for the production workflow.

### Code: eight scripts, three supporting files

All new code lives under `code/analysis/`; leave the root-level `vacany_analysis.do` and `classify_jobs.py` intact as legacy code.

| File under `code/analysis/` | Responsibility | Programme / external AI |
|---|---|---|
| `run.py` | Single entry point; creates a run directory, freezes inputs, runs selected stages, records completion and logs. Invokes Stata only when requested. | Python; no AI |
| `prepare.py` | Validate snapshot, clean fields, apply employer aliases and join classification/extraction results by job ID. Export a documented analysis CSV. | Python; no AI |
| `extract.py` | Read available HTML/text; recover closing dates/pay, rule-based locations and youth/skills/recruitment flags; retain source evidence. | Python; no AI |
| `descriptives.py` | Time, employer, salary, geography and youth/skills tables and figures; classification shares when available. | Python; no AI |
| `exposure.py` | Apply versioned occupation/index crosswalks and report match coverage and sensitivity. | Python; no AI |
| `ai/enrich.py` | Separately requested ISIC/ISCO recoding and optional semantic extraction. Validates responses and saves resumable results. | Python; paid AI API |
| `duration.do` | Read prepared observations; apply cohort/censoring rules; export survival/duration tables and figures. | Stata; no AI |
| `survey_comparison.do` | Adapt the main comparison from the old do-file; read SDES and prepared vacancy data; export industry/occupation comparisons. | Stata; no AI |

Supporting files: `config.yaml` (paths, cohort dates, stage choices, versions), `README.md` (commands/dependencies/field definitions) and `ai/prompts.yaml` (versioned classification and extraction instructions). Start with these **11 files**; add another module only when a distinct task needs one. Reuse existing audit methods rather than copying entire audit scripts.

Python uses the existing project environment and dependency file, with any needed analysis packages added explicitly. Stata uses the installed Stata programme; check the version, executable path and existing `labmask`/`labutil` dependency. The survey do-file accepts the SDES path from configuration. No survey microdata are copied into this repository. Stata reads Python's CSV exports, retaining occupation codes as strings so leading zeros survive.

### Inputs and outputs

```text
code/analysis/                         # the 11 files specified above
analysis/README.md                     # index of preserved and new results
analysis/legacy/pre-refresh-<date>/     # preserved previous results/code/inputs + manifest
analysis/reference/                    # small, versioned aliases, codebooks and crosswalks
analysis/cache/ai/<schema-prompt-model-version>/
                                       # reusable responses, keyed by job ID + input hash
analysis/runs/<date>_<label>/
    inputs/                            # frozen all_jobs.json, config, reference files
                                       # and classification/extraction inputs actually used
    data/                              # adverts.csv, observations.csv, locations.csv, skills.csv
    tables/                            # CSV tables behind every figure
    figures/                           # presentation PNGs and shareable PDFs
    logs/                              # Python logs and Stata .log files
    manifest.json                      # input hashes, code version, stages and status
    README.md                          # definitions, coverage and limitations
analysis/latest.json                   # pointer to the latest complete run
```

Read `json_output/` and `archive/` without changing them; retain `reports/` for existing audits. Source HTML remains in the existing archive, referenced by immutable path/hash, rather than copied into every run. Record external SDES and index sources, versions and hashes; freeze redistributable small reference inputs. Save the exact new analysis code used in each run's `inputs/code/` as well as its Git revision, so uncommitted working changes do not undermine reproducibility.

### Preserve previous analysis before implementing

1. Create a named legacy snapshot containing the four existing outputs in `analysis/`: the industry, occupation and combined PNGs, and `vacancy_v_sdes.xlsx`.
2. Include copies of `vacany_analysis.do`, `classify_jobs.py`, `json_to_csv.py`, and the existing `LLM_processed_jobs0`–`6` JSON/CSV files. These are distinct historical classification runs: do not merge or overwrite them.
3. Add a manifest of original paths and hashes, plus a note that the legacy charts use run 6 and external SDES data. Preserve what exists without claiming the original environment is fully reconstructible.
4. Verify copied hashes. Keep originals in their present locations initially so old paths continue to work. New scripts write only to named run folders; no new loose outputs go directly into `analysis/`.

This initial duplication is deliberate and small. A later cleanup can remove redundant loose copies after the archived results have been checked; it is not necessary for the new pipeline. The existing source `archive/` is for scraped evidence, so historical analytical results belong under `analysis/legacy/`.

### Rules that keep directories clean

- Give every run a unique name, e.g. `2026-10-19_baseline-v1`. Refuse an existing directory unless explicitly resuming an incomplete run with matching inputs. Completed runs are immutable; changed inputs or methods create a new run.
- Use stable output names inside each run, such as `tables/employer_counts.csv` and `figures/employer_counts.png`; avoid `final2` or timestamp suffixes on every file. Each script owns named outputs to prevent collisions.
- Share one AI cache across runs. Freeze the subset actually consumed into the run inputs, including evidence and version metadata. A normal local run never silently starts paid calls; missing AI results appear in coverage tables.
- Keep intermediate scratch files in a system temporary directory and clean them at completion. Retain review evidence and final derived data, not every temporary join/export. Failed runs retain logs and an explicit incomplete status.
- Update `latest.json` only after all requested stages succeed. State in the manifest whether the run includes AI enrichment, Stata duration and SDES comparison; a baseline-only run is clearly labelled.
- Track code, configuration, small reference tables and the analysis index in Git. Keep generated `analysis/runs/` and `analysis/cache/` in the existing Dropbox workspace and exclude them from Git when implementing. Preserve the legacy snapshot in Dropbox; commit its compact index/manifest, with ignore rules scoped so that manifest stays trackable. Existing tracked results are left intact.
- Never delete previous completed runs automatically. Mark superseded versions in the index. Package a selected run for sharing rather than creating another scattered set of presentation copies.

Planned commands: `python code/analysis/run.py --config ... --stages baseline`, a separate explicit `python code/analysis/ai/enrich.py --config ...`, then `python code/analysis/run.py --config ... --stages baseline,duration,survey,exposure`. These commands will be implemented with the scripts; they do not exist yet. Local processing remains usable without Stata for the baseline stages, and without an API key for every non-AI stage.

The local pipeline must run without an AI key. AI runs write a versioned cache, which the local pipeline can consume. Record job ID, input hash, schema/prompt/model versions and source excerpts; reuse unchanged results, retry failures and validate a small reviewed pilot before scaling.

## Ordered work

| Stage | Data task and output | Outside AI API? |
|---|---|---|
| 1. Analysis base | Freeze a source snapshot; check IDs, date coverage, title/description defects, employer fields and prior classification coverage. Build one advert-level table with missingness and source flags. Audit available full HTML before recoding. | No |
| 2. Time and employers | Monthly/weekly first-seen counts, plus advertised-date sensitivity; mark initial stock, partial periods and the September gap. Normalize employer aliases; rank counts and shares, top-10 concentration and recruiter versus employer where identifiable. | No; manual alias review |
| 3. Duration and closing dates | Recover explicit closing dates from HTML/text using selectors and date rules. Compare advertised application windows with observed listing lifetimes. Report mean and median with censoring handled explicitly. | No initially; optional ambiguous-text extraction |
| 4. Refresh previous charts | Audit old ISIC/ISCO outputs and job-ID coverage, refresh classification after source repair, then reproduce industry/occupation shares and SDES comparisons with missing/unclassified shares shown. | Yes for fresh model classification; charting and SDES joins are local |
| 5. Salary coverage | Reuse reviewed salary evidence and distinguish description versus full-page recovery; update counts only for a changed snapshot. Keep pay period, currency, allowances and source completeness separate. | No for existing evidence and structured extraction; optional AI interpretation |
| 6. Youth and skills | First locate any earlier skills coding: the current classifier only contains ISIC/ISCO. Extract education, experience years, named skills, apprenticeships, graduate/entry-level roles and explicit age restrictions; retain evidence and unknowns. | Rules/manual pilot: no. Scalable semantic coding: yes if using an external model |
| 7. Geography and special recruitment | Create multi-location records; distinguish work location, employer address and recruitment eligibility. Flag explicit expatriate/national restrictions, overseas roles, seasonal work and fixed-term contracts separately. | Parsing/rules: no. Optional AI for ambiguous wording |
| 8. AI exposure | Select a published occupation-based index, verify its crosswalk and merge locally to refreshed ISCO codes; show match coverage and sensitivity. Test task-level feasibility on a small sample before commissioning task extraction. Industry-based measures are a fallback/proxy. | Index research/download and joins: no AI API. New occupation/task inference: yes if model-based |

## Key analytical decisions

- **Duration:** provisionally start the incident cohort on 2 November 2025, subject to observation checks. Exclude initial stock; censor still-live adverts at the snapshot end. Treat disappearance between successful scrapes as an interval, and flag/exclude spells crossing 1–19 September 2026 in sensitivity checks. `last_seen` alone is not a confirmed closing date. Use survival estimates, including a restricted mean over a common follow-up horizon if needed; do not average completed adverts alone.
- **Salary:** the 15 October snapshot already has 58/3,712 adverts (1.56%) with numeric pay in descriptions and 88/3,712 (2.37%) using held HTML too. These are reviewed disclosures, not reliable values in the existing salary field. Do not extrapolate archive-subset coverage to all adverts.
- **Geography:** retain all named locations. Use fractional counts for an additive regional chart, and report multi-region/unspecified shares. Compare with external employment distributions only after harmonizing geography and denominators; online adverts describe recruitment flows, survey employment describes a stock.
- **Youth:** graduate/entry-level opportunities are proxies, not direct evidence that vacancies are for young people. Skills are stated demand, not a measure of applicants' ability.
- **Additional useful outputs:** education/experience barriers by occupation; employer concentration by industry; repeat advertising; domestic versus overseas recruitment. Seasonal-work mentions can be measured now; calendar seasonality needs more complete years of observation.

Delivery order: local baseline first (1–3 and 5), reviewed AI recoding second (4, 6–7), exposure linkage last (8). External index/survey acquisition is a separate non-AI dependency. No paid AI runs are part of writing this plan.
