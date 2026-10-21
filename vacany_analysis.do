* AI refresh analysis. Existing output folders are never overwritten.
* From repository root:
* do vacany_analysis.do "/path/to/project" "analysis/2026-10-21_ai"
* Optional third argument: full path to the 2022 SDES person file.
* Fourth argument "charts" adds core PNG charts to an existing analysis folder.
* Fifth argument overrides the matching basic-analysis folder.
version 13.1
clear all
set more off
set linesize 120
args project run_dir sdes_file action basic_dir
if `"`project'"' == "" local project `"`c(pwd)'"'
cd `"`project'"'
local project `"`c(pwd)'"'
if `"`run_dir'"' == "" local run_dir "analysis/2026-10-21_ai"
if inlist(`"`sdes_file'"', "", ".") local sdes_file "../micro-data-work/RAW/Socio Demog Economic Survey 2022/Microdata/SPC_PNG_2022_SDES_Person_v01_PUF.dta"
if `"`basic_dir'"' == "" local basic_dir "`run_dir'/basic"
if !inlist(`"`action'"', "", "charts") error 198
if substr(`"`run_dir'"',1,1) != "/" local run_dir `"`project'/`run_dir'"'
if substr(`"`sdes_file'"',1,1) != "/" local sdes_file `"`project'/`sdes_file'"'
if substr(`"`basic_dir'"',1,1) != "/" local basic_dir `"`project'/`basic_dir'"'
if `"`action'"' != "charts" confirm file `"`sdes_file'"'
confirm file "`run_dir'/LLM_processed_jobs.csv"
import delimited "`run_dir'/LLM_processed_jobs.csv", clear varnames(1) stringcols(_all) bindquote(strict)
isid job_id
assert job_id != ""
count if status != "success"
if r(N) {
    display as error "Pending/failed AI rows remain. Resume classification and reconvert before analysing the full sample."
    exit 459
}
local processed_n = _N
local non_jobs = 0
capture confirm variable is_job_advert
if !_rc {
    assert inlist(is_job_advert,"0","1")
    count if is_job_advert == "0"
    local non_jobs = r(N)
    if `"`action'"' != "charts" {
        preserve
            keep if is_job_advert == "0"
            keep job_id title employer classification_summary
            export delimited using "`run_dir'/non_job_adverts.csv"
        restore
    }
    keep if is_job_advert == "1"
}
local total_n = _N
global OUT "`run_dir'/analysis"
if `"`action'"' == "charts" {
    confirm file "${OUT}/classified_adverts.dta"
    log using "${OUT}/charts.log", text
    copy "vacany_analysis.do" "${OUT}/charts.do"
}
else {
    capture mkdir "${OUT}"
    if _rc {
        display as error "Analysis folder exists or cannot be created; refusing to overwrite. Use a new run label."
        exit 693
    }
    log using "${OUT}/analysis.log", text
    copy "vacany_analysis.do" "${OUT}/vacany_analysis.do"
}
display "Stata: " c(stata_version) "; processed records: `processed_n'; non-jobs excluded: `non_jobs'; retained job adverts: `total_n'"
display `"Output folder: ${OUT}"'
display `"Survey input: `sdes_file'"'
display "Confidence scores are model self-assessments. Online advert flows and survey employment stocks are different populations."

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

* Shared plotting helpers keep all summary charts in one do-file.
program define vacancy_plot
    syntax varname(numeric), OVER(varname) NAME(string) TITLE(string) NOTE(string) ///
        [SUBNOTE(string) SORT MAX(real 0) STEP(real 0) FORMAT(string) DENOM(string)]
    if "`format'" == "" local format "%4.1f"
    if "`denom'" == "" local denom "Percent of all adverts"
    if `max' <= 0 {
        quietly summarize `varlist'
        local max = max(10,ceil(r(max)/10)*10)
    }
    if `step' <= 0 local step = cond(`max'<=50,10,20)
    local ordering ""
    if "`sort'" != "" local ordering "sort(1) descending"
    local upper = `max'*1.12
    graph hbar (asis) `varlist', over(`over', `ordering' label(labsize(small))) ///
        bar(1, color("0 72 136")) ///
        blabel(bar, format(`format') position(outside) size(small) color(black)) ///
        ylabel(0(`step')`max', labsize(small)) yscale(range(0 `upper')) ///
        ytitle("`denom'", size(small)) title("`title'", size(medium)) ///
        note("`note'" "`subnote'", size(vsmall)) legend(off) ///
        graphregion(color(white)) plotregion(color(white)) xsize(12) ysize(6.5)
    vacancy_export using "${OUT}/`name'"
