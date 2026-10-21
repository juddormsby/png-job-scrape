# HTML source archive: operation and recovery

Implemented 15 October 2026 as steps 1–2 of the [improvement plan](SCRAPER_IMPROVEMENT_PLAN.md). Historical field backfills, extraction repairs and classification reruns remain separate work.

## Preserved historical evidence

All **26 workflow artifacts retained at the start of preservation, from 20 September through the morning of 15 October**, were downloaded before expiry. Each original ZIP passed its GitHub SHA-256 digest check and every ZIP member passed its CRC check. The ZIPs total **243,397,762 bytes** (232.12 MiB).

- Exact ZIPs, including their original JSON snapshots: `preserved_artifacts/2026-10-15/zips/`, in this Dropbox working folder. These large ZIPs are ignored by Git. Their relative download receipts are in `preserved_artifacts/2026-10-15/receipts.json`. Dropbox cloud synchronization was not independently verified.
- Permanent, Git-tracked artifact inventory: [`archive/preservation/artifacts.json`](../archive/preservation/artifacts.json). It records artifact/run IDs, source commits, expiry times, ZIP digests and member metadata.
- Imported HTML: **678 distinct job IDs**, **1,198 source versions**, and **9,980 artifact HTML observations**. Compressed source payloads occupy **8.79 MiB** before manifests, indexes and Git overhead. Identical or equivalent source evidence is reused, with every artifact observation retained in a manifest.

The old scraper saved BeautifulSoup serialization, rather than original HTTP response bytes. These recovered pages are labelled `legacy_beautifulsoup_serialization`. Artifact times and reported per-job scrape times are retained as provenance; their HTTP status and precise response capture time remain unknown. Importing them does not claim that every old page was fetched again on every artifact's date. There is no attempt to reconstruct already-expired artifacts or unobserved September adverts.

## What future runs retain

The scraper saves response-body bytes **before extraction and before raising an HTTP status error**. Requests has already decoded HTTP transfer/content compression; the saved bytes are its response body, not a packet capture. A first advert version and subsequent changed versions are compressed as immutable `.html.gz` files. Full source bodies include text beyond the extractor's existing 10,000-character description cap.

```text
archive/
  html/YYYY/MM/job_ID/<source-sha256>.html.gz
  html/YYYY/MM/page_URLHASH/<source-sha256>.html.gz
  index/SHARD/<resource>-<category>-<status>.json
  manifests/YYYY/MM/<run-id>.jsonl
  manifests/YYYY/MM/<run-id>.json
  preservation/artifacts.json
```

Each observation records requested/final URLs, job ID, run and code commit, UTC capture time, HTTP status, selected response headers, body size, observed response hash, source file/hash, content fingerprint and provenance. The JSONL also records extraction completion/failure and network errors. Completion means the existing extractor returned, not that every field passed a new quality assessment. Run summaries record completion status and storage/reuse counts.

The content fingerprint is independent of extracted JSON. For the current recognized template it covers the advert container, document head and hiring organization; a conservative whole-body fallback handles unfamiliar templates. Scripts, styles, comments, hidden token values, nonces, Cloudflare email encoding and redirect authorization tokens are normalized away. Title, salary, full description, employer and application-link changes are covered by tests. This policy may retain harmless extra versions if the site changes its markup; future template changes should be reviewed.

When only excluded volatile content changes, a prior source version is reused. **`observed_response_sha256` and `source_sha256` may then differ** and `raw_response_retained` is false: the manifest explicitly records that this observation's exact bytes were not retained. This is a first/changed-evidence archive, not byte-for-byte retention of every daily response.

HTTP errors and unrecognized job pages have separate version pointers. A 404 or a blocked page cannot replace the last valid advert source. A connection failure records an error with no invented response body or HTTP status. Existing live adverts are refreshed even when archived HTML and local JSON files already exist, so edits can be observed.

Newly fetched successful records in both consolidated JSON and CSV carry `source_archive_file`, `source_archive_sha256` and `source_archive_run_id`. The file path is relative to the repository root. Older records gain these references when normally revisited; the artifact importer does not rewrite the historical database.

## GitHub publishing and temporary recovery

The daily 02:00 UTC schedule and manual trigger remain enabled. Changes to archive/scraper code, its tests or the workflow on `main` also trigger an end-to-end run. One concurrency group serializes these runs.

