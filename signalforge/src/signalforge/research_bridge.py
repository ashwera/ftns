"""Stage C bridge: claims -> small traceable evidence bundle -> F1 -> R1 (plan only).

The F1/R1 eligibility logic and credential guard are used unchanged. When no API key is configured the live call raises
LLMError (reported as blocked). `simulated_f1` / `simulated_r1` are deterministic stand-ins for offline integration only;
their output labels itself SIMULATED and they never make a model or network call.
"""
import dataclasses
import json
import re
from pathlib import Path
from unittest import mock

from . import f1_research_angle_selector as f1
from . import r1_research_investigator as r1
from .config import Config
from .pipeline_contract import read_jsonl, write_json

FAMILIES = {"capacity_conversion": re.compile(r"(?i)capacity|under_construction|awarded|commission|pipeline|implementation"),
            "renewable_transition": re.compile(r"(?i)renew|solar|wind|\bRE\b|green|hydro|nuclear|non-fossil"),
            "hidden_relationships": re.compile(r"(?i)joint venture|subsidiar|related part|associate")}
SIM_TAG = "SIMULATED: deterministic stand-in, no model call; ordering reflects evidence counts only."

def select_bundle(claims, evidence_by_id, *, statuses=("extracted", "ambiguous"), max_claims=40, per_chunk=4):
    """Pick a small set of claims (never the whole archive). Only parsed chunks whose identity is verified are eligible."""
    picked, per = [], {}
    def key(c): return (0 if c["extraction_status"] == "extracted" else 1, c["unit"] is None, c["period_type"] == "unknown", c["claim_id"])
    for c in sorted((c for c in claims if c["extraction_status"] in statuses), key=key):
        rec = evidence_by_id.get(c["source_chunk_id"])
        if not rec or rec.get("company_identity_status") != "verified" or rec.get("parsing_status") != "parsed": continue
        text = " ".join(filter(None, [c.get("metric"), c.get("raw_metric_text"), c["source_excerpt"]]))
        fam = [n for n, rx in FAMILIES.items() if rx.search(text)]
        if not fam or per.get(c["source_chunk_id"], 0) >= per_chunk: continue
        picked.append({**c, "_families": fam}); per[c["source_chunk_id"]] = per.get(c["source_chunk_id"], 0) + 1
        if len(picked) >= max_claims: break
    ids = sorted({c["source_chunk_id"] for c in picked})
    return {"claims": picked, "evidence_records": [evidence_by_id[i] for i in ids], "limits": {"max_claims": max_claims, "per_chunk": per_chunk, "statuses": list(statuses)}}

