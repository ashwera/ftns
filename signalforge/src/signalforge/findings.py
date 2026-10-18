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

def evidence_strength(inputs_used, verifications, calculations, sources, *, contradictions=0, independent_count=None):
    """`verifications` are the effective results of the KEY inputs. independent_count (if given) is the minimum number of independent
    confirming source groups across key inputs; otherwise it is derived from `sources`."""
    comps = [c for c in calculations if c["status"] == "computed"]
    if not comps or contradictions or any(v["outcome"] in ("contradicted", "unresolved", "unable_to_verify") for v in verifications): return "None"
    primary = all(v["outcome"] == "confirmed" and v["verification_level"] == "primary_source" for v in verifications)
    if not primary: return "Weak"
    ind = independent_count if independent_count is not None else assess_independence(sources)["independent_source_count"]
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
               alternative_explanations, falsification_conditions, missing_evidence=(), limitations=(), stage_provenance, claims_all_unverified, synthetic=False, reference_year=None, periods=(),
               key_verifications=None, independence_by_input=None, audit_trail=(), decision_log=(), conflicts=0, qualifying_evidence_count=0):
    """Key inputs decide the verdict: a contradicted key input rejects the finding, a conflicted or unconfirmed key input downgrades it.
    Non-key inputs are listed in the audit trail and limitations but cannot raise the strength."""
    keys = list(key_verifications) if key_verifications is not None else list(verifications)
    key_contra = [v for v in keys if v["outcome"] == "contradicted"]
    log = list(decision_log); downgrades = []
    if key_contra:
        return reject_finding(finding_id=finding_id, run_id=run_id, company=company, headline=headline, why_it_matters=why_it_matters, failed=key_contra, inputs=inputs, calculations=calculations,
                              contradictory_evidence=contradictory_evidence, missing_evidence=missing_evidence, stage_provenance=stage_provenance, claims_all_unverified=claims_all_unverified, synthetic=synthetic,
                              audit_trail=audit_trail, decision_log=log, alternative_explanations=alternative_explanations, falsification_conditions=falsification_conditions)
    # Evidence that merely qualifies (conflicting sources, failed non-key inputs) caps strength at Weak instead of voiding the finding;
    # any other contradictory evidence still blocks it.
    blocking = max(0, len(contradictory_evidence) - qualifying_evidence_count)
    contradictions = blocking + conflicts
    ind = min(independence_by_input.values()) if independence_by_input else None
    strength = evidence_strength(inputs, keys, calculations, sources, contradictions=blocking, independent_count=ind)
    if strength in ("Moderate", "Strong") and (conflicts or qualifying_evidence_count): strength = "Weak"
    checks = [c["ok"] for calc in calculations for c in calc["compatibility_checks"]] + [x["ok"] for v in keys for x in v["cross_checks"]]
    consistency = (sum(checks) / len(checks)) if checks else 0.0
    years = [int(i["as_of_date"][:4]) for i in inputs if i.get("as_of_date")]
    independent = ind if ind is not None else (assess_independence(sources)["independent_source_count"] if sources else 0)
    score, comps = rank(strength, materiality_pp, independent, consistency, max(years) if years else None, reference_year, contradictions)
    material = abs(materiality_pp) >= RUBRIC["materiality_threshold"]
    for v in keys:
        if v["outcome"] != "confirmed": downgrades.append(f"key input '{v['input_name']}' is {v['outcome']}")
        elif v["verification_level"] != "primary_source": downgrades.append(f"key input '{v['input_name']}' is confirmed only against the project's text extraction, not a primary source")
    if conflicts: downgrades.append(f"{conflicts} key input(s) have conflicting primary sources")
    if independent < 2 and strength in ("Moderate", "Weak"): downgrades.append(f"only {independent} independent source group(s) back the key inputs; Strong needs at least 2")
    if strength in ("Strong", "Moderate") and material: status = "supported_finding"
    elif strength == "Weak" and material: status = "provisional_hypothesis"; score = min(score, RUBRIC["provisional_rank_cap"])
    else: status = "no_defensible_signal"; score = min(score, RUBRIC["no_signal_rank_cap"])
    log.append(f"strength={strength}; materiality={abs(materiality_pp):.1f} pp (threshold {RUBRIC['materiality_threshold']}); independent groups={independent}; status={status}")
    lim = list(limitations)
    if status == "no_defensible_signal": lim.append("No defensible signal: " + ("evidence strength is None" if strength == "None" else f"effect of {abs(materiality_pp):.1f} pp is below the {RUBRIC['materiality_threshold']} pp materiality threshold"))
    if status == "provisional_hypothesis": lim.append("Provisional: not every key input is confirmed against a primary source; do not treat as a supported finding.")
    summary = {"key_inputs": len(keys), "confirmed_primary": sum(v["outcome"] == "confirmed" and v["verification_level"] == "primary_source" for v in keys), "confirmed_text_only": sum(v["outcome"] == "confirmed" and v["verification_level"] != "primary_source" for v in keys),
               "partial": sum(v["outcome"] == "partially_supported" for v in keys), "unresolved_or_unverifiable": sum(v["outcome"] in ("unresolved", "unable_to_verify") for v in keys), "contradicted": 0, "conflicts": conflicts, "min_independent_groups": independent}
    f = {"schema_version": "1.0", "finding_id": finding_id, "run_id": run_id, "company": company, "finding_status": status, "evidence_strength": strength, "headline": headline, "why_it_matters": why_it_matters,
         "periods": list(periods), "rank_score": score, "rank_components": comps, "inputs": inputs, "calculations": [{"calculation_id": c["calculation_id"], "name": c["name"], "formula": c["formula"], "result": c["result"],
         "input_names": [i["name"] for i in c["inputs"]], "trace": c["trace"]} for c in calculations], "supporting_evidence": list(supporting_evidence), "contradictory_evidence": list(contradictory_evidence),
         "alternative_explanations": list(alternative_explanations), "falsification_conditions": list(falsification_conditions), "missing_evidence": list(missing_evidence), "limitations": lim,
         "stage_provenance": list(stage_provenance), "all_claims_unverified": bool(claims_all_unverified), "synthetic": synthetic,
         "provisional_rubric": {"status": RUBRIC["status"], "weights": RUBRIC["weights"], "materiality_threshold_pp": RUBRIC["materiality_threshold"], "strength_rules": RUBRIC["strength_rules"]},
         "audit_trail": list(audit_trail), "decision_log": log, "downgrade_reasons": downgrades, "rejected_hypothesis": None, "verification_summary": summary}
    validate_against(f, "finding"); return f

