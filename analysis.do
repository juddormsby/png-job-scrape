*** check how consistent over rune

	
forvalues i = 0/5 {
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
forvalues i = 1/5 {
	merge 1:1 job_id using "`temp`i''"
	assert _merge == 3 
	rename _merge merge`i'

}

drop merge*

keep job_id isic_simp? isic_1digit_confidence0 isco_1digit_confidence0 isco_simp?
order isic* , after(job_id)


egen isco_min = rowmin(isco_si*)
egen isco_max = rowmax(isco_sim*)
gen isco_constant = isco_min == isco_max

tab isco_constant // so like with four model runs the result is the same ... a lot but not always.

*** okay I'm calling it let's just use the last run unless there is an obvious reason not too.

** sidequest
* flag the obs that don't replicate
* see how many values they each hvae 
* show that the general pattern is like similar across runs? (probably it is especially if errors are random).
* I guess i really do want unique values per ob ... (annoying) probably easiest is to sum the binary indicators using row sum :D).

levelsof isco_simp , local(isco_simp_lvls)

foreach val of local isco_simp_lvls {
	di "`val'"
	gen ind_`val' 
}
