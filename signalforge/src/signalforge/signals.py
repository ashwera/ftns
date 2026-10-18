"""Deterministic financial-signal calculators with full traces. Arithmetic is plain Python, never an LLM.

Families implemented: capacity_pipeline_conversion, renewable_transition, subsidiary_jv_exposure (composition/share of a group
total by entity part), financial_performance (period growth). Every calculation records its inputs (claim and verification ids),
formula, unit/period/basis compatibility checks, assumptions, missing inputs, a counterargument and a falsification test.
No company values or thresholds live here; callers pass verified inputs.
"""
import hashlib
from .pipeline_contract import validate_against

USABLE = ("confirmed", "partially_supported")
UNIT_TO_BASE = {"MW": ("MW", 1.0), "GW": ("MW", 1000.0), "MWh": ("MWh", 1.0), "GWh": ("MWh", 1000.0), "MU": ("MU", 1.0), "BU": ("MU", 1000.0)}

def make_input(name, value, unit, *, as_of=None, period_text=None, basis=None, status=None, claim_ids=(), verification=None, rounding=None):
    """verification: a verification_result dict (or None). rounding: half-unit of the last reported digit, in `unit`."""
    return {"name": name, "value": float(value), "unit": unit, "as_of_date": as_of, "period_text": period_text, "basis": basis, "statement_status": status,
            "claim_ids": list(claim_ids), "verification_ids": (verification.get("verification_ids") or [verification["verification_id"]]) if verification else [], "verification_outcome": verification["outcome"] if verification else "unverified",
            "rounding_uncertainty": rounding}

def to_base(inp):
    """Convert to a base unit (MW, MWh, MU) with explicit scale and propagated rounding uncertainty. Unknown units stay as-is."""
    base, k = UNIT_TO_BASE.get(inp["unit"], (inp["unit"], 1.0))
    return {**inp, "value": inp["value"] * k, "unit": base, "rounding_uncertainty": (inp["rounding_uncertainty"] * k) if inp["rounding_uncertainty"] is not None else None}

def _cid(family, name, inputs):
    return "calc_" + hashlib.sha256("|".join([family, name] + [f"{i['name']}={i['value']}:{','.join(i['claim_ids'])}" for i in inputs]).encode()).hexdigest()[:16]

def _check(name, ok, detail): return {"check": name, "ok": bool(ok), "detail": detail}

def _build(family, name, status, formula, inputs, result, checks, assumptions, missing, counter, falsify, trace, synthetic):
    calc = {"schema_version": "1.0", "calculation_id": _cid(family, name, inputs), "signal_family": family, "name": name, "status": status, "formula": formula, "inputs": inputs, "result": result,
            "compatibility_checks": checks, "assumptions": assumptions, "missing_inputs": missing, "counterargument": counter, "falsification_test": falsify, "trace": trace, "synthetic": synthetic}
    validate_against(calc, "signal_calculation"); return calc

def _not_computable(family, name, formula, inputs, checks, missing, counter, falsify, synthetic, why):
    return _build(family, name, "not_computable", formula, inputs, None, checks, [], missing, counter, falsify, f"not computed: {why}", synthetic)

def _usable_checks(inputs):
    return [_check(f"input_verified:{i['name']}", i["verification_outcome"] in USABLE, f"verification outcome = {i['verification_outcome']}") for i in inputs]

STATUS_OK = {"capacity_pipeline_conversion": {("under_implementation", "commissioned"), ("under_implementation", "actual"), ("commissioned", "commissioned"), ("under_implementation", "under_implementation")},
             "renewable_transition": {("commissioned", "commissioned"), ("under_implementation", "under_implementation"), ("under_implementation", "commissioned"), ("commissioned", "actual"), ("actual", "actual")}}

def _bounds(num, den):
    ua, ub = num["rounding_uncertainty"] or 0.0, den["rounding_uncertainty"] or 0.0
    if den["value"] - ub <= 0: return None, None
    return 100 * max(0.0, num["value"] - ua) / (den["value"] + ub), 100 * (num["value"] + ua) / (den["value"] - ub)

