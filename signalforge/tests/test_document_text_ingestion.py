import json
import tempfile
import unittest
from pathlib import Path

from signalforge.document_text_ingestion import build_category_readiness, ingest_directory, split_page_blocks

REGISTRY={"companies":[{"canonical_name":"NTPC Limited","verified_identifier":"INE733E01010","identifiers":["NTPC","532555"],"aliases":["NTPC"],"verification_status":"verified","verification_source":"https://example.test/filing"}]}

class DocumentTextIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
        (self.root/"in/quarterly reports").mkdir(parents=True)
        (self.root/"reg.json").write_text(json.dumps(REGISTRY),encoding="utf-8")
    def run_ingest(self):
        return ingest_directory(self.root/"in",self.root/"out",self.root/"reg.json",root=self.root)
    def test_crlf_page_markers_and_repeated_pages(self):
        blocks=split_page_blocks("﻿Page 1\r\nalpha\r\nPage 1\r\nbeta\r\nPage 3\r\ngamma".replace("\r\n","\n").lstrip("﻿"))
        self.assertEqual([(1,1,"alpha"),(1,2,"beta"),(3,1,"gamma")],blocks)
    def test_exchange_identifier_verifies_but_name_only_does_not(self):
        d=self.root/"in/quarterly reports"
        (d/"strong.csv").write_bytes("Page 1\r\nScrip Code - 532555 solar capacity MW under construction at NTPC Limited\r\n".encode("utf-8-sig"))
        (d/"weak.csv").write_bytes("Page 1\r\nMentions NTPC Limited as a counterparty with enough text here\r\n".encode("utf-8-sig"))
        records,report=self.run_ingest()
        status={r["source_path"].rsplit("/",1)[1]:r["company_identity_status"] for r in records}
        self.assertEqual({"strong.csv":"verified","weak.csv":"unresolved"},status)
        self.assertEqual(0,report["auto_approved_records"]); self.assertEqual(0,report["metrics_extracted"])
        for r in records:
            self.assertEqual("unverified",r["claim_verification_status"]); self.assertIsNone(r["metric_value"]); self.assertTrue(r["extraction_warnings"])
    def test_fragments_flagged_empty_and_readiness_excludes_them(self):
        d=self.root/"in/quarterly reports"
        (d/"a.csv").write_bytes("Page 1\n,,\nPage 2\nINE733E01010 solar installed capacity of 100 MW was commissioned in the year\n".encode("utf-8"))
        records,report=self.run_ingest()
        self.assertEqual(["empty","parsed"],[r["parsing_status"] for r in records])
        cat=build_category_readiness(records,report)["categories"]
        self.assertEqual(1,cat["renewable_transition_and_revenue_mix"]["verified_association_candidate_count"])
        for c in cat.values(): self.assertEqual([],c["usable_validated_evidence_ids"])
    def test_originals_not_modified_and_no_files_written_outside_output(self):
        d=self.root/"in/quarterly reports"; f=d/"a.csv"; f.write_bytes(b"Page 1\nsome text here that is long enough\n")
        before=f.read_bytes(); self.run_ingest()
        self.assertEqual(before,f.read_bytes()); self.assertEqual({"evidence.jsonl","source_records.jsonl","ingestion_report.json"},{p.name for p in (self.root/"out").iterdir()})

if __name__=="__main__": unittest.main()
