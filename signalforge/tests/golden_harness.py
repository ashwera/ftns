"""Shared harness for the golden claim fixtures (signalforge/tests/fixtures/golden_claims).

Fixture contract (proposed to Codex in COORDINATION.md): chunks.jsonl holds verbatim evidence records,
cases.jsonl holds one case per line. Expected status lists are a CEILING on confidence: an extractor
may be more conservative than `status_allowed` lists but may never exceed it; `forbidden_extracted`
values must not appear as `extracted`; `no_extracted_claims` forbids any `extracted` claim for the case.
"""
import json
import re
from pathlib import Path

from signalforge import claim_extraction as L1
from signalforge import table_extraction as T
from signalforge.f1_research_angle_selector import validate_output

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "golden_claims"
SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "claim.schema.json"

def collapse(s): return re.sub(r"\s+", " ", s or "").strip()

def load():
    chunks = {r["evidence_id"]: r for r in (json.loads(l) for l in (FIXTURES / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
    cases = [json.loads(l) for l in (FIXTURES / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return chunks, cases

def run_extractor(kind, case, chunks):
    target = L1.TargetCompany(case["target_company"]["name"], tuple(case["target_company"]["aliases"]))
    claims = []
    if kind == "prose":
        for cid in case["chunk_ids"]:
            claims += L1.extract_claims(chunks[cid], "doc_golden", target=target)
        return claims, None

    input_ids = case.get("context_chunk_ids", []) + case["chunk_ids"]
    records = [chunks[cid] for cid in input_ids]
    if case.get("order_by_page"):
        records = [rec for _, rec in sorted(enumerate(records), key=lambda pair: (pair[1].get("page_number", -1), pair[0]))]
    paths = {r["source_path"] for r in records}
    doc_bases = {path: any(bool(r.get("document_has_both_standalone_and_consolidated"))
                           for r in records if r["source_path"] == path) for path in paths}
    ctx = T.Ctx(doc_bases=doc_bases)
    extractor = T.make_extractor(ctx, target=target)
    for rec in records:
        claims += extractor(rec, "doc_golden")
    return claims, ctx

def scoped(claims, focus):
    f = collapse(focus)
    return [c for c in claims if f in collapse(c.get("source_row_text") or "") or f in collapse(c["source_excerpt"])]

def evaluate(case, kind, chunks):
    """Return a list of check dicts {name, ok, expected, actual}."""
    claims, ctx = run_extractor(kind, case, chunks); checks = []
    def add(name, ok, expected, actual): checks.append({"name": name, "ok": bool(ok), "expected": expected, "actual": actual})
    allowed_source_chunks = set(case["chunk_ids"] + case.get("context_chunk_ids", []))
    for c in claims:
        try: validate_output(c, SCHEMA); ok = c["claim_verification_status"] == "unverified" and c["source_chunk_id"] in allowed_source_chunks and c["source_path"] == chunks[c["source_chunk_id"]]["source_path"]
        except ValueError as e: ok = False
        if not ok: add("schema_unverified_provenance", False, "valid, unverified, provenance preserved", c["claim_id"])
    if not any(ch["name"] == "schema_unverified_provenance" for ch in checks): add("schema_unverified_provenance", True, "valid, unverified, provenance preserved", f"{len(claims)} claims")
    if case["expected"]["no_extracted_claims"]:
        # Context chunks may contain valid neighboring claims; this expectation
        # applies to the primary chunk(s), while context only informs alignment.
        bad = [(c["raw_value_text"], c["raw_metric_text"]) for c in claims
               if c["source_chunk_id"] in case["chunk_ids"] and c["extraction_status"] == "extracted"]
        add("no_extracted_claims", not bad, "no extracted claim", bad[:5] or "none")
    for f in case["expected"]["forbidden_extracted"]:
        hits = [c for c in scoped(claims, f["focus"]) if c["source_chunk_id"] in case["chunk_ids"]
                and c["value"] is not None and abs(c["value"] - f["value"]) < 1e-9]
        bad = [c for c in hits if c["extraction_status"] == "extracted"]
        add(f"forbidden_extracted[{f['value']}]", not bad, "never `extracted`", [(c["extraction_status"], c["metric"]) for c in hits] or "not emitted")
    for e in case["expected"]["claims"]:
        hits = [c for c in scoped(claims, e["focus"]) if c["value"] is not None and abs(c["value"] - e["value"]) < 1e-9]
        if e["period_text"]:
            ph = [c for c in hits if collapse(e["period_text"]).lower() in collapse(c["raw_period_text"] or "").lower()]
            hits = ph or hits
        name = f"expected[{e['value']}]"
        must_exist = e["status_allowed"] == ["extracted"] or e.get("must_emit", False)
        if not hits: add(name, not must_exist, f"present, status in {e['status_allowed']}", "absent"); continue
        if e.get("source_chunk_id") is not None:
            hits = [c for c in hits if c["source_chunk_id"] == e["source_chunk_id"]]
            if not hits: add(name, False, f"source chunk {e['source_chunk_id']}", "claim from another chunk or absent"); continue
        c = hits[0]; ok = c["extraction_status"] in e["status_allowed"]; detail = [c["extraction_status"]]
        if e["metric"] and c["metric"] not in (e["metric"], None) and not (c["metric"] == "capacity" and re.match(r"(?:capacity|installed_capacity|commercial_capacity)", e["metric"])): ok = False; detail.append(f"metric {c['metric']!r} != {e['metric']!r}")
        rmc = e.get("raw_metric_contains")
        if rmc and c["raw_metric_text"] and collapse(rmc).lower() not in collapse(c["raw_metric_text"]).lower(): ok = False; detail.append(f"label {c['raw_metric_text']!r} lacks {rmc!r}")
        if c["extraction_status"] == "extracted" or e.get("must_emit", False):
            for k, want, got in (("unit", e["unit"], c["unit"]), ("period_type", e["period_type"], c["period_type"]), ("as_of_date", e["as_of_date"], c["as_of_date"])):
                if want != got: ok = False; detail.append(f"{k} {got!r} != {want!r}")
            if e.get("period_text") is not None and collapse(e["period_text"]) != collapse(c["raw_period_text"] or ""):
                ok = False; detail.append(f"period text {c['raw_period_text']!r} != {e['period_text']!r}")
            if e.get("source_chunk_id") is not None and c["source_chunk_id"] != e["source_chunk_id"]:
                ok = False; detail.append(f"source chunk {c['source_chunk_id']!r} != {e['source_chunk_id']!r}")
            expected_header = e.get("source_header_chunk_id")
            row_matches = [m for m in (ctx.continuation_matches if ctx else []) if m["row_chunk_id"] == c["source_chunk_id"]]
            if expected_header:
                if not any(m["header_chunk_id"] == expected_header for m in row_matches):
                    ok = False; detail.append(f"header source {[(m['header_chunk_id']) for m in row_matches]!r} != {expected_header!r}")
            elif "source_header_chunk_id" in e and row_matches:
                ok = False; detail.append(f"unexpected attached header {[(m['header_chunk_id']) for m in row_matches]!r}")
            if e["entity"] == "target" and c["entity"] != case["target_company"]["name"]: ok = False; detail.append(f"entity {c['entity']!r}")
            if e["entity"] not in ("target", None) and c["entity"] != e["entity"]: ok = False; detail.append(f"entity {c['entity']!r}")
            if e.get("must_emit") and e["entity"] is None and c["entity"] is not None: ok = False; detail.append(f"entity {c['entity']!r} should remain unresolved")
        add(name, ok, f"status in {e['status_allowed']}, " + f"{e['unit']} {e['period_text']}", "; ".join(detail))
    if case["case_id"] in {"GC-34", "GC-35", "GC-36", "GC-37"}:
        row_ids = {e["source_chunk_id"] for e in case["expected"]["claims"]}
        actual = sorted((c["source_chunk_id"], c["metric"], c["value"], c["unit"], c["period_type"], c["raw_period_text"], c["as_of_date"])
                        for c in claims if c.get("extraction_method") == "table_row" and c["source_chunk_id"] in row_ids)
        expected = sorted((e["source_chunk_id"], e["metric"], e["value"], e["unit"], e["period_type"], e["period_text"], e["as_of_date"])
                          for e in case["expected"]["claims"])
        add("exact_claim_set", actual == expected, expected, actual)
    return checks

def run_all():
    chunks, cases = load(); results = []
    for case in cases:
        for kind in case["applies_to"]:
            checks = evaluate(case, kind, chunks)
            results.append({"case_id": case["case_id"], "category": case["category"], "extractor": kind, "synthetic": case["synthetic"], "xfail": case.get("xfail"), "checks": checks, "passed": all(c["ok"] for c in checks)})
    return results

def report_markdown(results):
    lines = ["| Case | Category | Extractor | Result | Failing checks (expected vs actual) |", "|---|---|---|---|---|"]
    for r in results:
        res = ("XFAIL (accepted gap)" if not r["passed"] else "XPASS") if r["xfail"] else ("PASS" if r["passed"] else "FAIL")
        bad = "; ".join(f"{c['name']}: want {c['expected']} / got {c['actual']}" for c in r["checks"] if not c["ok"])
        lines.append(f"| {r['case_id']}{' (synthetic)' if r['synthetic'] else ''} | {r['category']} | {r['extractor']} | {res} | {bad} |")
    return "\n".join(lines)


def detail_markdown(results):
    out = []
    for r in results:
        res = ("XFAIL (accepted gap: %s)" % r["xfail"] if not r["passed"] else "XPASS") if r["xfail"] else ("PASS" if r["passed"] else "FAIL")
        out.append(f"### {r['case_id']} · {r['category']} · {r['extractor']} extractor · **{res}**" + (" · synthetic" if r["synthetic"] else ""))
        out.append("| Check | Result | Expected | Actual |\n|---|---|---|---|")
        for c in r["checks"]: out.append(f"| {c['name']} | {'ok' if c['ok'] else 'FAIL'} | {str(c['expected']).replace('|', '/')} | {str(c['actual']).replace('|', '/')} |")
        out.append("")
    return "\n".join(out)

if __name__ == "__main__":
    import sys
    res = run_all()
    if "--detail" in sys.argv: print(detail_markdown(res))
    else: print(report_markdown(res))
    print(f"\n{sum(r['passed'] for r in res)}/{len(res)} case x extractor runs passed")
