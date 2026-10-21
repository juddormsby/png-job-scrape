* Offline vacancy summary with project codebook helper. Stata 13.1 or later.
* Run from repository root:
* do code/vacancy_summary.do "/path/to/pngworkforce-scrape" "2026-10-19"
* An optional third argument sets the cohort start, e.g. "02nov2025".
* Existing output directories are NEVER reused. Use a new label for a rerun.
version 13.1
clear all
set more off
set linesize 120
set scheme s2color
args project run_label cohort_start
if `"`project'"' == "" local project `"`c(pwd)'"'
if `"`run_label'"' == "" {
    local run_label = string(date("`c(current_date)'", "DMY"), "%tdCCYY-NN-DD")
}
if `"`cohort_start'"' == "" local cohort_start "02nov2025"
if !regexm("`run_label'", "^[a-zA-Z0-9_-]+$") error 198
local cohort = date("`cohort_start'", "DMY")
if missing(`cohort') error 198
cd `"`project'"'
confirm file "json_output/all_jobs.csv"
confirm file "json_output/all_jobs.json"
confirm file "code/vacancy_summary.do"
confirm file "code/ado/codebook_export.ado"
adopath ++ "`c(pwd)'/code/ado"
local out "analysis/`run_label'"
capture mkdir "analysis"
capture mkdir "`out'"
if _rc {
    display as error "Output folder already exists or cannot be created: `out'"
    display as error "Choose a fresh run label; previous results have not been touched."
    exit 693
}
capture log close
log using "`out'/analysis.log", text
copy "code/vacancy_summary.do" "`out'/vacancy_summary.do"
copy "code/ado/codebook_export.ado" "`out'/codebook_export.ado"
copy "json_output/all_jobs.csv" "`out'/input_all_jobs.csv"
copy "json_output/all_jobs.json" "`out'/input_all_jobs.json"
display "Stata version: " c(stata_version)
display "Run label: `run_label'; cohort start: " %td `cohort'
display "Unit: advert IDs, not independently verified individual positions."

* Save PNG charts only. The old Mac console uses temporary EPS plus Ghostscript.
program define vacancy_export
    syntax using/
    confirm new file `"`using'.png"'
    capture graph export `"`using'.png"', width(2400)
    if _rc {
        * Old Mac console: EPS is temporary; PNG is the only saved chart.
        tempfile eps
        graph export `"`eps'"', as(eps)
        shell gs -q -dSAFER -dBATCH -dNOPAUSE -dEPSCrop -sDEVICE=png16m -r200 -sOutputFile="`using'.png" "`eps'"
        confirm file `"`using'.png"'
    }
end

* 1. ANALYSIS BASE. Read the scraper's pretty-printed JSON inside Stata.
* This intentionally supports its present one-property-per-line schema, not
* arbitrary JSON. Check every description ID against the independently read CSV.
* No external packages, Python, network requests, or model calls are used.
gen str32 job_id = ""
gen strL description = ""
gen long description_group = .
mata:
void vacancy_read_json(string scalar path)
{
    real scalar fh, n, group, expected
    string scalar line, t, id, q, raw, text, updated
    transmorphic scalar groups
    fh = fopen(path, "r")
    n = 0; group = 0; expected = .; updated = ""
    groups = asarray_create("string", 1)
    asarray_notfound(groups, 0)
    while ((line=fget(fh)) != J(0,0,"")) {
        t = strtrim(line)
        if (strpos(t, char(34)+"failed_jobs"+char(34)+":")==1) break
        if (strpos(t, char(34)+"total_jobs"+char(34)+":")==1) {
            q = subinstr(substr(t,14,.), ",", "")
            expected = strtoreal(strtrim(q))
        }
        if (strpos(t, char(34)+"last_updated"+char(34)+":")==1) {
            updated = subinstr(subinstr(strtrim(substr(t,16,.)), char(34), ""), ",", "")
        }
        if (strpos(t, char(34)+"job_id"+char(34)+":")==1) {
            id = strtrim(subinstr(subinstr(substr(t,10,.), char(34), ""), ",", ""))
        }
        if (strpos(t, char(34)+"description"+char(34)+":")==1) {
            q = strtrim(substr(t,15,.))
            if (substr(q,strlen(q),1)==",") q=substr(q,1,strlen(q)-1)
            if (substr(q,1,1)!=char(34) | substr(q,strlen(q),1)!=char(34)) _error(3498)
            raw = substr(q,2,strlen(q)-2)
            n++; st_addobs(1)
            st_sstore(n,"job_id",id)
            if (asarray(groups,raw)==0) {
                group++
                asarray(groups,raw,group)
            }
            st_store(n,"description_group",asarray(groups,raw))
            // Decode only escapes relevant to readable evidence/date matching.
            text = subinstr(raw,char(92)+"n"," ")
            text = subinstr(text,char(92)+"r"," ")
            text = subinstr(text,char(92)+"t"," ")
            text = subinstr(text,char(92)+char(34),char(34))
            text = subinstr(text,char(92)+"/","/")
            st_sstore(n,"description",text)
        }
    }
    fclose(fh)
    if (n!=expected | n==0) _error(3498)
    st_local("json_total",strofreal(expected))
    st_local("json_updated",updated)
}
vacancy_read_json(st_local("out")+"/input_all_jobs.json")
end
display "JSON snapshot updated: `json_updated'; advert records: `json_total'"
isid job_id
bysort description_group: gen int description_copies = _N
gen byte repeat_description = description_copies > 1 & description != ""

* Conservative closing-date extraction: require a closing cue and a full year.
* Multiple distinct dates and ambiguous numeric day/month order go to review.
gen double closing_day = .
gen byte closing_mentioned = 0
gen byte closing_review = 0
gen int closing_candidates = 0
gen str244 closing_evidence = ""
mata:
string scalar vacancy_clip(string scalar s, real scalar n)
{
    // Stata 13 counts UTF-8 bytes: do not cut an evidence quote mid-character.
    if (strlen(s)<=n) return(s)
    while (n>0 & ascii(substr(s,n+1,1))>=128 & ascii(substr(s,n+1,1))<192) n--
    return(substr(s,1,n))
}
real rowvector vacancy_date(string scalar token)
{
    real scalar d, a, b
    string scalar months
    months="(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
    if (regexm(token,"^([0-3]?[0-9])(st|nd|rd|th)?[ -]+"+months+"[ ,/-]+(20[0-9][0-9])$")) {
        d=date(regexs(1)+" "+regexs(3)+" "+regexs(4),"DMY")
        return((d,0))
    }
    if (regexm(token,"^"+months+"[ ]+([0-3]?[0-9])(st|nd|rd|th)?[ ,]+(20[0-9][0-9])$")) {
        d=date(regexs(2)+" "+regexs(1)+" "+regexs(4),"DMY")
        return((d,0))
    }
    if (regexm(token,"^20[0-9][0-9]-[01]?[0-9]-[0-3]?[0-9]$")) return((date(token,"YMD"),0))
    if (regexm(token,"^([0-3]?[0-9])[/-]([01]?[0-9])[/-](20[0-9][0-9])$")) {
        a=strtoreal(regexs(1)); b=strtoreal(regexs(2))
        d=date(token,"DMY")
        return((d,(a<=12 & b<=12 & a!=b)))
    }
    return((.,1))
}
void vacancy_closing()
{
    real scalar i, pos, mentioned, review, count, found
    real colvector dates
    real rowvector parsed
    string scalar months, datepat, cue, text, rest, tail, evidence, token, lead
    months="(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
    datepat="([0-3]?[0-9](st|nd|rd|th)?[ -]+"+months+"[ ,/-]+20[0-9][0-9]|"+months+"[ ]+[0-3]?[0-9](st|nd|rd|th)?[ ,]+20[0-9][0-9]|20[0-9][0-9]-[01]?[0-9]-[0-3]?[0-9]|[0-3]?[0-9][/-][01]?[0-9][/-]20[0-9][0-9])"
    cue="(applications? (close|closes|closing)|closing (date|on)|application deadline|deadline for applications|apply (by|before|on or before)|applications? (must be |should be |are to be )?(received|submitted)|no later than|on or before|close of business)"
    for (i=1;i<=st_nobs();i++) {
        text=strlower(st_sdata(i,"description")); rest=text
        dates=J(0,1,.); mentioned=0; review=0; evidence=""
        while (regexm(rest,cue)) {
            lead=regexs(0); pos=strpos(rest,lead); mentioned=1
            tail=substr(rest,pos+strlen(lead),120)
            if (evidence=="") evidence=vacancy_clip(substr(rest,pos,.),240)
            while (regexm(tail,datepat)) {
                token=regexs(0)
                pos=strpos(tail,token)
                parsed=vacancy_date(token)
                if (missing(parsed[1])) review=1
                else {
                    dates=dates\parsed[1]
                    review=max((review,parsed[2]))
                }
                tail=substr(tail,pos+strlen(token),.)
            }
            pos=strpos(rest,lead)
            rest=substr(rest,pos+strlen(lead),.)
        }
        if (rows(dates)) dates=uniqrows(sort(dates,1))
        count=rows(dates); found=.
        if (count==1 & !review) found=dates[1]
        if (mentioned & (count!=1 | review)) review=1
        st_store(i,"closing_day",found)
        st_store(i,"closing_mentioned",mentioned)
        st_store(i,"closing_review",review)
        st_store(i,"closing_candidates",count)
        st_sstore(i,"closing_evidence",evidence)
    }
}
// Small checks on substantive date ambiguities, not a second implementation.
assert((vacancy_date("30 october 2026"))[1]==date("30oct2026","DMY"))
assert((vacancy_date("30th october 2026"))[1]==date("30oct2026","DMY"))
assert((vacancy_date("october 30, 2026"))[1]==date("30oct2026","DMY"))
assert((vacancy_date("2026-10-30"))[1]==date("30oct2026","DMY"))
assert((vacancy_date("10/11/2026"))[2]==1)
assert((vacancy_date("30/10/2026"))[2]==0)
vacancy_closing()
end
tempfile descriptions base checks summary curves
save `descriptions'

import delimited using "`out'/input_all_jobs.csv", clear varnames(1) stringcols(_all) bindquote(strict)
local csv_rows = _N
count if status == "failed"
local failed_rows = r(N)
count if status != "success" & status != "failed"
local unknown_status = r(N)
keep if status == "success"
* CSV was imported as strings to protect IDs; these two fields are counts.
destring description_length retry_count, replace
assert _N == `json_total'
isid job_id
merge 1:1 job_id using `descriptions', assert(match) nogen
local n = _N
foreach v in first last {
    gen double `v'_day = date(substr(`v'_seen,1,10), "YMD")
}
gen double posted_day = date(date_posted, "DMY")
format first_day last_day posted_day closing_day %tdCCYY-NN-DD
gen byte invalid_dates = missing(first_day,last_day) | last_day < first_day
gen byte posted_after_seen = posted_day > first_day & !missing(posted_day,first_day)
quietly summarize last_day, meanonly
local cutoff = r(max)
quietly summarize first_day, meanonly
local startup = r(min)
gen byte initial_stock = first_day == `startup'
gen byte live_at_cutoff = last_day == `cutoff' if !missing(last_day)
gen byte incident = first_day >= `cohort' & !invalid_dates & !initial_stock
gen int observed_span_days = last_day-first_day if !invalid_dates
gen int followup_days = observed_span_days+1 if incident
gen byte approximate_exit = last_day < `cutoff' if incident
gen byte crosses_gap = first_day <= date("19sep2026","DMY") & last_day >= date("01sep2026","DMY") if !invalid_dates
gen byte gap_affected = crosses_gap | last_day == date("31aug2026","DMY") | (first_day == date("20sep2026","DMY") & posted_day <= date("19sep2026","DMY")) if !invalid_dates
gen byte closing_before_posted = closing_day < posted_day if !missing(closing_day,posted_day)
gen int application_window_days = closing_day-posted_day if !missing(closing_day,posted_day) & !closing_before_posted
gen str244 employer_clean = lower(itrim(trim(employer)))
replace employer_clean = "[employer not stated]" if employer_clean == ""
label var observed_span_days "Last minus first observed calendar day; lower bound on visibility"
label var followup_days "Inclusive observed days; last seen used as approximate exit"
label var closing_day "Unambiguous full-year closing date near explicit cue; description only"
label var crosses_gap "Observed spell overlaps collection interruption 1-19 Sep 2026"
label var gap_affected "Crosses gap, last seen pre-gap, or caught up at restart"
label var repeat_description "Identical stored description in multiple IDs; not proven duplicates"
display "Snapshot cutoff from data: " %td `cutoff'
display "Startup stock first observed: " %td `startup'
display "Time/ID/date checks retain all successful rows; no candidate reposts removed."
display "No full-HTML closing dates. No inference for yearless or ambiguous dates."
save "`out'/analysis_base.dta"
save `base'
codebook_export
replace quality_note = "Broken raw salary extractor: punctuation and incidental numbers. Neither nonmissing nor non-placeholder means usable salary; recover pay from source evidence separately." if varname == "salary"
replace quality_note = "Punctuation-only contact placeholders flagged. Remaining numbers/text are not verified contact details." if inlist(varname,"employer_phone","employer_address")
replace quality_note = "Failure metadata: expected to be empty after retaining successful adverts only." if inlist(varname,"error","failure_type","retry_count","failed_at","last_attempted")
replace quality_note = "Missing record-level source reference does not mean no HTML exists in the separate archive/index." if inlist(varname,"source_archive_file","source_archive_run_id","source_archive_sha256")
replace quality_note = "Underlying Stata day count; varformat identifies its date display format. Source dates can be edited or stale." if inlist(varname,"first_day","last_day","posted_day","closing_day")
replace quality_note = "Derived only for the incident cohort; missing values outside that cohort are intentional." if inlist(varname,"followup_days","approximate_exit")
replace quality_note = "Rule-extracted description closing dates, not manually verified. Blank includes absent, ambiguous, or unparsed dates; HTML-only dates excluded." if varname == "closing_day"
export excel using "`out'/codebook.xlsx", firstrow(variables)
export delimited using "`out'/codebook.csv"
use `base', clear

tempname ck
postfile `ck' str70 check double value using `checks'
post `ck' ("csv_rows_including_failures") (`csv_rows')
post `ck' ("failed_rows_excluded") (`failed_rows')
post `ck' ("unknown_status_rows_excluded") (`unknown_status')
post `ck' ("successful_unique_advert_ids") (`n')
post `ck' ("snapshot_cutoff_stata_day") (`cutoff')
post `ck' ("cohort_start_stata_day") (`cohort')
foreach flag in invalid_dates posted_after_seen initial_stock incident live_at_cutoff crosses_gap gap_affected repeat_description closing_mentioned closing_review closing_before_posted {
    quietly count if `flag' == 1
    post `ck' ("`flag'") (r(N))
}
foreach field in posted_day first_day last_day {
    quietly count if missing(`field')
    post `ck' ("unparsed_`field'") (r(N))
}
quietly count if !missing(closing_day)
post `ck' ("closing_date_extracted") (r(N))
postclose `ck'
preserve
use `checks', clear
list, noobs abbreviate(32)
export delimited using "`out'/checks.csv"
restore
preserve
keep job_id title employer date_posted first_day last_day closing_day closing_mentioned closing_review closing_candidates closing_before_posted application_window_days closing_evidence
export delimited using "`out'/closing_dates.csv"
restore

* 2. TIME AND EMPLOYERS.
preserve
gen int month = mofd(first_day)
gen byte one = 1
collapse (sum) first_seen_adverts=one, by(month)
tempfile monthly
save `monthly'
use `base', clear
gen int month = mofd(posted_day)
gen byte one = 1
collapse (sum) advertised_date_adverts=one, by(month)
merge 1:1 month using `monthly', nogen
drop if missing(month)
tsset month
tsfill
foreach v in first_seen_adverts advertised_date_adverts {
    replace `v' = 0 if missing(`v')
}
replace first_seen_adverts = . if month < mofd(`startup')
format month %tmCCYY-NN
gen byte initial_stock_month = month == mofd(`startup')
gen byte partial_latest_month = month == mofd(`cutoff') & `cutoff' < dofm(month+1)-1
gen byte september_gap = month == ym(2026,9)
export delimited using "`out'/monthly_adverts.csv"
local monthstart = mofd(`startup')
local monthend = mofd(`cutoff')
quietly summarize first_seen_adverts, meanonly
local ytop = ceil(r(max)/100)*100
twoway (bar first_seen_adverts month if month >= `monthstart', color("0 72 136") barwidth(.7) base(0)), ///
    xlabel(`monthstart'(1)`monthend', angle(45) labsize(small)) ///
    yscale(range(0)) ylabel(0(100)`ytop', angle(horizontal)) ///
    ytitle("Distinct advert IDs") xtitle("") title("Adverts first recorded by month", span) ///
    note("Startup stock in Oct 2025; latest month may be partial." "No collection 1-19 Sep 2026; counts include later catch-up.", span size(vsmall)) ///
    graphregion(color(white) margin(l+3 r+3 t+4 b+2)) name(monthly, replace)
vacancy_export using "`out'/monthly_adverts"
restore

preserve
gen byte one = 1
collapse (sum) adverts=one, by(employer_clean)
gsort -adverts employer_clean
gen int rank = _n
gen double share = adverts/`n'
gen double cumulative_share = sum(share)
format share cumulative_share %6.4f
export delimited using "`out'/employer_counts.csv"
quietly summarize share if rank <= 10, meanonly
display "Top 10 employer-name groups account for " %5.1f (100*r(sum)) "% of adverts."
replace employer_clean = "[all other employers]" if rank > 15
collapse (sum) adverts, by(employer_clean)
gen double share_percent = 100*adverts/`n'
export delimited using "`out'/employer_chart.csv"
gsort -adverts employer_clean
gen int chart_order = _n
replace chart_order = _N+1 if employer_clean == "[all other employers]"
gen str60 employer_label = ""
mata: for (i=1;i<=st_nobs();i++) st_sstore(i,"employer_label",vacancy_clip(st_sdata(i,"employer_clean"),40)+(strlen(st_sdata(i,"employer_clean"))>40 ? "..." : ""))
graph hbar (asis) adverts, over(employer_label, sort(chart_order) label(labsize(small))) ///
    bar(1, color("0 72 136")) ytitle("Distinct advert IDs") title("Employers by advert count", span size(medium)) ///
    note("Top 15 name groups plus remainder; case/spacing normalized only." "Recruiters may advertise for several employers.", span size(vsmall)) ///
    graphregion(color(white) margin(l+4 r+3 t+3 b+2)) xsize(10) ysize(8) name(employers, replace)
vacancy_export using "`out'/employer_counts"
restore

* 3. DURATION. Approximate exits use last seen; a cross-sectional CSV does not
* contain the first successful observation of disappearance. A one-day inclusive
* scale retains same-day adverts in Stata's survival risk set (no zero-time loss).
* Restrict mean to 30 inclusive days and show gap-excluded sensitivity separately.
tempname su
postfile `su' str35 scenario long adverts exits censored application_windows double mean_observed_span median_observed_span km_median_inclusive rmst30_inclusive mean_application_window median_application_window using `summary'
local horizon = 30
forvalues scenario = 1/2 {
    use `base', clear
    keep if incident
    if `scenario' == 2 keep if !gap_affected
    local label "incident_all"
    if `scenario' == 2 local label "incident_excluding_gap"
    local ns = _N
    quietly count if approximate_exit == 1
    local ne = r(N)
    local nc = `ns'-`ne'
    quietly summarize observed_span_days, detail
    local rawmean = r(mean)
    local rawmedian = r(p50)
    quietly summarize application_window_days, detail
    local napp = r(N)
    local appmean = r(mean)
    local appmedian = r(p50)
    stset followup_days, failure(approximate_exit == 1)
    assert _st == 1
    sts generate survival = s
    quietly summarize followup_days if survival <= .5, meanonly
    local median = r(min)
    if `scenario' == 1 {
        local median_marker ""
        local duration_ticks "0(15)90"
        if !missing(`median') & `median' <= 90 {
            * Dotted guides identify the 50% threshold and its median day.
            local median_marker `"addplot(scatteri .5 0 .5 `median', recast(line) lpattern(dot) lcolor("196 18 48") lwidth(medthin) || scatteri 0 `median' .5 `median', recast(line) lpattern(dot) lcolor("196 18 48") lwidth(medthin) || scatteri .5 `median' (2) "Median: `median' days", msymbol(O) msize(medium) mcolor("196 18 48") mlabcolor("196 18 48") mlabsize(small))"'
            * Label the exact median without a neighbouring tick crowding it.
            local duration_ticks "`median'"
            forvalues tick = 0(15)90 {
                if abs(`tick'-`median') > 3 local duration_ticks "`duration_ticks' `tick'"
            }
        }
        local cohort_label : display %tdDD_Mon_CCYY `cohort'
        local cutoff_label : display %tdDD_Mon_CCYY `cutoff'
        local sample_label = trim(string(`ns', "%9.0fc"))
        local censored_label = trim(string(`nc', "%9.0fc"))
        sts graph, survival tmax(90) xlabel(`duration_ticks') title("How long do job adverts stay online?", span) ///
            `median_marker' legend(off) ///
            xtitle("Days since first seen") ytitle("Estimated share still online") ///
            note("`sample_label' adverts first seen `cohort_label' to `cutoff_label'; excludes adverts present at collection start." ///
                "Last seen approximates removal; `censored_label' still listed on `cutoff_label' are censored (followed only to that date)." ///
                "Days include the first and last day seen. First 90 days shown; collection paused 1-19 Sep 2026.", span size(vsmall)) ///
            plotregion(margin(zero)) graphregion(color(white) margin(l+3 r+3 t+4 b+2)) name(duration, replace)
        vacancy_export using "`out'/duration"
    }
    keep followup_days survival
    collapse (min) survival, by(followup_days)
    sort followup_days
    quietly summarize followup_days, meanonly
    local maxtime = r(max)
    local rmst = .
    gen double previous_time = cond(_n==1,0,followup_days[_n-1])
    gen double previous_survival = cond(_n==1,1,survival[_n-1])
    gen double area = previous_survival*(min(followup_days,`horizon')-min(previous_time,`horizon'))
    quietly summarize area, meanonly
    local area = r(sum)
    local lastsurv = survival[_N]
    if `maxtime' >= `horizon' | `lastsurv' == 0 local rmst = `area'
    post `su' ("`label'") (`ns') (`ne') (`nc') (`napp') (`rawmean') (`rawmedian') (`median') (`rmst') (`appmean') (`appmedian')
    keep followup_days survival
    local next = _N+1
    set obs `next'
    replace followup_days = 0 in `next'
    replace survival = 1 in `next'
    gen str35 scenario = "`label'"
    if `scenario' == 2 append using `curves'
    sort scenario followup_days
    save `curves', replace
}
postclose `su'
use `curves', clear
export delimited using "`out'/duration_curve.csv"
use `summary', clear
gen int restriction_inclusive_days = `horizon'
gen str10 snapshot_cutoff = string(`cutoff',"%tdCCYY-NN-DD")
gen str10 cohort_start = string(`cohort',"%tdCCYY-NN-DD")
list, noobs abbreviate(25)
export delimited using "`out'/duration_summary.csv"

file open notes using "`out'/README.txt", write text
file write notes "COMPLETED: single-file Stata vacancy summary" _n
file write notes "Run: `run_label'; Stata " (c(stata_version)) "; snapshot updated `json_updated'." _n
file write notes "Cutoff: " %tdCCYY-NN-DD (`cutoff') "; incident cohort starts " %tdCCYY-NN-DD (`cohort') "." _n
file write notes "Frozen CSV/JSON and the executed do-file are included. Original files unchanged." _n
file write notes "codebook.xlsx/CSV summarize all analysis-base variables; helper source is frozen here too." _n
file write notes "Missing means Stata missing, not invalid placeholders or unusable values (e.g. salary commas)." _n
file write notes "Codebook also reports whitespace/punctuation placeholders and their combined missing percentage." _n
file write notes "quality_note explains broken salary extraction, expected structural missingness and archive-reference limits." _n
file write notes "Adverts are not a verified count of positions. Repeated descriptions remain in counts." _n
file write notes "Time counts use first discovery; startup stock, September gap and partial months flagged." _n
file write notes "Employer grouping normalizes case/spacing only; full ranking and chart data are CSVs." _n
file write notes "Observed span is last minus first seen. Survival uses inclusive days (span+1)." _n
file write notes "Last seen is an approximate exit, not a verified removal/closing/fill date." _n
file write notes "Right-censor live adverts; sensitivity excludes gap overlaps, last seen 31 Aug, and catch-up stock at 20 Sep." _n
file write notes "KM median and 30-day restricted mean use inclusive days; observed means are NOT vacancy lifetimes." _n
file write notes "Closing dates: description cues + full years only; numeric ambiguities/multiple dates go to review." _n
file write notes "closing_review=0 with closing_mentioned=0 means no cue found, not proof no date exists." _n
file write notes "Extracted closing dates are rule candidates, not manually verified; evidence retained for review." _n
file write notes "Application window = closing minus latest stored posted date; negative windows flagged/excluded." _n
file write notes "JSON reader expects current scraper formatting; matched-ID/count assertions protect schema drift." _n
file write notes "No AI/API calls, survey comparisons, source repairs or changes to older results." _n
file write notes "PNG-only charts use native Stata export, or temporary EPS plus local Ghostscript." _n
file close notes
display "ANALYSIS_COMPLETED_SUCCESSFULLY: `out'"
log close
