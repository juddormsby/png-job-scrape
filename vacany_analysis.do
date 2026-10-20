* Prepared AI refresh analysis. NOT RUN during preparation.
* From repository root:
* do vacany_analysis.do "/path/to/project" "analysis/2026-10-20_ai"
* Optional third argument: full path to the 2022 SDES person file.
version 13.1
clear all
set more off
set linesize 120
args project run_dir sdes_file
if `"`project'"' == "" local project `"`c(pwd)'"'
cd `"`project'"'
if `"`run_dir'"' == "" local run_dir "analysis/2026-10-20_ai"
if `"`sdes_file'"' == "" local sdes_file "../micro-data-work/RAW/Socio Demog Economic Survey 2022/Microdata/SPC_PNG_2022_SDES_Person_v01_PUF.dta"
confirm file `"`sdes_file'"'
confirm file "`run_dir'/LLM_processed_jobs.csv"
import delimited "`run_dir'/LLM_processed_jobs.csv", clear varnames(1) stringcols(_all) bindquote(strict)
isid job_id
assert job_id != ""
count if status != "success"
if r(N) {
    display as error "Pending/failed AI rows remain. Resume classification and reconvert before analysing the full sample."
    exit 459
}
local total_n = _N
global OUT "`run_dir'/analysis"
capture mkdir "${OUT}"
if _rc {
    display as error "Analysis folder exists or cannot be created; refusing to overwrite. Use a new run label."
    exit 693
}
log using "${OUT}/analysis.log", text
copy "vacany_analysis.do" "${OUT}/vacany_analysis.do"
display "Stata: " c(stata_version) "; successful advert IDs: `total_n'"
display "Confidence scores are model self-assessments. Online advert flows and survey employment stocks are different populations."

program define vacancy_export
    syntax using/
    graph save `"`using'.gph"'
    capture graph export `"`using'.png"', width(2400)
    local png_rc = _rc
    capture graph export `"`using'.pdf"'
    local pdf_rc = _rc
    if `png_rc' | `pdf_rc' {
        tempfile eps
        graph export `"`eps'"', as(eps)
        if `png_rc' {
            shell gs -q -dSAFER -dBATCH -dNOPAUSE -dEPSCrop -sDEVICE=png16m -r200 -sOutputFile="`using'.png" "`eps'"
            confirm file `"`using'.png"'
        }
        if `pdf_rc' {
            shell gs -q -dSAFER -dBATCH -dNOPAUSE -dEPSCrop -sDEVICE=pdfwrite -sOutputFile="`using'.pdf" "`eps'"
            confirm file `"`using'.pdf"'
        }
    }
end

* Simple tables for the new fields. Flags indicate explicit mentions, not age or eligibility.
foreach v in experience_required_years experience_preferred_years graduate_opportunity apprenticeship_opportunity entry_level_opportunity skill_digital skill_technical_trade skill_communication skill_teamwork skill_leadership skill_organisation {
    destring `v', replace
}
save "${OUT}/classified_adverts.dta"
preserve
contract education_level education_requirement, freq(adverts)
gen double share = adverts/`total_n'
export delimited using "${OUT}/education_counts.csv"
restore
tempfile requirements_table coverage
tempname requirements_post coverage_post
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

graph combine ind occ , ///
	title("Vacancy data are not representative of survey data") ///
	name(comb, replace) 
	
graph display comb
 vacancy_export using "${OUT}/vacancy_v_sdes_combined"

display "AI_REFRESH_ANALYSIS_COMPLETED_SUCCESSFULLY"
log close
* Historical seven-run robustness code is preserved in the legacy archive.
