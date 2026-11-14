import json
import tempfile
import unittest
from pathlib import Path

from pipeline.fetch_jobs import map_himalayas
from pipeline.validate_jobs import employment, experience, india_eligibility, plain_text, schema_errors, valid_https, validate, work_mode


ROOT = Path(__file__).resolve().parents[1]


class ValidationTests(unittest.TestCase):
    def test_plain_text_removes_markup_and_scripts(self):
        self.assertEqual(plain_text("<p>Hello <b>world</b></p><script>bad()</script>"), "Hello world")

    def test_https_validation_rejects_credentials_and_http(self):
        self.assertTrue(valid_https("https://example.org/job/1"))
        self.assertFalse(valid_https("http://example.org/job/1"))
        self.assertFalse(valid_https("https://user:pass@example.org/job/1"))

    def test_india_eligibility_does_not_match_preposition_in(self):
        eligible, _ = india_eligibility({"source_key": "greenhouse:fixture", "location_raw": "Based in London"})
        self.assertIsNone(eligible)

    def test_remote_title_is_not_marked_onsite(self):
        self.assertEqual(work_mode("Python Finance Developer (100% Remote) Berlin"), "remote")

    def test_location_without_mode_evidence_is_unknown(self):
        self.assertEqual(work_mode("Bengaluru, India"), "unknown")

    def test_international_does_not_mean_intern(self):
        self.assertEqual(experience("SEO & GEO Manager"), "mid")
        self.assertEqual(employment(None, "International Account Executive"), "unknown")

    def test_explicit_intern_is_preserved(self):
        self.assertEqual(experience("Marketing Intern"), "intern")
        self.assertEqual(employment(None, "Marketing Internship"), "internship")

    def test_schema_rejects_missing_top_level_contract(self):
        errors = schema_errors({"schema_version": "1.0", "jobs": [], "sources": [], "stats": {}})
        self.assertIn("generated_at", errors)
        self.assertIn("scope", errors)
        self.assertIn("stats.total", errors)

    def test_himalayas_source_credit_does_not_reuse_apply_link(self):
        mapped = map_himalayas({"guid": "job-1", "applicationLink": "https://apply.example.org/job-1"}, Path("raw.json"), "2026-11-14T09:30:00Z")
        self.assertEqual(mapped["application_url_raw"], "https://apply.example.org/job-1")
        self.assertEqual(mapped["source_url_raw"], "https://himalayas.app")

    def test_fixture_passes_and_preserves_application_link(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / "validated.json"
            report = directory / "qa.json"
            rejected = directory / "rejected.json"
            code = validate(ROOT / "tests/fixtures/research_pass.json", output, report, rejected, None)
            snapshot = json.loads(output.read_text())
            qa = json.loads(report.read_text())
            self.assertEqual(code, 0)
            self.assertEqual(qa["decision"], "pass")
            self.assertEqual(snapshot["jobs"][0]["application_url"], "https://himalayas.app/jobs/fixture/apply")
            self.assertEqual(schema_errors(snapshot), [])

    def test_zero_successful_sources_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "research.json"
            source.write_text(json.dumps({"run_id": "blocked", "sources": [{"key": "himalayas", "name": "Himalayas", "status": "failed", "fetched_at": None, "records_received": 0, "attribution_url": "https://himalayas.app"}], "jobs": []}))
            output = directory / "validated.json"
            report = directory / "qa.json"
            code = validate(source, output, report, directory / "rejected.json", None)
            qa = json.loads(report.read_text())
            self.assertEqual(code, 3)
            self.assertEqual(qa["decision"], "block")
            self.assertIn("zero_verifiably_successful_sources", qa["blockers"])


if __name__ == "__main__":
    unittest.main()