def ratio_signal(family, name, numerator, denominator, *, counterargument, falsification_test, synthetic=False, same_asof=True, basis_relation=None, status_pairs=None, assumptions=()):
    """numerator / denominator x 100 (percent). basis_relation: set of allowed (num_basis, den_basis) pairs; default requires equal basis."""
    n, d = to_base(numerator), to_base(denominator); inputs = [numerator, denominator]
    checks = _usable_checks(inputs)
    checks.append(_check("units_compatible", n["unit"] == d["unit"] and n["unit"] is not None, f"{n['unit']} vs {d['unit']}"))
    if same_asof: checks.append(_check("same_as_of_date", n["as_of_date"] is not None and n["as_of_date"] == d["as_of_date"], f"{n['as_of_date']} vs {d['as_of_date']}"))
    allowed = basis_relation or {(n["basis"], n["basis"])}
    checks.append(_check("basis_compatible", (n["basis"], d["basis"]) in allowed, f"{n['basis']} / {d['basis']} (allowed: {sorted(map(str, allowed))})"))
    pairs = status_pairs if status_pairs is not None else STATUS_OK.get(family)
    if pairs is not None: checks.append(_check("statement_status_compatible", (n["statement_status"], d["statement_status"]) in pairs, f"{n['statement_status']} / {d['statement_status']}"))
    checks.append(_check("denominator_nonzero", d["value"] != 0, f"denominator = {d['value']}"))
    formula = f"{numerator['name']} / {denominator['name']} x 100"
    if not all(c["ok"] for c in checks):
        return _not_computable(family, name, formula, inputs, checks, [c["detail"] for c in checks if not c["ok"]], counterargument, falsification_test, synthetic, "; ".join(f"{c['check']} failed ({c['detail']})" for c in checks if not c["ok"]))
    val = 100 * n["value"] / d["value"]; lo, hi = _bounds(n, d)
    trace = f"{n['name']} = {n['value']:g} {n['unit']} ({numerator['value']:g} {numerator['unit']}); {d['name']} = {d['value']:g} {d['unit']}; 100 x {n['value']:g} / {d['value']:g} = {val:.4f}%"
    if lo is not None: trace += f"; rounding bounds [{lo:.4f}%, {hi:.4f}%]"
    return _build(family, name, "computed", formula, inputs, {"value": round(val, 6), "unit": "percent", "lower_bound": None if lo is None else round(lo, 6), "upper_bound": None if hi is None else round(hi, 6)},
                  checks, list(assumptions) + ["Inputs are used as verified at their stated verification level."], [], counterargument, falsification_test, trace, synthetic)

def difference_input(name, whole, part, *, basis, status=None, synthetic_note=None):
    """Derived input = whole - part (same unit/as-of/status). Raises if incompatible; keeps both parents' claim and verification ids."""
    w, p = to_base(whole), to_base(part)
    if w["unit"] != p["unit"] or w["as_of_date"] != p["as_of_date"]: raise ValueError(f"cannot subtract {part['name']} from {whole['name']}: unit or as-of date differs")
    if w["value"] < p["value"]: raise ValueError(f"{part['name']} exceeds {whole['name']}")
    outcomes = {whole["verification_outcome"], part["verification_outcome"]}
    outcome = "confirmed" if outcomes == {"confirmed"} else ("partially_supported" if outcomes <= set(USABLE) else "unresolved")
    unc = None if w["rounding_uncertainty"] is None and p["rounding_uncertainty"] is None else (w["rounding_uncertainty"] or 0) + (p["rounding_uncertainty"] or 0)
    return {"name": name, "value": w["value"] - p["value"], "unit": w["unit"], "as_of_date": w["as_of_date"], "period_text": whole["period_text"], "basis": basis, "statement_status": status or whole["statement_status"],
            "claim_ids": sorted(set(whole["claim_ids"] + part["claim_ids"])), "verification_ids": sorted(set(whole["verification_ids"] + part["verification_ids"])), "verification_outcome": outcome, "rounding_uncertainty": unc}

def composition_signal(family, name, parts, total, *, counterargument, falsification_test, tolerance=0.0, synthetic=False):
    """Each part's share of `total`, plus a sum-consistency check (parts must add up to the total within tolerance)."""
    inputs = [*parts, total]; checks = _usable_checks(inputs)
    base_parts, base_total = [to_base(p) for p in parts], to_base(total)
    checks.append(_check("units_compatible", len({p["unit"] for p in base_parts} | {base_total["unit"]}) == 1, "all in " + str(base_total["unit"])))
    checks.append(_check("same_as_of_date", len({p["as_of_date"] for p in base_parts} | {base_total["as_of_date"]}) == 1, str({p["as_of_date"] for p in base_parts} | {base_total["as_of_date"]})))
    s = sum(p["value"] for p in base_parts); checks.append(_check("parts_sum_to_total", abs(s - base_total["value"]) <= tolerance, f"sum of parts {s:g} vs total {base_total['value']:g}"))
    checks.append(_check("denominator_nonzero", base_total["value"] != 0, f"total = {base_total['value']:g}"))
    formula = "share_i = part_i / total x 100"
    if not all(c["ok"] for c in checks):
        return _not_computable(family, name, formula, inputs, checks, [c["detail"] for c in checks if not c["ok"]], counterargument, falsification_test, synthetic, "; ".join(c["detail"] for c in checks if not c["ok"]))
    shares = {p["name"]: 100 * p["value"] / base_total["value"] for p in base_parts}
    trace = "; ".join(f"{k} = {v:.4f}%" for k, v in shares.items()) + f"; sum of parts {s:g} = total {base_total['value']:g}"
    return _build(family, name, "computed", formula, inputs, {"value": round(max(shares.values()), 6), "unit": "percent", "lower_bound": None, "upper_bound": None}, checks,
                  ["Result field holds the largest share; every share is in the trace."], [], counterargument, falsification_test, trace, synthetic)