def reject_finding(*, finding_id, run_id, company, headline, why_it_matters, failed, inputs, calculations, contradictory_evidence, missing_evidence, stage_provenance, claims_all_unverified, synthetic,
                   audit_trail, decision_log, alternative_explanations=(), falsification_conditions=()):
    """A key input was contradicted by its source: the hypothesis is preserved for the record but is not published as a finding."""
    names = [v["input_name"] for v in failed]
    contra = list(contradictory_evidence) + [{"statement": f"Key input '{v['input_name']}' was contradicted: " + "; ".join(v["discrepancies"]), "claim_ids": [v["claim_id"]] if v["claim_id"] else [],
              "citation": {"source_chunk_id": v["source"]["source_chunk_id"], "source_path": v["source"]["source_path"], "page": v["source"]["page"], "locator": v["verification_id"], "excerpt": collapse(v["source"]["passage"])[:300], "url": v["source"]["url"]}, "independent": False} for v in failed]
    log = list(decision_log) + [f"REJECTED: key input(s) {names} contradicted by their source"]
    f = {"schema_version": "1.0", "finding_id": finding_id, "run_id": run_id, "company": company, "finding_status": "no_defensible_signal", "evidence_strength": "None", "headline": "Hypothesis rejected: a key input was contradicted by its source.",
         "why_it_matters": f"The hypothesis could not be supported because key input(s) {names} fail verification.", "periods": [], "rank_score": 0.0, "rank_components": {}, "inputs": inputs, "calculations": [], "supporting_evidence": [],
         "contradictory_evidence": contra, "alternative_explanations": list(alternative_explanations), "falsification_conditions": list(falsification_conditions), "missing_evidence": list(missing_evidence) + ["resolve the contradicted key input against the primary source"],
         "limitations": [f"Rejected because of failed verification of {names}."], "stage_provenance": list(stage_provenance), "all_claims_unverified": bool(claims_all_unverified), "synthetic": synthetic,
         "provisional_rubric": {"status": RUBRIC["status"]}, "audit_trail": list(audit_trail), "decision_log": log, "downgrade_reasons": [f"key input '{n}' contradicted" for n in names],
         "rejected_hypothesis": {"headline_if_inputs_held": headline, "why_it_would_matter": why_it_matters, "failed_inputs": names},
         "verification_summary": {"key_inputs": len(failed), "contradicted": len(failed)}}
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
