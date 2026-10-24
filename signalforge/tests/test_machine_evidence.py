"""Synthetic PDF tests; no live models, network or human approvals."""
import copy
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signalforge.config import Config, ROOT
from signalforge.data_loader import DataLoadError
from signalforge.f1_research_angle_selector import eligible_ingested_evidence, run, validate_output
from signalforge.machine_evidence import create_machine_records, create_machine_evidence, main, _digest
from signalforge.r1_research_investigator import load_evidence_ids

ISSUER = "Name of the entity: Example Energy Limited; ISIN EXAMPLE123."
PASSAGE = "Our renewable generation capacity increased to 120 MW during the reporting year."
REGISTRY = {"companies": [{"canonical_name": "Example Energy Limited",
    "verified_identifier": "EXAMPLE123", "aliases": ["Example"],
    "verification_status": "verified", "verification_source": "https://exchange.example/filing"}]}


def pdf_bytes(pages):
    """Build a small valid text PDF without another optional generation library."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        page_id = len(objects) + 1
        kids.append(f"{page_id} 0 R")
        stream = ("BT /F1 10 Tf 20 700 Td (" + text + ") Tj ET").encode("ascii")
        objects.extend([
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
             f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>").encode(),
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"])
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()
    data = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(data)
    data += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return data + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


@unittest.skipUnless(importlib.util.find_spec("pypdf"), "declared pypdf dependency unavailable")
class MachineEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "original.pdf"
        self.original = pdf_bytes([ISSUER, PASSAGE, ""])
        self.pdf.write_bytes(self.original)
        self.hash = hashlib.sha256(self.original).hexdigest()
        self.kwargs = dict(expected_sha256=self.hash, company="Example", registry=REGISTRY,
                           issuer_page=1, issuer_passage=ISSUER, passages=[(2, PASSAGE)])
        self.record = create_machine_records(self.pdf, **self.kwargs)[0]
        self.registry = self.root / "registry.json"
        self.registry.write_text(json.dumps(REGISTRY))
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.csv = self.root / "quotes.csv"
        self.csv.write_text("Date,Close\n2025-01-01,10\n")
        self.cfg = dataclasses.replace(Config(), registry_path=self.registry,
                                      evidence_dir=self.evidence, csv_path=self.csv)

    def eligible(self, record):
        return eligible_ingested_evidence([record], "Example Energy Limited", "EXAMPLE123")

    def store(self, record):
        path = self.evidence / "evidence.jsonl"
        path.write_text(json.dumps(record) + "\n")
        return path

    def test_real_pdf_schema_machine_state_and_immutability(self):
        validate_output(self.record, ROOT / "schemas/evidence_record.schema.json")
        self.assertEqual([self.record], self.eligible(self.record))
        self.assertEqual("automatically_cross_checked", self.record["review_status"])
        for key in ("reviewed_by", "reviewed_at", "review_note"):
            self.assertIsNone(self.record[key])
        self.assertEqual("unverified", self.record["claim_verification_status"])
        self.assertEqual(self.original, self.pdf.read_bytes())
        second = create_machine_records(self.pdf, **self.kwargs)[0]
        self.assertEqual(self.record["evidence_id"], second["evidence_id"])

    def test_f1_model_payload_and_r1_allowlist_have_parity(self):
        path = self.store(self.record)
        self.assertEqual([self.record["evidence_id"]], load_evidence_ids(path, "Example", self.cfg))
        output = {"company_name": "Example Energy Limited", "dataset_summary": {
            "row_count": 1, "columns": [], "date_coverage": None,
            "missing_information": [], "data_limitations": []},
            "ranking_reliable": False, "ranking_limitation": "Insufficient evidence",
            "ranked_candidates": [], "recommended_candidate_id": None}
        with patch("signalforge.f1_research_angle_selector.generate_json", return_value=output) as model:
            run("Example", self.csv, self.root / "f1.json", self.cfg)
        payload = model.call_args.args[1]
        self.assertEqual([self.record], payload["verified_ingested_evidence"])
        self.assertIn("Required F1 output JSON Schema", model.call_args.args[0])
        self.assertIn("not human approval or claim verification", payload["evidence_boundary"])

    def test_missing_or_modified_original_fails_closed_and_blocks_model(self):
        path = self.store(self.record)
        self.pdf.write_bytes(self.original + b"altered")
        self.assertEqual([], self.eligible(self.record))
        self.assertEqual([], load_evidence_ids(path, "Example", self.cfg))
        with patch("signalforge.f1_research_angle_selector.generate_json") as model:
            with self.assertRaises(DataLoadError):
                run("Example", self.csv, self.root / "blocked.json", self.cfg)
            model.assert_not_called()
        self.pdf.unlink()
        self.assertEqual([], self.eligible(self.record))

    def test_status_labels_and_metadata_are_not_sufficient(self):
        mutations = [
            lambda r: r.pop("machine_verification"),
            lambda r: r.update(review_status="pending_review"),
            lambda r: r.update(review_status="rejected"),
            lambda r: r.update(review_status="approved"),
            lambda r: r.update(reviewed_by="automated reviewer"),
            lambda r: r.update(reviewed_at="2026-10-24T00:00:00Z"),
            lambda r: r.update(review_note="Machine checked"),
            lambda r: r["machine_verification"].update(verified_at="2026-10-24"),
            lambda r: r["machine_verification"].update(policy_version="unknown"),
            lambda r: r["machine_verification"]["checks"].update(canonical_issuer=False),
            lambda r: r["machine_verification"]["checks"].update(canonical_issuer=1),
            lambda r: r["machine_verification"].update(passage_sha256="0" * 64),
            lambda r: r.update(company_name="Other Energy Limited"),
            lambda r: r.update(verified_identifier="OTHER123"),
            lambda r: r.update(parsing_status="ocr_required"),
            lambda r: r.update(claim_verification_status="independently_corroborated"),
        ]
        for mutate in mutations:
            record = copy.deepcopy(self.record)
            mutate(record)
            if "machine_verification" in record:
                record["machine_verification"]["record_sha256"] = _digest(record)
            with self.subTest(record=record):
                self.assertEqual([], self.eligible(record))

    def test_exact_page_passage_and_issuer_checked_even_after_rehash(self):
        for updates, metadata in [
            ({"excerpt_or_fact": PASSAGE.replace("120", "121")}, {}),
            ({"excerpt_or_fact": PASSAGE.lower()}, {}),
            ({"excerpt_or_fact": "120 MW"}, {}),
            ({"page_number": 1, "source_locator": "page:1"}, {}),
            ({"page_number": True, "source_locator": "page:True"}, {}),
            ({}, {"issuer_page": 2}),
            ({}, {"issuer_passage": "Subsidiary: Example Energy Limited; ISIN EXAMPLE123."}),
            ({}, {"issuer_passage": ISSUER.replace("EXAMPLE123", "OTHER123")}),
        ]:
            record = copy.deepcopy(self.record)
            record.update(updates)
            record["machine_verification"].update(metadata)
            record["machine_verification"]["passage_sha256"] = hashlib.sha256(record["excerpt_or_fact"].encode()).hexdigest()
            record["machine_verification"]["record_sha256"] = _digest(record)
            with self.subTest(updates=updates, metadata=metadata):
                self.assertEqual([], self.eligible(record))

    def test_record_hash_binds_all_fields(self):
        for key, value in [("source_url", "https://other.example/report.pdf"),
                           ("excerpt_or_fact", PASSAGE + " Invented statement."),
                           ("evidence_id", "ev_" + "0" * 24)]:
            record = copy.deepcopy(self.record)
            record[key] = value
            self.assertEqual([], self.eligible(record))

    def test_creation_rejects_bad_hash_registry_pages_fragments_and_bounds(self):
        cases = [dict(expected_sha256="0" * 64), dict(expected_sha256=None),
                 dict(registry={"companies": []}), dict(company="Other"),
                 dict(passages=[]), dict(passages=[(2, PASSAGE)] * 41),
                 dict(passages=[(2, PASSAGE)] * 2), dict(passages=[(3, PASSAGE)]),
                 dict(passages=[(0, PASSAGE)]), dict(passages=[(True, PASSAGE)]),
                 dict(passages=[(2, "120 MW")]), dict(passages=[(2, "word " * 1000)]),
                 dict(issuer_passage="Example Energy Limited EXAMPLE123")]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                create_machine_records(self.pdf, **{**self.kwargs, **changes})

    def test_schema_requires_machine_metadata_and_excludes_human_metadata(self):
        for mutate in [lambda r: r.pop("machine_verification"),
                       lambda r: r.update(reviewed_by="robot"),
                       lambda r: r["machine_verification"].update(source_sha256="bad")]:
            record = copy.deepcopy(self.record)
            mutate(record)
            with self.assertRaises(ValueError):
                validate_output(record, ROOT / "schemas/evidence_record.schema.json")

    def test_parser_failure_is_ineligible(self):
        with patch("signalforge.machine_evidence._read_pdf_pages", side_effect=RuntimeError("parser failure")):
            self.assertEqual([], self.eligible(self.record))

    def test_three_argument_api_scans_original_and_cli_refuses_overwrite(self):
        records = create_machine_evidence(self.pdf, "Example", self.cfg)
        self.assertTrue(records)
        self.assertTrue(all(self.eligible(r) for r in records))
        selected = create_machine_evidence(self.pdf, "Example", self.cfg,
                                          expected_sha256=self.hash, pages=[2], max_records=1)
        self.assertEqual([2], [r["page_number"] for r in selected])
        out = self.root / "cli"
        argv = ["--original-pdf", str(self.pdf), "--company", "Example",
                "--registry", str(self.registry), "--output-dir", str(out),
                "--expected-sha256", self.hash, "--pages", "2", "--max-records", "1"]
        self.assertEqual(0, main(argv))
        saved = (out / "evidence.jsonl").read_bytes()
        self.assertEqual(2, main(argv))
        self.assertEqual(saved, (out / "evidence.jsonl").read_bytes())

    def test_equity_isin_declaration_is_generic_and_not_a_bare_name_mention(self):
        issuer = "ISIN of the Equity Shares of Example Energy Limited is - EXAMPLE123"
        self.pdf.write_bytes(pdf_bytes([issuer, PASSAGE]))
        records = create_machine_evidence(self.pdf, "Example", self.cfg, pages=[2])
        self.assertEqual(1, len(records))
        self.assertTrue(self.eligible(records[0]))
        self.pdf.write_bytes(pdf_bytes(["A supplier is Example Energy Limited with identifier EXAMPLE123.", PASSAGE]))
        with self.assertRaisesRegex(ValueError, "issuer"):
            create_machine_evidence(self.pdf, "Example", self.cfg)

    def test_three_argument_api_bounds_and_empty_pages(self):
        for changes in [dict(max_records=0), dict(max_records=41), dict(pages=[True]),
                        dict(pages=[99]), dict(pages=[3]), dict(expected_sha256="f" * 64)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                create_machine_evidence(self.pdf, "Example", self.cfg, **changes)


if __name__ == "__main__":
    unittest.main()
