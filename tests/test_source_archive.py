import gzip
import csv
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from source_archive import SourceArchive, export_run, find_job_source, verify_archive, verify_source
from preserve_artifacts import preserve
from scraper import PNGworkforceScraper


URL = "https://www.pngworkforce.com/jobs/view/operator-power-station/12345"


def page(title="Operator - Power Station", salary="PGK120,000", token="one",
         description="Original full job description", employer="Example employer",
         apply="https://example.org/apply/12345"):
    return (f'<html><head><title>{title} - PNG</title><script>token={token}</script></head>'
            f'<body><div class="seeker-obj"><h3><span itemprop="title">{title}</span></h3>'
            f'<span itemprop="baseSalary">{salary}</span><span itemprop="salaryCurrency">PGK</span>'
            f'<div class="jobadvert"><div itemprop="description">{description}'
            f'<div class="apply-forms"><input type="hidden" name="csrf" value="{token}">'
            f'<a href="{apply}">Apply</a></div></div></div></div>'
            f'<div itemprop="hiringOrganization"><span itemprop="name">{employer}</span></div>'
            '</body></html>').encode()


def response(body, status=200):
    value = requests.Response()
    value.status_code = status
    value._content = body
    value.url = URL
    value.headers['Content-Type'] = 'text/html; charset=utf-8'
    value.encoding = 'utf-8'
    return value


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "archive"

    def archive(self, run_id="run-one"):
        return SourceArchive(self.root, run_id=run_id,
                             started_at="2026-10-15T12:00:00+00:00")

    def test_original_bytes_round_trip_and_header_allowlist(self):
        body = page(description="Qualifications: naïve café.\nAll text retained.")
        archive = self.archive()
        row = archive.capture(body, URL, headers={'ETag': 'version1', 'Set-Cookie': 'private'})
        archive.finish()
        self.assertEqual(verify_source(self.root, row['source_path'], row['source_sha256']), body)
        self.assertEqual(row['headers'], {'etag': 'version1'})
        self.assertTrue(row['raw_response_retained'])
        self.assertEqual(verify_archive(self.root)['verified_sources'], 1)

    def test_volatile_script_and_hidden_token_reuse_source_but_log_each_response(self):
        archive = self.archive()
        first = archive.capture(page(token="first"), URL)
        second = archive.capture(page(token="different"), URL)
        self.assertEqual(first['source_path'], second['source_path'])
        self.assertNotEqual(first['observed_response_sha256'], second['observed_response_sha256'])
        self.assertFalse(second['raw_response_retained'])
        self.assertTrue(second['reused_source_version'])
        self.assertEqual(archive.counts['stored_versions'], 1)
        self.assertEqual(verify_archive(self.root)['observations'], 2)

    def test_advert_evidence_changes_create_versions_including_long_tail(self):
        archive = self.archive()
        original = archive.capture(page(description="x" * 12000 + " original tail"), URL)
        variants = [page(title="Operator - Electrical"), page(salary="PGK140,000"),
                    page(employer="Changed employer"), page(apply="https://example.org/new-id"),
                    page(description="x" * 12000 + " changed tail")]
        for body in variants:
            with self.subTest(body_sha=hashlib.sha256(body).hexdigest()):
                changed = archive.capture(body, URL)
                self.assertNotEqual(changed['fingerprint_sha256'], original['fingerprint_sha256'])
                self.assertNotEqual(changed['source_path'], original['source_path'])
        self.assertEqual(verify_archive(self.root)['verified_sources'], 6)

    def test_revisit_an_older_version_does_not_duplicate_payload(self):
        archive = self.archive()
        first = archive.capture(page(), URL)
        archive.capture(page(salary="PGK140,000"), URL)
        third = archive.capture(page(), URL)
        self.assertEqual(first['source_path'], third['source_path'])
        self.assertTrue(third['reused_source_version'])
        self.assertEqual(archive.counts['stored_versions'], 2)

    def test_404_and_soft_error_keep_last_valid_source(self):
        archive = self.archive()
        good = archive.capture(page(), URL)
        error = archive.capture(b'<html><title>Not found</title></html>', URL, status_code=404)
        soft = archive.capture(b'<html><title>Temporarily blocked</title></html>', URL)
        self.assertEqual(error['category'], 'http_error')
        self.assertEqual(soft['category'], 'unrecognized_job_html')
        self.assertEqual(verify_source(self.root, good['source_path'], good['source_sha256']), page())
        states = [json.loads(p.read_text()) for p in (self.root / 'index').rglob('*.json')]
        self.assertEqual(next(s for s in states if s['category'] == 'job_html')['source_sha256'], good['source_sha256'])

    def test_corrupted_source_is_detected(self):
        archive = self.archive()
        row = archive.capture(page(), URL)
        (self.root / row['source_path']).write_bytes(gzip.compress(b'wrong body', mtime=0))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            verify_archive(self.root)

    def test_reference_cannot_escape_root(self):
        with self.assertRaisesRegex(ValueError, 'escapes'):
            verify_source(self.root, '../outside.gz', '0' * 64)
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            SourceArchive(self.root, run_id='../../escape')

    def test_source_lookup_uses_legacy_then_prefers_successful_response(self):
        self.assertIsNone(find_job_source(self.root, '12345'))
        archive = self.archive()
        legacy = archive.capture(page(title='Legacy title'), URL, status_code=None,
                                 source_form='legacy_beautifulsoup_serialization')
        self.assertEqual(find_job_source(self.root, '12345'), self.root / legacy['source_path'])
        good = archive.capture(page(), URL)
        archive.capture(b'Expired advert', URL, status_code=404)
        self.assertEqual(find_job_source(self.root, '12345'), self.root / good['source_path'])
        (self.root / good['source_path']).write_bytes(gzip.compress(b'corrupt'))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            find_job_source(self.root, '12345')

    def test_export_is_self_contained_for_reused_source_from_prior_run(self):
        first = self.archive()
        first.capture(page(), URL)
        first.finish()
        second = self.archive('run-two')
        second.capture(page(token='changed token'), URL)
        second.finish()
        exported = Path(self.temporary.name) / 'exported'
        export_run(self.root, 'run-two', exported)
        result = verify_archive(exported)
        self.assertEqual(result['manifests'], 1)
        self.assertEqual(result['observations'], 1)
        self.assertEqual(result['verified_sources'], 1)


class ScraperIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.scraper = PNGworkforceScraper(output_root=self.temporary.name)
        self.addCleanup(self.scraper.session.close)

    def test_source_persists_before_extractor_exception(self):
        body = page()
        with patch.object(self.scraper.session, 'get', return_value=response(body)), \
             patch.object(self.scraper, 'extract_structured_data', side_effect=ValueError('parser failed')):
            with self.assertRaisesRegex(ValueError, 'parser failed'):
                self.scraper.scrape_job_detail(URL)
        self.assertEqual(verify_archive(self.scraper.archive.root)['verified_sources'], 1)
        rows = [json.loads(line) for line in self.scraper.archive.manifest.read_text().splitlines()]
        self.assertEqual(rows[-1]['status'], 'extractor_failed')

    def test_http_error_body_is_retained_and_not_mislabeled_as_network_error(self):
        with patch.object(self.scraper.session, 'get', return_value=response(b'Expired advert', 404)):
            job, error = self.scraper.fetch_page_with_error(URL)
        self.assertIsNone(job)
        self.assertIn('404', error)
        self.assertEqual(self.scraper.archive.counts['network_errors'], 0)
        self.assertEqual(verify_archive(self.scraper.archive.root)['verified_sources'], 1)

    def test_network_error_is_logged_without_fabricated_body(self):
        with patch.object(self.scraper.session, 'get', side_effect=requests.Timeout('timed out')):
            job, error = self.scraper.fetch_page_with_error(URL)
        self.assertIsNone(job)
        self.assertEqual(self.scraper.archive.counts['network_errors'], 1)
        self.assertEqual(verify_archive(self.scraper.archive.root)['verified_sources'], 0)

    def test_archived_source_does_not_stop_live_refresh(self):
        self.scraper.archive.capture(page(), URL)
        (self.scraper.json_dir / 'job_12345.json').write_text(json.dumps({'title':'Cached'}))
        self.assertFalse(self.scraper.is_job_already_scraped('12345'))
        self.scraper.refresh_existing = False
        self.assertTrue(self.scraper.is_job_already_scraped('12345'))
        (self.scraper.json_dir / 'job_12345.json').unlink()
        self.assertFalse(self.scraper.is_job_already_scraped('12345'))

    def test_new_job_has_durable_source_reference(self):
        with patch.object(self.scraper.session, 'get', return_value=response(page())):
            job, error = self.scraper.scrape_job_detail(URL)
        self.assertIsNone(error)
        archived = Path(self.temporary.name) / job['source_archive_file']
        self.assertFalse((Path(self.temporary.name) / 'html_output').exists())
        self.assertEqual(job['html_file'], str(archived))
        self.assertEqual(job['html_file_rel'], job['source_archive_file'])
        self.assertEqual(gzip.decompress(archived.read_bytes()), page())
        self.assertEqual(hashlib.sha256(page()).hexdigest(), job['source_archive_sha256'])
        self.scraper.save_consolidated_files([job], [])
        with (self.scraper.json_dir / 'all_jobs.csv').open() as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row['source_archive_file'], job['source_archive_file'])
        self.assertEqual(row['source_archive_sha256'], job['source_archive_sha256'])
        self.assertEqual(row['html_file'], job['source_archive_file'])

    def test_full_scrape_completes_using_archive_only(self):
        self.scraper.delay = 0
        with patch.object(self.scraper, 'scrape_homepage_jobs', return_value=[{'url': URL}]), \
             patch.object(self.scraper, 'fetch_page', return_value=None), \
             patch.object(self.scraper.session, 'get', return_value=response(page())), \
             patch('builtins.print'):
            jobs = self.scraper.scrape_all(update_existing=False)
        self.assertEqual([job['job_id'] for job in jobs], ['12345'])
        summary = json.loads((self.scraper.json_dir / 'scrape_summary.json').read_text())
        self.assertEqual(summary['total_jobs_in_database'], 1)
        self.assertEqual(verify_archive(self.scraper.archive.root)['verified_sources'], 1)
        self.assertFalse((Path(self.temporary.name) / 'html_output').exists())


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bundle = self.root / 'original.zip'
        with zipfile.ZipFile(self.bundle, 'w') as z:
            z.writestr('html_output/job_12345.html', page())
            z.writestr('json_output/job_12345.json', json.dumps({'url':URL,'scraped_at':'2025-11-01T12:00:00'}))
            z.writestr('json_output/all_jobs.json', json.dumps({'jobs':[]}))
            z.writestr('../../unexpected.txt', 'must not be extracted')
        digest = hashlib.sha256(self.bundle.read_bytes()).hexdigest()
        self.receipt = {'artifact_id':1,'run_id':2,'created_at':'2026-09-20T07:52:21Z',
                        'expires_at':'2026-10-20T07:52:19Z','saved_file':str(self.bundle),
                        'digest':'sha256:'+digest}

    def test_import_integrity_provenance_and_idempotence_without_backfill(self):
        archive = self.root / 'archive'
        production = self.root / 'json_output' / 'all_jobs.json'
        production.parent.mkdir()
        production.write_bytes(b'unchanged production data')
        original = self.bundle.read_bytes()
        first = preserve([self.receipt], archive, {
            str(self.receipt['artifact_id']): {'workflow_run': {'head_sha': 'abc123'}}
        })
        inventory = json.loads((archive / 'preservation/artifacts.json').read_text())
        second = preserve([self.receipt], archive, inventory)
        self.assertEqual(first['unique_html_job_ids'], 1)
        self.assertEqual(second['verification']['manifests'], 1)
        self.assertEqual(self.bundle.read_bytes(), original)
        self.assertEqual(production.read_bytes(), b'unchanged production data')
        self.assertFalse((self.root / 'unexpected.txt').exists())
        manifest = next((archive / 'manifests').rglob('*.jsonl'))
        row = next(json.loads(line) for line in manifest.read_text().splitlines()
                   if json.loads(line)['record_type']=='observation')
        self.assertEqual(row['source_form'], 'legacy_beautifulsoup_serialization')
        self.assertIsNone(row['captured_at'])
        self.assertIsNone(row['http_status'])
        self.assertEqual(row['provenance']['reported_scraped_at'], '2025-11-01T12:00:00')
        recovered = self.root / 'recovered-archive'
        preserve([self.receipt], recovered, inventory)
        summary = next((recovered / 'manifests').rglob('*.json'))
        self.assertEqual(json.loads(summary.read_text())['source_commit'], 'abc123')

    def test_bad_original_zip_digest_stops_import(self):
        self.receipt['digest'] = 'sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError, 'digest mismatch'):
            preserve([self.receipt], self.root / 'archive')


if __name__ == '__main__':
    unittest.main()
