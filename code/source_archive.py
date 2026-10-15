#!/usr/bin/env python3
"""Versioned source bodies and per-observation manifests, independent of extraction."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Comment

SCHEMA_VERSION = 1
FINGERPRINT_VERSION = "advert-dom-v1"
HEADER_ALLOWLIST = {"content-type", "content-encoding", "etag", "last-modified", "date"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def atomic_write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_json(path, data):
    atomic_write(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode())


def protected_email(value):
    try:
        encoded = bytes.fromhex(value)
        return bytes(c ^ encoded[0] for c in encoded[1:]).decode("utf-8")
    except (ValueError, IndexError, UnicodeDecodeError):
        return value


def fingerprint(body, scope="job"):
    """Broad independent DOM evidence; never use extracted job JSON as a cache key."""
    soup = BeautifulSoup(body, "html.parser")
    recognized = bool(soup.select_one('[itemprop="title"]') and
                      soup.select_one('[itemprop="description"]'))
    if scope == "job" and recognized:
        main = soup.select_one(".seeker-obj")
        # Conservative fallback for a future template without the familiar wrapper.
        if main is None:
            main = soup.body or soup
        fragments = [str(soup.head or ""), str(main)]
        organization = soup.select_one('[itemprop="hiringOrganization"]')
        if organization is not None:
            fragments.append(str(organization))
        normalized = BeautifulSoup("\n".join(fragments), "html.parser")
    else:
        normalized = soup
    for node in normalized.select("script, style"):
        node.decompose()
    for comment in normalized.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    for node in normalized.find_all(True):
        # Hidden values include CSRF/application tokens, not advertised job data.
        if node.name == "input" and node.get("type", "").lower() == "hidden":
            node.attrs.pop("value", None)
        node.attrs.pop("nonce", None)
        if node.get("data-cfemail"):
            node["data-cfemail"] = protected_email(node["data-cfemail"])
        href = node.get("href", "")
        if "/cdn-cgi/l/email-protection#" in href:
            node["href"] = "mailto:" + protected_email(href.split("#", 1)[1])
        elif "/s/redirect" in href:
            parsed = urlsplit(href)
            query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                     if k != "auth"]
            node["href"] = urlunsplit(parsed._replace(query=urlencode(query)))
    return sha256(str(normalized).encode("utf-8")), recognized


def resource_name(url, job_id=None):
    match = re.search(r"/(\d+)/?$", urlsplit(url).path)
    job_id = str(job_id) if job_id is not None else match.group(1) if match else None
    if job_id is not None:
        if not re.fullmatch(r"\d{1,12}", job_id):
            raise ValueError("Invalid archive job ID")
        return "job_" + job_id, job_id
    return "page_" + sha256(url.encode())[:24], None


class SourceArchive:
    def __init__(self, root, run_id=None, source_commit=None, started_at=None):
        self.root = Path(root)
        self.started_at = started_at or utc_now()
        github_run = os.environ.get("GITHUB_RUN_ID")
        default_run = (f"github-{github_run}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
                       if github_run else "local-" + uuid.uuid4().hex)
        self.run_id = str(run_id or default_run)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", self.run_id):
            raise ValueError("Unsafe archive run ID")
        self.source_commit = source_commit or os.environ.get("GITHUB_SHA")
        parsed_start = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
        self.partition = parsed_start.strftime("%Y/%m")
        self.manifest = self.root / "manifests" / self.partition / (self.run_id + ".jsonl")
        self.summary = self.manifest.with_suffix(".json")
        self.counts = {"observations": 0, "stored_versions": 0,
                       "reused_versions": 0, "network_errors": 0}
        self._fingerprints = {}
        if self.manifest.exists():
            raise FileExistsError(f"Archive run already exists: {self.run_id}")
        self._append({"record_type": "run_start", "schema_version": SCHEMA_VERSION,
                      "run_id": self.run_id, "started_at": self.started_at,
                      "source_commit": self.source_commit})

    def _append(self, row):
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def capture(self, body, requested_url, final_url=None, status_code=200,
                headers=None, encoding=None, scope="job", job_id=None,
                captured_at=None, source_form="http_response_body", provenance=None):
        if not isinstance(body, bytes):
            raise TypeError("Archive original response bytes, not decoded/re-serialized text")
        resource, job_id = resource_name(requested_url, job_id)
        raw_hash = sha256(body)
        cached = self._fingerprints.get((raw_hash, scope))
        if cached is None:
            cached = fingerprint(body, scope)
            self._fingerprints[(raw_hash, scope)] = cached
        evidence_hash, recognized = cached
        if source_form != "http_response_body":
            category = "legacy_html"
        elif status_code is not None and status_code >= 400:
            category = "http_error"
        elif scope == "job" and not recognized:
            category = "unrecognized_job_html"
        else:
            category = "job_html" if scope == "job" else "listing_html"
        # Error pages have their own pointer and cannot displace the last valid page.
        state_key = f"{resource}-{category}-{status_code}"
        shard = job_id[:3] if job_id else resource[5:8]
        state_path = self.root / "index" / shard / (state_key + ".json")
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        reused = bool(state and state.get("fingerprint_version") == FINGERPRINT_VERSION
                      and state.get("fingerprint_sha256") == evidence_hash)
        if reused:
            source_path = state["source_path"]
            source_hash = state["source_sha256"]
            verify_source(self.root, source_path, source_hash)
            self.counts["reused_versions"] += 1
        else:
            source_path = str(Path("html") / self.partition / resource / (raw_hash + ".html.gz"))
            source_hash = raw_hash
            destination = self.root / source_path
            if destination.exists():
                verify_source(self.root, source_path, raw_hash)
                reused = True
                self.counts["reused_versions"] += 1
            else:
                atomic_write(destination, gzip.compress(body, mtime=0))
                self.counts["stored_versions"] += 1
            write_json(state_path, {
                "schema_version": SCHEMA_VERSION, "resource": resource,
                "category": category, "fingerprint_version": FINGERPRINT_VERSION,
                "fingerprint_sha256": evidence_hash, "source_path": source_path,
                "source_sha256": raw_hash,
            })
        row = {
            "record_type": "observation", "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id, "source_commit": self.source_commit,
            "archived_at": utc_now(), "captured_at": captured_at,
            "requested_url": requested_url, "final_url": final_url,
            "resource": resource, "job_id": job_id, "scope": scope,
            "http_status": status_code, "category": category,
            "headers": {k.lower(): v for k, v in (headers or {}).items()
                        if k.lower() in HEADER_ALLOWLIST},
            "reported_encoding": encoding, "source_form": source_form,
            "observed_response_sha256": raw_hash, "observed_response_bytes": len(body),
            "source_sha256": source_hash, "source_path": source_path,
            "raw_response_retained": raw_hash == source_hash,
            "reused_source_version": reused,
            "fingerprint_version": FINGERPRINT_VERSION,
            "fingerprint_sha256": evidence_hash,
            "recognized_job_page": recognized if scope == "job" else None,
            "provenance": provenance or {},
        }
        self._append(row)
        self.counts["observations"] += 1
        return row

    def capture_response(self, response, requested_url, scope="job"):
        return self.capture(
            response.content, requested_url=requested_url, final_url=response.url,
            status_code=response.status_code, headers=response.headers,
            encoding=response.encoding, scope=scope, captured_at=utc_now(),
        )

    def network_error(self, url, error, scope="job"):
        resource, job_id = resource_name(url)
        self._append({"record_type": "network_error", "run_id": self.run_id,
                      "captured_at": utc_now(), "requested_url": url,
                      "resource": resource, "job_id": job_id, "scope": scope,
                      "http_status": None, "error": str(error)})
        self.counts["network_errors"] += 1

    def extraction_event(self, url, status, error=None):
        self._append({"record_type": "extraction", "run_id": self.run_id,
                      "at": utc_now(), "requested_url": url,
                      "status": status, "error": error})

    def finish(self, status="completed", details=None):
        write_json(self.summary, {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
            "source_commit": self.source_commit, "started_at": self.started_at,
            "finished_at": utc_now(), "status": status,
            "manifest": str(self.manifest.relative_to(self.root)),
            **self.counts, "details": details or {},
        })
        return self.counts.copy()


def verify_source(root, relative_path, expected_hash):
    root = Path(root).resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Archive reference escapes archive root")
    with gzip.open(path, "rb") as stream:
        body = stream.read()
    if sha256(body) != expected_hash:
        raise ValueError(f"Archive hash mismatch: {relative_path}")
    return body


def verify_archive(root):
    root = Path(root)
    checked = {}
    observations = 0
    manifests = sorted((root / "manifests").rglob("*.jsonl"))
    for path in manifests:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get("record_type") == "observation":
                key = (row["source_path"], row["source_sha256"])
                if key not in checked:
                    checked[key] = len(verify_source(root, *key))
                observations += 1
                if row["raw_response_retained"]:
                    assert row["observed_response_sha256"] == row["source_sha256"]
    for path in (root / "index").rglob("*.json"):
        row = json.loads(path.read_text())
        key = (row["source_path"], row["source_sha256"])
        if key not in checked:
            checked[key] = len(verify_source(root, *key))
    return {"manifests": len(manifests), "observations": observations,
            "verified_sources": len(checked), "uncompressed_bytes": sum(checked.values())}


def export_run(root, run_id, destination):
    """Self-contained current-run fallback without duplicating the entire archive."""
    import shutil
    root, destination = Path(root), Path(destination)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", run_id):
        raise ValueError("Unsafe run ID")
    manifests = list((root / "manifests").glob(f"*/*/{run_id}.jsonl"))
    if len(manifests) != 1:
        raise ValueError(f"Expected one manifest for {run_id}, found {len(manifests)}")
    manifest = manifests[0]
    paths = {manifest.relative_to(root)}
    if manifest.with_suffix(".json").exists():
        paths.add(manifest.with_suffix(".json").relative_to(root))
    for line in manifest.read_text().splitlines():
        row = json.loads(line)
        if row.get("source_path"):
            verify_source(root, row["source_path"], row["source_sha256"])
            paths.add(Path(row["source_path"]))
    for relative in paths:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    return {"run_id": run_id, "exported_files": len(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "export"])
    parser.add_argument("--archive-root", type=Path,
                        default=Path(__file__).resolve().parent.parent / "archive")
    parser.add_argument("--run-id")
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if args.command == "export":
        if not args.run_id or not args.destination:
            parser.error("export requires --run-id and --destination")
        print(json.dumps(export_run(args.archive_root, args.run_id, args.destination), indent=2))
        return
    result = verify_archive(args.archive_root)
    if not result["verified_sources"]:
        raise SystemExit("No archived sources to verify")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
