#!/usr/bin/env python3
"""Inventory saved workflow ZIPs and preserve their HTML without modifying job data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from source_archive import SourceArchive, verify_archive, write_json

ROOT = Path(__file__).resolve().parent.parent


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def preserve(receipts, archive_root, metadata=None):
    """ZIP SHA/CRC checks precede imports; original ZIPs remain untouched."""
    archive_root = Path(archive_root)
    inventory_path = archive_root / "preservation" / "artifacts.json"
    previous = json.loads(inventory_path.read_text()) if inventory_path.exists() else {}
    completed = {item["artifact_id"]: item for item in previous.get("artifacts", [])}
    metadata = metadata or {}
    # The permanent inventory can also supply provenance for a fresh import.
    if 'artifacts' in metadata:
        metadata = {str(item['artifact_id']): {
            'workflow_run': {'head_sha': item.get('source_commit')}
        } for item in metadata['artifacts']}
    fingerprint_cache = {}
    results = []
    for receipt in sorted(receipts, key=lambda item: item["created_at"]):
        artifact_id = receipt["artifact_id"]
        path = Path(receipt["saved_file"])
        if not path.is_absolute():
            path = ROOT / path
        expected = receipt["digest"].removeprefix("sha256:")
        actual = file_hash(path)
        if actual != expected:
            raise ValueError(f"Original ZIP digest mismatch for artifact {artifact_id}")
        old = completed.get(artifact_id)
        if old and old["zip_sha256"] == actual:
            summary = archive_root / old["import_summary"]
            if summary.exists() and json.loads(summary.read_text())["status"] == "completed":
                old.setdefault('source_commit', json.loads(summary.read_text()).get('source_commit'))
                results.append(old)
                print(f"Already preserved artifact {artifact_id}", flush=True)
                continue
        run_id = f"artifact-{artifact_id}"
        partition = datetime.fromisoformat(receipt["created_at"].replace("Z", "+00:00")).strftime("%Y/%m")
        if (archive_root / "manifests" / partition / (run_id + ".jsonl")).exists():
            # Keep incomplete evidence; a new import attempt gets its own manifest.
            run_id += "-retry-" + uuid.uuid4().hex[:8]
        info = metadata.get(str(artifact_id), {})
        archive = SourceArchive(archive_root, run_id=run_id,
                                started_at=receipt["created_at"],
                                source_commit=info.get("workflow_run", {}).get("head_sha"))
        archive._fingerprints = fingerprint_cache
        html_ids = set()
        try:
            with zipfile.ZipFile(path) as bundle:
                bad = bundle.testzip()
                if bad:
                    raise ValueError(f"ZIP CRC mismatch for artifact {artifact_id}")
                members = bundle.infolist()
                names = set(bundle.namelist())
                for member in members:
                    match = re.fullmatch(r"html_output/job_(\d+)\.html", member.filename)
                    if not match:
                        continue
                    job_id = match.group(1)
                    json_name = f"json_output/job_{job_id}.json"
                    job = {}
                    if json_name in names:
                        try:
                            job = json.loads(bundle.read(json_name))
                        except (ValueError, UnicodeDecodeError):
                            pass
                    if not isinstance(job, dict):
                        job = {}
                    url = job.get("url") or f"https://www.pngworkforce.com/jobs/view/archived/{job_id}"
                    archive.capture(
                        bundle.read(member), requested_url=url, job_id=job_id,
                        status_code=None, captured_at=None,
                        source_form="legacy_beautifulsoup_serialization",
                        provenance={
                            "artifact_id": artifact_id, "workflow_run_id": receipt["run_id"],
                            "artifact_created_at": receipt["created_at"],
                            "artifact_zip_sha256": actual, "zip_member": member.filename,
                            "reported_scraped_at": job.get("scraped_at"),
                            "capture_time_note": "Legacy JSON timestamp may be timezone-naive; cached files can predate the artifact run.",
                        },
                    )
                    html_ids.add(job_id)
                archive.finish("completed", {"artifact_id": artifact_id})
            try:
                local_path = str(path.relative_to(ROOT))
            except ValueError:
                local_path = path.name
            result = {
                "artifact_id": artifact_id, "workflow_run_id": receipt["run_id"],
                "source_commit": archive.source_commit,
                "created_at": receipt["created_at"], "original_expires_at": receipt["expires_at"],
                "local_zip_path": local_path, "zip_bytes": path.stat().st_size,
                "zip_sha256": actual, "github_digest_verified": True, "zip_crc_verified": True,
                "member_count": len(members),
                "members": [{"name": m.filename, "bytes": m.file_size, "crc32": f"{m.CRC:08x}"}
                            for m in members],
                "import_manifest": str(archive.manifest.relative_to(archive_root)),
                "import_summary": str(archive.summary.relative_to(archive_root)),
                "html_job_ids": sorted(html_ids, key=int),
                "preserved_html_files": len(html_ids),
            }
            results.append(result)
            write_json(inventory_path, {"schema_version": 1, "artifacts": results})
            print(f"Preserved artifact {artifact_id}: {len(html_ids)} HTML files", flush=True)
        except BaseException:
            archive.finish("failed", {"artifact_id": artifact_id})
            raise
    ids = {job_id for item in results for job_id in item["html_job_ids"]}
    report = {
        "schema_version": 1, "artifact_count": len(results),
        "original_zip_bytes": sum(item["zip_bytes"] for item in results),
        "unique_html_job_ids": len(ids),
        "html_job_ids": sorted(ids, key=int), "artifacts": results,
        "verification": verify_archive(archive_root),
    }
    write_json(inventory_path, report)
    return {k: v for k, v in report.items() if k not in ("artifacts", "html_job_ids")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--archive-root", type=Path, default=ROOT / "archive")
    args = parser.parse_args()
    receipts = json.loads(args.receipts.read_text())
    metadata = json.loads(args.metadata.read_text()) if args.metadata else {}
    print(json.dumps(preserve(receipts, args.archive_root, metadata), indent=2))


if __name__ == "__main__":
    main()
