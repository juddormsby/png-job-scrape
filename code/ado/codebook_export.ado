*! Project helper: one unweighted summary row per variable; Stata 13.1+.
program define codebook_export
    version 13.1
    syntax

    tempfile results
    tempname handle
    tempvar screened
    preserve
    quietly postfile `handle' str32 varname str80 varlabel str7 vartype ///
        str8 storage str49 varformat ///
        double unique double missing double nonmissing double pct_missing ///
        double placeholder double pct_missing_or_placeholder ///
        double mean double min double max double sd ///
        using "`results'"

    foreach v of varlist _all {
        local label : variable label `v'
        local storage : type `v'
        local fmt : format `v'
        quietly count if missing(`v')
        local n_missing = r(N)
        local n_nonmissing = _N - `n_missing'
        local pct : display %24.17g cond(_N, 100*`n_missing'/_N, .)
        local n_placeholder = 0
        local n_unique = 0
        local avg = .
        local minimum = .
        local maximum = .
        local stdev = .

        capture confirm numeric variable `v'
        if !_rc {
            local kind "numeric"
            if `n_nonmissing' {
                quietly summarize `v'
                local avg : display %24.17g r(mean)
                local minimum : display %24.17g r(min)
                local maximum : display %24.17g r(max)
                local stdev : display %24.17g r(sd)
                mata: st_local("n_unique", strofreal(rows(uniqrows(sort(select(st_data(.,"`v'"),st_data(.,"`v'"):<.),1)))))
            }
        }
        else {
            local kind "string"
            * Flag nonempty whitespace/punctuation, without changing source data.
            quietly gen strL `screened' = subinstr(subinstr(subinstr(`v', char(9), " ", .), char(10), " ", .), char(13), " ", .)
            quietly replace `screened' = trim(subinstr(`screened', char(194)+char(160), " ", .))
            quietly count if !missing(`v') & (`screened' == "" | regexm(`screened', "^[ .,;:/_?*!#|+()=-]+$"))
            local n_placeholder = r(N)
            drop `screened'
            if `n_nonmissing' {
                mata: st_local("n_unique", strofreal(rows(uniqrows(sort(select(st_sdata(.,"`v'"),st_sdata(.,"`v'"):!=""),1)))))
            }
        }
        local pct_extended : display %24.17g cond(_N, 100*(`n_missing'+`n_placeholder')/_N, .)
        post `handle' ("`v'") (`"`label'"') ("`kind'") ///
            ("`storage'") ("`fmt'") ///
            (`n_unique') (`n_missing') (`n_nonmissing') (`pct') ///
            (`n_placeholder') (`pct_extended') ///
            (`avg') (`minimum') (`maximum') (`stdev')
    }
    postclose `handle'
    quietly use "`results'", clear
    restore, not
    gen str244 quality_note = ""
    format pct_missing pct_missing_or_placeholder %6.2f
    label variable pct_missing "Literal Stata missing (%)"
    label variable placeholder "Nonempty whitespace/punctuation-only strings"
    label variable pct_missing_or_placeholder "Literal missing or whitespace/punctuation placeholder (%)"
    list varname vartype unique missing placeholder pct_missing_or_placeholder, noobs abbreviate(24)
end
