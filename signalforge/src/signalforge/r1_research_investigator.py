"""R1 research-plan runner. Consumes F1 output and supplied evidence IDs; performs no retrieval."""
import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .f1_research_angle_selector import _validate
from .llm_client import LLMError, generate_json

def validate_plan(plan, schema_path, supplied_ids=()):
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    errors = _validate(plan, schema)
    known = set(supplied_ids)
    for i, item in enumerate(plan.get("evidence_ledger", []) if isinstance(plan, dict) else []):
        eid = item.get("evidence_id") if isinstance(item, dict) else None
        if eid is not None and eid not in known: errors.append(f"$/evidence_ledger/{i}: evidence_id {eid!r} was not supplied")
        if isinstance(item, dict) and item.get("status") == "planned_lookup" and (item.get("source_url") or item.get("excerpt_or_data_point")):
            errors.append(f"$/evidence_ledger/{i}: planned lookup must not contain a URL or excerpt")
    if errors: raise ValueError("R1 output failed validation: " + "; ".join(errors))
    return plan

def select_candidate(f1):
    cid = f1.get("recommended_candidate_id")
    if not cid: raise ValueError("F1 output has no recommended candidate")
    cand = next((c for c in f1.get("ranked_candidates", []) if c.get("candidate_id") == cid), None)
    if cand is None: raise ValueError(f"Recommended candidate {cid!r} not found in F1 output")
    return cand

def load_evidence_ids(path, company):
    p = Path(path)
    if not p.exists(): return []
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r["evidence_id"] for r in rows if r.get("company_identity_status") == "verified" and str(r.get("company_name") or "").casefold() == company.casefold()]

def run(f1_path, output_path, config=None):
    config = config or Config()
    f1 = json.loads(Path(f1_path).read_text(encoding="utf-8"))
    if not f1.get("ranking_reliable"): raise ValueError("F1 ranking is not reliable; R1 will not plan from it")
    cand = select_candidate(f1)
    ids = load_evidence_ids(config.evidence_dir / "evidence.jsonl", f1["company_name"])
    prompt = (config.prompt_dir / "r1_research_investigator.md").read_text(encoding="utf-8")
    payload = {"company_name": f1["company_name"], "candidate": cand, "dataset_summary": f1.get("dataset_summary"), "supplied_evidence_ids": ids}
    plan = generate_json(prompt, payload, config)
    plan["retrieval_performed"] = False
    validate_plan(plan, config.schema_path.with_name("r1_output.schema.json"), ids)
    out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"R1 plan saved to {out} ({len(plan['checklist'])} steps; no retrieval performed)")
    return plan

def main(argv=None):
    config = Config()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--f1", default=str(config.output_dir / "f1_output.json"))
    ap.add_argument("--output", default=str(config.output_dir / "r1_plan.json"))
    args = ap.parse_args(argv)
    try: run(args.f1, args.output, config); return 0
    except (FileNotFoundError, ValueError, LLMError, OSError) as e:
        print(f"R1 error: {e}", file=sys.stderr); return 2

if __name__ == "__main__":
    raise SystemExit(main())