def growth_signal(name, current, prior, *, counterargument, falsification_test, synthetic=False):
    """Period-over-period change (%) for the same unit and basis; the periods must differ."""
    c, p = to_base(current), to_base(prior); inputs = [current, prior]; checks = _usable_checks(inputs)
    checks.append(_check("units_compatible", c["unit"] == p["unit"], f"{c['unit']} vs {p['unit']}"))
    checks.append(_check("basis_compatible", c["basis"] == p["basis"], f"{c['basis']} vs {p['basis']}"))
    checks.append(_check("periods_differ_and_known", bool(c["as_of_date"] or c["period_text"]) and (c["as_of_date"], c["period_text"]) != (p["as_of_date"], p["period_text"]), f"{c['as_of_date'] or c['period_text']} vs {p['as_of_date'] or p['period_text']}"))
    checks.append(_check("denominator_nonzero", p["value"] != 0, f"prior = {p['value']:g}"))
    formula = "(current - prior) / prior x 100"
    if not all(x["ok"] for x in checks): return _not_computable("financial_performance", name, formula, inputs, checks, [x["detail"] for x in checks if not x["ok"]], counterargument, falsification_test, synthetic, "; ".join(x["detail"] for x in checks if not x["ok"]))
    val = 100 * (c["value"] - p["value"]) / p["value"]
    return _build("financial_performance", name, "computed", formula, inputs, {"value": round(val, 6), "unit": "percent", "lower_bound": None, "upper_bound": None}, checks, ["Same definition and basis assumed across the two periods."], [], counterargument, falsification_test,
                  f"({c['value']:g} - {p['value']:g}) / {p['value']:g} x 100 = {val:.4f}%", synthetic)

def target_coverage_signal(name, achieved_inputs, target, *, counterargument, falsification_test, synthetic=False):
    """(sum of achieved + in-progress capacity) / target x 100. The target is forward-looking and kept labelled as such."""
    inputs = [*achieved_inputs, target]; checks = _usable_checks(inputs)
    base = [to_base(i) for i in achieved_inputs]; t = to_base(target)
    checks.append(_check("units_compatible", len({b["unit"] for b in base} | {t["unit"]}) == 1, "all in " + str(t["unit"])))
    checks.append(_check("target_is_labelled_forward_looking", t["statement_status"] in ("target", "forecast"), f"target status = {t['statement_status']}"))
    checks.append(_check("achieved_inputs_not_targets", all(b["statement_status"] not in ("target", "forecast") for b in base), str([b["statement_status"] for b in base])))
    checks.append(_check("basis_compatible", len({b["basis"] for b in base} | {t["basis"]}) == 1, str({b["basis"] for b in base} | {t["basis"]})))
    checks.append(_check("denominator_nonzero", t["value"] != 0, f"target = {t['value']:g}"))
    formula = "(sum(achieved + under implementation)) / target x 100"
    if not all(c["ok"] for c in checks): return _not_computable("renewable_transition", name, formula, inputs, checks, [c["detail"] for c in checks if not c["ok"]], counterargument, falsification_test, synthetic, "; ".join(c["detail"] for c in checks if not c["ok"]))
    s = sum(b["value"] for b in base); unc = sum((b["rounding_uncertainty"] or 0) for b in base); val = 100 * s / t["value"]
    lo, hi = 100 * max(0, s - unc) / (t["value"] + (t["rounding_uncertainty"] or 0)), 100 * (s + unc) / max(1e-12, t["value"] - (t["rounding_uncertainty"] or 0))
    return _build("renewable_transition", name, "computed", formula, inputs, {"value": round(val, 6), "unit": "percent", "lower_bound": round(lo, 6), "upper_bound": round(hi, 6)}, checks,
                  ["Under-implementation capacity is not commissioned and may slip or be cancelled.", "The target is a forward-looking statement, not an outcome."], [], counterargument, falsification_test,
                  " + ".join(f"{b['value']:g}" for b in base) + f" = {s:g} {t['unit']}; / target {t['value']:g} = {val:.4f}% (bounds [{lo:.4f}%, {hi:.4f}%])", synthetic)
