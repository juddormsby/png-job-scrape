"""Offline fixtures only: no SDK, credentials, actual adverts, or network calls."""
import contextlib
import copy
import csv
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def test_duplicate_model_mentions_keep_one_flag_and_audit_discarded_quote(self):
        value = result()
        mention = value["requirements"]["skills_mentioned"][0]
        value["requirements"]["skills_mentioned"].append(copy.deepcopy(mention))
        response = SimpleNamespace(status="completed", output_text=json.dumps(value), id="fixture", usage=None)
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
        sdk = SimpleNamespace(OpenAI=lambda **kwargs: contextlib.nullcontext(client))
        with patch.dict(sys.modules, {"openai": sdk}):
            saved = ai.classify_job(job(), {"model": ai.MODEL, "reasoning": "low"}, "fixture-key")
        self.assertEqual(saved["status"], "success")
        self.assertEqual(saved["requirements"]["skills_mentioned"], [mention])
        self.assertEqual(saved["discarded_duplicate_skill_mentions"], [mention])

    def test_retry_receives_the_specific_validation_failure(self):
        invalid = result()
        invalid["requirements"]["education_quote"] = "Invented qualification."
        outputs = iter([invalid, result()])
        requests = []
        def respond(**kwargs):
            requests.append(kwargs["input"])
            return SimpleNamespace(status="completed", output_text=json.dumps(next(outputs)), id="fixture", usage=None)
        client = SimpleNamespace(responses=SimpleNamespace(create=respond))
        sdk = SimpleNamespace(OpenAI=lambda **kwargs: contextlib.nullcontext(client))
        with patch.dict(sys.modules, {"openai": sdk}), patch.object(ai.time, "sleep"):
            saved = ai.classify_job(job(), {"model": ai.MODEL, "reasoning": "low"}, "fixture-key")
        self.assertEqual(saved["status"], "success")
        self.assertEqual(len(requests), 2)
        self.assertIn("Invented qualification.", requests[1][-1]["content"])

    def test_2025_prompt_matches_recovered_archived_wording(self):
        config = ai.prompt_config("2025")
        self.assertEqual(ai.prompt_hash(config), "dc329b7225dc2c45b5fd486ac682868b8650bee5ac90483080ac4b855d115537")
        self.assertEqual(set(config["schema"]["properties"]), {"industry_classification", "occupation_classification", "classification_summary"})
        messages = ai.request_messages(job(), config)
        self.assertIn("Job Title: Assistant\nEmployer: Example", messages[1]["content"])
        self.assertIn("If a classification cannot be determined", messages[1]["content"])

    def test_2025_retry_preserves_messages_and_excludes_new_fields(self):
        valid = result()
        valid.pop("requirements")
        invalid = copy.deepcopy(valid)
        invalid["classification_summary"] = 7
        outputs = iter([invalid, valid])
        requests = []
        def respond(**kwargs):
            requests.append(kwargs)
            return SimpleNamespace(status="completed", output_text=json.dumps(next(outputs)), id="fixture", usage=None)
        client = SimpleNamespace(responses=SimpleNamespace(create=respond))
        sdk = SimpleNamespace(OpenAI=lambda **kwargs: contextlib.nullcontext(client))
        with patch.dict(sys.modules, {"openai": sdk}), patch.object(ai.time, "sleep"):
            saved = ai.classify_job(job(), {"model": ai.MODEL, "reasoning": "low", "prompt_style": "2025"}, "fixture-key")
        self.assertEqual(saved["status"], "success")
        self.assertNotIn("requirements", saved)
        self.assertEqual(requests[0]["input"], requests[1]["input"])
        self.assertEqual(requests[0]["text"]["format"]["schema"], ai.prompt_config("2025")["schema"])

    def test_2025_prepare_and_convert_keep_outputs_classification_only(self):
        folder = self.root / "code/prompts"
        folder.mkdir(parents=True)
        shutil.copyfile(ROOT / "code/prompts/classification_2025.json", folder / "classification_2025.json")
        legacy = self.root / "legacy_run"
        metadata = ai.prepare(self.root, legacy, prompt_style="2025")
        jobs = json.loads((legacy / "prepared_jobs.json").read_text())
        records = []
        for advert in jobs:
            saved = stored(advert)
            saved.pop("requirements")
            saved["prompt_version"] = metadata["prompt_version"]
            records.append(saved)
        ai.write_json(legacy / "LLM_processed_jobs.json", records)
        output, count = converter.convert(legacy)
        with output.open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(count, 3)
        self.assertNotIn("education_level", rows[0])
        self.assertEqual(rows[0]["isco_2digit"], "01 - Fixture label")
        self.assertTrue((legacy / "code/prompts/classification_2025.json").exists())

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

    def test_qualification_can_be_required_without_a_stated_level(self):
        advert = job()
        advert["input"]["description"] = advert["input"]["description"].replace("Diploma preferred.", "Relevant qualification required.")
        value = result()
        value["requirements"].update(education_level="not_stated", education_requirement="required", education_quote="Relevant qualification required.")
        ai.validate_result(value, advert)
        value["requirements"]["education_quote"] = None
        with self.assertRaises(ValueError):
            ai.validate_result(value, advert)

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
