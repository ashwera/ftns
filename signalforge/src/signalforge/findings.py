"""Evidence-based finding adjudication and ranking (provisional, configurable rubric - not statistically calibrated).

Possible results: supported_finding, provisional_hypothesis, no_defensible_signal. The absence of a signal is a valid result.
Duplicate documents and same-publisher repeats count once; contradictions lower the score and can block publication.
"""
import re

from .claim_verification import assess_independence
from .pipeline_contract import collapse, validate_against

RUBRIC = {
    "status": "PROVISIONAL - transparent initial weights, no calibration data",
    "strength_rules": {
        "None": "no computed calculation, or any key input contradicted/unresolved/unverified",
        "Weak": "all key inputs at least partially_supported, but verification is extracted_text_review only (no primary-source check) or some input is partial",
        "Moderate": "all key inputs confirmed at primary_source level, no contradiction",
        "Strong": "Moderate plus >=2 independent sources, passing cross-checks and no missing inputs"},
    "materiality_threshold": 10.0,          # percentage points; below this the effect is not material for a finding
    "weights": {"strength": 40, "materiality": 25, "corroboration": 15, "recency": 10, "consistency": 10},
    "strength_value": {"None": 0.0, "Weak": 0.4, "Moderate": 0.75, "Strong": 1.0},
    "materiality_full_at": 50.0,            # percentage points that earn full materiality credit
    "provisional_rank_cap": 49.0, "no_signal_rank_cap": 10.0,   # a provisional hypothesis never outranks a supported finding
    "contradiction_penalty": 15.0, "max_penalty": 30.0,
    "recency_years": [(1, 1.0), (2, 0.7), (4, 0.4)], "recency_floor": 0.1}

def evidence_strength(inputs_used, verifications, calculations, sources, *, contradictions=0):
    comps = [c for c in calculations if c["status"] == "computed"]
    if not comps or contradictions or any(v["outcome"] in ("contradicted", "unresolved", "unable_to_verify") for v in verifications): return "None"
    primary = all(v["outcome"] == "confirmed" and v["verification_level"] == "primary_source" for v in verifications)
    if not primary: return "Weak"
    ind = assess_independence(sources)["independent_source_count"]
    cross_ok = all(x["ok"] for v in verifications for x in v["cross_checks"])
    if ind >= 2 and cross_ok and not any(c["missing_inputs"] for c in calculations): return "Strong"
    return "Moderate"

def recency_score(latest_year, reference_year):
    if latest_year is None or reference_year is None: return RUBRIC["recency_floor"]
    age = reference_year - latest_year
    for limit, score in RUBRIC["recency_years"]:
        if age <= limit: return score
    return RUBRIC["recency_floor"]

def rank(strength, materiality_pp, independent_count, consistency, latest_year, reference_year, contradictions):
    w = RUBRIC["weights"]
    comps = {"strength": w["strength"] * RUBRIC["strength_value"][strength], "materiality": w["materiality"] * min(abs(materiality_pp) / RUBRIC["materiality_full_at"], 1.0),
             "corroboration": w["corroboration"] * min(independent_count / 3, 1.0), "recency": w["recency"] * recency_score(latest_year, reference_year), "consistency": w["consistency"] * consistency}
    penalty = min(RUBRIC["contradiction_penalty"] * contradictions, RUBRIC["max_penalty"]); comps["contradiction_penalty"] = -penalty
    return round(max(0.0, min(100.0, sum(comps.values()))), 2), {k: round(v, 3) for k, v in comps.items()}

