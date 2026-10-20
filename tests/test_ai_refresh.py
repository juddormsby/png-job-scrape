"""Offline fixtures only: no SDK, credentials, actual adverts, or network calls."""
import contextlib
import copy
import csv
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import classify_jobs as ai
import json_to_csv as converter


def job(jid="1"):
    payload = {"title": "Assistant", "description": "Diploma preferred. Three years required; five years preferred. Graduates are encouraged to apply. Excel skills.",
               "employer": "Example", "location": "PNG", "industry": "Agriculture", "employer_external_website": ""}
    return {"job_id": jid, "input_hash": ai.digest(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()), "input": payload, "preparation": {}}


def result(j=None):
    j = j or job()
    value = {"industry_classification": {}, "occupation_classification": {}, "classification_summary": "Fixture classification.",
             "requirements": {"education_level": "diploma", "education_requirement": "preferred", "education_quote": "Diploma preferred.",
                 "experience_required_years": 3, "experience_preferred_years": 5,
                 "experience_quotes": ["Three years required; five years preferred."],
                 "graduate_opportunity": True, "apprenticeship_opportunity": False, "entry_level_opportunity": False,
                 "entry_route_quotes": ["Graduates are encouraged to apply."],
                 "skills_mentioned": [{"category": "digital", "quote": "Excel skills."}]}}
    for prefix, section, codes in (("isic", "industry_classification", ["A", "01", "011", "0111"]),
                                   ("isco", "occupation_classification", ["0", "01", "011", "0110"])):
        for level, code in enumerate(codes, 1):
            value[section][f"{prefix}_{level}digit"] = code + " - Fixture label"
            value[section][f"{prefix}_{level}digit_confidence"] = .8
    return value


