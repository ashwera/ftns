"""End-to-end vertical slice: claims -> bundle -> F1/R1 -> (retrieval) -> verification -> signals -> finding -> frontend contract.

Run: PYTHONPATH=signalforge/src python3 -m signalforge.pipeline --company "NTPC Limited" --claims <claims.jsonl> --evidence <evidence.jsonl>
         --inputs <reviewed_inputs.json> --run-dir signalforge/data/runs/<id> [--simulate-llm] [--catalog catalog.json --allow-network]
Every stage records whether it was real, simulated, blocked or not executed. Claims are never mutated or marked verified.
"""
import argparse
import dataclasses
import json
import sys
from pathlib import Path

from . import claim_verification as V
from . import findings as FD
from . import research_bridge as RB
from . import signals as S
from . import source_retrieval as SR
from .config import Config, ROOT
from .pipeline_contract import ClaimStore, citation, collapse, read_jsonl, target_from_registry, validate_against, write_json

ROLES = ("installed_total_group", "re_installed_group", "re_pipeline_group", "pipeline_total_group", "pipeline_jv_sub", "re_pipeline_jv_sub", "re_target")

def _stage(stages, name, execution, detail): stages.append({"stage": name, "execution": execution, "detail": detail})

def verify_inputs(spec, store, evidence_by_id, target, level_for=None):
    """Build verification results for each reviewed input. The assertion's value/unit come from the claim; a spec that disagrees is an error."""
    results, verified = [], {}
    for n, item in enumerate(spec["inputs"]):
        claim = store.get(item["claim_id"]); rec = evidence_by_id[claim["source_chunk_id"]]
        a = V.assertion_from_claim(claim, basis=item["basis"], statement_status=item["statement_status"], label_terms=item["label_terms"], entity_names=[*target.names])
        a["entity"] = target.name
        if item.get("as_of_date") is not None or claim["as_of_date"] is None: a["as_of_date"] = item.get("as_of_date")
        a["period_text"] = item.get("period_text") or claim["raw_period_text"]
        src = {"source_chunk_id": rec["evidence_id"], "source_path": rec["source_path"], "page": rec.get("page_number"), "url": rec.get("source_url"), "publisher": rec.get("source_organization"),
               "publication_date": rec.get("publication_date"), "retrieved_at": None, "document_family": rec.get("document_title")}
        r = V.verify_assertion(a, rec["excerpt_or_fact"], source=src, level=(level_for(rec) if level_for else "extracted_text_review"), verification_id=f"ver_{item['role']}_{claim['claim_id'][-8:]}",
                               input_name=item["name"], claim_id=claim["claim_id"], reviewer=spec["reviewer"] | {"kind": "ai_assisted_analyst", "note": spec["reviewer"]["note"]}, cross_checks=item.get("cross_checks", []))
        results.append(r); verified[item["role"]] = (item, claim, rec, r)
    return results, verified

def _inp(role, verified, unit_of_claim=True):
    item, claim, rec, r = verified[role]
    return S.make_input(item["name"], claim["value"], claim["unit"], as_of=item.get("as_of_date"), period_text=item.get("period_text"), basis=item["basis"], status=item["statement_status"], claim_ids=[claim["claim_id"]], verification=r, rounding=item.get("rounding_uncertainty"))

