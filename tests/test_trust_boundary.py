import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "grounded_manual.py"
PDF_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "tiny_evidence.pdf"


class GroundedManualCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "project"
        self.pack = self.project / "docs" / "grounded_manual"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, check=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if check and result.returncode != 0:
            self.fail(
                f"command failed: {args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def init_project(self):
        self.run_cli("init-project", self.project)
        return self.pack

    def write_jsonl(self, rel, rows):
        path = self.pack / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        return path

    def read_jsonl(self, rel):
        path = self.pack / rel
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                rows.append(json.loads(line))
        return rows

    def latest_audit_rows(self):
        logs = sorted((self.pack / "logs").glob("audit_*.jsonl"))
        self.assertTrue(logs, "expected an audit log")
        rows = []
        for line in logs[-1].read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def add_indexed_text_source(self, text="Alpha locator claim evidence line.\n"):
        self.init_project()
        fixture_dir = self.pack / "sources" / "fixtures"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        source = fixture_dir / "evidence.txt"
        source.write_text(text, encoding="utf-8")
        self.run_cli(
            "register-source",
            source,
            "--root",
            self.project,
            "--source-id",
            "evidence",
            "--kind",
            "text",
            "--sync-policy",
            "public",
        )
        self.run_cli("build-index", "--root", self.project)
        search = self.run_cli(
            "search",
            "locator evidence",
            "--root",
            self.project,
            "--json",
        )
        rows = json.loads(search.stdout)
        self.assertTrue(rows, "expected search hit for evidence source")
        return source, rows[0]

    def test_init_project_creates_expected_pack_layout(self):
        self.init_project()
        for rel in [
            "project.yaml",
            "grounded_manual.lock",
            "sources/sources.manifest.jsonl",
            "claims/claims.jsonl",
            "notes/public_notes.ai.md",
            "manual/manual.ai.md",
        ]:
            self.assertTrue((self.pack / rel).exists(), rel)
        for rel in ["sources", "claims", "logs", "index", "extracted/public"]:
            self.assertTrue((self.pack / rel).is_dir(), rel)

    def test_register_source_build_index_search_json_excludes_manual_by_default(self):
        _, hit = self.add_indexed_text_source()
        self.assertEqual(hit["evidence_allowed"], 1)
        self.assertNotEqual(hit["source_type"], "manual")
        self.assertEqual(hit["source_id"], "evidence")

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf is required for PDF extraction")
    def test_extract_pdf_records_text_and_manifest(self):
        self.init_project()
        fixture_dir = self.pack / "sources" / "fixtures"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        pdf = fixture_dir / "tiny_evidence.pdf"
        shutil.copyfile(PDF_FIXTURE, pdf)
        self.run_cli(
            "extract-pdf",
            pdf,
            "--root",
            self.project,
            "--source-id",
            "tiny_pdf",
            "--sync-policy",
            "public",
        )

        extracted = self.pack / "extracted" / "public" / "tiny_pdf_pages.md"
        self.assertIn("Tiny PDF evidence text.", extracted.read_text(encoding="utf-8"))
        manifest = self.read_jsonl("sources/sources.manifest.jsonl")
        self.assertEqual(manifest[0]["source_id"], "tiny_pdf")
        self.assertEqual(manifest[0]["path_strategy"], "relative")
        self.assertEqual(manifest[0]["ocr_status"], "not_needed")
        self.assertEqual(len(manifest[0]["page_hashes"]), 1)

    def test_audit_precise_span_is_needs_review_with_span_hit_type(self):
        _, hit = self.add_indexed_text_source()
        self.write_jsonl(
            "claims/claims.jsonl",
            [
                {
                    "id": "C-precise",
                    "text": "Alpha locator claim evidence line.",
                    "status": "draft",
                    "source_spans": [
                        {"source_id": "evidence", "chunk_hash": hit["chunk_hash"]}
                    ],
                }
            ],
        )

        self.run_cli("audit-claims", "--root", self.project, "--write")
        claim = self.read_jsonl("claims/claims.jsonl")[0]
        self.assertEqual(claim["status"], "needs_review")
        self.assertIn("semantic support not checked", claim["audit_reason"])
        audit = self.latest_audit_rows()[0]
        self.assertEqual(audit["audit_result"], "needs_review")
        self.assertEqual(audit["claim_status_before"], "draft")
        self.assertEqual(audit["claim_status_after"], "needs_review")
        self.assertEqual(audit["write_action"], "updated")
        self.assertEqual(audit["hits"][0]["hit_type"], "span_resolved")

    def test_audit_source_only_span_is_weak_candidate_not_span_resolved(self):
        self.add_indexed_text_source()
        self.write_jsonl(
            "claims/claims.jsonl",
            [
                {
                    "id": "C-weak",
                    "text": "Alpha locator claim evidence line.",
                    "status": "draft",
                    "source_spans": [{"source_id": "evidence"}],
                }
            ],
        )

        self.run_cli("audit-claims", "--root", self.project, "--write")
        audit = self.latest_audit_rows()[0]
        self.assertEqual(audit["audit_result"], "needs_review")
        self.assertIn("source-only locator is not a precise span", audit["reason"])
        self.assertTrue(audit["query_terms"])
        self.assertEqual(audit["hits"][0]["hit_type"], "fts_candidate")

    def test_audit_preserves_human_and_stale_statuses(self):
        _, hit = self.add_indexed_text_source()
        rows = []
        for status in ["supported", "partial", "contradicted", "stale"]:
            rows.append(
                {
                    "id": f"C-{status}",
                    "text": "Alpha locator claim evidence line.",
                    "status": status,
                    "audit_reason": f"human review kept {status}",
                    "source_spans": [
                        {"source_id": "evidence", "chunk_hash": hit["chunk_hash"]}
                    ],
                }
            )
        self.write_jsonl("claims/claims.jsonl", rows)

        self.run_cli("audit-claims", "--root", self.project, "--write")
        claims = self.read_jsonl("claims/claims.jsonl")
        self.assertEqual([claim["status"] for claim in claims], [row["status"] for row in rows])
        self.assertEqual([claim["audit_reason"] for claim in claims], [row["audit_reason"] for row in rows])
        audits = self.latest_audit_rows()
        self.assertTrue(all(audit["write_action"] == "preserved" for audit in audits))
        self.assertTrue(all(audit["claim_status_after"] == audit["claim_status_before"] for audit in audits))

    def test_audit_skips_note_claims_without_writing_claim(self):
        self.add_indexed_text_source()
        self.write_jsonl(
            "claims/claims.jsonl",
            [
                {
                    "id": "C-note",
                    "text": "Personal interpretation.",
                    "status": "note",
                    "source_spans": [{"source_id": "evidence"}],
                }
            ],
        )

        self.run_cli("audit-claims", "--root", self.project, "--write")
        claim = self.read_jsonl("claims/claims.jsonl")[0]
        self.assertEqual(claim["status"], "note")
        self.assertNotIn("last_audited_at", claim)
        audit = self.latest_audit_rows()[0]
        self.assertEqual(audit["audit_result"], "skipped_note")
        self.assertEqual(audit["write_action"], "skipped")

    def test_audit_without_write_leaves_claims_file_unchanged(self):
        _, hit = self.add_indexed_text_source()
        claims_path = self.write_jsonl(
            "claims/claims.jsonl",
            [
                {
                    "id": "C-nowrite",
                    "text": "Alpha locator claim evidence line.",
                    "status": "draft",
                    "source_spans": [
                        {"source_id": "evidence", "chunk_hash": hit["chunk_hash"]}
                    ],
                }
            ],
        )
        before = claims_path.read_text(encoding="utf-8")

        self.run_cli("audit-claims", "--root", self.project)
        self.assertEqual(claims_path.read_text(encoding="utf-8"), before)

    def test_audit_no_span_and_no_candidate_is_unsupported(self):
        self.add_indexed_text_source()
        self.write_jsonl(
            "claims/claims.jsonl",
            [
                {
                    "id": "C-unsupported",
                    "text": "zzqnonmatchterm never appears anywhere",
                    "status": "draft",
                    "source_spans": [],
                }
            ],
        )

        self.run_cli("audit-claims", "--root", self.project, "--write")
        claim = self.read_jsonl("claims/claims.jsonl")[0]
        self.assertEqual(claim["status"], "unsupported")
        audit = self.latest_audit_rows()[0]
        self.assertEqual(audit["audit_result"], "unsupported")
        self.assertEqual(audit["hits"], [])

    def test_verify_sources_mark_stale_returns_three_and_marks_claim(self):
        source, hit = self.add_indexed_text_source()
        self.write_jsonl(
            "claims/claims.jsonl",
            [
                {
                    "id": "C-stale",
                    "text": "Alpha locator claim evidence line.",
                    "status": "needs_review",
                    "source_spans": [
                        {"source_id": "evidence", "chunk_hash": hit["chunk_hash"]}
                    ],
                }
            ],
        )
        source.write_text("Changed source text.\n", encoding="utf-8")

        result = self.run_cli("verify-sources", "--root", self.project, "--mark-stale", check=False)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        claim = self.read_jsonl("claims/claims.jsonl")[0]
        self.assertEqual(claim["status"], "stale")
        self.assertEqual(claim["stale_reason"], "source_hash_changed")

    def test_minimal_example_excludes_local_and_rebuildable_files(self):
        example = REPO_ROOT / "examples" / "minimal_project" / "docs" / "grounded_manual"
        self.assertTrue((example / "project.yaml").exists())
        for rel in [
            "sources/local_overrides.yaml",
            "notes/private_notes.local.md",
            "index",
            "logs",
        ]:
            self.assertFalse((example / rel).exists(), rel)
        manifest = self.read_example_jsonl(example / "sources" / "sources.manifest.jsonl")
        self.assertTrue(all(row["sync_policy"] == "public" for row in manifest))
        self.assertTrue(all(row["path_strategy"] == "relative" for row in manifest))

    def read_example_jsonl(self, path):
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                rows.append(json.loads(line))
        return rows


if __name__ == "__main__":
    unittest.main()
