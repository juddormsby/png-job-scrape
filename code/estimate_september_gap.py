#!/usr/bin/env python3
"""Estimate the September 2026 outage loss from immutable local Git history.

Reads committed scraper snapshots only. Writes derived evidence under docs/.
No network requests, scraper execution, production data edits, or LLM calls.
"""

from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import random
import statistics
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "audits" / "2026-10-15" / "september-gap"
BEFORE = "4eb95fea89d36cf0840bec9dadc8cb31d925c191"
RESTART = "48d76911f5e1a4e4d0f265a8060e50a33aeefae0"
AS_OF = "6020b3f4e245e8f485f3f9e1b191050a4a1acc28"
DAY = dt.timedelta(days=1)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def snapshot(ref: str) -> dict:
    return json.loads(git("show", f"{ref}:json_output/all_jobs.json"))


def dates(start: str | dt.date, end: str | dt.date):
    start = dt.date.fromisoformat(start) if isinstance(start, str) else start
    end = dt.date.fromisoformat(end) if isinstance(end, str) else end
    while start <= end:
        yield start
        start += DAY


def quantile(values, probability):
    values = sorted(values)
    x = (len(values) - 1) * probability
    low = int(x)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (x - low)


def describe(values):
    return {
        "n": len(values), "mean": statistics.mean(values),
        "median": statistics.median(values), "min": min(values),
        "p10": quantile(values, .1), "p90": quantile(values, .9),
        "max": max(values),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before, restart, current = map(snapshot, (BEFORE, RESTART, AS_OF))
    pre_ids = {int(j["job_id"]) for j in before["jobs"]}
    resume_ids = {int(j["job_id"]) for j in restart["jobs"]}
    current_ids = {int(j["job_id"]) for j in current["jobs"]}
    lower, upper = max(pre_ids), max(resume_ids)
    slots = set(range(lower + 1, upper + 1))
    captured_resume = slots & resume_ids
    captured_eventually = slots & current_ids
    failed_ids = {int(j["job_id"]) for j in current["failed_jobs"]}
    missing_ids = slots - current_ids
    elapsed = (dt.datetime.fromisoformat(restart["last_updated"]) - dt.datetime.fromisoformat(before["last_updated"])).total_seconds() / 86400
    exposure = 20
    later_rows = [j for j in current["jobs"] if int(j["job_id"]) in captured_eventually-captured_resume]
    # One later success is dated 10 September; the other is dated 9 October
    # and is not established as a published outage-cohort advert.
    later_confirmed_gap = [j for j in later_rows if j.get("date_posted", "")[3:] == "09/2026" and "01" <= j["date_posted"][:2] <= "19"]
    arrival_recoveries = len(captured_resume) + len(later_confirmed_gap)

    # Commit list is fixed at AS_OF, excluding later local documentation changes.
    log = git("log", "--reverse", "--format=%H\t%cI", "--since=2026-05-01T00:00:00Z", AS_OF, "--", "json_output/all_jobs.json").decode()
    refs = {}
    for line in log.splitlines():
        ref, timestamp = line.split("\t")
        refs[timestamp[:10]] = ref
    wanted = [d.isoformat() for d in dates("2026-05-01", "2026-08-31")] + [d.isoformat() for d in dates("2026-09-20", "2026-10-15")]
    cache_path = OUT / "daily-observations.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    daily = {}
    for n, date in enumerate(wanted, 1):
        ref = refs[date]
        if date in cache and cache[date]["commit"] == ref:
            daily[date] = cache[date]
            continue
        data = snapshot(ref)
        assert data["last_updated"][:10] == date, (date, data["last_updated"])
        jobs = data["jobs"]
        daily[date] = {
            "commit": ref, "scraped_at": data["last_updated"],
            "total_jobs": len(jobs), "max_id": max(int(j["job_id"]) for j in jobs),
            "observed_ids": sorted(int(j["job_id"]) for j in jobs if j.get("last_seen", "")[:10] == date),
            "new_ids": sorted(int(j["job_id"]) for j in jobs if j.get("first_seen", "")[:10] == date),
        }
        if n % 20 == 0:
            print(f"Read {n}/{len(wanted)} daily snapshots", flush=True)
    cache_path.write_text(json.dumps(daily, indent=2) + "\n")

    # Rate baseline: include zero-arrival dates; exclude the catch-up day itself.
    rate_periods = [("July", "2026-07-01", "2026-07-31"), ("August", "2026-08-01", "2026-08-31"), ("post_restart", "2026-09-21", "2026-10-14"), ("nearby_pooled", "2026-07-01", "2026-08-31")]
    rates = {}
    for label, start, end in rate_periods:
        counts = [len(daily[d.isoformat()]["new_ids"]) for d in dates(start, end)]
        rates[label] = {
            "start": start, "end": end, "days": len(counts), "captured_new_ids": sum(counts),
            "daily_rate": statistics.mean(counts),
            "expected_over_20_days": statistics.mean(counts) * exposure,
            "lost_after_140_confirmed_recoveries": max(0, statistics.mean(counts) * exposure - arrival_recoveries),
        }
    pooled_counts = [len(daily[d.isoformat()]["new_ids"]) for d in dates("2026-07-01", "2026-08-31")] + [len(daily[d.isoformat()]["new_ids"]) for d in dates("2026-09-21", "2026-10-14")]
    rng = random.Random(20261015)
    boot = []
    # Weekday-stratified resampling: preserves the weekday mix of the actual interval.
    baseline_days = list(dates("2026-07-01", "2026-08-31")) + list(dates("2026-09-21", "2026-10-14"))
    by_weekday = collections.defaultdict(list)
    for date in baseline_days:
        by_weekday[date.weekday()].append(len(daily[date.isoformat()]["new_ids"]))
    for _ in range(4000):
        n = sum(rng.choice(by_weekday[d.weekday()]) for d in dates("2026-09-01", "2026-09-20"))
        boot.append(max(0, n - arrival_recoveries))
    rates["pooled_all"] = {
        "days": len(pooled_counts), "captured_new_ids": sum(pooled_counts),
        "daily_rate": statistics.mean(pooled_counts),
        "expected_over_20_days": statistics.mean(pooled_counts) * exposure,
        "lost_after_140_confirmed_recoveries": statistics.mean(pooled_counts) * exposure - arrival_recoveries,
        "weekday_resampled_lost_p10_p90": [quantile(boot, .1), quantile(boot, .9)],
        "resampling_note": "Descriptive independent-day sensitivity, not a formal uncertainty interval; it omits seasonality and serial correlation.",
    }
    nearby_counts = [len(daily[d.isoformat()]["new_ids"]) for d in dates("2026-08-01", "2026-08-31")] + [len(daily[d.isoformat()]["new_ids"]) for d in dates("2026-09-21", "2026-10-14")]
    rates["august_and_post_restart"] = {"days":len(nearby_counts),"captured_new_ids":sum(nearby_counts),"daily_rate":statistics.mean(nearby_counts),"expected_over_20_days":statistics.mean(nearby_counts)*exposure,"lost_after_140_confirmed_recoveries":statistics.mean(nearby_counts)*exposure-arrival_recoveries}

    # ID coverage calibration: count eventual captures inside contiguous ID spans
    # generated during unaffected periods. Allocation slots are not all adverts.
    id_controls = []
    for end in dates("2026-07-01", "2026-08-31"):
        start = end - exposure * DAY
        if start.isoformat() not in daily:
            continue
        lo = daily[start.isoformat()]["max_id"]
        hi = daily[end.isoformat()]["max_id"]
        if hi <= lo:
            continue
        seen = sum(lo < job_id <= hi for job_id in current_ids)
        coverage = seen / (hi - lo)
        id_controls.append({
            "before": start.isoformat(), "restart": end.isoformat(),
            "lower_exclusive": lo, "upper_inclusive": hi,
            "slots": hi-lo, "captured": seen, "coverage": coverage,
            "estimated_loss_for_actual_span": max(0, coverage*len(slots)-len(captured_eventually)),
        })
    for end in dates("2026-10-10", "2026-10-15"):
        start = end - exposure * DAY
        if start.isoformat() not in daily:
            continue
        lo, hi = daily[start.isoformat()]["max_id"], daily[end.isoformat()]["max_id"]
        coverage = sum(lo < i <= hi for i in current_ids) / (hi-lo)
        id_controls.append({"before": start.isoformat(),"restart":end.isoformat(),"lower_exclusive":lo,"upper_inclusive":hi,"slots":hi-lo,"captured":sum(lo<i<=hi for i in current_ids),"coverage":coverage,"estimated_loss_for_actual_span":max(0,coverage*len(slots)-len(captured_eventually))})
    # Match the actual 25-day follow-up. Controls ending after 6 August would
    # cross the real outage, so they are not used for this primary calibration.
    first_seen_dates = {int(j["job_id"]): j["first_seen"][:10] for j in current["jobs"]}
    matched_controls=[]
    for row in id_controls:
        end=dt.date.fromisoformat(row["restart"])
        followup=end+25*DAY
        if end>dt.date(2026,8,6):
            continue
        seen=sum(row["lower_exclusive"]<i<=row["upper_inclusive"] and first_seen_dates[i]<=followup.isoformat() for i in current_ids)
        coverage=seen/row["slots"]
        matched_controls.append(dict(row,followup_end=followup.isoformat(),captured=seen,coverage=coverage,estimated_loss_for_actual_span=max(0,coverage*len(slots)-len(captured_eventually))))

    # Historical outage experiments: remove 19 daily runs and resume on day 20.
    # Ground truth is the set first captured in the hidden interval. Allow 25 days
    # after restart for recapture, matching the actual audit follow-up duration.
    pseudo = []
    for pre in dates("2026-05-01", "2026-07-17"):
        resume = pre + exposure * DAY
        followup = resume + 25 * DAY
        cohort = set().union(*(set(daily[d.isoformat()]["new_ids"]) for d in dates(pre+DAY, resume)))
        at_resume = set(daily[resume.isoformat()]["observed_ids"])
        after_resume = set().union(*(set(daily[d.isoformat()]["observed_ids"]) for d in dates(resume, followup)))
        recovered, lost = len(cohort & after_resume), len(cohort-after_resume)
        frac = lost/len(cohort)
        pseudo.append({
            "last_scrape": pre.isoformat(), "restart": resume.isoformat(), "followup_end": followup.isoformat(),
            "arrivals":len(cohort), "recovered_on_restart":len(cohort & at_resume),
            "recovered_by_followup":recovered, "lost":lost, "lost_fraction":frac,
            "actual_loss_from_recovered_140": arrival_recoveries*lost/recovered if recovered else None,
            "same_restart_weekday":resume.weekday()==dt.date(2026,9,20).weekday(),
        })
    lifetime_jobs = [j for j in before["jobs"] if "2026-05-01" <= j.get("first_seen", "")[:10] <= "2026-08-10"]
    spans = [(dt.date.fromisoformat(j["last_seen"][:10])-dt.date.fromisoformat(j["first_seen"][:10])).days+1 for j in lifetime_jobs]
    # This span approximation can bridge absences/reposts; actual daily-ID masking
    # above is the preferred empirical duration method.
    span_loss_fraction = statistics.mean(sum(length < age for age in range(1,21))/20 for length in spans)

    def pooled_pseudo(rows):
        n = sum(r["arrivals"] for r in rows)
        lost = sum(r["lost"] for r in rows)
        fraction = lost/n
        return {"windows":len(rows),"weighted_loss_fraction":fraction,"loss_from_actual_recoveries":arrival_recoveries*fraction/(1-fraction),"loss_estimates":describe([r["actual_loss_from_recovered_140"] for r in rows]),"arrival_counts":describe([r["arrivals"] for r in rows])}

    # Measured archive size, with deterministic gzip compression, excludes assets.
    sizes=[];compressed=[]
    legacy_files = git("ls-tree", "-r", "--name-only", AS_OF, "--", "html_output").decode().splitlines()
    legacy_files = [p for p in legacy_files if p.endswith('.html')]
    for p in legacy_files:
        raw=git("show", f"{AS_OF}:{p}");sizes.append(len(raw));compressed.append(len(gzip.compress(raw,mtime=0)))
    lifetime_unique_pages = len(current_ids)
    mean_raw,mean_gz=statistics.mean(sizes),statistics.mean(compressed)
    archive={"sample_pages":len(sizes),"mean_html_bytes":mean_raw,"mean_gzip_bytes":mean_gz,"all_3707_pages_raw_mib":lifetime_unique_pages*mean_raw/2**20,"all_3707_pages_gzip_mib":lifetime_unique_pages*mean_gz/2**20,"daily_206_pages_raw_mib":206*mean_raw/2**20,"daily_206_pages_gzip_mib":206*mean_gz/2**20,"annual_daily_206_pages_raw_gib":365*206*mean_raw/2**30,"annual_daily_206_pages_gzip_gib":365*206*mean_gz/2**30,"note":"189 older local pages; illustrative sizing, not measured current storage. Full daily raw pages include changing application tokens, so exact-byte hashes alone may not deduplicate them."}
    recovered_rows=[j for j in current["jobs"] if int(j["job_id"]) in captured_eventually]
    dated_september=[j for j in [j for j in restart["jobs"] if int(j["job_id"]) in captured_resume] + later_confirmed_gap if j.get("date_posted","")[3:]=="09/2026" and "01"<=j["date_posted"][:2]<="19"]
    id_bins=[]
    for lo in range(lower+1,upper+1,40):
        hi=min(lo+39,upper);ids=set(range(lo,hi+1))
        id_bins.append({"from":lo,"to":hi,"slots":len(ids),"captured":len(ids&current_ids),"not_captured":len(ids-current_ids)})
    recent_observed=set().union(*(set(v["observed_ids"]) for day,v in daily.items() if day>="2026-09-20"))
    legacy_ids={int(Path(p).stem.split("_")[1]) for p in legacy_files}
    archive.update({"recent_observed_ids_potentially_in_retained_artifacts":len(recent_observed),"recent_plus_legacy_source_ids":len(recent_observed|legacy_ids),"artifact_caveat":"Potential recoverable source coverage inferred from successful runs and workflow upload paths; artifacts not downloaded or individually verified."})

    result={
        "as_of_commit":AS_OF,"estimand":"Distinct advert IDs never obtaining a successful full record because of the outage, relative to ordinary daily capture; not positions, not missed daily observations.",
        "boundaries":{"before_commit":BEFORE,"restart_commit":RESTART,"before_time":before["last_updated"],"restart_time":restart["last_updated"],"elapsed_days":elapsed,"missed_scheduled_runs":19,"daily_model_exposure_days":exposure},
        "id_evidence":{"lower_exclusive":lower,"upper_inclusive":upper,"allocation_slots":len(slots),"successful_at_restart":len(captured_resume),"successful_by_audit":len(captured_eventually),"confirmed_arrival_cohort_recoveries":arrival_recoveries,"successful_with_recorded_publication_1_to_19_september":len(dated_september),"later_successes":[{"job_id":j["job_id"],"first_seen":j["first_seen"],"date_posted":j["date_posted"]} for j in current["jobs"] if int(j["job_id"]) in captured_eventually-captured_resume],"not_successfully_captured_ids":sorted(missing_ids),"unseen_slots":len(missing_ids),"known_failed_metadata_ids":sorted(missing_ids & failed_ids),"upper_bound_caveat":"Conditional allocation-span ceiling, not an unconditional bound on all published adverts. Slots can be drafts/deletions and older IDs can be republished.","id_bins":id_bins,"control_coverage":describe([r["coverage"] for r in id_controls]),"control_loss_estimates":describe([r["estimated_loss_for_actual_span"] for r in id_controls]),"controls":id_controls,"matched_25_day_followup":{"windows":len(matched_controls),"coverage":describe([r["coverage"] for r in matched_controls]),"loss_estimates":describe([r["estimated_loss_for_actual_span"] for r in matched_controls]),"pooled_coverage":sum(r['captured'] for r in matched_controls)/sum(r['slots'] for r in matched_controls),"controls":matched_controls}},
        "publishing_rate":rates,
        "historical_outage_experiments":{"all":pooled_pseudo(pseudo),"same_weekday":pooled_pseudo([r for r in pseudo if r["same_restart_weekday"]]),"windows":pseudo,"caveat":"Windows overlap; descriptive sensitivity ranges are not independent-sample confidence intervals. Windows end before the real billing interruption. Captures on the restart day are included in both actual and simulated cohorts."},
        "observed_span_approximation":{"cohort_start":"2026-05-01","cohort_end":"2026-08-10","jobs":len(spans),"inclusive_visible_span_days":describe(spans),"uniform_arrival_loss_fraction":span_loss_fraction,"loss_from_140_recovered":arrival_recoveries*span_loss_fraction/(1-span_loss_fraction),"caveat":"First-to-last span can bridge interrupted listings; use historical daily masking as primary duration evidence."},
        "archive_size_estimates":archive,
        "working_estimate":{"lost_adverts":75,"sensitivity_low":40,"sensitivity_high":90,"basis":"Rounded central planning estimate from nearby publishing rates (about 80), matched ID-span calibration (about 78), and weekday-matched historical outage experiments (about 64). Methods are dependent; this is not a statistical meta-analysis or confidence interval.","estimated_recovered_fraction":arrival_recoveries/(arrival_recoveries+75),"estimated_missing_fraction_of_adjusted_full_database":75/(len(current_ids)+75)},
    }
    (OUT/"estimates.json").write_text(json.dumps(result,indent=2)+"\n")
    (OUT/"missing-id-candidates.json").write_text(json.dumps({"note":"Unobserved allocation slots; not a confirmed list of lost published adverts.","ids":sorted(missing_ids)},indent=2)+"\n")
    print(json.dumps({"id_evidence":{k:v for k,v in result["id_evidence"].items() if k not in ("controls","not_successfully_captured_ids")},"rate_baselines":rates,"outage_experiments":{k:v for k,v in result["historical_outage_experiments"].items() if k!="windows"},"span_approximation":result["observed_span_approximation"],"archive_sizes":archive},indent=2),flush=True)


if __name__ == "__main__":
    main()
