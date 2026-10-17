"""Stage A: reproducible full-archive evaluation of the prose-only and table-aware extractors into a fresh run directory.

Writes run_manifest.json, archive_evaluation_summary.json, archive_evaluation_report.md, duplicate_claim_groups.jsonl and
claim_audit_sample.jsonl. It never modifies earlier outputs, never verifies or approves claims, and calls no network or model.
"""
import argparse
import datetime as dt
import hashlib
import json
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import claim_extraction as L1
from . import table_extraction as T
from .config import ROOT

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def read_jsonl(path): return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]

def run_cmd(cmd, env_pp):
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": env_pp})
    return {"command": " ".join(cmd), "exit_code": p.returncode, "seconds": round(time.time() - t0, 2), "stdout_tail": p.stdout.strip().splitlines()[-2:], "stderr_tail": p.stderr.strip().splitlines()[-3:]}

def summarize(claims):
    by_method = defaultdict(Counter)
    for c in claims: by_method[c.get("extraction_method", "prose_regex")][c["extraction_status"]] += 1
    n = max(len(claims), 1)
    miss = {"metric": sum(c["metric"] is None for c in claims), "unit": sum(c["unit"] is None for c in claims), "period": sum(c["period_type"] == "unknown" for c in claims),
            "entity": sum(c["entity"] is None for c in claims), "source_page": sum(c["source_page"] is None for c in claims), "source_chunk_id": sum(not c["source_chunk_id"] for c in claims),
            "source_excerpt": sum(not c["source_excerpt"] for c in claims)}
    return {"total_claims": len(claims), "status_by_method": {m: dict(c) for m, c in by_method.items()}, "status_total": dict(Counter(c["extraction_status"] for c in claims)),
            "missing_counts": miss, "missing_rates": {k: round(v / n, 4) for k, v in miss.items()},
            "verification_status_values": sorted({c["claim_verification_status"] for c in claims})}

def duplicate_groups(claims):
    """Same metric/value/unit/period/entity-less key seen more than once. Repeats are NOT independent corroboration."""
    groups = defaultdict(list)
    for c in claims:
        if c["metric"] is None or c["value"] is None: continue
        groups[(c["metric"], c["value"], c["unit"], c["period_type"], c["as_of_date"] or c["raw_period_text"])].append(c)
    out = []
    for k, cs in groups.items():
        docs = {c["source_path"] for c in cs}; chunks = {c["source_chunk_id"] for c in cs}
        if len(cs) < 2: continue
        out.append({"key": {"metric": k[0], "value": k[1], "unit": k[2], "period_type": k[3], "period": k[4]}, "claim_count": len(cs), "distinct_chunks": len(chunks), "distinct_documents": len(docs),
                    "claim_ids": [c["claim_id"] for c in cs][:50], "source_paths": sorted(docs)[:10], "independent_corroboration": False,
                    "note": "Repeats of the same figure across chunks/filings of one issuer are not independent corroboration."})
    return sorted(out, key=lambda g: (-g["claim_count"], g["claim_ids"][0]))

STRATA = [
    ("table_extracted", lambda c: c.get("extraction_method") == "table_row" and c["extraction_status"] == "extracted", 99),
    ("prose_extracted", lambda c: c.get("extraction_method") == "prose_regex" and c["extraction_status"] == "extracted", 99),
    ("table_ambiguous_period_unit", lambda c: c.get("extraction_method") == "table_row" and c["extraction_status"] == "ambiguous" and c["period_type"] != "unknown" and c["unit"], 8),
    ("table_ambiguous_other", lambda c: c.get("extraction_method") == "table_row" and c["extraction_status"] == "ambiguous" and not (c["period_type"] != "unknown" and c["unit"]), 5),
    ("prose_ambiguous", lambda c: c.get("extraction_method") == "prose_regex" and c["extraction_status"] == "ambiguous", 8),
    ("high_risk_subsidiary_jv", lambda c: "joint venture" in (c["ambiguity_notes"] or "") or "other organization" in (c["ambiguity_notes"] or "") or "legal entities" in (c["ambiguity_notes"] or ""), 6),
    ("high_risk_forward_looking", lambda c: "forward-looking" in (c["ambiguity_notes"] or ""), 6),
    ("high_risk_reversed_text", lambda c: c.get("reversal_applied") is True, 6),
    ("high_risk_national_scope", lambda c: "national/industry-scope" in (c["ambiguity_notes"] or ""), 4),
    ("high_risk_scale_or_glyph", lambda c: "scale not unambiguous" in (c["ambiguity_notes"] or "") or "backtick" in (c["ambiguity_notes"] or ""), 6)]