def compute_signals(verified, synthetic=False):
    """Role-based signals, company-agnostic. Missing roles yield not_computable calculations instead of guesses."""
    calcs, derived = [], {}
    have = lambda *rs: all(r in verified for r in rs)
    I = {r: _inp(r, verified) for r in verified}
    if have("pipeline_total_group", "pipeline_jv_sub"):
        derived["parent_pipeline_total"] = S.difference_input("parent_under_implementation", I["pipeline_total_group"], I["pipeline_jv_sub"], basis="parent_own", status="under_implementation")
    if have("re_pipeline_group", "re_pipeline_jv_sub"):
        derived["parent_re_pipeline"] = S.difference_input("parent_re_under_implementation", I["re_pipeline_group"], I["re_pipeline_jv_sub"], basis="parent_own", status="under_implementation")
    def add(c): calcs.append(c)
    ctr = "Reporting boundaries differ by company; a parent/subsidiary split may reflect legal structure rather than economics, since subsidiaries are consolidated."
    if have("re_pipeline_group", "pipeline_total_group"):
        add(S.ratio_signal("renewable_transition", "re_share_of_group_pipeline", I["re_pipeline_group"], I["pipeline_total_group"], counterargument="Pipeline entries may be at different stages and can slip or be cancelled.", falsification_test="The filing's component table does not sum to the total, or the renewable total is defined differently from the pipeline total.", synthetic=synthetic, basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")}))
    if have("re_pipeline_jv_sub", "re_pipeline_group"):
        add(S.ratio_signal("subsidiary_jv_exposure", "jv_subsidiary_share_of_re_pipeline", I["re_pipeline_jv_sub"], I["re_pipeline_group"], counterargument=ctr, falsification_test="The JV/subsidiary renewable amount is shown to be a subset of a different denominator or a different date.", synthetic=synthetic, basis_relation={("jv_subsidiary_part", "group")}, status_pairs={("under_implementation", "under_implementation")}))
    if "parent_re_pipeline" in derived and "parent_pipeline_total" in derived:
        add(S.ratio_signal("renewable_transition", "re_share_of_parent_own_pipeline", derived["parent_re_pipeline"], derived["parent_pipeline_total"], counterargument=ctr, falsification_test="The parent's own table reports a materially different renewable share than the subtraction implies.", synthetic=synthetic, basis_relation={("parent_own", "parent_own")}, status_pairs={("under_implementation", "under_implementation")}))
    if have("re_pipeline_jv_sub", "pipeline_jv_sub"):
        add(S.ratio_signal("renewable_transition", "re_share_of_jv_subsidiary_pipeline", I["re_pipeline_jv_sub"], I["pipeline_jv_sub"], counterargument=ctr, falsification_test="The JV/subsidiary table totals are not the same population as the renewable subset.", synthetic=synthetic, basis_relation={("jv_subsidiary_part", "jv_subsidiary_part")}, status_pairs={("under_implementation", "under_implementation")}))
    if have("pipeline_total_group", "installed_total_group"):
        add(S.ratio_signal("capacity_pipeline_conversion", "pipeline_relative_to_installed_base", I["pipeline_total_group"], I["installed_total_group"], counterargument="Pipeline includes coal and hydro as well as renewables; the ratio is not a forecast of additions.", falsification_test="Installed and pipeline totals are not on the same group boundary.", synthetic=synthetic, basis_relation={("group", "consolidated")}))
    if have("re_installed_group", "re_pipeline_group", "re_target"):
        add(S.target_coverage_signal("re_installed_plus_pipeline_vs_target", [I["re_installed_group"], I["re_pipeline_group"]], I["re_target"], counterargument="The target may be defined on a different boundary or year basis; pipeline is not commissioned.", falsification_test="Disclosed target is on a different boundary (e.g. parent-only) than the group capacities used here.", synthetic=synthetic))
    return calcs, derived, I

def build_finding(run_id, company, identity, calcs, derived, I, verifications, verified, evidence_by_id, spec, stages, synthetic, reference_year, claims_unverified):
    computed = {c["name"]: c for c in calcs if c["status"] == "computed"}
    inputs_out, seen = [], set()
    for role, (item, claim, rec, r) in verified.items():
        inp = I[role]; inputs_out.append({k: inp[k] for k in ("name", "value", "unit", "as_of_date", "basis", "statement_status", "claim_ids", "verification_ids")} | {"verification_outcome": r["verification_outcome"] if False else r["outcome"], "verification_level": r["verification_level"], "citation": citation(claim, rec)})
    for k, d in derived.items(): inputs_out.append({kk: d[kk] for kk in ("name", "value", "unit", "as_of_date", "basis", "statement_status", "claim_ids", "verification_ids")} | {"verification_outcome": d["verification_outcome"], "verification_level": "extracted_text_review", "citation": {"source_chunk_id": None, "source_path": None, "page": None, "locator": "derived by subtraction of two cited inputs", "excerpt": f"{d['name']} = whole - part (see calculation trace)", "url": None}})
    gate = [c for c in ("re_share_of_parent_own_pipeline", "re_share_of_jv_subsidiary_pipeline") if c in computed]
    prov = stages
    if len(gate) < 2:
        return FD.no_signal_finding(finding_id=f"find_{run_id}_none", run_id=run_id, company=company, reason="Required verified inputs are missing or incompatible, so the parent-versus-subsidiary renewable comparison cannot be computed.",
                                    missing_evidence=sorted({m for c in calcs for m in c["missing_inputs"]}) or ["verified inputs for all required roles"], stage_provenance=prov, claims_all_unverified=claims_unverified, synthetic=synthetic)
    parent, jv = computed["re_share_of_parent_own_pipeline"]["result"]["value"], computed["re_share_of_jv_subsidiary_pipeline"]["result"]["value"]
    jv_share = computed.get("jv_subsidiary_share_of_re_pipeline", {}).get("result", {}).get("value")
    direction = "jv_subsidiary" if jv > parent else "parent"
    headline = (f"{company['name']}: {parent:.1f}% of its own under-implementation pipeline is renewable versus {jv:.1f}% of the joint-venture and subsidiary pipeline"
                + (f"; {jv_share:.1f}% of the group's renewable pipeline sits in joint ventures and subsidiaries." if jv_share is not None else "."))
    supporting = []
    for v in verifications:
        for cc in v["cross_checks"]:
            supporting.append({"statement": f"Same-filing table cell check: {cc['description']} = {cc['found_value']} (expected {cc['expected_value']}, {'ok' if cc['ok'] else 'FAILED'})", "claim_ids": [v["claim_id"]] if v["claim_id"] else [],
                               "citation": {"source_chunk_id": v["source"]["source_chunk_id"], "source_path": v["source"]["source_path"], "page": v["source"]["page"], "locator": None, "excerpt": collapse(v["source"]["passage"])[:300], "url": None}, "independent": False})
    for name, c in computed.items():
        supporting.append({"statement": f"{name}: {c['trace']}", "claim_ids": sorted({cid for i in c["inputs"] for cid in i["claim_ids"]}), "citation": {"source_chunk_id": None, "source_path": None, "page": None, "locator": c["calculation_id"], "excerpt": c["formula"], "url": None}, "independent": False})
    contradictory = []
    for v in verifications:
        if v["outcome"] in ("contradicted",): contradictory.append({"statement": f"Verification of {v['input_name']} was contradicted: " + "; ".join(v["discrepancies"]), "claim_ids": [v["claim_id"]], "citation": {"source_chunk_id": v["source"]["source_chunk_id"], "source_path": v["source"]["source_path"], "page": v["source"]["page"], "locator": None, "excerpt": collapse(v["source"]["passage"])[:300], "url": None}, "independent": False})
    sources = [{"publisher": "issuer", "document_family": rec.get("source_path"), "sha256": rec.get("source_sha256") or rec.get("source_path"), "derived_from": []} for _, (_, _, rec, _) in verified.items()]
    return FD.adjudicate(finding_id=f"find_{run_id}_{spec['hypothesis_id']}", run_id=run_id, company=company, headline=headline,
        why_it_matters=("Renewable growth is concentrated in joint ventures and subsidiaries, so parent-only metrics and the parent's own capital plan can mis-describe the group's renewable transition, and exposure to those entities' financing and minority interests matters for valuation." if direction == "jv_subsidiary" else "Renewable growth is concentrated in the parent's own pipeline rather than in joint ventures and subsidiaries, which changes who bears the capital and financing exposure."),
        materiality_pp=abs(jv - parent), inputs=inputs_out, verifications=verifications, calculations=list(computed.values()), sources=sources, supporting_evidence=supporting, contradictory_evidence=contradictory,
        alternative_explanations=["Group (consolidated) reporting already includes these entities, so the split may be organisational rather than economic.", "Under-implementation capacity may slip or be re-scoped; the pipeline is not commissioned capacity.", "The parent may hold economic interests in the subsidiaries that offset the apparent concentration."],
        falsification_conditions=["The component table in the primary filing does not match the extracted text, so the parent and JV/subsidiary shares differ from those computed here.", "A different boundary or date is used for the renewable total than for the pipeline total.", "Prior-year disclosures show the same split, implying a structural reporting convention rather than a change."],
        missing_evidence=["Primary-source check of the page 91 table and sentences in the original filing or exchange submission.", "Independent corroboration (regulator or third-party data) of subsidiary renewable pipeline.", "Prior-year pipeline composition to test conversion and trend.", "Ownership percentage and consolidation treatment of each subsidiary/JV."],
        limitations=["All inputs are from the project's own text extraction; none was checked against the original PDF.", "The 14.5 GW and 6.8 GW figures are rounded in the source; bounds are carried through the calculations.", "Claims remain unverified; verification results are separate records."],
        stage_provenance=prov, claims_all_unverified=claims_unverified, synthetic=synthetic, reference_year=reference_year, periods=sorted({i["as_of_date"] for i in inputs_out if i["as_of_date"]}))

def run_pipeline(company, claims_path, evidence_path, inputs_path, run_dir, *, registry_path=None, simulate_llm=False, catalog_path=None, allow_network=False, synthetic=False, fetcher=None):
    run = Path(run_dir); run.mkdir(parents=True, exist_ok=False); run_id = run.name; stages = []
    registry_path = registry_path or Config().registry_path
    target, identity = target_from_registry(registry_path, company)
    store = ClaimStore.load(claims_path); evidence = read_jsonl(evidence_path); by_id = {r["evidence_id"]: r for r in evidence}
    spec = json.loads(Path(inputs_path).read_text(encoding="utf-8"))
    _stage(stages, "claims_load", "real", f"{len(store.claims)} claims loaded; all unverified")
    wanted = {i["claim_id"] for i in spec["inputs"]}
    bundle = RB.select_bundle(store.claims, by_id, max_claims=40)
    bundle["claims"] = bundle["claims"] + [dict(store.get(c), _families=["spec"]) for c in wanted if c not in {x["claim_id"] for x in bundle["claims"]}]
    extra = [by_id[store.get(c)["source_chunk_id"]] for c in wanted]; bundle["evidence_records"] = list({r["evidence_id"]: r for r in bundle["evidence_records"] + extra}.values())
    RB.write_bundle(bundle, run / "bundle")
    _stage(stages, "evidence_bundle", "real", f"{len(bundle['claims'])} claims / {len(bundle['evidence_records'])} chunks selected for F1/R1 (bounded)")
    cfg = Config(); live_ready = bool(cfg.api_key) and not simulate_llm
    if live_ready or simulate_llm:
        fr = RB.run_f1_r1(target.name, run / "bundle", run / "research", config=dataclasses.replace(cfg, registry_path=Path(registry_path)), simulate=simulate_llm)
    else:
        fr = {"f1": {"execution": "blocked", "error": "SIGNALFORGE_API_KEY not configured; live F1 not attempted"}, "r1": {"execution": "not_executed", "reason": "F1 not run"}}
    for k in ("f1", "r1"):
        _stage(stages, k.upper(), fr[k]["execution"], fr[k].get("error") or fr[k].get("reason") or ("deterministic stand-in, no model call" if fr[k]["execution"] == "simulated" else "live"))
    plan = json.loads((run / "research" / "r1_plan.json").read_text()) if (run / "research" / "r1_plan.json").is_file() else None
    if catalog_path and allow_network and plan:
        reqs = SR.plan_requests(plan, SR.load_catalog(catalog_path), sorted(wanted), spec["hypothesis_id"]); res = SR.execute(reqs, run / "retrieval", fetcher=fetcher, registry_path=registry_path, company=target.name)
        _stage(stages, "source_retrieval", "real" if fetcher is None else "simulated", json.dumps(res["summary"]))
    else:
        _stage(stages, "source_retrieval", "not_executed", "no operator catalog and/or network not allowed; the adapter is implemented and fixture-tested only")
    level_for = None
    verifications, verified = verify_inputs(spec, store, by_id, target, level_for)
    write_json(run / "verification_results.json", verifications)
    _stage(stages, "source_verification", "real", f"{len(verifications)} assertions checked against the cited chunk text at level extracted_text_review (not primary-source); outcomes " + json.dumps({o: sum(v['outcome'] == o for v in verifications) for o in V.OUTCOMES if any(v['outcome'] == o for v in verifications)}))
    usable = {r: v for r, v in verified.items() if v[3]["outcome"] in S.USABLE}
    calcs, derived, I = compute_signals(usable, synthetic=synthetic)
    write_json(run / "calculations.json", calcs)
    _stage(stages, "financial_signals", "real", f"{sum(c['status'] == 'computed' for c in calcs)} of {len(calcs)} calculations computed (deterministic code)")
    ident = {"name": target.name, "aliases": list(target.aliases), "identity_status": identity}
    finding = build_finding(run_id, ident, identity, calcs, derived, I, [v[3] for v in usable.values()], usable, by_id, spec, [], synthetic, spec.get("reference_year"), all(c["claim_verification_status"] == "unverified" for c in store.claims))
    finding["stage_provenance"] = stages + [{"stage": "adjudication", "execution": "real", "detail": f"status={finding['finding_status']} strength={finding['evidence_strength']} (provisional rubric)"}]
    validate_against(finding, "finding")
    problems = FD.check_traceability(finding, store, by_id)
    write_json(run / "finding_bundle.json", finding)
    write_json(run / "stage_manifest.json", {"run_id": run_id, "company": ident, "stages": finding["stage_provenance"], "traceability_problems": problems, "claims_path": str(claims_path), "evidence_path": str(evidence_path), "inputs_path": str(inputs_path),
                                             "network_used": bool(catalog_path and allow_network), "model_used": fr["f1"]["execution"] == "real"})
    return finding, problems

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--company", required=True); ap.add_argument("--claims", required=True); ap.add_argument("--evidence", default=str(ROOT / "data" / "processed_step6" / "evidence.jsonl"))
    ap.add_argument("--inputs", required=True); ap.add_argument("--run-dir", required=True); ap.add_argument("--registry"); ap.add_argument("--simulate-llm", action="store_true")
    ap.add_argument("--catalog"); ap.add_argument("--allow-network", action="store_true"); ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args(argv)
    try: f, problems = run_pipeline(a.company, a.claims, a.evidence, a.inputs, a.run_dir, registry_path=a.registry, simulate_llm=a.simulate_llm, catalog_path=a.catalog, allow_network=a.allow_network, synthetic=a.synthetic)
    except (OSError, ValueError, KeyError) as e:
        print(f"Pipeline error: {type(e).__name__}: {e}", file=sys.stderr); return 2
    print(json.dumps({"finding_status": f["finding_status"], "evidence_strength": f["evidence_strength"], "rank_score": f["rank_score"], "headline": f["headline"], "traceability_problems": problems}, indent=1))
    return 0 if not problems else 1

if __name__ == "__main__": raise SystemExit(main())
