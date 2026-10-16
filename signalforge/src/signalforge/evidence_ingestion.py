"""Local document ingestion with immutable sources and traceable normalized evidence."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from html.parser import HTMLParser

from .data_loader import DataLoadError, _norm, load_csv
from .config import Config

SUPPORTED = {".csv", ".pdf", ".txt", ".md", ".html", ".htm"}
DATE_FIELDS = {"date", "publication date", "published date", "filing date", "event date"}
PERIOD_FIELDS = {"period", "financial period", "reporting period", "quarter", "fiscal year"}
COMPANY_FIELDS = {"company", "company name", "issuer", "issuer name", "entity", "entity name"}
IDENTIFIER_FIELDS = {"ticker", "symbol", "isin", "cik", "lei", "company id", "issuer id"}
URL_FIELDS = {"url", "source url", "source link", "document url"}
ORG_FIELDS = {"source organization", "organization", "publisher", "exchange"}

@dataclass
class EvidenceRecord:
    evidence_id: str
    company_name: str | None
    verified_identifier: str | None
    company_identity_status: str
    source_organization: str | None
    document_title: str
    document_type: str
    source_url: str | None
    source_path: str | None
    source_locator: str
    source_identifier_status: str
    publication_date: str | None
    event_date: str | None
    retrieval_date: str
    excerpt_or_fact: str
    metric_name: str | None
    metric_value: float | str | None
    unit: str | None
    currency: str | None
    reporting_period: str | None
    evidence_category: str
    related_claim: str | None
    claim_key: str | None
    source_relationship: str
    claim_verification_status: str
    information_type: str
    parsing_status: str
    extraction_warnings: list[str]
    page_number: int | None = None
    table_identifier: str | None = None

def _stable_id(source_key, locator, content):
    raw="\x1f".join((source_key, str(locator), content))
    return "ev_"+hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

def _hash_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def load_registry(path=None):
    if not path: return {"version":1,"companies":[]}
    p=Path(path)
    if not p.is_file(): raise FileNotFoundError(f"Company registry not found: {p}")
    registry=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(registry.get("companies"),list): raise ValueError("Company registry must contain a companies array")
    return registry

def verify_company(value, registry):
    """Return canonical identity only for a verified registry entry with a verification source."""
    if not value: return None, None, "unresolved"
    matches=[]
    for entity in registry.get("companies",[]):
        names=[entity.get("canonical_name"),*entity.get("aliases",[]),*entity.get("identifiers",[])]
        if any(str(x).strip().casefold()==value.strip().casefold() for x in names if x):
            matches.append(entity)
    identities={(e.get("canonical_name"),e.get("verified_identifier")) for e in matches if e.get("canonical_name") or e.get("verified_identifier")}
    if len(identities)>1: return None,None,"unresolved"
    if matches:
        entity=matches[0]
        verified=entity.get("verification_status")=="verified" and bool(entity.get("verification_source"))
        return (entity.get("canonical_name"),entity.get("verified_identifier"),"verified") if verified else (None,None,"unresolved")
    return None,None,"unresolved"

def _record(source_key, locator, content, **kwargs):
    defaults=dict(company_name=None,verified_identifier=None,company_identity_status="unresolved",source_organization=None,
        document_title=Path(source_key).name,document_type="unknown",source_url=None,source_path=source_key,source_locator=str(locator),
        source_identifier_status="repository_path_only",publication_date=None,event_date=None,
        retrieval_date=dt.datetime.now(dt.timezone.utc).date().isoformat(),excerpt_or_fact=content,metric_name=None,
        metric_value=None,unit=None,currency=None,reporting_period=None,evidence_category="unclassified",
        related_claim=None,claim_key=None,source_relationship="unknown",claim_verification_status="unverified",information_type="reported_fact",parsing_status="parsed",extraction_warnings=[],page_number=None,table_identifier=None)
    defaults.update(kwargs)
    return EvidenceRecord(evidence_id=_stable_id(source_key,locator,content),**defaults)

def _csv_records(path, registry, source_path):
    rows,meta=load_csv(path)
    company_cols=[c for c in meta["columns"] if _norm(c) in COMPANY_FIELDS]
    identifier_cols=[c for c in meta["columns"] if _norm(c) in IDENTIFIER_FIELDS]
    date_cols=[c for c in meta["columns"] if _norm(c) in DATE_FIELDS or _norm(c).endswith(" date")]
    period_cols=[c for c in meta["columns"] if _norm(c) in PERIOD_FIELDS]
    url_cols=[c for c in meta["columns"] if _norm(c) in URL_FIELDS]
    org_cols=[c for c in meta["columns"] if _norm(c) in ORG_FIELDS]
    unit_cols=[c for c in meta["columns"] if _norm(c) in {"unit","units","measurement unit"}]
    currency_cols=[c for c in meta["columns"] if _norm(c) in {"currency","ccy"}]
    metrics=[c for c in meta["columns"] if c not in company_cols+identifier_cols+date_cols+period_cols+unit_cols+currency_cols+url_cols+org_cols]
    records=[]
    for rowno,row in enumerate(rows,2):
        raw_company=next((row.get(c) for c in company_cols if row.get(c)),None)
        raw_id=next((row.get(c) for c in identifier_cols if row.get(c)),None)
        cname,verified_id,status=verify_company(raw_id or raw_company,registry)
        event=next((row.get(c) for c in date_cols if row.get(c)),None)
        reporting_period=next((row.get(c) for c in period_cols if row.get(c)),None) or event
        row_url=next((row.get(c) for c in url_cols if row.get(c)),None)
        row_org=next((row.get(c) for c in org_cols if row.get(c)),None)
        row_unit=next((row.get(c) for c in unit_cols if row.get(c)),None)
        row_currency=next((row.get(c) for c in currency_cols if row.get(c)),None)
        for metric in metrics:
            value=row.get(metric," ").strip()
            if not value: continue
            numeric=re.sub(r"[ ,]", "", value)
            try: number=float(numeric) if re.fullmatch(r"[-+]?\d+(?:\.\d+)?",numeric) else None
            except ValueError: number=None
            content=f"{metric}={value}"
            rec=_record(source_path,f"row:{rowno}:{metric}",content,company_name=cname,verified_identifier=verified_id,company_identity_status=status,
                document_type="csv_market_or_financial_data",source_url=row_url,source_identifier_status="provided_url" if row_url else "repository_path_only",source_organization=row_org,event_date=event,publication_date=None,reporting_period=reporting_period,
                metric_name=metric,metric_value=number if number is not None else value,unit=row_unit,currency=row_currency,
                evidence_category="market_data" if any(t in _norm(metric).split() for t in ("open","high","low","close","vwap","volume","trades","value","ltp")) else "reported_metric",
                extraction_warnings=((["Company name/ticker inferred from row field but not linked to a verified registry entry."] if (raw_company or raw_id) else ["No row-level company identifier is present; do not join this record to a company."]) if status!="verified" else []) + (["Publication date is not present in the CSV; row date is retained only as event/trading date."] if not row_url else []) + (["Unit and currency are not specified or inferred for this metric."] if number is not None else []))
            records.append(rec)
    return records,meta

def _text_records(path, source_path):
    text=Path(path).read_text(encoding="utf-8-sig")
    warnings=[]
    if not text.strip(): status="empty"; warnings.append("No text content was found.")
    else: status="parsed"
    return [_record(source_path,"document",text.strip(),document_type="plain_text",parsing_status=status,extraction_warnings=warnings)]

class _PageTextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.title_parts=[]; self.text_parts=[]; self.in_title=False; self.meta={}
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag.lower()=="title": self.in_title=True
        if tag.lower()=="meta":
            key=(attrs.get("name") or attrs.get("property") or "").lower()
            if key in {"article:published_time","datepublished","date"}: self.meta[key]=attrs.get("content")
    def handle_endtag(self,tag):
        if tag.lower()=="title": self.in_title=False
        if tag.lower() in {"p","div","tr","li","h1","h2","h3","br"}: self.text_parts.append(" ")
    def handle_data(self,data):
        if self.in_title: self.title_parts.append(data.strip())
        if data.strip(): self.text_parts.append(data.strip())

def _html_records(path,source_path):
    parser=_PageTextParser(); parser.feed(Path(path).read_text(encoding="utf-8-sig")); text=" ".join(parser.text_parts)
    title=" ".join(parser.title_parts).strip() or Path(path).name
    warnings=["HTML text extraction may flatten tables and page structure; verify figures against the original page."]
    if not text.strip(): warnings.append("No readable HTML text was extracted.")
    return [_record(source_path,"webpage",text,document_title=title,document_type="webpage",parsing_status="parsed" if text.strip() else "empty",extraction_warnings=warnings)], parser.meta

def _pdf_records(path, source_path, reader_class=None):
    if reader_class is None:
        try: from pypdf import PdfReader
        except ImportError as e: raise RuntimeError("PDF ingestion requires pypdf. Install with: python -m pip install 'pypdf>=4,<6'") from e
        reader_class=PdfReader
    warnings=[]; records=[]
    try: reader=reader_class(str(path))
    except Exception as e:
        return [_record(source_path,"pdf-open", "",document_type="pdf",parsing_status="failed",extraction_warnings=[f"PDF open failed: {type(e).__name__}: {e}"])]
    metadata=getattr(reader,"metadata",None)
    title=(getattr(metadata,"title",None) if metadata else None) or Path(path).name
    author=(getattr(metadata,"author",None) if metadata else None)
    org=None
    for page_no,page in enumerate(getattr(reader,"pages",[]),1):
        extraction_failed=False
        try: text=(page.extract_text() or "").strip()
        except Exception as e:
            text=""; extraction_failed=True; warnings=[f"Page text extraction failed: {type(e).__name__}: {e}"]
        if not text:
            status="failed" if extraction_failed else "ocr_required"
            reason="Text extraction failed; inspect parser error and source page." if extraction_failed else "No extractable text on page; OCR/manual review required."
            records.append(_record(source_path,f"page:{page_no}","",document_title=title,source_organization=org,document_type="pdf",
                parsing_status=status,page_number=page_no,extraction_warnings=warnings+[reason,"Tables/layout may not be preserved by text extraction."]+(["PDF author metadata is available but is not treated as source organization."] if author else [])))
        else:
            records.append(_record(source_path,f"page:{page_no}",text,document_title=title,source_organization=org,document_type="pdf",
                parsing_status="parsed",page_number=page_no,extraction_warnings=warnings+["Tables/layout may not be preserved by text extraction; verify amounts and units against the source page."]+(["PDF author metadata is available but is not treated as source organization."] if author else [])))
    if not records:
        records.append(_record(source_path,"pdf-empty","",document_title=title,document_type="pdf",parsing_status="failed",extraction_warnings=["PDF contains no readable pages."]))
    return records

def ingest_file(path, registry=None, root=None, source_url=None, source_organization=None, retrieved_at=None, publication_date=None, source_relationship="unknown", company_name=None, verified_identifier=None, company_identity_status="unresolved"):
    path=Path(path); registry=registry or {"companies":[]}
    if not path.is_file(): raise FileNotFoundError(f"Source file not found: {path}")
    ext=path.suffix.lower()
    if ext not in SUPPORTED: raise ValueError(f"Unsupported source format {ext!r}; supported: {', '.join(sorted(SUPPORTED))}")
    try: source_path=path.resolve().relative_to(Path(root).resolve()).as_posix() if root else path.as_posix()
    except ValueError: source_path=path.resolve().as_posix()
    file_hash=_hash_file(path)
    if ext==".csv":
        records,meta=_csv_records(path,registry,source_path)
        with path.open("r",encoding="utf-8-sig",newline="") as f:
            raw_rows=list(csv.DictReader(f,skipinitialspace=True))
        source_records=[{"source_path":source_path,"source_sha256":file_hash,"source_record_id":"sr_"+hashlib.sha256(f"{file_hash}:row:{i+2}".encode()).hexdigest()[:24],"raw_record":row} for i,row in enumerate(raw_rows)]
        detail={"row_count":meta["row_count"],"columns":meta["columns"]}
    elif ext==".pdf":
        records=_pdf_records(path,source_path); detail={"page_count":len(records)}
        source_records=[{"source_path":source_path,"source_sha256":file_hash,"source_record_id":"sr_"+hashlib.sha256(f"{file_hash}:page:{r.page_number}".encode()).hexdigest()[:24],"raw_extracted_text":r.excerpt_or_fact,"extraction_status":r.parsing_status} for r in records]
    elif ext in {".html",".htm"}:
        records,html_meta=_html_records(path,source_path); detail={"html_metadata":html_meta}
        source_records=[{"source_path":source_path,"source_sha256":file_hash,"source_record_id":"sr_"+hashlib.sha256(f"{file_hash}:webpage".encode()).hexdigest()[:24],"raw_extracted_text":records[0].excerpt_or_fact}]
    else:
        records=_text_records(path,source_path); detail={}
        source_records=[{"source_path":source_path,"source_sha256":file_hash,"source_record_id":"sr_"+hashlib.sha256(f"{file_hash}:document".encode()).hexdigest()[:24],"raw_extracted_text":records[0].excerpt_or_fact}]
    records=[asdict(r) for r in records]
    retrieved_at=retrieved_at or dt.datetime.now(dt.timezone.utc).isoformat()
    for record in records:
        record["retrieval_date"]=retrieved_at[:10]
        if source_url:
            record["source_url"]=source_url; record["source_identifier_status"]="provided_url"
        if source_organization: record["source_organization"]=source_organization
        if publication_date: record["publication_date"]=publication_date
        record["source_relationship"]=source_relationship
        if company_identity_status=="verified" and verified_identifier:
            record["company_name"]=company_name; record["verified_identifier"]=verified_identifier; record["company_identity_status"]="verified"
        if record.get("metric_name") and record.get("reporting_period") and record.get("verified_identifier"):
            key="\x1f".join((record["verified_identifier"].casefold(),_norm(record["metric_name"]),record["reporting_period"].casefold()))
            record["claim_key"]="cl_"+hashlib.sha256(key.encode()).hexdigest()[:24]
        if source_url and not publication_date: record["extraction_warnings"].append("Publication date not established during retrieval; retrieval timestamp is not a substitute.")
    return {"source_path":source_path,"source_sha256":file_hash,"file_format":ext[1:],"source_url":source_url,"retrieved_at":retrieved_at,"records":records,"source_records":source_records,"source_details":detail}

def _conflicts(all_records):
    groups={}
    for r in all_records:
        if r.get("metric_name") is None or r.get("reporting_period") is None or r.get("metric_value") is None: continue
        key=(r.get("verified_identifier") or r.get("company_name"),r["metric_name"].casefold(),r["reporting_period"],r.get("unit"),r.get("currency"))
        if key[0]: groups.setdefault(key,[]).append(r)
    return [{"claim_key":list(k),"values":[{"value":r["metric_value"],"evidence_id":r["evidence_id"],"source_path":r["source_path"]} for r in rs],"warning":"Conflicting values preserved; review reporting basis, amendment status, and period definitions."} for k,rs in groups.items() if len({str(r["metric_value"]) for r in rs})>1]

def _repeated_facts(all_records):
    groups={}
    for r in all_records:
        if r.get("company_identity_status")!="verified" or r.get("metric_name") is None or r.get("reporting_period") is None: continue
        key=(r.get("verified_identifier"),r["metric_name"].casefold(),r["reporting_period"],str(r.get("metric_value")),r.get("unit"),r.get("currency"))
        groups.setdefault(key,[]).append(r)
    return [{"fact_key":list(k),"evidence_ids":[r["evidence_id"] for r in rs],"source_paths":sorted({r["source_path"] for r in rs}),"warning":"Repeated fact across records/documents; verify whether disclosures are duplicate, repeated, or amended."} for k,rs in groups.items() if len({r["source_path"] for r in rs})>1]

def _cross_validation_summary(all_records):
    groups={}
    for record in all_records:
        if record.get("claim_key"): groups.setdefault(record["claim_key"],[]).append(record)
    result=[]
    for claim_key,items in groups.items():
        primary={r["source_path"] for r in items if r.get("source_relationship")=="original_disclosure"}
        independent={r["source_path"] for r in items if r.get("source_relationship")=="independent_source"}
        republications={r["source_path"] for r in items if r.get("source_relationship")=="republication"}
        result.append({"claim_key":claim_key,"evidence_ids":[r["evidence_id"] for r in items],"primary_source_count":len(primary),"independent_source_count":len(independent),"republication_count":len(republications),"status":"independently_corroborated" if primary and independent else "directly_reported" if primary else "unverified","note":"Republications are reported separately and are not counted as independent corroboration."})
    return result

def registry_mapping_conflicts(registry, alias, canonical_name, identifier):
    conflicts=[]
    for entity in registry.get("companies",[]):
        names=[entity.get("canonical_name"),*entity.get("aliases",[]),*entity.get("identifiers",[])]
        matches=alias.casefold() in [str(x).casefold() for x in names if x]
        has_identity=bool(entity.get("canonical_name") or entity.get("verified_identifier"))
        if matches and has_identity and (entity.get("canonical_name")!=canonical_name or entity.get("verified_identifier") not in {None,identifier}): conflicts.append(entity)
    return conflicts

def ingest_paths(paths, output_dir, registry_path=None, root=None, source_metadata=None):
    registry=load_registry(registry_path); docs=[]
    source_metadata=source_metadata or {}
    for path in paths: docs.append(ingest_file(path,registry,root,**source_metadata.get(str(Path(path)),{})))
    all_records=[r for d in docs for r in d["records"]]
    source_records=[r for d in docs for r in d["source_records"]]
    from .f1_research_angle_selector import validate_output
    schema=Config().schema_path.parent/"evidence_record.schema.json"
    for record in all_records: validate_output(record,schema)
    # Duplicate content is reported; no document or evidence record is discarded.
    hash_groups={}
    for d in docs: hash_groups.setdefault(d["source_sha256"],[]).append(d["source_path"])
    duplicates=[{"source_sha256":h,"source_paths":ps} for h,ps in hash_groups.items() if len(ps)>1]
    warnings=[]
    for r in all_records:
        if not r["publication_date"]: warnings.append({"evidence_id":r["evidence_id"],"warning":"Publication date missing or not extractable."})
        if not r.get("source_url"): warnings.append({"evidence_id":r["evidence_id"],"warning":"No source URL; repository path is the available source locator."})
        if r["company_identity_status"]!="verified": warnings.append({"evidence_id":r["evidence_id"],"warning":"Company identity unresolved; exclude from company-specific joins."})
        if r.get("reporting_period") and re.search(r"\b(?:FY\s*\d{2,4}|Q[1-4]\s*\d{2,4})\b",r["reporting_period"],re.I):
            if not re.search(r"\b(?:20\d{2}|19\d{2})\b",r["reporting_period"]):
                warnings.append({"evidence_id":r["evidence_id"],"warning":"Reporting period may be ambiguous; clarify fiscal/calendar basis."})
    amended=[r["evidence_id"] for r in all_records if re.search(r"\b(amended|revision|revised|supplemental)\b",r["document_title"],re.I)]
    inconsistent={}
    for r in all_records:
        if r.get("metric_name") and (r.get("unit") or r.get("currency")):
            inconsistent.setdefault((r.get("verified_identifier"),r["metric_name"].casefold(),r.get("reporting_period")),set()).add((r.get("unit"),r.get("currency")))
    unit_flags=[{"claim_key":list(k),"unit_currency_pairs":[list(v) for v in vals]} for k,vals in inconsistent.items() if len(vals)>1]
    report={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"source_documents": [{k:v for k,v in d.items() if k not in {"records","source_records"}} for d in docs],
        "document_count":len(docs),"evidence_record_count":len(all_records),"duplicate_documents":duplicates,"repeated_facts":_repeated_facts(all_records),"conflicts":_conflicts(all_records),
        "unit_currency_inconsistencies":unit_flags,"amended_or_revised_document_records":amended,"claim_cross_validation":_cross_validation_summary(all_records),"manual_review_evidence_ids":[r["evidence_id"] for r in all_records if r["parsing_status"]!="parsed" or r["extraction_warnings"]],"data_quality_warnings":warnings}
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    (out/"source_records.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in source_records),encoding="utf-8")
    (out/"evidence.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in all_records),encoding="utf-8")
    (out/"ingestion_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return all_records,report

def main(argv=None):
    cfg=Config(); parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",action="append",default=[],help="CSV, PDF, TXT, or Markdown source; repeat as needed")
    parser.add_argument("--input-dir",help="Ingest supported files directly within this directory")
    parser.add_argument("--output-dir",default=str(cfg.evidence_dir))
    parser.add_argument("--registry",default=str(cfg.registry_path))
    parser.add_argument("--inspect",action="store_true",help="Print normalized evidence records (optionally filtered to a verified company)")
    parser.add_argument("--company",help="For --inspect, include only verified matching company evidence")
    args=parser.parse_args(argv)
    try:
        if args.inspect:
            evidence_path=Path(args.output_dir)/"evidence.jsonl"
            if not evidence_path.is_file(): raise FileNotFoundError(f"Normalized evidence not found: {evidence_path}; run ingestion first.")
            records=[json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if args.company: records=[r for r in records if r.get("company_identity_status")=="verified" and (str(r.get("company_name") or "").casefold()==args.company.casefold() or str(r.get("verified_identifier") or "").casefold()==args.company.casefold())]
            print(json.dumps({"record_count":len(records),"records":records[:100],"truncated":len(records)>100},indent=2,ensure_ascii=False)); return 0
        paths=[Path(x) for x in args.source]
        if args.input_dir: paths.extend(sorted(p for p in Path(args.input_dir).iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED))
        if not paths: parser.error("provide --source or --input-dir")
        records,report=ingest_paths(paths,args.output_dir,args.registry,root=Path.cwd())
        print(f"Ingested {report['document_count']} documents into {len(records)} evidence records; {len(report['manual_review_evidence_ids'])} records flagged for manual review.")
        print(f"Duplicates: {len(report['duplicate_documents'])}; conflicting values: {len(report['conflicts'])}; report: {Path(args.output_dir)/'ingestion_report.json'}")
        return 0
    except (OSError,ValueError,DataLoadError,RuntimeError) as e:
        print(f"Evidence ingestion error: {e}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