def audit_sample(claims, seed=20261018):
    rng = random.Random(seed); chosen = {}; sample = []
    for name, pred, cap in STRATA:
        pool = sorted((c for c in claims if pred(c) and c["claim_id"] not in chosen), key=lambda c: c["claim_id"])
        pick = pool if len(pool) <= cap else rng.sample(pool, cap)
        for c in pick:
            chosen[c["claim_id"]] = name
            sample.append({"stratum": name, "claim_id": c["claim_id"], "extraction_method": c.get("extraction_method"), "extraction_status": c["extraction_status"], "entity": c["entity"], "metric": c["metric"], "raw_metric_text": c["raw_metric_text"],
                           "value": c["value"], "raw_value_text": c["raw_value_text"], "unit": c["unit"], "period_type": c["period_type"], "raw_period_text": c["raw_period_text"], "as_of_date": c["as_of_date"],
                           "source_path": c["source_path"], "source_page": c["source_page"], "source_chunk_id": c["source_chunk_id"], "source_excerpt": c["source_excerpt"][:500],
                           "source_header_text": (c.get("source_header_text") or "")[:300], "ambiguity_notes": c["ambiguity_notes"], "claim_verification_status": c["claim_verification_status"],
                           "stratum_population": sum(1 for x in claims if pred(x)), "audit_result": None, "audit_note": None})
    return sample

def evaluate(run_dir, input_dir, python="python3"):
    run = Path(run_dir); run.mkdir(parents=True, exist_ok=False)
    inp = Path(input_dir); pp = str(ROOT / "src")
    prose_dir, table_dir = run / "prose_only", run / "table_aware"
    cmds = [run_cmd([python, "-m", "signalforge.claim_extraction", "--input-dir", str(inp), "--output-dir", str(prose_dir)], pp),
            run_cmd([python, "-m", "signalforge.table_extraction", "--input-dir", str(inp), "--output-dir", str(table_dir), "--baseline-dir", str(ROOT / "data" / "claims_step1")], pp)]
    manifest = {"run_id": run.name, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "inputs": {str(p): sha256(p) for p in sorted(inp.glob("*.jsonl")) + [inp / "ingestion_report.json"] if p.is_file()},
                "versions": {"claim_extraction": L1.PARSER_VERSION, "table_extraction": T.TABLE_PARSER_VERSION, "claim_schema_version": T.CLAIM_SCHEMA_VERSION, "claim_schema_sha256": sha256(ROOT / "schemas" / "claim.schema.json")},
                "commands": cmds, "outputs_dir": str(run), "parameters": {"audit_seed": 20261018, "table_thresholds": T.TableConfig().__dict__}, "network_used": False, "model_used": False}
    if any(c["exit_code"] not in (0,) for c in cmds):
        (run / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8"); raise RuntimeError("an extraction command failed; see run_manifest.json")
    prose, table = read_jsonl(prose_dir / "claims.jsonl"), read_jsonl(table_dir / "claims.jsonl")
    reports = {"prose_only": json.loads((prose_dir / "extraction_report.json").read_text()), "table_aware": json.loads((table_dir / "extraction_report.json").read_text())}
    summary = {"run_id": run.name, "input_record_count": reports["table_aware"]["input_record_count"], "prose_only": summarize(prose), "table_aware": summarize(table),
               "reports": {k: {x: v.get(x) for x in ("run_status", "failed_chunk_count", "schema_validation_failures", "chunk_classification", "table_rows", "reversal", "claims_by_method", "top_review_reasons", "continuation", "claims_missing") if x in v} for k, v in reports.items()}}
    dups = duplicate_groups(table); (run / "duplicate_claim_groups.jsonl").write_text("".join(json.dumps(d) + "\n" for d in dups), encoding="utf-8")
    summary["duplicate_groups"] = {"groups": len(dups), "groups_spanning_multiple_documents": sum(d["distinct_documents"] > 1 for d in dups), "independent_corroboration_claimed": 0}
    sample = audit_sample(table); (run / "claim_audit_sample.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sample), encoding="utf-8")
    summary["audit_sample"] = {"size": len(sample), "by_stratum": dict(Counter(s["stratum"] for s in sample)), "note": "Audit results are recorded separately in claim_audit_results.csv and never change production claims."}
    (run / "archive_evaluation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest["outputs"] = {f.name: sha256(f) for f in sorted(run.glob("*.json*")) if f.name != "run_manifest.json"}
    manifest["outputs"].update({f"{d.name}/{f.name}": sha256(f) for d in (prose_dir, table_dir) for f in sorted(d.glob("*.json*"))})
    (run / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True); ap.add_argument("--input-dir", default=str(ROOT / "data" / "processed_step6"))
    a = ap.parse_args(argv)
    try: s = evaluate(a.run_dir, a.input_dir)
    except (RuntimeError, FileExistsError, OSError) as e:
        print(f"Archive evaluation error: {e}", file=sys.stderr); return 2
    print(json.dumps({"prose_only": s["prose_only"]["status_total"], "table_aware": s["table_aware"]["status_total"], "audit_sample": s["audit_sample"]["size"], "duplicate_groups": s["duplicate_groups"]}))
    return 0

if __name__ == "__main__": raise SystemExit(main())
