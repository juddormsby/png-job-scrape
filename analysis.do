*** check how consistent over rune

forvalues i = 0/2 {
	import delimited "/Users/juddormsby/Library/CloudStorage/Dropbox/ADB/pngworkforce-scrape/json_output/LLM_processed_jobs`i'.csv", clear
	
	capture confirm string variable job_id
	if !_rc {
		destring job_id, replace
	}

	rename * *`i'
	rename job_id`i' job_id
	
	gen isco_simp`i' = substr(isco_1digit`i',1,1)
	gen isic_simp`i' = substr(isic_1digit`i',1,1)
	
	tempfile temp`i'
	save "`temp`i''"

}


clear
use "`temp0'"
forvalues i = 1/2 {
	merge 1:1 job_id using "`temp`i''"
	assert _merge == 3 
	rename _merge merge`i'

}

drop merge*

keep job_id isic_simp? isco_simp?
order isic* , after(job_id)


egen isic_min = rowmin(isic*)
egen isic_max = rowmax(isic*)
gen isic_constant = isic_min == isic_max