end

program define vacancy_distribution
    syntax varname, NAME(string) TITLE(string) NOTE(string) ///
        [SUBNOTE(string) FORMAT(string) DENOM(string)]
    local n = _N
    contract `varlist', freq(adverts)
    gen double percent = 100*adverts/`n'
    vacancy_plot percent, over(`varlist') name("`name'") title("`title'") ///
        note("`note'") subnote("`subnote'") format("`format'") denom("`denom'")
end

program define vacancy_core_charts
    syntax, BASIC(string)
    set scheme s2color
    local n = _N
    tempfile adverts source_fields required_years preferred_years availability routes skills
    capture confirm variable education_level
    local has_requirements = !_rc
    if `has_requirements' {
        foreach v in experience_required_years experience_preferred_years graduate_opportunity apprenticeship_opportunity entry_level_opportunity skill_digital skill_technical_trade skill_communication skill_teamwork skill_leadership skill_organisation {
            capture confirm numeric variable `v'
            if _rc destring `v', replace
        }
    }
    save `adverts'

    if `has_requirements' {
        gen byte education_group = .
        local row = 0
        foreach value in no_qualification_required secondary vocational diploma bachelor postgraduate other not_stated {
            replace education_group = `row' if education_level == "`value'"
            local ++row
        }
        assert !missing(education_group)
        label define education_groups 0 "No qualification required" 1 "Secondary / high school" ///
            2 "Vocational / trade certificate" 3 "Diploma" 4 "Bachelor's degree" ///
            5 "Postgraduate" 6 "Other qualification" 7 "Level not stated"
        label values education_group education_groups
        vacancy_distribution education_group, name("education_level") ///
            title("Education level stated in adverts") ///
            note("All `n' job adverts. Highest compulsory level; lowest acceptable route where credentials are alternatives.") ///
            subnote("These are advertised credentials, not applicants' educational attainment.")

        use `adverts', clear
        gen byte education_status = .
        replace education_status = 0 if education_requirement == "required"
        replace education_status = 1 if education_requirement == "preferred"
        replace education_status = 2 if education_requirement == "alternative_accepted"
        replace education_status = 3 if education_requirement == "not_stated"
        replace education_status = 4 if education_level == "no_qualification_required"
        assert !missing(education_status)
        label define education_statuses 0 "Qualification required" 1 "Qualification preferred" ///
            2 "Alternative route accepted" 3 "No education requirement stated" 4 "No qualification required"
        label values education_status education_statuses
        vacancy_distribution education_status, name("education_requirement") ///
            title("How education requirements are stated") note("All `n' adverts. Unspecified requirements are not treated as waived.") ///
            subnote("Alternative route: experience or another non-credential route can substitute for the qualification.")

        * Compare required/preferred years only among adverts stating years.
        foreach kind in required preferred {
            use `adverts', clear
            keep if !missing(experience_`kind'_years)
            local n_`kind' = _N
            gen byte years_group = 0 if experience_`kind'_years == 0
            replace years_group = 1 if experience_`kind'_years > 0 & experience_`kind'_years < 1
            replace years_group = 2 if inrange(experience_`kind'_years,1,2)
            replace years_group = 3 if experience_`kind'_years > 2 & experience_`kind'_years <= 5
            replace years_group = 4 if experience_`kind'_years > 5 & experience_`kind'_years <= 10
            replace years_group = 5 if experience_`kind'_years > 10
            assert !missing(years_group)
            label define experience_groups 0 "Explicitly zero years" 1 "Less than 1 year" 2 "1-2 years" ///
                3 "More than 2, up to 5 years" 4 "More than 5, up to 10 years" 5 "More than 10 years", replace
            label values years_group experience_groups
            contract years_group, freq(adverts)
            gen double `kind' = 100*adverts/`n_`kind''
            keep years_group `kind'
            save ``kind'_years'
        }
        use `required_years', clear
        merge 1:1 years_group using `preferred_years', nogen
        replace required = 0 if missing(required)
        replace preferred = 0 if missing(preferred)
        graph hbar (asis) required preferred, over(years_group, label(labsize(small))) ///
            bar(1, color("0 72 136")) bar(2, color("141 198 63")) ///
            blabel(bar, format(%4.1f) position(outside) size(small)) ///
            ylabel(0(20)100, labsize(small)) yscale(range(0 110)) ///
            ytitle("Percent of adverts stating years", size(small)) title("Minimum experience years stated") ///
            legend(order(1 "Required" 2 "Preferred") rows(1) pos(6) size(small)) ///
            note("Bases differ: required years stated in `n_required' adverts; preferred years in `n_preferred'." ///
                "Unstated years are excluded here, not treated as zero. See the field-coverage chart.", size(vsmall)) ///
            graphregion(color(white)) plotregion(color(white)) xsize(12) ysize(6.5)
        vacancy_export using "${OUT}/experience_years"

        use `adverts', clear
        tempname route_post
        postfile `route_post' str50 category double percent using `routes'
        foreach v in graduate_opportunity entry_level_opportunity apprenticeship_opportunity {
            assert inlist(`v',0,1)
            local caption "Graduate opportunity"
            if "`v'" == "entry_level_opportunity" local caption "Entry-level opportunity"
            if "`v'" == "apprenticeship_opportunity" local caption "Apprenticeship opportunity"
            quietly summarize `v'
            post `route_post' ("`caption'") (100*r(mean))
        }
        postclose `route_post'
        use `routes', clear
        vacancy_plot percent, over(category) name("entry_routes") title("Explicit entry-route opportunities") ///
            note("All `n' adverts; categories can overlap.") ///
            subnote("No explicit mention does not mean graduates or young people are ineligible.") sort max(2) step(.5)

        use `adverts', clear
        tempname skill_post
        postfile `skill_post' str50 category double percent using `skills'
        foreach v in digital technical_trade communication teamwork leadership organisation {
            assert inlist(skill_`v',0,1)
            local caption = proper("`v'")
            if "`v'" == "technical_trade" local caption "Technical / trade"
            quietly summarize skill_`v'
            post `skill_post' ("`caption'") (100*r(mean))
        }
        postclose `skill_post'
        use `skills', clear
        vacancy_plot percent, over(category) name("skills") title("Skills explicitly mentioned in adverts") ///
            note("All `n' adverts; an advert can mention several categories, so shares do not add to 100%.") ///
            subnote("Broad mention categories, not proficiency or a detailed skills taxonomy.") sort

        use `adverts', clear
        tempname availability_post
        postfile `availability_post' str50 category double percent using `availability'
        quietly count if regexm(substr(trim(isic_1digit),1,1),"^[A-U]$")
        post `availability_post' ("Industry assigned") (100*r(N)/`n')
        quietly count if regexm(substr(trim(isco_1digit),1,1),"^[0-9]$")
        post `availability_post' ("Occupation assigned") (100*r(N)/`n')
        quietly count if education_level != "not_stated"
        post `availability_post' ("Education level or explicit waiver stated") (100*r(N)/`n')
        quietly count if education_requirement != "not_stated"
        post `availability_post' ("Education requirement status stated") (100*r(N)/`n')
        quietly count if !missing(experience_required_years)
        post `availability_post' ("Required experience years stated") (100*r(N)/`n')
        quietly count if !missing(experience_preferred_years)
        post `availability_post' ("Preferred experience years stated") (100*r(N)/`n')
        postclose `availability_post'
        use `availability', clear
        vacancy_plot percent, over(category) name("field_coverage") title("Coverage of the core extracted fields") ///
            note("All `n' adverts completed AI processing. These percentages describe information assigned or stated.") ///
            subnote("Missing information is kept separate from explicit zero or no qualification required.") sort
    }

    ******************************
    * Advertised work locations
    use `adverts', clear
    capture confirm variable region_southern
    if !_rc {
        foreach region in southern highlands momase islands {
            capture confirm numeric variable region_`region'
            if _rc destring region_`region', replace
        }
        destring work_nationwide work_remote, replace
        preserve
            keep job_id title work_provinces work_regions work_outside_png work_nationwide work_remote work_location_evidence
            export delimited using "${OUT}/vacancy_locations.csv"
        restore

        tempfile region_counts location_coverage
        tempname rp lp
        postfile `rp' str30 category long adverts double percent using `region_counts'
        foreach region in southern highlands momase islands {
            quietly count if region_`region' == 1
            local count = r(N)
            local caption = proper("`region'")
            post `rp' ("`caption'") (`count') (100*`count'/`n')
        }
        postclose `rp'
        preserve
            use `region_counts', clear
            export delimited using "${OUT}/region_counts.csv"
            vacancy_plot percent, over(category) name("work_regions") title("Where are the jobs based?") ///
                note("All `n' job adverts; multiple work regions allowed, counted once per region.") ///
                subnote("Nationwide, overseas and unknown locations are not assigned to every PNG region.") sort
        restore

        postfile `lp' str45 category long adverts double percent using `location_coverage'
        gen byte named_region = work_regions != ""
        gen byte overseas_work = work_outside_png != ""
        gen byte location_unknown = !named_region & !overseas_work & !work_nationwide & !work_remote
        foreach field in named_region work_nationwide overseas_work work_remote location_unknown {
            local caption "Named PNG work region"
            if "`field'" == "work_nationwide" local caption "PNG-wide work"
            if "`field'" == "overseas_work" local caption "Overseas work location"
            if "`field'" == "work_remote" local caption "Remote / home-based work"
            if "`field'" == "location_unknown" local caption "No resolved work location"
            quietly count if `field'
            local count = r(N)
            post `lp' ("`caption'") (`count') (100*`count'/`n')
        }
        postclose `lp'
        use `location_coverage', clear
        export delimited using "${OUT}/location_coverage.csv"
        vacancy_plot percent, over(category) name("location_coverage") title("What work-location information is available?") ///
            note("All `n' job adverts; categories can overlap.") ///
            subnote("Work sites only: excludes FIFO departure points, contact addresses and employer history.")
    }

    * Use the matching frozen basic analysis for source fields and existing PNGs.
    use `adverts', clear
    merge 1:1 job_id using "`basic'/analysis_base.dta", ///
        keepusing(employment_type closing_day closing_mentioned closing_review application_window_days)
    assert _merge == 3
    assert _N == `n'
    drop _merge
    save `source_fields'
    replace employment_type = "Not stated" if trim(employment_type) == ""
    vacancy_distribution employment_type, name("employment_type") title("Employment type as recorded by the website") ///
        note("All `n' adverts. Labels mix contract duration (Permanent/Contract) and hours (Full-Time/Part-Time).") ///
        subnote("Categories are retained as supplied; a blank is not inferred to mean full-time or permanent.") format("%4.2f")

    use `source_fields', clear
    gen byte closing_group = 0 if !missing(closing_day)
    replace closing_group = 1 if missing(closing_day) & (closing_mentioned | closing_review)
    replace closing_group = 2 if missing(closing_group)
    label define closing_groups 0 "Closing-date candidate extracted" 1 "Closing cue, date unresolved" 2 "No closing cue identified"
    label values closing_group closing_groups
    vacancy_distribution closing_group, name("closing_date_coverage") title("Closing-date information in descriptions") ///
        note("All `n' adverts. Rules use explicit closing cues and full years; candidates are not manually verified.") ///
        subnote("No detected cue is not proof that no closing date exists elsewhere in the source.")

    use `source_fields', clear
    keep if !missing(application_window_days)
    assert application_window_days >= 0
    local window_n = _N
    gen byte window_group = 0 if application_window_days == 0
    replace window_group = 1 if inrange(application_window_days,1,7)
    replace window_group = 2 if inrange(application_window_days,8,14)
    replace window_group = 3 if inrange(application_window_days,15,30)
    replace window_group = 4 if application_window_days > 30
    assert !missing(window_group)
    label define window_groups 0 "Same day" 1 "1-7 days" 2 "8-14 days" 3 "15-30 days" 4 "More than 30 days"
    label values window_group window_groups
    vacancy_distribution window_group, name("application_window") title("Time from recorded posting to closing date") ///
        note("Base: `window_n' adverts with a non-negative, rule-extracted window; missing/negative windows excluded.") ///
        subnote("Uses the latest stored posted date, which can have been edited; not time to fill a vacancy.") ///
        denom("Percent of adverts with an extracted window")

    foreach name in monthly_adverts employer_counts duration {
        confirm new file "${OUT}/`name'.png"
        copy "`basic'/`name'.png" "${OUT}/`name'.png"
    }
    use `adverts', clear
end

if `"`action'"' == "charts" {
    use "${OUT}/classified_adverts.dta", clear
    vacancy_core_charts, basic(`"`basic_dir'"')
    display "CORE_PNG_CHARTS_COMPLETED_SUCCESSFULLY"
    log close
    exit
}

