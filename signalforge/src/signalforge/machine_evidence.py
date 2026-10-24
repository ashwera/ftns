"""Deterministic PDF evidence, distinct from human approval and claim verification.

Generic recovered-source procedure: preserve the original PDF; obtain its expected
SHA-256 from the source manifest independently of this helper; supply a verified
registry, an exact issuer declaration (canonical name and identifier), its physical
1-based PDF page, and at most 40 exact page passages. Call
``create_machine_records(pdf, expected_sha256=..., company=..., registry=...,
issuer_page=..., issuer_passage=..., passages=[(page, passage), ...])`` and serialize
the returned records to a NEW evidence store. This function never writes sources,
changes human review fields on existing records, or certifies numerical claims.

Eligibility reopens the pinned bytes and repeats the checks. Hashes detect stale
or altered records; they are not signatures or proof of publisher authenticity.
Source provenance and the registry remain trusted operator inputs. Machine checks
do not establish independent corroboration or justify Strong/Moderate findings.
"""
from dataclasses import asdict
import argparse
import datetime as dt
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from .evidence_ingestion import _record, verify_company, load_registry

POLICY = "pdf_exact_passage_v1"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_PAGES = 1000
MAX_PASSAGE_BYTES = 4000
MAX_RECORDS = 40
CHECKS = {
    "original_sha256": True, "verbatim_page_passage": True,
    "canonical_issuer": True, "substantive_text": True,
}


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _digest(record):
    data = {**record, "machine_verification": dict(record["machine_verification"])}
    data["machine_verification"].pop("record_sha256", None)
    return _sha(json.dumps(data, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False).encode("utf-8"))


def _substantive(text):
    # Reject headings, page fragments, numeric debris and empty/scanned pages.
    return (isinstance(text, str) and 40 <= len(text.encode("utf-8")) <= MAX_PASSAGE_BYTES
            and len(re.findall(r"[^\W\d_]{2,}", text, re.UNICODE)) >= 8)


def _read_source(path, expected_sha256):
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("A pinned original SHA-256 is required")
    with Path(path).open("rb") as source:
        data = source.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("Source must be a bounded original PDF")
    if _sha(data) != expected_sha256:
        raise ValueError("Original PDF hash mismatch")
    return data


def _read_pdf_pages(data, page_numbers):
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or oversized PDF is ineligible")
    result = {}
    for number in page_numbers:
        if type(number) is not int or not 1 <= number <= len(reader.pages):
            raise ValueError("Invalid physical PDF page")
        text = reader.pages[number - 1].extract_text() or ""
        if len(text.encode("utf-8")) > 250_000:
            raise ValueError("PDF page text exceeds extraction limit")
        result[number] = text
    return result


