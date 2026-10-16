import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from signalforge.evidence_ingestion import _pdf_records, ingest_file, ingest_paths, load_registry, verify_company
from signalforge.f1_research_angle_selector import validate_output

class FakePage:
    def __init__(self,text=None,error=False): self.text=text; self.error=error
    def extract_text(self):
        if self.error: raise RuntimeError("broken page")
        return self.text
class FakeReader:
    def __init__(self,path): self.metadata=types.SimpleNamespace(title="Sample disclosure",author="Example Exchange"); self.pages=[FakePage("Revenue was INR 20 crore.")]

class EvidenceIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
    def test_pdf_text_extraction_and_page_provenance(self):
        pdf=self.root/"doc.pdf"; pdf.write_bytes(b"fixture")
        records=_pdf_records(pdf,"doc.pdf",FakeReader)
        self.assertEqual("parsed",records[0].parsing_status); self.assertEqual(1,records[0].page_number)
        self.assertEqual("page:1",records[0].source_locator)
        self.assertIn("INR 20",records[0].excerpt_or_fact)
    def test_pdf_failed_and_scanned_extraction(self):
        class BadReader:
            def __init__(self,path): self.metadata=None; self.pages=[FakePage(error=True),FakePage("")]
        records=_pdf_records("scan.pdf","scan.pdf",BadReader)
        self.assertEqual(["failed","ocr_required"],[r.parsing_status for r in records])
        self.assertTrue(any("failed" in w.lower() for w in records[0].extraction_warnings))
    def test_missing_metadata_schema_and_identity_unresolved(self):
        txt=self.root/"note.txt"; txt.write_text("Fact without a date or source URL",encoding="utf-8")
        result=ingest_file(txt,root=self.root)
        record=result["records"][0]
        schema=Path(__file__).resolve().parents[1]/"schemas/evidence_record.schema.json"
        validate_output(record,schema)
        self.assertIsNone(record["publication_date"]); self.assertEqual("unresolved",record["company_identity_status"])
        self.assertEqual("repository_path_only",record["source_identifier_status"])
    def test_company_verification_requires_source(self):
        registry={"companies":[{"canonical_name":"Acme Energy","verified_identifier":"ACME","aliases":["Acme"],"verification_status":"unresolved","verification_source":None}]}
        self.assertEqual("unresolved",verify_company("Acme",registry)[2])
        registry["companies"][0].update(verification_status="verified",verification_source="https://example.com/primary")
        self.assertEqual(("Acme Energy","ACME","verified"),verify_company("Acme",registry))
    def test_duplicate_document_and_conflicting_values_preserved(self):
        p1=self.root/"a.csv"; p2=self.root/"b.csv"
        content="Company,Date,Revenue\nAcme,2025-12-31,10\n"
        p1.write_text(content); p2.write_text(content.replace(",10",",12"))
        registry=self.root/"registry.json"
        registry.write_text(json.dumps({"companies":[{"canonical_name":"Acme","verified_identifier":"ACME","identifiers":["ACME"],"aliases":["Acme"],"verification_source":"https://example.com/filing","verification_status":"verified"}]}))
        _,report=ingest_paths([p1,p2],self.root/"out",registry,root=self.root)
        self.assertEqual(0,len(report["duplicate_documents"]))
        self.assertEqual(1,len(report["conflicts"]))
        self.assertEqual(2,report["evidence_record_count"])
    def test_duplicate_documents_reported_not_dropped(self):
        p1=self.root/"one.txt"; p2=self.root/"two.txt"; p1.write_text("same"); p2.write_text("same")
        records,report=ingest_paths([p1,p2],self.root/"out")
        self.assertEqual(1,len(report["duplicate_documents"])); self.assertEqual(2,len(records))
    def test_actual_repository_csv_is_only_source_and_unverified(self):
        csv_path=Path(__file__).resolve().parents[2]/"Quote-Equity-NTPC-EQ-15-04-2026-15-10-2026.csv"
        if not csv_path.is_file(): self.skipTest("repository source CSV unavailable")
        result=ingest_file(csv_path,load_registry(Path(__file__).resolve().parents[1]/"data/company_registry.json"),root=csv_path.parent)
        self.assertEqual(126,result["source_details"]["row_count"])
        self.assertEqual(126,len(result["source_records"]))
        self.assertTrue(all(r["company_identity_status"]=="unresolved" for r in result["records"]))
        self.assertTrue(all(r["source_url"] is None for r in result["records"]))

if __name__=="__main__": unittest.main()