* Simple tables for the new fields. Flags indicate explicit mentions, not age or eligibility.
tempfile coverage
tempname coverage_post
capture confirm variable education_level
if !_rc {
foreach v in experience_required_years experience_preferred_years graduate_opportunity apprenticeship_opportunity entry_level_opportunity skill_digital skill_technical_trade skill_communication skill_teamwork skill_leadership skill_organisation {
    destring `v', replace
}
save "${OUT}/classified_adverts.dta"
preserve
contract education_level education_requirement, freq(adverts)
gen double share = adverts/`total_n'
export delimited using "${OUT}/education_counts.csv"
restore
tempfile requirements_table
tempname requirements_post
postfile `requirements_post' str32 field str24 measure long available double mean double minimum double maximum using `requirements_table'
foreach v in experience_required_years experience_preferred_years graduate_opportunity apprenticeship_opportunity entry_level_opportunity skill_digital skill_technical_trade skill_communication skill_teamwork skill_leadership skill_organisation {
    local measure "explicit mention share"
    if strpos("`v'","experience_")==1 local measure "minimum years stated"
    quietly summarize `v'
    post `requirements_post' ("`v'") ("`measure'") (r(N)) (r(mean)) (r(min)) (r(max))
}
postclose `requirements_post'
preserve
use `requirements_table', clear
export delimited using "${OUT}/requirements_summary.csv"
restore
}
else {
    * The original 2025 prompt did not request education/experience/skill fields.
    save "${OUT}/classified_adverts.dta"
    display "Classification-only input: no new requirement fields were requested."
}

vacancy_core_charts, basic(`"`basic_dir'"')

* Reproduce original ISIC/ISCO comparison, retaining unclassified coverage separately.
postfile `coverage_post' str4 classification long total long classified long unclassified double classified_share using `coverage'
foreach v in isic isco {
    preserve
    gen str1 `v'_1d = substr(trim(`v'_1digit),1,1)
    local pattern "^[A-U]$"
    if "`v'" == "isco" local pattern "^[0-9]$"
    replace `v'_1d = "" if !regexm(`v'_1d,"`pattern'")
    quietly count if `v'_1d != ""
    local classified_here = r(N)
    local classified_`v' = `classified_here'
    post `coverage_post' ("`v'") (`total_n') (`classified_here') (`total_n'-`classified_here') (`classified_here'/`total_n')
    if `classified_here'==0 {
        display as error "No classified adverts for `v'; inspect the AI outputs."
        exit 2000
    }
    drop if `v'_1d == ""
    gen byte one = 1
    collapse (sum) n=one, by(`v'_1d)
    gen double vacancy_share = n/`classified_`v''
    gen double vacancy_share_all = n/`total_n'
    rename `v'_1d `v'
    tempfile vacancies_`v'
    save `vacancies_`v''
    restore
}
postclose `coverage_post'
preserve
use `coverage', clear
export delimited using "${OUT}/classification_coverage.csv"
restore

* repeat for SDES. 
use `"`sdes_file'"', clear

** think the unclassified are not workign
gen employed = inlist(1,c19_paidwork, c20_salingactivity, c21_businessactivity, c22_voluntaryhelp, c23_absentfrompaidjob)
tab c25 employed , mis
tab c24 employed , mis // yes it's basically about not working - so it's fine.

foreach v in c25_act_code1 c24_occ_code1 {

    preserve
		* drop not elsewhere classified
		if "`v'" == "c25_act_code1"  drop if `v' == 22 | missing(`v')
		if "`v'" == "c24_occ_code1"  drop if `v' == 11 | missing(`v')
		
		* tabluate svset data.
		svyset [pweight = genwgt]
		svy : tab `v'
		
		* collapse to weighted totals by category
		collapse (sum) wgt=genwgt, by(`v')
		egen total_wgt = total(wgt)
		gen sdes_share = wgt / total_wgt
		
		keep `v' sdes_share
		* turn value label into string
		decode `v', gen(`v'_label)
		gen `v'_1d = substr(`v'_label, 1, 1)
		if "`v'" == "c24_occ_code1" {
			gen `v'_1d_num = real(`v'_1d) // this can be numeric rather than "1" etc.
			drop `v'_1d
			
		}
		
		if "`v'" == "c25_act_code1" rename `v'_1d isic
		if "`v'" == "c24_occ_code1" rename `v'_1d_num isco

		list
		
		tempfile sdes_`v'
		save `sdes_`v''
    restore
}
***************
***** isic charts
use `vacancies_isic' , clear
merge 1:1 isic using `sdes_c25_act_code1'
replace vacancy_share = 0 if vacancy_share == . & _merge == 2
replace vacancy_share_all = 0 if _merge == 2
replace n = 0 if _merge == 2

replace c25_act_code1_label = isic+" - ISIC category absent from survey" if c25_act_code1_label == ""

* create ordering variable
gsort - vacancy_share
gen ord = _n

*** shorten some labels.
replace c25_act_code1_label = "T - Activities of households as employers" if isic == "T"
replace c25_act_code1_label = "G - Wholesale and retail trade; repair of vehicles" if isic == "G"
replace c25_act_code1_label = "E - Water supply, sewerage, waste management" if isic == "E"
replace c25_act_code1_label = "O - Public administration, defence, and social security" if isic == "O"
replace c25_act_code1_label = "U - Activities of extraterritorial organizations" if isic == "U"


replace c25_act_code1_label = substr(c25_act_code1_label,5,.)


forvalues row = 1/`=_N' {
    local text = c25_act_code1_label[`row']
    label define industry_plot `row' `"`text'"', add
}
label values ord industry_plot

twoway ///
 (bar vacancy_share ord, horizontal barwidth(0.8) ///
     fcolor("0 72 136") lcolor(none)) ///
 (scatter ord sdes_share, ///
     msymbol(Oh) msize(small) mcolor("141 198 63")) ///
, yscale(reverse) ///
  ylabel(1(1)`=_N', valuelabel angle(horizontal) labsize(vsmall) noticks) ///
  xscale(range(0 .5)) ///
  xlabel(0(.1).5, format(%4.2f)) ///
  xtitle("Share") ///
  ytitle("") ///
  legend(order(1 "Vacancy share" 2 "Survey employment share") ///
         rows(1) pos(6) ring(1) size(vsmall) ///
         region(lstyle(none))) ///
  xsize(13) ysize(10) ///
  plotregion(margin(l+1 r+3 t+2 b+2)) ///
  title("Industry") ///
  graphregion(color(white) margin(l+1 r+1 t+1 b+1)) ///
  note("Classified adverts: `classified_isic' / `total_n'. Shares conditional on classification.", span size(vsmall)) name(ind , replace)
 
 
 *export chart
 graph display ind
 vacancy_export using "${OUT}/vacancy_v_sdes_industry"
 
 * prep data for export

 rename c25_act_code1 labels_full
 rename ord label_short
 order isic labels_full label_short sdes_share , first
 drop _merge c25_act_code1_label
 
 *export data
 export delimited using "${OUT}/vacancy_v_sdes_industry.csv"
 export excel using "${OUT}/vacancy_v_sdes.xlsx", sheet("industry") firstrow(variables)
 

 ***** isco
 
use `vacancies_isco' , clear
gen isco_num = real(isco)
drop isco
rename isco_num isco

merge 1:1 isco using `sdes_c24_occ_code1'
* Keep categories absent from SDES and report them instead of failing silently.
replace c24_occ_code1_label = string(isco)+" - ISCO category absent from survey" if c24_occ_code1_label == ""
replace vacancy_share = 0 if vacancy_share == . & _merge == 2
replace vacancy_share_all = 0 if _merge == 2
replace n = 0 if _merge == 2

* create ordering variable
gsort - vacancy_share
gen ord = _n

replace c24_occ_code1_label = substr(c24_occ_code1_label,5,.)

forvalues row = 1/`=_N' {
    local text = c24_occ_code1_label[`row']
    label define occupation_plot `row' `"`text'"', add
}
label values ord occupation_plot

twoway ///
 (bar vacancy_share ord, horizontal barwidth(0.8) ///
     fcolor("0 72 136") lcolor(none)) ///
 (scatter ord sdes_share, ///
     msymbol(Oh) msize(small) mcolor("141 198 63")) ///
, yscale(reverse) ///
  ylabel(1(1)`=_N', valuelabel angle(horizontal) labsize(vsmall) noticks) ///
  xscale(range(0 .5)) ///
  xlabel(0(.1).5, format(%4.2f)) ///
  xtitle("Share") ///
  ytitle("") ///
  legend(order(1 "Vacancy share" 2 "Survey employment share") ///
         rows(1) pos(6) ring(1) size(vsmall) ///
         region(lstyle(none))) ///
  xsize(13) ysize(10) ///
  plotregion(margin(l+1 r+3 t+2 b+2)) ///
  title("Occupation") ///
  graphregion(color(white) margin(l+1 r+1 t+1 b+1)) ///
  note("Classified adverts: `classified_isco' / `total_n'. Shares conditional on classification.", span size(vsmall)) name(occ , replace)
  
*export chart
graph display occ
 vacancy_export using "${OUT}/vacancy_v_sdes_occupation"
 
* prep data for export

rename c24_occ_code1 labels_full
rename ord label_short
order isco labels_full label_short sdes_share , first
drop _merge c24_occ_code1_label
 
*export data
export delimited using "${OUT}/vacancy_v_sdes_occupation.csv"
export excel using "${OUT}/vacancy_v_sdes.xlsx", sheet("occupation") firstrow(variables) sheetreplace

graph combine ind occ , cols(1) xsize(13) ysize(20) iscale(.45) ///
    graphregion(color(white)) ///
    title("Vacancy adverts and survey employment") ///
    name(comb, replace)
	
graph display comb
 vacancy_export using "${OUT}/vacancy_v_sdes_combined"

display "AI_REFRESH_ANALYSIS_COMPLETED_SUCCESSFULLY"
log close
* Historical seven-run robustness code is preserved in the legacy archive.