The workflow runs the preservation tests, scrapes, verifies every referenced archived source, prepares a self-contained current-run copy, uploads the usual outputs plus that copy as a 30-day artifact, and commits the durable archive and successful consolidated results to Git. The current-run copy includes reused source files even when they originated in older runs. It avoids repeatedly uploading the whole historical archive.

If scraping raises an error after starting, the workflow still attempts verification, the recovery upload and publication of the verified source archive; it does not publish potentially partial consolidated data. Staging or pushing failures remain visible failures. An abrupt runner loss can still prevent publication; the independent artifact attempt and a local mirror reduce, but do not eliminate, that risk. Actions artifacts expire; the repository archive is the durable source store.

Pulling GitHub updates into this Dropbox checkout mirrors Git-tracked evidence locally. GitHub does not push updates directly into Dropbox; local synchronization still requires a pull. Review archive growth around 250 MiB and plan larger storage before roughly 500 MiB–1 GiB, as described in the improvement plan. Source HTML is public website content, and the repository is public.

## Verify and restore

From the repository root, using Python 3.11+ with `requirements.txt` installed:

```bash
python code/source_archive.py verify
python -m unittest discover -s tests -v
```

Verification decompresses source references from all manifests and indexes and compares SHA-256 hashes. It exits with an error for a missing/corrupt source. Historical manifest observations can be inspected without contacting the website.

To restore a specific version, read its `source_path` and `source_sha256` from an observation. With the archive module on the Python path:

```python
import sys
from pathlib import Path
sys.path.insert(0, "code")
from source_archive import verify_source

# Replace these values with a selected manifest observation.
body = verify_source(Path("archive"), observation["source_path"], observation["source_sha256"])
# Parse `body` offline with BeautifulSoup or a future corrected extractor.
```

To prepare an independently restorable run bundle:

```bash
python code/source_archive.py export \
  --run-id github-RUN_ID-ATTEMPT \
  --destination archive_run
python code/source_archive.py verify --archive-root archive_run
```

To repeat the legacy import, use the saved receipts and metadata from the inventory; completed artifact runs are skipped. The importer verifies original ZIP digests/CRCs and reads matching members without extracting arbitrary ZIP paths. It writes only the archive and its inventory, never `json_output` or `html_output`:

```bash
python code/preserve_artifacts.py \
  --receipts preserved_artifacts/2026-10-15/receipts.json \
  --metadata archive/preservation/artifacts.json
```

## Validation evidence

The 15 preservation/import/integration tests passed locally and on GitHub. An isolated [live smoke test](audits/2026-10-15/archive-live-smoke.json) captured three active adverts, verified original-body recovery and offline re-extraction, confirmed repeat-source reuse, and verified a self-contained export. The HVAC advert's source contains 12,137 description characters, including the tail beyond the extractor's existing 10,000-character limit. Production outputs were not modified by that smoke test. A fresh local clone restored and verified all 1,198 historical sources from Git alone.

The [full deployment workflow](https://github.com/juddormsby/png-job-scrape/actions/runs/38741244563) completed successfully, including source verification, recovery artifact upload and automatic Git publication. Its [saved verification report](audits/2026-10-15/archive-deployment-verification.json) records:

- 244 responses archived: 221 job requests covering **211 distinct live job IDs**, plus 23 listing requests. No network failures or extractor exceptions occurred in this run.
- **3,712 jobs** in the resulting database, including **five new IDs**. No old IDs or first-seen dates were lost; all 3,501 unvisited historical records were unchanged. JSON and CSV IDs and source hashes agree.
- Every refreshed job's portable source reference resolves and matches its SHA-256. All **1,442 historical and new source files** verify in both the working checkout and a fresh Git clone.
- The downloaded recovery ZIP matches GitHub's digest, passes all member CRC checks, and independently restores its 244 referenced sources without the repository archive.

The existing summary still counts new URL requests rather than distinct new IDs (six versus five in this run), and aliases cause extra detail requests. That reporting/discovery repair remains in Phase 2; final database IDs are unique. Historical 404 entries in the existing failure list are also distinct from errors in this live run. The successful automatic results commit was fast-forwarded into this Dropbox checkout.

Known extraction defects remain documented in the [audit](SCRAPER_AUDIT_2026-10-15.md): title cuts, salary handling, description truncation and interface text are separate repairs. Archiving the full source now makes later correction possible when that source survives.
