# Prepared AI refresh — not executed

The existing classifier, CSV converter and Stata comparison are prepared for a fresh full-sample run. No classification requests or Stata analysis were run during preparation. The default model is `gpt-6-luna` with low reasoning effort and eight workers. This is a candidate to evaluate on the pilot, not a claim of measured accuracy.

## What is preserved

`analysis/legacy/pre-ai-refresh-2026-10-20/` contains verified copies of the original three scripts, requirements file, classification runs 0–6 (JSON and CSV), and four old comparison outputs. Its manifest records all 22 hashes. Originals of the historical classification files and charts stay in place. Current root scripts are the prepared versions; their previous versions are in that archive and Git history. Generated archives/run bundles remain in Dropbox rather than being added to Git.

## Where the next run will live

`analysis/2026-10-20_ai/` holds the frozen source JSON, `prepared_jobs.json`, `pilot_ids.json`, a preparation manifest and copies of the scripts/dependency files. It contains no invented classifications. The latest **local** source snapshot is dated 19 October and has 3,760 successful advert IDs; preparation does not fetch newer remote data.

Preparation strips only known trailing site controls. Where available HTML has a matching description/prefix, it can restore the marked advert title and full description, preserving legitimate dashes. Mismatched HTML is flagged and not substituted. No original scraper records are changed. The manifest and each prepared record identify the chosen source, hashes and capped-description flags. Missing HTML or truncated JSON remains a source limitation.

The pilot is a reproducible 100-advert selection: 40 from the previous final classification sample and 60 newly added adverts. Review the old/new overlaps and visibly ambiguous cases, plus the new evidence quotes. Old classifications are a comparison, not ground truth. Input repairs also mean disagreement cannot automatically be attributed to a model change.

After an authorized run:

- `pilot/LLM_processed_jobs.json` and `.csv`: the separate pilot.
- `LLM_processed_jobs.json` and `.csv`: the full refreshed sample, including retriable errors/pending rows in CSV.
- `analysis/`: Stata data, education/requirements tables, classification coverage, two survey comparisons (CSV/Excel), graphs (PNG/PDF/GPH), and a log. Stata stops if unfinished/failed AI rows remain and refuses an existing analysis output folder.

A full run reclassifies every advert using the same prepared model/prompt. It does not import the old model's classifications as completed results. Within a run, successful matching results are reused; errors are retried. Each completion is saved atomically, with source hash, model/prompt version, summary and returned token usage. CSV columns are fixed, including explicit failure status. Classification confidence is a model self-assessment, not calibrated accuracy.

## Simple new fields

| Fields | Meaning and examples |
|---|---|
| `education_level` | Lowest explicitly acceptable credential: secondary, vocational/trade/certificate, diploma, bachelor, postgraduate, other; or explicit no qualification required / not stated. No inference from job title. |
| `education_requirement` | Required, preferred, or alternative accepted (e.g. degree **or** equivalent experience). A preferred diploma is not counted as a compulsory entry barrier. |
| `experience_required_years`, `experience_preferred_years` | Separate minimum stated years. “3–5 years required” becomes 3 required years. Explicit “no experience required” is 0; silence or “experienced” without years is blank/null. Do not sum overlapping years. |
| `graduate_opportunity`, `apprenticeship_opportunity`, `entry_level_opportunity` | Explicit invitations/programmes/entry-level roles. **1 means explicitly identified; 0 means not explicitly identified.** Zero does not mean graduates/young people are ineligible. Requiring a university degree alone does not make a graduate opportunity. |
| `skill_digital`, `skill_technical_trade`, `skill_communication`, `skill_teamwork`, `skill_leadership`, `skill_organisation` | Six broad mention flags, not a detailed skills taxonomy. A role may have several. Digital includes software/IT/data; technical/trade includes practical or professional technical skills. Zero means no explicit mention identified, not that the skill is unnecessary. |

Education, experience, positive entry-route flags and each identified skill retain short supporting quotes. Unsupported quotes are rejected for retry. No extra salary, closing-date, geography, nationality, age or task-exposure fields are added. Those should not be guessed or conflated with the four field groups above.

The old ISIC/ISCO 1–4 digit columns and confidence fields remain compatible with the survey comparison. The previously discarded classification summary is now saved. The refreshed Stata script reproduces the old conditional-on-classification shares, additionally exports shares of all adverts and unclassified coverage, and keeps the SDES year/weighting/category exclusions as before. It removes the old seven-run robustness block from the main execution and uses built-in value labels rather than requiring `labmask`. The old robustness code remains archived.

## Commands for later — do not execute until the run is approved

Use the project Python environment. The OpenAI SDK is declared in `requirements-ai.txt`; it is not installed in the current project environment. Install dependencies before the first live run:

```bash
venv/bin/python -m pip install -r requirements-ai.txt
```

Preparation alone is local and has already been completed for the named folder. For a different source/model/prompt, choose a NEW folder:

```bash
venv/bin/python classify_jobs.py --run-dir analysis/NEW_DATE_ai --prepare
```

A preview, with no credentials read and no API calls:

```bash
venv/bin/python classify_jobs.py --run-dir analysis/2026-10-20_ai --pilot
```

Only after approval, execute and review the pilot:

```bash
venv/bin/python classify_jobs.py --run-dir analysis/2026-10-20_ai --pilot --execute
venv/bin/python json_to_csv.py --run-dir analysis/2026-10-20_ai --pilot
```

Only after accepting the pilot, execute the full sample and convert it:

```bash
venv/bin/python classify_jobs.py --run-dir analysis/2026-10-20_ai --execute
venv/bin/python json_to_csv.py --run-dir analysis/2026-10-20_ai
```

Then, separately, from Stata in the repository root:

```stata
do vacany_analysis.do "" "analysis/2026-10-20_ai"
```

The optional third Stata argument overrides the external 2022 SDES person-file path. The default sibling-project location currently exists. No survey microdata are copied. The existing Mac console graphics fallback uses installed Ghostscript locally.

Live requests read `OPENAI_API_KEY`, falling back to the existing ignored `png-jobscraper.txt`. Preparation/preview never reads that file. No credentials are archived or written to outputs. Changing a prepared model, reasoning setting, prompt or input requires a fresh run folder. The classifier deliberately requires `--execute`; preparation and the default preview cannot launch paid calls.

## Validation and current limits

Eleven offline fixture tests cover output/evidence validation, leading-zero codes, unknown versus zero experience, matched/mismatched HTML, nonmutating previews, cached-error retries using a fake client, fixed CSV headers, and changed-input/model rejection. No real adverts were classified in tests and no SDK/API was contacted. The Stata analysis is prepared and inspected but deliberately not executed. Model access, live schema compatibility, token cost and classification accuracy still need the authorized pilot. Historical source gaps, title/description defects without matching HTML, sparse salary disclosure and advert-versus-position differences remain.

Model/endpoint reference: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [official GPT-6 migration guidance](https://developers.openai.com/api/docs/guides/latest-model), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
