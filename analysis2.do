*** check how consistent over rune

	
forvalues i = 0/6 {
	import delimited "/Users/juddormsby/Library/CloudStorage/Dropbox/ADB/pngworkforce-scrape/json_output/LLM_processed_jobs`i'.csv", clear
	
	capture confirm string variable job_id
	if !_rc {
		destring job_id, replace force
		drop if job_id == .
	}

	rename * *`i'
	rename job_id`i' job_id
	
	gen isco_simp`i' = real(substr(isco_1digit`i',1,1))
	gen isic_simp`i' = substr(isic_1digit`i',1,1)
	
	tempfile temp`i'
	save "`temp`i''"

}


clear
use "`temp0'"
forvalues i = 1/6 {
	merge 1:1 job_id using "`temp`i''"
	assert _merge == 3 |`i' == 6
	keep if _merge == 3 // the new jobs let's just ignore for now
	rename _merge merge`i'

}

drop merge*

keep job_id isic_simp? isic_1digit_confidence0 isco_1digit_confidence0 isco_simp?
order isic* , after(job_id)


egen isco_min = rowmin(isco_simp3-isco_simp6)
egen isco_max = rowmax(isco_simp3-isco_simp6)
gen isco_constant = isco_min == isco_max

tab isco_constant // so sort of 79-85% are always classified the same (depending on whehter using same prompt or not)..

*** okay I'm calling it let's just use the last run unless there is an obvious reason not to.

** sidequest
* flag the obs that don't replicate
* see how many values they each hvae 
* show that the general pattern is like similar across runs? (probably it is especially if errors are random).
* I guess i really do want unique values per ob ... (annoying) probably easiest is to sum the binary indicators using row sum :D).

levelsof isco_simp0 , local(isco_simp_lvls)
foreach val of local isco_simp_lvls {
	di "`val'"
	cap drop ind_`val'
	egen ind_`val' = anycount(isco_simp?), values(`val')
}
tab1 ind?*

egen max_ind = rowmax(ind_*)
tab1 max_ind

** main quest:

* Show the number of jobs posted each day in late Nov - Dec.
	* Merge on additional data. 
	* 
* Choose the most common classification and go with that. But then that would ideally have like 100 runs. Grr well just never mind.

gen one = 1
forvalues i = 0/6 {
	foreach var in isco isic {
		preserve
			collapse (count) one , by(isco_simp`i')
			rename isco_simp isco_code
			rename one N_`i'
			tempfile isco_`var'`i'
			save "`isco_`var'`i''"
		restore
	}
}

preserve
use "`isco_isco0'" , clear
forvalues i = 1/6 {
	merge 1:1 isco_code using "`isco_isco`i''"
	drop _merge
}

restore

**** Okay let's grab key figures that we need and then we can say "results are robust" which the above analysis showed.
** let's just analyze this from the last run.

import delimited "/Users/juddormsby/Library/CloudStorage/Dropbox/ADB/pngworkforce-scrape/json_output/LLM_processed_jobs6.csv", clear


** do the shares for isic and isco.

foreach v in isic isco {

    preserve
		* construct clean 1-digit merge key
		gen `v'_1d = substr(`v'_1digit, 1, 1)
		replace `v'_1d = trim(`v'_1d)

		drop if missing(`v'_1d)

		* collapse to counts
		collapse (count) n = job_id, by(`v'_1d)

		* convert to shares
		egen total_n = total(n)
		gen vacancy_share = n / total_n

		keep `v'_1d vacancy_share
		rename `v'_1d `v'
		
		tempfile vacancies_`v'
		save `vacancies_`v''
		
		
    restore
}

* repeat for SDES. 
use "${RAW}/Socio Demog Economic Survey 2022/Microdata/SPC_PNG_2022_SDES_Person_v01_PUF.dta", clear

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
***** isic
use `vacancies_isic' , clear
merge 1:1 isic using `sdes_c25_act_code1'
replace vacancy_share = 0 if vacancy_share == . & _merge == 2

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


labmask ord, values(c25_act_code1_label)

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
  graphregion(color(white) margin(l+1 r+1 t+1 b+1)) name(ind , replace)

 ***** isco
 
use `vacancies_isco' , clear
gen isco_num = real(isco)
drop isco
rename isco_num isco

merge 1:1 isco using `sdes_c24_occ_code1'
assert _merge != 1
replace vacancy_share = 0 if vacancy_share == . & _merge == 2

* create ordering variable
gsort - vacancy_share
gen ord = _n

replace c24_occ_code1_label = substr(c24_occ_code1_label,5,.)

labmask ord, values(c24_occ_code1_label)

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
  graphregion(color(white) margin(l+1 r+1 t+1 b+1)) name(occ , replace)
  
graph combine ind occ , ///
	title("Vacancy data are not representative of survey data") ///
	name(comb, replace) 

