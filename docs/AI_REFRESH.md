# AI refresh — 20 October 2026

The authorized refresh completed on the 20 October source snapshot: **3,780 successful advert IDs, no failed classifications**. The model is `gpt-6-luna`, with low reasoning effort. The 100-advert pilot and both full-sample Stata analyses completed. Start with `analysis/2026-10-20_ai_final/README.md` for results and file locations.

## Files and folders

- `classify_jobs.py`: prepare frozen inputs, classify, and resume failed/pending adverts. Only `--execute` makes AI/API calls.
- `json_to_csv.py`: local JSON-to-CSV conversion, retaining explicit success/error/pending status.
- `vacany_analysis.do`: local Stata analysis of classifications, requirements and SDES comparisons.
- `code/vacancy_summary.do`: local Stata analysis of raw data quality, time, employers, duration and closing dates.
- `code/ado/codebook_export.ado`: the shared Stata codebook helper.
- `analysis/2026-10-20_ai_final/`: current frozen inputs, preparation manifest, source scripts, AI results, execution logs and pilot review. Its `analysis/` subfolder holds final Stata outputs. `executed_code/` records any execution fixes made after preparation; original frozen files remain intact.
- `analysis/2026-10-20_v3/`: completed basic Stata analysis of the same latest raw snapshot, with frozen inputs and executed code.
- `analysis/legacy/ai-pilots-2026-10-20/`: intermediate pilots, including the preceding pilot that supplied 99 validated same-input, same-prompt results to the final pilot.
- `analysis/legacy/pre-ai-refresh-2026-10-20/`: verified original scripts, runs 0–6 and previous comparison outputs. Its manifest records 22 hashes. Historical results elsewhere remain untouched.

Dated run folders and archives are kept in Dropbox and ignored by Git. The reusable scripts, tests and documentation are tracked. Existing Stata output folders are refused, so a rerun needs a fresh run label. `OUT` is the absolute selected AI run folder plus `/analysis`; the Stata log prints it and the resolved survey input path. No survey microdata are copied.

## Inputs and pilot

Preparation uses local JSON and archived HTML, without API calls. Matching HTML repaired 753 advert inputs; no HTML-body mismatch was found. It preserves legitimate title dashes and application instructions, stripping only known trailing site controls. Original scraper records are unchanged. Missing HTML and capped descriptions remain source limitations; provenance and hashes are saved per input.

The reproducible pilot contains 40 adverts from the previous final sample and 60 newer adverts. Its review is in `pilot/REVIEW.md`. Historical classifications are not ground truth, and disagreement can reflect repaired text or more conservative coding. Evidence quotes and code hierarchies are checked; fine-code labels have not been exhaustively verified against official lookup tables.

The first pilot exposed ambiguity in credential alternatives. The prompt now explicitly selects the lowest acceptable level (high school OR vocational certificate becomes secondary) and distinguishes alternative credentials from a non-credential route. Duplicate skill categories retain one quote, with discarded mentions retained separately in JSON. A validation correction allows a qualification to be required even when its level is unspecified. Validation retries now include the rejected candidate and the specific error, so quote/code corrections can be targeted. These execution fixes preserve input hashes, the final prompt, and the meanings of the output fields.

## Simple new fields

| Fields | Interpretation |
|---|---|
| `education_level` | Lowest explicitly acceptable credential: secondary, vocational/trade/certificate, diploma, bachelor, postgraduate, other; explicit no qualification required; or no stated level. A high-school diploma is secondary. |
| `education_requirement` | Required, preferred, alternative accepted (a non-credential route can substitute), or not stated. A qualification may be required without a stated level. |
| Required/preferred experience years | Separate minimum stated years. A 3–5 range becomes 3; explicit no experience becomes 0; silence/vague experience stays blank. Overlapping experience is not summed. |
| Graduate/apprenticeship/entry-level flags | Explicit programmes, roles or invitations only. Zero means no explicit identification; it does not mean young people are ineligible. |
| Six skill mention flags | Digital, technical/trade, communication, teamwork, leadership and organisation. These are broad mentions, not a detailed skills taxonomy or measures of proficiency. |

Short evidence quotes support stated requirements and positive flags. Multi-role adverts can combine entry routes and requirements for different positions; fields describe the advert. No salary, geography, nationality, age or task-exposure fields are guessed. The old ISIC/ISCO 1–4 digit columns and confidence fields remain; confidence is a model self-assessment, not measured accuracy.

## Running again

Use the project environment (`venv/bin/python`); dependencies are in `requirements-ai.txt`. Preparation and previews do not read credentials or import the OpenAI SDK. Live execution uses `OPENAI_API_KEY`, falling back to the existing ignored key file; credentials are never archived.

For a new source/model/prompt, use a NEW folder:

```bash
venv/bin/python classify_jobs.py --run-dir analysis/NEW_DATE_ai --prepare
venv/bin/python classify_jobs.py --run-dir analysis/NEW_DATE_ai --pilot --execute
venv/bin/python json_to_csv.py --run-dir analysis/NEW_DATE_ai --pilot
```