def write_bundle(bundle, bundle_dir):
    d = Path(bundle_dir); d.mkdir(parents=True, exist_ok=True)
    (d / "evidence.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in bundle["evidence_records"]), encoding="utf-8")
    write_json(d / "bundle_manifest.json", {"claim_ids": [c["claim_id"] for c in bundle["claims"]], "evidence_ids": [r["evidence_id"] for r in bundle["evidence_records"]], "limits": bundle["limits"],
                                           "note": "Claims remain unverified; the bundle is a bounded, traceable selection, not an approval."})
    return d

def simulated_f1(prompt, payload, config):
    ev = payload["verified_ingested_evidence"]; cands = []
    for fam in FAMILIES:
        hits = [e for e in ev if FAMILIES[fam].search(e["excerpt_or_fact"])]
        if not hits: continue
        found = [{"statement": re.sub(r"\s+", " ", e["excerpt_or_fact"])[:160], "source_type": "ingested_annual_report_text", "source_url": None, "date": None, "row_identifier": e["source_locator"], "evidence_id": e["evidence_id"], "status": "observed_in_ingested_source"} for e in hits[:3]]
        s = {"financial_significance": 3, "evidence_availability": min(5, 1 + len(hits)), "testability": 3, "non_obviousness": 2, "cross_validation_potential": 2}
        cands.append({"candidate_id": f"sim_{fam}", "rank": 0, "category": fam, "hypothesis": f"[{fam}] Reported narrative and disclosed figures can be compared for consistency using the supplied evidence.",
                      "financial_importance": "Placeholder from the simulated stand-in; not a model judgement.", "metrics_and_periods": ["as disclosed in the supplied evidence"], "evidence_found": found,
                      "additional_evidence_needed": ["primary-source check of every figure", "independent corroboration"], "alternative_explanation": "Definitions or reporting bases may differ between disclosures.",
                      "falsification_condition": "Figures fail to reconcile on a common basis and period.", "data_risks_and_limitations": [SIM_TAG], "scores": {k: {"score": v, "rationale": "simulated"} for k, v in s.items()},
                      "weighted_score": round(f1.weighted_score(s), 2), "weighted_score_rationale": "simulated; f1.weighted_score over fixed placeholder scores", "next_research_action": "Retrieve the primary filings and verify the inputs."})
    cands.sort(key=lambda c: (-c["weighted_score"], c["candidate_id"]))
    for i, c in enumerate(cands, 1): c["rank"] = i
    return {"company_name": payload["company"], "dataset_summary": {"row_count": 0, "columns": [], "date_coverage": None, "missing_information": ["live model ranking"], "data_limitations": [SIM_TAG]},
            "ranking_reliable": bool(cands), "ranking_limitation": SIM_TAG, "ranked_candidates": cands, "recommended_candidate_id": cands[0]["candidate_id"] if cands else None}

def simulated_r1(prompt, payload, config):
    c = payload["candidate"]; ids = payload["supplied_evidence_ids"]
    ledger = [{"evidence_id": e["evidence_id"], "source_type": e["source_type"], "source_url": None, "publication_date": None, "excerpt_or_data_point": e["statement"], "claim_supported": c["hypothesis"], "kind": "unverified_hypothesis", "status": "supplied"} for e in c["evidence_found"] if e.get("evidence_id") in ids]
    ledger.append({"evidence_id": None, "source_type": "annual_report_or_exchange_filing", "source_url": None, "publication_date": None, "excerpt_or_data_point": None, "claim_supported": c["hypothesis"], "kind": "unverified_hypothesis", "status": "planned_lookup"})
    return {"company_name": payload["company_name"], "candidate_id": c["candidate_id"], "hypothesis": c["hypothesis"] + " " + SIM_TAG, "retrieval_performed": False,
            "research_questions": [{"question": "Do the disclosed figures reconcile on a common basis and period?", "metrics": c["metrics_and_periods"], "periods": ["latest disclosed"], "supported_by_dataset": True, "missing": c["additional_evidence_needed"]}],
            "evidence_ledger": ledger, "checklist": [{"step": "Locate each input in the primary filing", "expected_evidence": "page/table with value, unit, period, basis", "cross_validation_sources": ["exchange filing", "regulator data"], "calculation": None, "completion_criteria": "every input has a verification result"},
                                                      {"step": "Compute the comparison with deterministic code", "expected_evidence": "calculation trace", "cross_validation_sources": [], "calculation": "see signals module", "completion_criteria": "compatibility checks pass"}],
            "alternative_explanation": c["alternative_explanation"], "falsification_test": c["falsification_condition"]}

def run_f1_r1(company, bundle_dir, out_dir, *, config=None, simulate=False):
    """Run F1 then R1 against a bundle directory. Returns {stage: {...}}. Never bypasses the eligibility gate or the credential guard."""
    base = config or Config(); cfg = dataclasses.replace(base, evidence_dir=Path(bundle_dir)); out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    stages = {}
    f1_path, r1_path = out / "f1_output.json", out / "r1_plan.json"
    ctx1 = mock.patch.object(f1, "generate_json", simulated_f1) if simulate else mock.patch.object(f1, "generate_json", f1.generate_json)
    ctx2 = mock.patch.object(r1, "generate_json", simulated_r1) if simulate else mock.patch.object(r1, "generate_json", r1.generate_json)
    try:
        with ctx1: f1.run(company, str(cfg.csv_path), f1_path, cfg)
        stages["f1"] = {"execution": "simulated" if simulate else "real", "output": str(f1_path)}
    except (f1.DataLoadError, f1.LLMError, ValueError, OSError) as e:
        stages["f1"] = {"execution": "blocked", "error": f"{type(e).__name__}: {e}"}; stages["r1"] = {"execution": "not_executed", "reason": "F1 did not produce an output"}; return stages
    try:
        with ctx2: r1.run(f1_path, r1_path, cfg)
        stages["r1"] = {"execution": "simulated" if simulate else "real", "output": str(r1_path), "retrieval_performed": False}
    except (ValueError, f1.LLMError, OSError) as e:
        stages["r1"] = {"execution": "blocked", "error": f"{type(e).__name__}: {e}"}
    return stages
