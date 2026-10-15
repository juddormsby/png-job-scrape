#!/usr/bin/env python3
"""Read-only dataset summary and shareable monthly chart; never rewrite scrape data.

Run with the bundled document Python (ReportLab and pypdfium2), or install those
two packages in an analysis environment. Counts use Python's standard library.
"""
import argparse
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def parse_date(value):
    value = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", value.strip(), flags=re.I)
    for pattern in ("%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    return datetime.fromisoformat(value)


def repeated_groups(jobs, fields):
    groups = defaultdict(list)
    for job in jobs:
        groups[tuple(job.get(field, "") for field in fields)].append(job)
    return [items for items in groups.values() if len(items) > 1]


def repeat_summary(groups):
    return {"groups": len(groups), "records": sum(map(len, groups)),
            "records_beyond_one_per_group": sum(len(group)-1 for group in groups)}


def summarize(source):
    body = source.read_bytes()
    data = json.loads(body)
    jobs = data["jobs"]
    n = len(jobs)
    first = Counter(parse_date(job["first_seen"]).strftime("%Y-%m") for job in jobs)
    posted = Counter(parse_date(job["date_posted"]).strftime("%Y-%m") for job in jobs)
    latest_day = parse_date(data["last_updated"]).date()
    seen_latest = [job for job in jobs if parse_date(job["last_seen"]).date() == latest_day]
    referenced = [job for job in jobs if job.get("source_archive_run_id")]
    latest_run = max(referenced, key=lambda job: parse_date(job["scraped_at"]))["source_archive_run_id"]
    seen_in_run = [job for job in jobs if job.get("source_archive_run_id")==latest_run]
    descriptions = [job.get("description") or "" for job in jobs]
    before_controls = []
    for description in descriptions:
        text = description.split("\nEmail job to a friend", 1)[0].strip()
        if text.endswith("\nApply"):
            text = text[:-len("\nApply")].rstrip()
        before_controls.append(len(text))
    exact = repeated_groups(jobs, ("description",))
    strict = repeated_groups(jobs, ("employer", "title", "date_posted", "description"))
    result = {
        "source": "json_output/all_jobs.json", "source_sha256": hashlib.sha256(body).hexdigest(),
        "last_updated": data["last_updated"], "record_count": n,
        "unique_job_ids": len({str(job["job_id"]) for job in jobs}),
        "duplicate_id_rows": n-len({str(job["job_id"]) for job in jobs}),
        "failed_entries_excluded": len(data.get("failed_jobs", [])),
        "seen_on_latest_scrape_date": len(seen_latest),
        "latest_source_archive_run_id": latest_run,
        "seen_in_latest_run": len(seen_in_run),
        "latest_day_count_note": "The date-based count can include an advert seen only in an earlier run that day. The latest-run count uses its source-reference run ID.",
        "collection_first_seen_min": min(job["first_seen"] for job in jobs),
        "collection_first_seen_max": max(job["first_seen"] for job in jobs),
        "monthly_first_recorded": dict(sorted(first.items())),
        "monthly_latest_stored_advertised_date": dict(sorted(posted.items())),
        "descriptions": {
            "nonempty": sum(bool(text.strip()) for text in descriptions),
            "nonempty_percent": 100*sum(bool(text.strip()) for text in descriptions)/n,
            "median_characters": statistics.median(len(text.strip()) for text in descriptions),
            "minimum_characters": min(len(text.strip()) for text in descriptions),
            "at_10000_character_cap": sum(len(text)==10000 for text in descriptions),
            "with_share_form_phrase": sum("Email job to a friend" in text for text in descriptions),
            "median_characters_before_share_controls": statistics.median(before_controls),
            "at_least_1000_characters_before_share_controls": sum(length>=1000 for length in before_controls),
            "note": "Share-control removal is a descriptive length check, not a new cleaned dataset. Completeness is not inferred from length alone.",
        },
        "exact_description_repeats": repeat_summary(exact),
        "exact_employer_description_repeats": repeat_summary(repeated_groups(jobs,("employer","description"))),
        "exact_employer_title_description_repeats": repeat_summary(repeated_groups(jobs,("employer","title","description"))),
        "exact_employer_title_posted_date_description_repeats": repeat_summary(strict),
        "interpretation": {
            "unit": "Distinct advert IDs, not independently verified individual positions or unique recruitment episodes.",
            "monthly_definition": "First successful observation in this dataset. Initial capture is a stock of already-live adverts. Rediscovery of the same ID does not add another first observation.",
            "posted_dates": "Latest saved advertised date, normalized in memory only; this date can change on editing or re-advertising. It is not a reconstructed original publication series.",
            "gap": "No scrape ran 1–19 September 2026. Surviving adverts were recovered after restart; adverts removed before restart can be missing. No missing-advert estimate is added to these counts.",
            "repeated_text": "Different IDs sharing exactly identical stored text. Reposts, multiple positions, rounds and templates can all cause repeats. No records have been deleted or merged.",
        },
    }
    assert n == data["total_jobs"] == sum(first.values()) == sum(posted.values())
    candidates = []
    for group in sorted(exact, key=lambda group: (-len(group), min(str(j["job_id"]) for j in group))):
        candidates.append({"description_sha256": hashlib.sha256(group[0]["description"].encode()).hexdigest(),
                           "description_characters": len(group[0]["description"]),
                           "description_preview": group[0]["description"][:350],
                           "members": [{key: job.get(key) for key in
                                        ("job_id","title","employer","date_posted","first_seen","url")}
                                       for job in group]})
    return result, candidates


def chart(summary, destination):
    from reportlab.graphics.shapes import Drawing, String, Rect, Line
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics import renderPDF, renderSVG
    from reportlab.lib.colors import HexColor, white
    import pypdfium2 as pdfium

    ink, muted = HexColor("#193448"), HexColor("#536575")
    blue, initial, outage, partial = map(HexColor, ("#2C658B", "#9CA9B3", "#C7902B", "#9DBCD1"))
    drawing = Drawing(1040, 700)
    drawing.add(Rect(0, 0, 1040, 700, fillColor=white, strokeColor=None))
    def text(x, y, value, size=12, color=ink, bold=False):
        drawing.add(String(x,y,value,fontName="Helvetica-Bold" if bold else "Helvetica",
                           fontSize=size,fillColor=color))
    text(60, 653, f"{summary['unique_job_ids']:,} job adverts recorded", 28, bold=True)
    text(60, 626, "PNGworkforce | Unique advert IDs first recorded, 31 Oct 2025 to 15 Oct 2026", 13, muted)
    text(60, 603, "Advert counts are not a count of individual positions: one advert can cover several vacancies.", 11, muted)
    for x, value, label in [(60,"0","duplicate advert IDs"),
                            (385,str(summary['seen_in_latest_run']),"seen in the latest scrape"),
                            (720,"100%","have stored descriptions")]:
        text(x, 550, value, 27, bold=True)
        text(x, 529, label, 12, muted)
    text(60, 489, "New advert IDs first recorded each month", 14, bold=True)

    monthly = summary["monthly_first_recorded"]
    months, values = list(monthly), list(monthly.values())
    bars = VerticalBarChart()
    bars.x, bars.y, bars.width, bars.height = 75, 230, 900, 230
    bars.data = [values]
    bars.categoryAxis.categoryNames = [datetime.strptime(month,"%Y-%m").strftime("%b\n%Y") for month in months]
    bars.categoryAxis.labels.fontName = "Helvetica"
    bars.categoryAxis.labels.fontSize = 10
    bars.categoryAxis.labels.fillColor = muted
    bars.categoryAxis.labels.dy = -9
    bars.categoryAxis.visibleTicks = False
    bars.categoryAxis.strokeColor = HexColor("#B7C4CD")
    bars.valueAxis.valueMin, bars.valueAxis.valueMax, bars.valueAxis.valueStep = 0, 450, 100
    bars.valueAxis.labels.fontName = "Helvetica"
    bars.valueAxis.labels.fontSize = 10
    bars.valueAxis.labels.fillColor = muted
    bars.valueAxis.visibleGrid = True
    bars.valueAxis.gridStrokeColor = HexColor("#E3E9ED")
    bars.valueAxis.visibleAxis = False
    bars.valueAxis.visibleTicks = False
    bars.bars[0].fillColor = blue
    bars.bars[0].strokeColor = None
    bars.groupSpacing, bars.barSpacing = 18, 0
    bars.barLabelFormat = "%d"
    bars.barLabels.fontName = "Helvetica-Bold"
    bars.barLabels.fontSize = 11
    bars.barLabels.fillColor = ink
    bars.barLabels.nudge = 7
    for index, month in enumerate(months):
        if month=="2025-10": bars.bars[(0,index)].fillColor = initial
        elif month=="2026-09": bars.bars[(0,index)].fillColor = outage
        elif month=="2026-10": bars.bars[(0,index)].fillColor = partial
    drawing.add(bars)
    for x, color, label in [(60,initial,"Initial capture: 31 Oct 2025"),
                             (390,outage,"September: collection gap"),
                             (720,partial,"October 2026: through 15 Oct")]:
        drawing.add(Rect(x,171,10,10,fillColor=color,strokeColor=None))
        text(x+17,171,label,10,muted)
    text(60, 143, "September: no scraping on 1-19 Sep. Surviving adverts were recovered later; some adverts were missed.", 11, muted)
    text(60, 124, "The initial capture and October 2026 cover partial months. These bars are recorded arrivals, not monthly vacancy demand.", 11, muted)
    drawing.add(Line(60,105,980,105,strokeColor=HexColor("#DDE5EA")))
    text(60, 83, "Descriptions: median 3,673 characters; 72 adverts (1.9%) reach the current 10,000-character limit.", 11)
    text(60, 63, "Repeated text: 433 records (11.7%) share an exact description with another ID; these are not all proven duplicate vacancies.", 11)
    text(60, 32, "Source: all_jobs.json, updated 15 Oct 2026, 13:28 UTC. No gap imputation or deduplication by text has been applied.", 9, muted)
    renderSVG.drawToFile(drawing, str(destination/"monthly_adverts.svg"))
    pdf_bytes = renderPDF.drawToString(drawing)
    document = pdfium.PdfDocument(pdf_bytes)
    page = document[0]
    image = page.render(scale=2).to_pil()
    image.save(destination/"monthly_adverts.png")
    page.close()
    document.close()


def report(summary):
    n = summary["record_count"]
    descriptions = summary["descriptions"]
    lines = ["# PNGworkforce dataset summary — 15 October 2026", "",
             f"The consolidated dataset contains **{n:,} distinct advert IDs**, updated at {summary['last_updated']} UTC. "
             f"{summary['seen_in_latest_run']} IDs were seen in the latest scrape. These are advert records, not a verified count of individual positions; one advert can cover multiple vacancies.", "",
             "![Monthly advert registrations](monthly_adverts.png)", "",
             "## Monthly counts", "",
             "The main chart uses **the month an ID was first recorded by the scraper**. It does not count repeat observations of that ID. "
             "The first column below is therefore the appropriate definition of registrations. "
             "The second is a supplementary grouping by the latest stored advertised date, which may change when an advert is edited or re-advertised. All date normalization is in memory; source files are unchanged.", "",
             "| Month | First recorded by scraper | Latest stored advertised date |", "|---|---:|---:|"]
    first, posted = summary["monthly_first_recorded"], summary["monthly_latest_stored_advertised_date"]
    for month in sorted(set(first)|set(posted)):
        label = datetime.strptime(month,"%Y-%m").strftime("%b %Y")
        if month=="2025-10": label += " (initial capture on 31 Oct)"
        if month=="2026-09": label += " (scrape interruption)"
        if month=="2026-10": label += " (through 15 Oct)"
        lines.append(f"| {label} | {first.get(month, '—')} | {posted.get(month, 0)} |")
    lines += [f"| **Total** | **{n:,}** | **{n:,}** |", "",
              "October 2025 includes a stock of existing adverts captured at startup. October 2026 is partial. "
              "The 1–19 September 2026 interruption caused missing observations and later catch-up. Counts include captured survivors, with no adjustment for unobserved adverts. "
              "See the [September gap estimate](../../docs/SEPTEMBER_2026_GAP_ESTIMATE.md), which estimates about 75 missed IDs, with a 40–90 sensitivity range. "
              "That estimate is not an additional list of observed jobs and is not inserted into this chart.", "",
              "## Duplicates and repeated advertising", "",
              f"- **{summary['duplicate_id_rows']} duplicate ID rows**: all {n:,} records have different job IDs.",
              "- **169 groups of exactly identical stored descriptions**, involving **433 records (11.7%)**. There are 264 records beyond one per identical-description group (7.1% of all records). This does not establish 264 duplicate vacancies.",
              "- A stricter screen requiring the same employer, title, latest advertised date and description finds **49 groups involving 102 records** (53 beyond one per group). These remain candidates for review, not automatic deletions.",
              "- Different IDs may represent reposts, parallel positions or separate recruitment rounds. Identical company templates and known title cuts also complicate matching. Near-duplicates with changed wording are not measured here.",
              "- Repeated detail requests caused by URL aliases do not create repeated IDs in the final database.", "",
              "The reviewable candidates are saved in [exact_description_repeat_groups.json](exact_description_repeat_groups.json). No records were merged or removed.", "",
              "## Description coverage", "",
              f"- **{descriptions['nonempty']:,}/{n:,} records (100%) have nonempty descriptions**. The shortest stored description has {descriptions['minimum_characters']} characters; the median is {int(descriptions['median_characters']):,}.",
              f"- Removing only the known trailing sharing controls for a length check leaves a median of {descriptions['median_characters_before_share_controls']:,.1f} characters; {descriptions['at_least_1000_characters_before_share_controls']:,}/{n:,} ({100*descriptions['at_least_1000_characters_before_share_controls']/n:.1f}%) still have at least 1,000 characters. This is not a full semantic-cleaning or completeness test.",
              f"- **{descriptions['at_10000_character_cap']} records (1.9%)** are exactly at the extractor's 10,000-character limit and are truncation candidates. Some current examples are confirmed truncated.",
              f"- {descriptions['with_share_form_phrase']:,} descriptions (98.1%) contain the site's sharing-form phrase. Most have substantive job text, but the stored text includes interface material. Some short on-site adverts link to fuller external descriptions.",
              "- The full HTML archiver now preserves additional source text for later re-extraction where available. Historical field repair and classifier reruns have not been performed for this summary.", "",
              "## Suggested wording for Silvia", "",
              f'“As of 15 October 2026, we have collected {n:,} distinct PNGworkforce job adverts over almost a year; {summary["seen_in_latest_run"]} were visible in the latest scrape. '
              'All records have descriptions, typically around 3,700 characters. The database has no duplicate advert IDs, though some employers repost adverts, so advert counts should not be interpreted as a count of unique positions. '
              'The monthly chart shows first captures; October is partial and the September collection interruption means some adverts were missed.”', "",
              "## Reproducibility", "",
              f"Source SHA-256: `{summary['source_sha256']}`. Counts exclude {summary['failed_entries_excluded']} historical failure-list entries. "
              "All successful rows, including repeated-text candidates and long descriptions, remain in the denominator. "
              "The exact-description screen compares stored strings verbatim, without stemming, whitespace normalization or model-based matching.", "",
              "Numeric results: [summary.json](summary.json). Reproduction: run `code/summarize_dataset.py` against this source snapshot using Python with ReportLab and pypdfium2. The scraper, production dataset and classifier are not modified.", ""]
    return "\n".join(lines)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=root/"json_output/all_jobs.json")
    parser.add_argument("--output-dir",type=Path,default=root/"reports/2026-10-15")
    args = parser.parse_args()
    summary, candidates = summarize(args.source)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
    (args.output_dir/"exact_description_repeat_groups.json").write_text(json.dumps(candidates,indent=2,ensure_ascii=False)+"\n")
    chart(summary,args.output_dir)
    (args.output_dir/"README.md").write_text(report(summary))
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
