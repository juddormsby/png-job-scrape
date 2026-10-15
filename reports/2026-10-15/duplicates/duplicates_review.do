* Read-only duplicate review. Run from the repository root, optionally passing it:
* do reports/2026-10-15/duplicates/duplicates_review.do "/path/to/repository"
version 13
clear all
set more off
set linesize 120
args project
if `"`project'"' != "" cd `"`project'"'
local out "reports/2026-10-15/duplicates"
capture log close
log using "`out'/duplicates_stata.log", text replace
display "Installed Stata version: " c(stata_version)
if c(stata_version) < 14 {
    use "`out'/duplicate_keys_stata13.dta", clear
    display "Stata 13 compatibility file: ASCII display labels; hashes use full original Unicode descriptions."
}
else {
    use "`out'/duplicate_review.dta", clear
}
assert _N == 3712
isid job_id
* description_key is SHA-256 of the ENTIRE original description, not a prefix.
* Python independently checks every key against the original source string.
duplicates report job_id
duplicates report description_key
duplicates report employer_key description_key
duplicates report employer_key title_key description_key
duplicates report employer_key title_key date_posted description_key
duplicates report employer_key title_key posted_day description_key
duplicates tag description_key, generate(dup_description)
assert dup_description == copy_count - 1
count if dup_description > 0
assert r(N) == 433
bysort description_key (first_day job_id): generate byte first_text = _n == 1
count if first_text
assert r(N) == 3448
count if !first_text
assert r(N) == 264
* Every member of a repeated group is tagged: not just the surplus copies.
tabulate copy_count
sort repeat_group first_day job_id
list repeat_group job_id employer title first_day posted_day if inlist(job_id,28894,28895,28893,28060,26460,26461), noobs sepby(repeat_group) abbreviate(24)
save "`out'/duplicates_tagged.dta", replace
display "REVIEW_COMPLETED_SUCCESSFULLY: no source records dropped or modified"
log close
