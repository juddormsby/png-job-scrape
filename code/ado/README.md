# Project Stata helpers

Keep reusable `.ado` commands here. From the repository root, add this folder to the current Stata session:

```stata
adopath ++ "code/ado"
```

`code/vacancy_summary.do` adds the absolute project helper path automatically. Nothing is installed in Stata's global directories.

## codebook_export

```stata
use "analysis/2026-10-19/analysis_base.dta", clear
codebook_export
export excel using "codebook.xlsx", firstrow(variables) replace
```

The command replaces the dataset in memory with one row per variable, as in the original workflow. It restores the original data if it fails. To keep data after a successful call, surround the call and exports with `preserve` / `restore`.

Columns: variable name and label, numeric/string type, storage type, display format, distinct nonmissing values, literal missing/nonmissing counts, percent missing (0–100), placeholder count, combined missing-or-placeholder percentage, unweighted numeric mean/min/max/SD, and `quality_note`.

`missing` means empty strings or numeric missing values (including `.a`–`.z`). `placeholder` separately counts nonempty whitespace-only or ASCII punctuation-only strings such as `","`, `".."` and `"--"`. `pct_missing_or_placeholder` combines those two counts. The helper changes no source values. Distinct counts include placeholders because they are literally nonmissing.

Neither measure validates a populated value. In this project the raw salary field contains both commas and incidental numbers: its remaining numeric-looking strings must not be interpreted as usable salaries. The main analysis fills `quality_note` with this warning and explains structural missingness in failure/cohort fields and incomplete archive-reference metadata. Generic calls leave that notes column empty for the caller to annotate. Text such as `"unknown"` is not automatically recoded.

Numeric dates remain underlying Stata day/time values; `varformat` identifies them. The main analysis explicitly converts `description_length` and `retry_count` to numeric counts after importing the CSV; IDs remain strings.

No `ssc install distinct` is required. Built-in Mata counts full values, including long `strL` descriptions, without truncation. This is a completeness inventory, not a field-validity audit; retain the analysis script's date and consistency checks.

The main analysis exports `codebook.xlsx` and `codebook.csv` into its new dated output folder and includes a frozen copy of this helper alongside the do-file.