def adjudicate(*, finding_id, run_id, company, headline, why_it_matters, materiality_pp, inputs, verifications, calculations, sources, supporting_evidence, contradictory_evidence=(),
               alternative_explanations, falsification_conditions, missing_evidence=(), limitations=(), stage_provenance, claims_all_unverified, synthetic=False, reference_year=None, periods=()):
    contradictions = len(contradictory_evidence) + sum(v["outcome"] == "contradicted" for v in verifications)
    strength = evidence_strength(inputs, verifications, calculations, sources, contradictions=contradictions)
    checks = [c["ok"] for calc in calculations for c in calc["compatibility_checks"]] + [x["ok"] for v in verifications for x in v["cross_checks"]]
    consistency = (sum(checks) / len(checks)) if checks else 0.0
    years = [int(i["as_of_date"][:4]) for i in inputs if i.get("as_of_date")]
    ind = assess_independence(sources)["independent_source_count"] if sources else 0
    score, comps = rank(strength, materiality_pp, ind, consistency, max(years) if years else None, reference_year, contradictions)
    material = abs(materiality_pp) >= RUBRIC["materiality_threshold"]
    if strength in ("Strong", "Moderate") and material: status = "supported_finding"
    elif strength == "Weak" and material: status = "provisional_hypothesis"; score = min(score, RUBRIC["provisional_rank_cap"])
    else: status = "no_defensible_signal"; score = min(score, RUBRIC["no_signal_rank_cap"])
    lim = list(limitations)
    if status == "no_defensible_signal": lim.append("No defensible signal: " + ("evidence strength is None" if strength == "None" else f"effect of {abs(materiality_pp):.1f} pp is below the {RUBRIC['materiality_threshold']} pp materiality threshold"))
    if status == "provisional_hypothesis": lim.append("Provisional: no input has been checked against a primary source; do not treat as a supported finding.")
    f = {"schema_version": "1.0", "finding_id": finding_id, "run_id": run_id, "company": company, "finding_status": status, "evidence_strength": strength, "headline": headline, "why_it_matters": why_it_matters,
         "periods": list(periods), "rank_score": score, "rank_components": comps, "inputs": inputs, "calculations": [{"calculation_id": c["calculation_id"], "name": c["name"], "formula": c["formula"], "result": c["result"],
         "input_names": [i["name"] for i in c["inputs"]], "trace": c["trace"]} for c in calculations], "supporting_evidence": list(supporting_evidence), "contradictory_evidence": list(contradictory_evidence),
         "alternative_explanations": list(alternative_explanations), "falsification_conditions": list(falsification_conditions), "missing_evidence": list(missing_evidence), "limitations": lim,
         "stage_provenance": list(stage_provenance), "all_claims_unverified": bool(claims_all_unverified), "synthetic": synthetic,
         "provisional_rubric": {"status": RUBRIC["status"], "weights": RUBRIC["weights"], "materiality_threshold_pp": RUBRIC["materiality_threshold"], "strength_rules": RUBRIC["strength_rules"]}}
    validate_against(f, "finding"); return f

def no_signal_finding(*, finding_id, run_id, company, reason, missing_evidence, stage_provenance, claims_all_unverified=True, synthetic=False, limitations=()):
    f = {"schema_version": "1.0", "finding_id": finding_id, "run_id": run_id, "company": company, "finding_status": "no_defensible_signal", "evidence_strength": "None", "headline": "No defensible signal can be produced from the available evidence.",
         "why_it_matters": reason, "periods": [], "rank_score": 0.0, "rank_components": {}, "inputs": [], "calculations": [], "supporting_evidence": [], "contradictory_evidence": [], "alternative_explanations": [],
         "falsification_conditions": [], "missing_evidence": list(missing_evidence), "limitations": list(limitations) + [reason], "stage_provenance": list(stage_provenance), "all_claims_unverified": claims_all_unverified, "synthetic": synthetic,
         "provisional_rubric": {"status": RUBRIC["status"]}}
    validate_against(f, "finding"); return f

def check_traceability(finding, claim_store, evidence_by_id=None):
    """Every displayed input and number must map to a stored claim, its source chunk text, and a calculation. Returns a list of problems (empty = traceable)."""
    problems = []; names = {i["name"] for i in finding["inputs"]}
    for i in finding["inputs"]:
        for cid in i["claim_ids"]:
            try: claim_store.get(cid)
            except KeyError: problems.append(f"input {i['name']}: unknown claim {cid}")
        ci = i["citation"]; rec = (evidence_by_id or {}).get(ci["source_chunk_id"])
        if rec is not None and collapse(ci["excerpt"]) and collapse(ci["excerpt"]) not in collapse(rec["excerpt_or_fact"]): problems.append(f"input {i['name']}: citation excerpt is not in chunk {ci['source_chunk_id']}")
        derived = (ci.get("locator") or "").startswith("derived") and bool(i["claim_ids"])
        if ci["url"] is None and ci["source_chunk_id"] is None and not derived: problems.append(f"input {i['name']}: citation has neither chunk nor url")
    for c in finding["calculations"]:
        missing = [n for n in c["input_names"] if n not in names]
        if missing: problems.append(f"calculation {c['name']}: inputs not displayed {missing}")
    shown = {round(i["value"], 2) for i in finding["inputs"]}
    shown |= {round(c["result"]["value"], 2) for c in finding["calculations"] if c["result"]}
    shown |= {round(x, 1) for x in list(shown)}
    for m in re.finditer(r"(?<![\w.])(\d[\d,]*\.?\d*)", finding["headline"]):
        if re.fullmatch(r"(?:19|20)\d{2}", m.group(1)): continue
        v = float(m.group(1).replace(",", ""))
        if v not in shown and round(v, 1) not in shown: problems.append(f"headline number {m.group(1)} does not map to an input or calculation")
    return problems