def stored(j, status="success"):
    record = {"job_id": j["job_id"], "input_hash": j["input_hash"], "model": ai.MODEL,
              "prompt_version": ai.PROMPT_VERSION, "status": status}
    record.update(result(j) if status == "success" else {"error": "Fixture failure"})
    return record


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "json_output").mkdir()
        adverts = [{"job_id": str(i), **job()["input"]} for i in range(1, 4)]
        (self.root / "json_output/all_jobs.json").write_text(json.dumps({"last_updated": "fixture", "jobs": adverts}))
        for filename in ("classify_jobs.py", "json_to_csv.py", "vacany_analysis.do", "requirements.txt", "requirements-ai.txt"):
            (self.root / filename).write_text("fixture code\n")
        self.run = self.root / "run"
        ai.prepare(self.root, self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_evidence_and_leading_zero_codes(self):
        ai.validate_result(result(), job())
        row = converter.flatten(job(), stored(job()))
        self.assertEqual(row["isco_2digit"], "01 - Fixture label")
        self.assertEqual(row["education_requirement"], "preferred")
        self.assertEqual(row["experience_required_years"], 3)
        self.assertEqual(row["experience_preferred_years"], 5)
        self.assertEqual(row["skill_digital"], 1)
        self.assertEqual(row["skill_teamwork"], 0)
        self.assertEqual(row["classification_summary"], "Fixture classification.")

    def test_no_requirement_vs_not_stated(self):
        value = result()
        req = value["requirements"]
        req.update(education_level="not_stated", education_requirement="not_stated", education_quote=None,
                   experience_required_years=None, experience_preferred_years=None, experience_quotes=[])
        ai.validate_result(value, job())
        self.assertIsNone(converter.flatten(job(), {**stored(job()), **value})["experience_required_years"])
        req["education_level"] = "no_qualification_required"
        with self.assertRaises(ValueError):
            ai.validate_result(value, job())

    def test_reject_unsupported_quotes_and_duplicate_skills(self):
        value = result()
        value["requirements"]["education_quote"] = "Doctorate essential."
        with self.assertRaises(ValueError):
            ai.validate_result(value, job())
        value = result()
        value["requirements"]["skills_mentioned"] *= 2
        with self.assertRaises(ValueError):
            ai.validate_result(value, job())

    def test_reject_inconsistent_codes_and_invalid_years(self):
        value = result()
        value["occupation_classification"]["isco_3digit"] = "211 - Wrong parent"
        with self.assertRaises(ValueError):
            ai.validate_result(value, job())
        value = result()
        value["requirements"]["experience_required_years"] = -1
        with self.assertRaises(ValueError):
            ai.validate_result(value, job())

    def test_body_matched_html_repairs_title_without_splitting_dash(self):
        source = self.root / "example.html"
        source.write_text('<span itemprop="title">Assistant - Agriculture</span><div itemprop="description"><p>Hello advert.</p><p>More details.</p></div>')
        raw = {"job_id": "1", "title": "Assistant", "description": "Hello advert.", "html_file_rel": "example.html"}
        prepared = ai.prepare_job(raw, self.root, {})
        self.assertEqual(prepared["input"]["title"], "Assistant - Agriculture")
        self.assertIn("More details.", prepared["input"]["description"])
        self.assertTrue(prepared["preparation"]["html_body_matched"])
        raw["description"] = "A changed advert."
        prepared = ai.prepare_job(raw, self.root, {})
        self.assertEqual(prepared["input"]["title"], "Assistant")
        self.assertEqual(prepared["input"]["description"], "A changed advert.")

    def test_cleaning_preserves_application_instructions(self):
        text = "Role.\nHow to apply\nSend a CV.\nSign in to apply\nUsername:"
        self.assertEqual(ai.clean_description(text), "Role.\nHow to apply\nSend a CV.")

    def test_prepare_refuses_existing_folder_and_never_reads_key(self):
        with self.assertRaises(ValueError):
            ai.prepare(self.root, self.run)
        self.assertFalse((self.run / "LLM_processed_jobs.json").exists())
        self.assertFalse((self.run / "analysis").exists())

    def test_default_is_nonmutating_no_api_dry_run(self):
        before = {p.name: p.read_bytes() for p in self.run.iterdir()}
        with patch.object(ai, "classify_job", side_effect=AssertionError("API must not be called")), contextlib.redirect_stdout(io.StringIO()):
            ai.main(["--run-dir", str(self.run)])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.run.iterdir()})

    def test_cached_errors_are_retried_successes_skipped_offline(self):
        jobs = json.loads((self.run / "prepared_jobs.json").read_text())
        ai.write_json(self.run / "LLM_processed_jobs.json", [stored(jobs[0]), stored(jobs[1], "error")])
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fixture-not-a-real-key"}), patch.object(ai, "classify_job", side_effect=lambda j, m, k: stored(j)) as fake, contextlib.redirect_stdout(io.StringIO()):
            ai.main(["--run-dir", str(self.run), "--execute", "--workers", "1"])
        self.assertEqual({call.args[0]["job_id"] for call in fake.call_args_list}, {"2", "3"})
        self.assertEqual(len(json.loads((self.run / "LLM_processed_jobs.json").read_text())), 3)

    def test_converter_fixed_columns_with_error_first_and_pending(self):
        jobs = json.loads((self.run / "prepared_jobs.json").read_text())
        ai.write_json(self.run / "LLM_processed_jobs.json", [stored(jobs[0], "error"), stored(jobs[1])])
        path, count = converter.convert(self.run)
        with path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            self.assertEqual(reader.fieldnames, converter.COLUMNS)
        self.assertEqual(count, 3)
        self.assertEqual([r["status"] for r in rows], ["error", "success", "pending"])
        self.assertEqual(rows[0]["skill_digital"], "")
        self.assertEqual(rows[1]["skill_digital"], "1")

    def test_changed_frozen_input_or_model_is_rejected(self):
        with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
            ai.main(["--run-dir", str(self.run), "--model", "different-model"])
        with (self.run / "prepared_jobs.json").open("a") as stream:
            stream.write(" ")
        with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()):
            ai.main(["--run-dir", str(self.run)])


if __name__ == "__main__":
    unittest.main()
