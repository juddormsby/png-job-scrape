# Simple vacancy analysis plan

Implemented in one analysis script, `code/vacancy_summary.do`, plus the reusable project helper `code/ado/codebook_export.ado`. No Python pipeline, AI calls, classifier refresh or survey comparisons. Compatible with installed Stata 13.1. This document replaces the larger proposed workflow.

From Stata, run `do code/vacancy_summary.do "/path/to/pngworkforce-scrape" "2026-10-19"`. Omit the project path only when already in the repository root; omit the date label to use the current date. An optional third argument sets the incident-cohort start, default `02nov2025`. A rerun needs a fresh label, for example `2026-10-19_v2`.

## Inputs and outputs

Read the latest `json_output/all_jobs.csv`. Use `json_output/all_jobs.json` only for description text needed to recover closing dates: the CSV has neither descriptions nor a closing-date field. Any JSON text reading/extraction stays inside the same do-file.

At the top of the script, set the project root, output date and provisional cohort start (2 November 2025). Derive the observation cutoff from the input data, not today's calendar date. Use relative paths below the project root.

Save everything under one dated folder:

```text
code/vacancy_summary.do
analysis/2026-10-19/
    vacancy_summary.do          # copy of the script actually run
    codebook_export.ado         # frozen helper used by the script
    input_all_jobs.csv          # frozen copy of input
    input_all_jobs.json         # frozen description source, if used
    analysis.log                # checks, definitions, counts and source timestamps
    analysis_base.dta           # prepared advert-level data and flags
    checks.csv
    codebook.xlsx               # one row per variable; literal missing + placeholders + quality notes
    codebook.csv                # same inventory in plain text
    monthly_adverts.csv
    monthly_adverts.png
    employer_counts.csv
    employer_chart.csv          # top 15 plus remainder, matching the chart
    employer_counts.png
    duration_summary.csv
    duration_curve.csv          # complete curves for both sensitivity groups
    duration.png
    closing_dates.csv
    README.txt                 # completion marker, dates and interpretation
```

Each chart also has a PDF and editable Stata `.gph`. Desktop Stata uses its native graphics exporters. The installed older Mac console cannot export PNG/PDF directly, so the same do-file uses already-installed Ghostscript for local EPS conversion; EPS intermediates stay in temporary storage. No additional script is needed.

Create the dated folder only if it does not exist. Stop if it already exists; for an intentional rerun use an explicit suffix such as `2026-10-19_v2`. No overwriting completed runs. Keep the original scripts, classifications, charts and workbook in place; no archive/move is needed because all new outputs have their own folder. The existing expanded plan remains recoverable in Git history.

## Three sections in the do-file

1. **Basic checks / analysis base.** Import successful advert rows; count failed rows separately. Check unique IDs, missing fields, date parsing, impossible dates and repeat-description candidates only if JSON text is available. Keep questionable records with flags. Report snapshot timing, initial stock, partial months and the September collection gap. Save the prepared `.dta` and a compact checks table.
2. **Time and employers.** Count distinct advert IDs by first-seen month, with advertised-date counts as a sensitivity check. Normalize employer whitespace/case, preserving original names and avoiding speculative company merges. Rank employer counts/shares, show top employers plus the remainder, and save the full ranking. Treat these as adverts, not verified numbers of positions.
3. **Duration and closing dates.** Calculate the observed first-to-last-seen span and distinguish it from a confirmed vacancy lifetime. Exclude startup stock from the incident cohort; censor still-live adverts at the snapshot cutoff; flag/exclude spells crossing 1–19 September 2026, last seen on 31 August, or caught up at restart on 20 September in a sensitivity result. The latest CSV does not record the first successful scrape where each advert disappeared, so label survival results as an approximation using last seen rather than pretending exact removal dates are known. Report the median and restricted mean over 30 inclusive observed days, alongside unadjusted observed-span summaries. Using span + 1 keeps same-day observations in the survival risk set; this convention is explicit in output column names. Recover explicit full-year closing dates near closing cues from JSON description text; retain evidence and flag ambiguous/multiple/unparsed dates. These are rule candidates, not manually verified dates. Distinguish advertised application windows from observed listing spans; negative windows are flagged and excluded from window summaries. Closing dates appearing only in HTML are outside this first pass.

Each figure has a corresponding CSV table. Use Stata's standard commands and record the Stata version in the log. No new software framework, configuration files, cache directories or external API calls. The JSON reader deliberately supports the current scraper's one-property-per-line format; row-count and matched-ID assertions stop the run if it drifts. `README.txt` is written only after successful completion; an incomplete run retains its log and cannot be silently overwritten.
