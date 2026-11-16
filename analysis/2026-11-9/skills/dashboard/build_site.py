"""Package only the static dashboard and prepared display data for hosting."""
from pathlib import Path
import json
import shutil

HERE = Path(__file__).resolve().parent
OUT = HERE / "public"
ASSETS = ["index.html", "styles.css", "app.mjs", "stats.mjs"]


def main():
    data = json.loads((HERE / "data/dashboard.json").read_text())
    jobs = data["jobs"]
    assert len(jobs) == data["meta"]["adverts"]
    assert len({job["id"] for job in jobs}) == len(jobs)
    for bucket in {job["detail"] for job in jobs}:
        details = json.loads((HERE / f"data/details/{bucket}.json").read_text())
        assert all(job["id"] in details for job in jobs if job["detail"] == bucket)
    # public/ is generated and contains no manually maintained files.
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for name in ASSETS:
        shutil.copy2(HERE / name, OUT / name)
    (OUT / "data/details").mkdir(parents=True)
    for name in ["dashboard.json", "provinces.json", "provenance.json"]:
        shutil.copy2(HERE / "data" / name, OUT / "data" / name)
    for bucket in {job["detail"] for job in jobs}:
        shutil.copy2(HERE / f"data/details/{bucket}.json", OUT / f"data/details/{bucket}.json")
    print(f"Packaged {len(jobs):,} adverts into {OUT.relative_to(HERE)}; static assets and display data only.")


if __name__ == "__main__":
    main()
