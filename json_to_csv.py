"""Flatten a prepared refresh with fixed columns, including errors/pending IDs."""
import argparse
import csv
import json
from pathlib import Path

from classify_jobs import ROOT, SKILLS, digest, validate_result

CLASSIFICATION_COLUMNS = [f"{prefix}_{level}digit{suffix}" for prefix in ("isic", "isco")
                          for suffix in ("", "_confidence") for level in range(1, 5)]
REQUIREMENT_COLUMNS = ["education_level", "education_requirement", "education_quote", "experience_required_years",
                       "experience_preferred_years", "experience_quotes", "graduate_opportunity", "apprenticeship_opportunity",
                       "entry_level_opportunity", "entry_route_quotes"]
COLUMNS = ["job_id", "title", "employer", *CLASSIFICATION_COLUMNS, "classification_summary", *REQUIREMENT_COLUMNS,
           *[f"skill_{s}" for s in SKILLS], *[f"skill_{s}_quote" for s in SKILLS],
           "status", "error", "model", "prompt_version", "input_hash", "processed_at", "response_id", "input_tokens", "output_tokens", "reasoning_tokens"]


def flatten(job, result):
    row = dict.fromkeys(COLUMNS, "")
    row.update(job_id=job["job_id"], title=job["input"]["title"], employer=job["input"]["employer"],
               input_hash=job["input_hash"], status="pending")
    if not result:
        return row
    for key in ("status", "error", "model", "prompt_version", "processed_at", "response_id"):
        row[key] = result.get(key, "")
    if result.get("status") != "success":
        return row
    validate_result({k: result[k] for k in ("industry_classification", "occupation_classification", "classification_summary", "requirements")}, job)
    for section in ("industry_classification", "occupation_classification"):
        row.update(result[section])
    row["classification_summary"] = result["classification_summary"]
    req = result["requirements"]
    for key in REQUIREMENT_COLUMNS:
        value = req[key]
        row[key] = " | ".join(value) if isinstance(value, list) else int(value) if isinstance(value, bool) else value
    skills = {item["category"]: item["quote"] for item in req["skills_mentioned"]}
    for category in SKILLS:
        row[f"skill_{category}"] = int(category in skills)
        row[f"skill_{category}_quote"] = skills.get(category, "")
    usage = result.get("usage") or {}
    for key in ("input_tokens", "output_tokens"):
        row[key] = usage.get(key, "")
    row["reasoning_tokens"] = (usage.get("output_tokens_details") or {}).get("reasoning_tokens", "")
    return row


def convert(run_dir, pilot=False):
    metadata = json.loads((run_dir / "manifest.json").read_text())
    body = (run_dir / "prepared_jobs.json").read_bytes()
    if digest(body) != metadata["prepared_jobs_sha256"]:
        raise ValueError("Frozen prepared input was changed")
    jobs = json.loads(body)
    if pilot:
        ids = set(json.loads((run_dir / "pilot_ids.json").read_text()))
        jobs = [job for job in jobs if job["job_id"] in ids]
    destination = run_dir / "pilot" if pilot else run_dir
    source = destination / "LLM_processed_jobs.json"
    raw = json.loads(source.read_text())  # No invented output when classification has not run.
    records = {str(r["job_id"]): r for r in raw}
    if len(records) != len(raw) or not set(records) <= {j["job_id"] for j in jobs}:
        raise ValueError("Duplicate or unexpected result IDs")
    for job in jobs:
        result = records.get(job["job_id"])
        if result and any(result.get(k) != value for k, value in (("input_hash", job["input_hash"]), ("model", metadata["model"]), ("prompt_version", metadata["prompt_version"]))):
            raise ValueError("Result model/prompt/input differs from prepared run")
    path = destination / "LLM_processed_jobs.csv"
    temp = path.with_suffix(".csv.tmp")
    with temp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(flatten(job, records.get(job["job_id"])) for job in jobs)
    temp.replace(path)
    return path, len(jobs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    path = Path(args.run_dir)
    if not path.is_absolute():
        path = ROOT / path
    output, count = convert(path, args.pilot)
    print(f"Converted {count} selected advert IDs to {output}; pending/error rows retained.")


if __name__ == "__main__":
    main()