Review the pilot, then execute the full run and convert:

```bash
venv/bin/python classify_jobs.py --run-dir analysis/NEW_DATE_ai --workers 32 --execute
venv/bin/python json_to_csv.py --run-dir analysis/NEW_DATE_ai
```

Repeated execution resumes matching successful results and retries errors. Each completion is saved atomically. The current full run reuses its 100 validated pilot results; historical model classifications are not used as completed results.

From Stata:

```stata
do vacany_analysis.do "/path/to/pngworkforce-scrape" "analysis/NEW_DATE_ai"
do code/vacancy_summary.do "/path/to/pngworkforce-scrape" "NEW_DATE_basic"
```

The optional third argument to `vacany_analysis.do` overrides the SDES person-file path; its default sibling-project path exists. Stata stops if any AI rows are unfinished. Outputs include classification coverage, education/requirements tables, CSV/Excel survey comparisons, classified data, PNG figures and logs. Comparison shares are conditional on classification, with shares of all adverts exported as well. SDES weighting/category exclusions follow the original analysis; survey employment stocks and online advert flows are different populations. Local Ghostscript handles exports unsupported by the old Mac Stata console.

Seventeen AI-refresh offline tests (32 tests in the full suite) cover validation, evidence, code hierarchies, duplicate mentions, unspecified qualification levels, source repair, frozen inputs, previews, resume behaviour, targeted retry feedback and CSV headers. No API is used in these tests. Both final Stata logs contain explicit completion markers. Chart totals, all-advert/conditional shares and survey totals were checked. Final completion, output hashes, software versions and accepted-response token usage are recorded in `execution_report.json`; that usage excludes rejected attempts, earlier pilots and interrupted calls, so it is not a complete billing total.

Official references: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).


## Original 2025 prompt with Luna

`analysis/2026-10-20_luna_2025prompt/` is the separate controlled rerun requested after the first refresh. Its raw JSON, prepared advert inputs and pilot IDs were verified byte-for-byte against `2026-10-20_ai_final`; Luna and low reasoning are held constant. The recovered 2025 system message, user template (including whitespace) and original classification-only schema are in `code/prompts/classification_2025.json`, with the source script hash. Recovery was checked against evaluating the archived original f-string.

Use `--prompt-style 2025` for both preparation and execution:

```bash
venv/bin/python classify_jobs.py --run-dir analysis/NEW_DATE_2025prompt --prompt-style 2025 --prepare
venv/bin/python classify_jobs.py --run-dir analysis/NEW_DATE_2025prompt --prompt-style 2025 --execute
venv/bin/python json_to_csv.py --run-dir analysis/NEW_DATE_2025prompt
```

This mode requests only the original industry, occupation, confidence and summary fields. It uses the original type contract and repeats identical messages on retries, with no new evidence instructions or validation-feedback prompts. The converter detects the mode from its manifest, and the same Stata script skips requirements tables when those fields were not requested. Richer education/experience/skill results remain in the preceding run. Existing outputs and defaults are preserved.

The 2025 historical analysis covered 503 adverts with a different model and input text. Comparing that result with the new full sample combines sample, model and source-text differences. The two full-sample Luna runs hold inputs, model and reasoning constant to compare prompt/schema effects, subject to model variability. The rerun completed all 3,780 responses successfully and regenerated the Stata comparisons. Industry coverage is 3,770 / 3,780 (99.7%) and occupation coverage is 3,775 / 3,780 (99.9%). See its README and execution report for comparisons and completion checks.


## Selected 2026 prompt and PNG-only charts

The selected main analysis is `analysis/2026-10-20_ai_final/`, using the 2026 requirements prompt. Its `analysis/` folder now has 15 PNG charts covering broad industry/occupation, education level/status, required/preferred experience, entry routes, skills, field coverage, employment type, closing dates/application windows, time, employers and duration. The run README contains the chart index and denominator notes. No new AI calls were made to produce the extra charts.

Both reusable Stata scripts now export PNG only. Temporary EPS is converted locally for the older Mac console; no EPS/PDF/GPH output is retained in the working chart folder. Six earlier PDF/GPH copies are preserved in the run's `legacy_graph_formats/` directory. Original classifications, data and tables remain unchanged.

The same Stata script adds charts to an existing completed run using its fourth `charts` argument. The fifth argument supplies a matching basic analysis; an ID merge checks that both samples are the same:

```stata
do vacany_analysis.do "/path/to/pngworkforce-scrape" "analysis/2026-10-20_ai_final" "." "charts" "analysis/2026-10-20_v3"
```

Existing chart files/logs are refused. For a later revision, archive earlier additions first. A fresh full analysis also creates these core charts. Education is advertised credential information, not observed applicant attainment. The experience chart uses separate stated-year bases; field coverage shows how many adverts provide those years. Salary and multi-place geography need further source work, and fine classifications, confidence, free text/contact fields and technical metadata are intentionally not plotted.