def _issuer_matches(passage, name, identifier):
    if not all(isinstance(s, str) and s.strip() for s in (passage, name, identifier)):
        return False
    # A name in a subsidiary list or unrelated discussion cannot identify issuer.
    declaration = re.search(
        r"(?:name\s+of\s+(?:the\s+)?(?:entity|company)|issuer(?:\s+name)?)\s*[:|\-]?\s*"
        + re.escape(name) + r"(?!\w)", passage, re.IGNORECASE)
    equity_isin = re.search(
        r"ISIN\s+of\s+the\s+Equity\s+Shares\s+of\s+" + re.escape(name)
        + r"\s+is\s*[-–—:]?\s*" + re.escape(identifier) + r"(?!\w)", passage, re.I)
    # Generic layout: the issuer's own name and an "ISIN" label sit within ~200
    # characters of the identifier (cover page, corporate information, shareholder
    # information). Requires the label, so a bare identifier in a table never counts.
    labelled = re.search(
        r"ISIN(?:\s+(?:No\.?|Number|Code))?\s*(?:of\s+(?:the\s+)?(?:equity\s+)?(?:shares|company))?[\s\S]{0,450}?"
        + re.escape(identifier) + r"(?!\w)", passage, re.I) and re.search(
        r"(?<!\w)" + re.escape(name) + r"(?!\w)", passage, re.I)
    corporate = (re.fullmatch(r"[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}", identifier)
        and re.search(r"(?:\bCIN\b|Corporate\s+Identi(?:ty|fication)\s+Number)\s*[:|\-]?\s*" + re.escape(identifier), passage, re.I)
        and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", passage, re.I))
    return bool(equity_isin or labelled or corporate or (declaration and re.search(
        r"(?<!\w)" + re.escape(identifier) + r"(?!\w)", passage, re.I)))


def _check_source(record, canonical_name, identifier):
    metadata = record["machine_verification"]
    page = record["page_number"]
    issuer_page = metadata["issuer_page"]
    passage = record["excerpt_or_fact"]
    if type(page) is not int or type(issuer_page) is not int:
        raise ValueError("Physical page numbers required")
    if not _substantive(passage) or not _issuer_matches(metadata["issuer_passage"], canonical_name, identifier):
        raise ValueError("Substantive passage and canonical issuer declaration required")
    if not 1 <= len(metadata["issuer_passage"].encode("utf-8")) <= MAX_PASSAGE_BYTES:
        raise ValueError("Issuer passage exceeds limit")
    data = _read_source(record["source_path"], metadata["source_sha256"])
    pages = _read_pdf_pages(data, {page, issuer_page})
    if passage not in pages[page] or metadata["issuer_passage"] not in pages[issuer_page]:
        raise ValueError("Passage does not match its original PDF page verbatim")
    if metadata["passage_sha256"] != _sha(passage.encode("utf-8")):
        raise ValueError("Passage hash mismatch")


def machine_evidence_eligible(record, canonical_name, verified_identifier):
    """Fail closed on absent, stale, forged-label-only or unreadable evidence."""
    try:
        if record.get("review_status") != "automatically_cross_checked":
            return False
        if any(record.get(k) is not None for k in ("reviewed_by", "reviewed_at", "review_note")):
            return False
        if (record.get("company_identity_status") != "verified"
                or record.get("company_name") != canonical_name
                or record.get("verified_identifier") != verified_identifier
                or record.get("parsing_status") != "parsed"
                or record.get("document_type") != "pdf"
                or record.get("source_relationship") != "original_disclosure"
                or record.get("source_organization") != canonical_name
                or record.get("claim_verification_status") != "unverified"
                or record.get("information_type") != "reported_fact"
                or record.get("source_locator") != f"page:{record.get('page_number')}"):
            return False
        metadata = record["machine_verification"]
        if (metadata["policy_version"] != POLICY or metadata["verifier"] != "signalforge.machine_evidence"
                or metadata["checks"] != CHECKS
                or not all(value is True for value in metadata["checks"].values())):
            return False
        timestamp = dt.datetime.fromisoformat(metadata["verified_at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return False
        if metadata["record_sha256"] != _digest(record):
            return False
        _check_source(record, canonical_name, verified_identifier)
        return True
    except Exception:
        # Parser/import/filesystem failures must never open the model gate.
        return False


def create_machine_records(pdf_path, *, expected_sha256, company, registry,
                           issuer_page, issuer_passage, passages):
    """Return new bounded machine records; reject the entire batch on any failure.

    ``passages`` is a sequence of (physical_page_number, exact_passage) pairs.
    No normalization, OCR, table inference, dates or human approval is invented.
    The issuer declaration must be present in the original document itself.
    """
    name, identifier, status = verify_company(company, registry)
    if status != "verified" or not name or not identifier:
        raise ValueError("Canonical registry-verified name and identifier required")
    if not isinstance(passages, (list, tuple)) or not 1 <= len(passages) <= MAX_RECORDS:
        raise ValueError("Supply between 1 and 40 explicit passages")
    path = str(Path(pdf_path).resolve())
    _read_source(path, expected_sha256)
    records = []
    seen = set()
    for page, passage in passages:
        record = asdict(_record(expected_sha256, f"page:{page}", passage,
            source_path=path, company_name=name, verified_identifier=identifier,
            company_identity_status="verified", source_organization=name,
            document_title=Path(path).name, document_type="pdf", page_number=page,
            source_relationship="original_disclosure", review_status="automatically_cross_checked",
            extraction_warnings=["Machine passage match only; claims and table interpretation remain unverified."
                                 " No independent corroboration established."]))
        record["machine_verification"] = {
            "policy_version": POLICY, "verifier": "signalforge.machine_evidence",
            "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_sha256": expected_sha256, "passage_sha256": _sha(passage.encode("utf-8")),
            "issuer_page": issuer_page, "issuer_passage": issuer_passage,
            "checks": dict(CHECKS),
        }
        _check_source(record, name, identifier)
        record["machine_verification"]["record_sha256"] = _digest(record)
        if record["evidence_id"] in seen:
            raise ValueError("Duplicate machine passage")
        seen.add(record["evidence_id"])
        records.append(record)
    return records


def create_machine_evidence(original_pdf, company, config, *, expected_sha256=None,
                            pages=None, max_records=16, research_question=None):
    """Scan a full PDF and return bounded, exact machine evidence records.

    ``config`` supplies registry_path only; credentials are never read here.
    An optional independently pinned hash is preferred. Without one, the original
    bytes' SHA-256 becomes the immutable baseline at intake. Neither proves the
    publisher's authenticity. ``pages`` optionally restricts candidate physical
    pages, while issuer discovery scans the full bounded original. Otherwise a
    deterministic generic financial/operating vocabulary ranks candidate pages.
    This is passage selection, not fact extraction or independent verification.
    """
    if type(max_records) is not int or not 1 <= max_records <= MAX_RECORDS:
        raise ValueError("max_records must be between 1 and 40")
    registry = load_registry(config.registry_path)
    name, identifier, status = verify_company(company, registry)
    if status != "verified" or not name or not identifier:
        raise ValueError("Canonical registry-verified identity required")
    if pages is not None and (not isinstance(pages, (list, tuple)) or not pages
            or len(pages) > MAX_RECORDS or any(type(p) is not int or p < 1 for p in pages)):
        raise ValueError("pages must contain 1 to 40 positive physical page numbers")
    path = Path(original_pdf).resolve()
    if expected_sha256 is None:
        with path.open("rb") as source:
            original = source.read(MAX_SOURCE_BYTES + 1)
        if len(original) > MAX_SOURCE_BYTES:
            raise ValueError("Original PDF exceeds size bound")
        expected_sha256 = _sha(original)
    data = _read_source(path, expected_sha256)
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or oversized PDF is ineligible")
    if pages and any(p > len(reader.pages) for p in pages):
        raise ValueError("Requested page exceeds original PDF")
    issuer = None
    candidates = []
    terms = r"\b(?:capacity|generation|renewable|revenue|profit|debt|cash|capital|commissioned|pipeline|risk|subsidiar\w*|joint venture)\b"
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if len(text.encode("utf-8")) > 250_000:
            continue
        # Preserve exact bytes of text; never fold whitespace in the stored passage.
        if issuer is None:
            for match in re.finditer(re.escape(identifier), text, re.I):
                snippet = text[max(0, match.start() - 1200):match.end() + 300]
                if _issuer_matches(snippet, name, identifier):
                    issuer = (number, snippet)
                    break
        if pages is not None and number not in pages:
            continue
        passage = text.encode("utf-8")[:3500].decode("utf-8", errors="ignore")
        if _substantive(passage):
            score = len(re.findall(terms, passage, re.I))
            candidates.append((score, number, passage))
    if issuer is None:
        raise ValueError("No explicit canonical issuer/identifier declaration in original PDF")
    if pages is not None:
        if {p for _, p, _ in candidates} != set(pages):
            raise ValueError("Requested page has no substantive parsed text")
        selected = sorted(candidates, key=lambda item: item[1])[:max_records]
    else:
        if research_question:
            words = set(re.findall(r"[a-z]{4,}", research_question.lower())) - {"whether", "company", "limited", "which", "their", "sources", "research", "evidence", "with", "from", "compare", "find"}
            matches = [{w for w in words if re.search(r"\b" + re.escape(w), passage, re.I)} for _, _, passage in candidates]
            counts = {w: sum(w in m for m in matches) for w in words}
            candidates = [(sum(1 / counts[w] for w in match), number, passage)
                          for (_, number, passage), match in zip(candidates, matches)]
        selected = sorted(candidates, key=lambda item: (-item[0], item[1]))[:max_records]
        selected.sort(key=lambda item: item[1])
    return create_machine_records(path, expected_sha256=expected_sha256, company=company,
        registry=registry, issuer_page=issuer[0], issuer_passage=issuer[1],
        passages=[(number, passage) for _, number, passage in selected])


def main(argv=None):
    """Emit machine records to a fresh output directory; never replace a store."""
    from .config import Config
    from .f1_research_angle_selector import validate_output
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-pdf", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--registry", default=str(Config().registry_path))
    parser.add_argument("--expected-sha256")
    parser.add_argument("--pages", type=int, nargs="+", help="Physical PDF pages, at most 40")
    parser.add_argument("--max-records", type=int, default=16)
    args = parser.parse_args(argv)
    from dataclasses import replace
    config = replace(Config(), registry_path=Path(args.registry))
    out = Path(args.output_dir)
    try:
        if out.exists():
            raise ValueError("Output directory already exists; choose a fresh directory")
        records = create_machine_evidence(args.original_pdf, args.company, config,
            expected_sha256=args.expected_sha256, pages=args.pages, max_records=args.max_records)
        for record in records:
            validate_output(record, config.schema_path.parent / "evidence_record.schema.json")
        out.mkdir(parents=True, exist_ok=False)
        (out / "evidence.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        print(f"Created {len(records)} automatically_cross_checked records in {out}; claims remain unverified.")
        return 0
    except Exception as error:
        print(f"Machine evidence error ({type(error).__name__}): {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
