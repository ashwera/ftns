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
from . import source_catalog as SC
from . import source_retrieval as SR
from .config import Config, ROOT
from .pipeline_contract import ClaimStore, citation, collapse, read_jsonl, target_from_registry, validate_against, write_json

ROLES = ("installed_total_group", "re_installed_group", "re_pipeline_group", "pipeline_total_group", "pipeline_jv_sub", "re_pipeline_jv_sub", "re_target")

def _stage(stages, name, execution, detail): stages.append({"stage": name, "execution": execution, "detail": detail})

def _src_meta(src, page):
    return {"source_chunk_id": None, "source_path": src["url"] or src["source_id"], "page": page, "url": src["url"], "publisher": src["publisher"], "publication_date": src["publication_date"],
            "retrieved_at": None, "document_family": src["source_id"]}

def verify_inputs(spec, store, evidence_by_id, target, sources=None):
    """Per input: the baseline text-extraction review plus one check per available catalog source, combined into an effective result.
    Contradictions between primary sources are preserved, never averaged. Returns (all_results, verified, audit)."""
    all_results, verified, audit = [], {}, []
    sources = sources or []
    for item in spec["inputs"]:
        claim = store.get(item["claim_id"]); rec = evidence_by_id[claim["source_chunk_id"]]
        a = V.assertion_from_claim(claim, basis=item["basis"], statement_status=item["statement_status"], label_terms=item["label_terms"], entity_names=[*target.names])
        a["entity"] = target.name
        if item.get("as_of_date") is not None or claim["as_of_date"] is None: a["as_of_date"] = item.get("as_of_date")
        a["period_text"] = item.get("period_text") or claim["raw_period_text"]
        reviewer = spec["reviewer"] | {"kind": "ai_assisted_analyst"}
        base_src = {"source_chunk_id": rec["evidence_id"], "source_path": rec["source_path"], "page": rec.get("page_number"), "url": rec.get("source_url"), "publisher": rec.get("source_organization"),
                    "publication_date": rec.get("publication_date"), "retrieved_at": None, "document_family": rec.get("document_title")}
        results = [V.verify_assertion(a, rec["excerpt_or_fact"], source=base_src, level="extracted_text_review", verification_id=f"ver_{item['role']}_{claim['claim_id'][-8:]}_text", input_name=item["name"],
                                      claim_id=claim["claim_id"], reviewer=reviewer, cross_checks=item.get("cross_checks", []))]
        notes = []
        for src in sources:
            if src["status"] != "available": notes.append({"source_id": src["source_id"], "status": src["status"], "error": src["error"]}); continue
            level = SC.level_for(src); hits = V.locate_passages(src["pages"], a["value"], item["label_terms"])
            variant, vlabel = a, "as asserted"
            if not hits and a["unit"] == "GW" and item.get("rounding_uncertainty") is not None:
                lo, hi = (a["value"] - item["rounding_uncertainty"]) * 1000, (a["value"] + item["rounding_uncertainty"]) * 1000
                for pg in src["pages"]:
                    for m in V.L1.QTY.finditer(V.collapse(pg["text"])):
                        v = V.L1._number(m.group("num"))
                        if v is not None and m.group("unit") == "MW" and lo <= v <= hi and any(t.lower() in V.collapse(pg["text"])[max(0, m.start() - 300):m.end() + 300].lower() for t in item["label_terms"]):
                            variant = {**a, "value": v, "unit": "MW"}; vlabel = f"precise MW figure {v:g} within the claim's rounding of {a['value']:g} GW"; hits = V.locate_passages([pg], v, item["label_terms"]); break
                    if hits: break
            if not hits:
                res = None
                for w in V.label_windows(src["pages"], item["label_terms"]):   # same label, different number => contradiction, not silence
                    cand = V.verify_assertion(a, w["passage"], source=_src_meta(src, w["page"]), level=level, verification_id=f"ver_{item['role']}_{src['source_id']}", input_name=item["name"], claim_id=claim["claim_id"],
                                              reviewer={"kind": "automated_passage_check", "id": "claim_verification.verify_assertion", "note": "value not found; label window inspected"}, cross_checks=item.get("cross_checks", []))
                    if cand["outcome"] == "contradicted": res = cand; break
                results.append(res or V.verify_assertion(a, "", source=_src_meta(src, None), level=level, verification_id=f"ver_{item['role']}_{src['source_id']}", input_name=item["name"], claim_id=claim["claim_id"],
                                                         reviewer={"kind": "automated_passage_check", "id": "claim_verification.verify_assertion", "note": "value not found in this source"}))
                continue
            h = hits[0]
            r = V.verify_assertion(variant, h["passage"], source=_src_meta(src, h["page"]), level=level, verification_id=f"ver_{item['role']}_{src['source_id']}", input_name=item["name"], claim_id=claim["claim_id"],
                                   reviewer={"kind": "automated_passage_check", "id": "claim_verification.verify_assertion", "note": vlabel}, cross_checks=item.get("cross_checks", []))
            results.append(r)
        all_results += results
        comb = V.combine_results(results); eff = json.loads(json.dumps(comb["representative"]))
        eff.update(outcome=comb["outcome"], verification_level=comb["level"], verification_ids=[r["verification_id"] for r in results], verification_id=f"eff_{item['role']}", conflict=comb["conflict"], rationale=comb["reason"] + ". " + eff["rationale"])
        by_id = {s["source_id"]: s for s in sources}
        confirming = [by_id[r["source"]["document_family"]] for r in results if r["verification_id"] in comb["confirming"] and r["source"]["document_family"] in by_id]
        descs = [{"publisher": c["publisher"], "document_family": c["source_id"], "sha256": c["sha256"], "derived_from": c["derived_from"], "issuer_submitted": c["issuer_submitted"] or (c["publisher"] or "").casefold() in {n.casefold() for n in target.names}} for c in confirming]
        groups = V.assess_independence(descs)["independent_source_count"] if descs else 0
        key = item.get("key", True)
        audit.append({"role": item["role"], "input_name": item["name"], "key": key, "claim_id": claim["claim_id"], "claim_extraction_status": claim["extraction_status"], "claim_verification_status": claim["claim_verification_status"],
                      "effective_outcome": comb["outcome"], "effective_level": comb["level"], "conflict": comb["conflict"], "reason": comb["reason"], "independent_confirming_groups": groups,
                      "unavailable_sources": notes, "results": [{"verification_id": r["verification_id"], "level": r["verification_level"], "outcome": r["outcome"], "source": r["source"]["document_family"] or "extracted_text", "page": r["source"]["page"], "url": r["source"]["url"],
                                                                 "passage_sha256": r["source"]["passage_sha256"], "failed_or_open_checks": {k: c["result"] for k, c in r["checks"].items() if c["result"] in ("mismatch", "unresolved")}, "discrepancies": r["discrepancies"], "reviewer": r["reviewer"]["note"]} for r in results]})
        verified[item["role"]] = (item, claim, rec, eff)
    return all_results, verified, audit

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
        add(S.ratio_signal("capacity_pipeline_conversion", "pipeline_relative_to_installed_base", I["pipeline_total_group"], I["installed_total_group"], counterargument="Pipeline includes coal and hydro as well as renewables; the ratio is not a forecast of additions.", falsification_test="Installed and pipeline totals are not on the same group boundary.", synthetic=synthetic, basis_relation={("group", "consolidated"), ("group", "group"), ("consolidated", "group"), ("consolidated", "consolidated")}))
    if have("re_installed_group", "re_pipeline_group", "re_target"):
        add(S.target_coverage_signal("re_installed_plus_pipeline_vs_target", [I["re_installed_group"], I["re_pipeline_group"]], I["re_target"], counterargument="The target may be defined on a different boundary or year basis; pipeline is not commissioned.", falsification_test="Disclosed target is on a different boundary (e.g. parent-only) than the group capacities used here.", synthetic=synthetic))
    return calcs, derived, I

def build_finding(run_id, company, identity, calcs, derived, I, verifications, verified, evidence_by_id, spec, stages, synthetic, reference_year, claims_unverified, *, all_verified=None, audit=(), decision_log=(), sources=(), all_results=()):
    computed = {c["name"]: c for c in calcs if c["status"] == "computed"}
    all_verified = all_verified or verified
    key_roles = [i["role"] for i in spec["inputs"] if i.get("key", True)]
    key_eff = {r: all_verified[r][3] for r in key_roles if r in all_verified}
    inputs_out, seen = [], set()
    for role, (item, claim, rec, r) in verified.items():
        inp = I[role]; inputs_out.append({k: inp[k] for k in ("name", "value", "unit", "as_of_date", "basis", "statement_status", "claim_ids", "verification_ids")} | {"verification_outcome": r["verification_outcome"] if False else r["outcome"], "verification_level": r["verification_level"], "citation": citation(claim, rec)})
    for k, d in derived.items(): inputs_out.append({kk: d[kk] for kk in ("name", "value", "unit", "as_of_date", "basis", "statement_status", "claim_ids", "verification_ids")} | {"verification_outcome": d["verification_outcome"], "verification_level": "extracted_text_review", "citation": {"source_chunk_id": None, "source_path": None, "page": None, "locator": "derived by subtraction of two cited inputs", "excerpt": f"{d['name']} = whole - part (see calculation trace)", "url": None}})
    gate = [c for c in ("re_share_of_parent_own_pipeline", "re_share_of_jv_subsidiary_pipeline") if c in computed]
    prov = stages
    key_contra = [e for e in key_eff.values() if e["outcome"] == "contradicted"]
    if key_contra:
        inputs_all = [{k: S.make_input(i["name"], all_verified[r][1]["value"], all_verified[r][1]["unit"], as_of=i.get("as_of_date"), period_text=i.get("period_text"), basis=i["basis"], status=i["statement_status"], claim_ids=[all_verified[r][1]["claim_id"]], verification=all_verified[r][3])[k] for k in ("name", "value", "unit", "as_of_date", "basis", "statement_status", "claim_ids", "verification_ids")}
                       | {"verification_outcome": all_verified[r][3]["outcome"], "verification_level": all_verified[r][3]["verification_level"], "citation": citation(all_verified[r][1], all_verified[r][2])} for r, (i, *_ ) in ((x["role"], (x,)) for x in spec["inputs"]) if r in all_verified]
        return FD.reject_finding(finding_id=f"find_{run_id}_{spec['hypothesis_id']}_rejected", run_id=run_id, company=company, headline="Parent-own vs JV/subsidiary renewable pipeline shares (hypothesis as specified)",
                                 why_it_matters="Would show where renewable growth sits relative to the parent.", failed=key_contra, inputs=inputs_all, calculations=[], contradictory_evidence=[], missing_evidence=[], stage_provenance=prov,
                                 claims_all_unverified=claims_unverified, synthetic=synthetic, audit_trail=list(audit), decision_log=list(decision_log))
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
    for v in all_results:
        if v["outcome"] == "contradicted" and v["verification_level"] == "primary_source":
            contradictory.append({"statement": f"Primary source {v['source']['document_family']} contradicts '{v['input_name']}': " + "; ".join(v["discrepancies"]), "claim_ids": [v["claim_id"]] if v["claim_id"] else [],
                                  "citation": {"source_chunk_id": None, "source_path": v["source"]["source_path"], "page": v["source"]["page"], "locator": v["verification_id"], "excerpt": collapse(v["source"]["passage"])[:300], "url": v["source"]["url"]}, "independent": True})
    sources = [{"publisher": "issuer", "document_family": rec.get("source_path"), "sha256": rec.get("source_sha256") or rec.get("source_path"), "derived_from": []} for _, (_, _, rec, _) in verified.items()]
    return FD.adjudicate(finding_id=f"find_{run_id}_{spec['hypothesis_id']}", run_id=run_id, company=company, headline=headline,
        why_it_matters=("Renewable growth is concentrated in joint ventures and subsidiaries, so parent-only metrics and the parent's own capital plan can mis-describe the group's renewable transition, and exposure to those entities' financing and minority interests matters for valuation." if direction == "jv_subsidiary" else "Renewable growth is concentrated in the parent's own pipeline rather than in joint ventures and subsidiaries, which changes who bears the capital and financing exposure."),
        materiality_pp=abs(jv - parent), inputs=inputs_out, verifications=verifications, calculations=list(computed.values()), sources=sources, supporting_evidence=supporting, contradictory_evidence=contradictory,
        alternative_explanations=["Group (consolidated) reporting already includes these entities, so the split may be organisational rather than economic.", "Under-implementation capacity may slip or be re-scoped; the pipeline is not commissioned capacity.", "The parent may hold economic interests in the subsidiaries that offset the apparent concentration."],
        falsification_conditions=["The component table in the primary filing does not match the extracted text, so the parent and JV/subsidiary shares differ from those computed here.", "A different boundary or date is used for the renewable total than for the pipeline total.", "Prior-year disclosures show the same split, implying a structural reporting convention rather than a change."],
        missing_evidence=["Primary-source check of the page 91 table and sentences in the original filing or exchange submission.", "Independent corroboration (regulator or third-party data) of subsidiary renewable pipeline.", "Prior-year pipeline composition to test conversion and trend.", "Ownership percentage and consolidation treatment of each subsidiary/JV."],
        limitations=[f"{sum(a['effective_level'] == 'primary_source' for a in audit)} of {len(audit)} inputs have effective primary-source verification; consult each input's outcome and open checks before relying on it.", "Rounded source figures retain their rounding bounds through the calculations.", "Claims remain unverified; verification results are separate records."],
        stage_provenance=prov, claims_all_unverified=claims_unverified, synthetic=synthetic, reference_year=reference_year, periods=sorted({i["as_of_date"] for i in inputs_out if i["as_of_date"]}),
        key_verifications=list(key_eff.values()), independence_by_input={a['input_name']: a['independent_confirming_groups'] for a in audit if a['key']} or None,
        audit_trail=list(audit), decision_log=list(decision_log), conflicts=sum(bool(e.get('conflict')) for e in key_eff.values()), qualifying_evidence_count=len(contradictory))

def run_pipeline(company, claims_path, evidence_path, inputs_path, run_dir, *, registry_path=None, simulate_llm=False, catalog_path=None, allow_network=False, synthetic=False, fetcher=None):
    run = Path(run_dir); run.mkdir(parents=True, exist_ok=False); run_id = run.name; stages = []
    registry_path = registry_path or Config().registry_path
    target, identity = target_from_registry(registry_path, company)
    store = ClaimStore.load(claims_path); evidence = read_jsonl(evidence_path); by_id = {r["evidence_id"]: r for r in evidence}
    spec = json.loads(Path(inputs_path).read_text(encoding="utf-8"))
    _stage(stages, "claims_load", "real", f"{len(store.claims)} claims loaded; all unverified")
    wanted = {i["claim_id"] for i in spec["inputs"]}
    bundle = RB.select_bundle(store.claims, by_id, max_claims=40)
    if len(wanted) > 40:
        raise ValueError("Reviewed input specification exceeds the 40-claim bundle limit")
    required = [dict(store.get(c), _families=["spec"]) for c in sorted(wanted)]
    bundle["claims"] = (required + [c for c in bundle["claims"] if c["claim_id"] not in wanted])[:40]
    source_ids = sorted({c["source_chunk_id"] for c in bundle["claims"]})
    bundle["evidence_records"] = [by_id[eid] for eid in source_ids]
    RB.write_bundle(bundle, run / "bundle")
    _stage(stages, "evidence_bundle", "real", f"{len(bundle['claims'])} claims / {len(bundle['evidence_records'])} chunks selected for F1/R1 (bounded)")
    cfg = Config(); live_ready = bool(cfg.api_key) and not simulate_llm
    if live_ready or simulate_llm:
        fr = RB.run_f1_r1(target.name, run / "bundle", run / "research", config=dataclasses.replace(cfg, registry_path=Path(registry_path)), simulate=simulate_llm)
    else:
        try:
            eligible_ids = RB.r1.load_evidence_ids(run / "bundle" / "evidence.jsonl", target.name, dataclasses.replace(cfg, registry_path=Path(registry_path)))
        except (OSError, ValueError):
            eligible_ids = []
        blockers = ["SIGNALFORGE_API_KEY not configured"]
        if not eligible_ids:
            blockers.append("no schema-valid human-approved company evidence")
        fr = {"f1": {"execution": "blocked", "error": "; ".join(blockers) + "; live F1 not attempted"}, "r1": {"execution": "not_executed", "reason": "F1 not run"}}
    for k in ("f1", "r1"):
        _stage(stages, k.upper(), fr[k]["execution"], fr[k].get("error") or fr[k].get("reason") or ("deterministic stand-in, no model call" if fr[k]["execution"] == "simulated" else "live"))
    srcs, dlog = [], []
    if catalog_path:
        cat = SC.load(catalog_path)
        if cat.get("company") and cat["company"].casefold() != target.name.casefold() and cat["company"].casefold() not in {x.casefold() for x in target.aliases}:
            raise ValueError(f"catalog is for {cat['company']!r}, not the target {target.name!r}")
        srcs = SC.materialize(cat, Path(catalog_path).parent, run / "sources", allow_network=allow_network, fetcher=fetcher, registry_path=registry_path, company=target.name)
        counts = {k: sum(x["status"] == k for x in srcs) for k in sorted({x["status"] for x in srcs})}
        _stage(stages, "source_catalog", "simulated" if (fetcher is not None and allow_network) else "real", f"{len(srcs)} catalog sources: {json.dumps(counts)}; network {'allowed' if allow_network else 'not used'}")
        write_json(run / "source_catalog_status.json", [SC.describe(x) for x in srcs])
        dlog += [f"source {x['source_id']}: {x['status']}, level {SC.level_for(x)}" + (f" ({x['error']})" if x["error"] else "") for x in srcs]
    else:
        _stage(stages, "source_catalog", "not_executed", "no --catalog supplied; verification limited to the project's text extraction")
    verifications, verified, audit = verify_inputs(spec, store, by_id, target, srcs)
    write_json(run / "verification_results.json", verifications); write_json(run / "audit_trail.json", audit)
    outs = json.dumps({o: sum(a["effective_outcome"] == o for a in audit) for o in V.OUTCOMES if any(a["effective_outcome"] == o for a in audit)})
    prim = sum(a["effective_level"] == "primary_source" for a in audit)
    _stage(stages, "source_verification", "real", f"{len(audit)} inputs verified; {prim} at primary_source level, {len(audit) - prim} at extracted_text_review only; effective outcomes {outs}")
    dlog += [f"input {a['role']}{' [key]' if a['key'] else ''}: {a['effective_outcome']} at {a['effective_level']}; {a['independent_confirming_groups']} independent confirming group(s)" + ("; CONFLICT" if a["conflict"] else "") for a in audit]
    usable = {r: v for r, v in verified.items() if v[3]["outcome"] in S.USABLE}
    calcs, derived, I = compute_signals(usable, synthetic=synthetic)
    write_json(run / "calculations.json", calcs)
    _stage(stages, "financial_signals", "real", f"{sum(c['status'] == 'computed' for c in calcs)} of {len(calcs)} calculations computed (deterministic code)")
    ident = {"name": target.name, "aliases": list(target.aliases), "identity_status": identity}
    finding = build_finding(run_id, ident, identity, calcs, derived, I, [v[3] for v in usable.values()], usable, by_id, spec, [], synthetic, spec.get("reference_year"), all(c["claim_verification_status"] == "unverified" for c in store.claims),
                            all_verified=verified, audit=audit, decision_log=dlog, all_results=verifications)
    finding["stage_provenance"] = stages + [{"stage": "adjudication", "execution": "real", "detail": f"status={finding['finding_status']} strength={finding['evidence_strength']} (provisional rubric)"}]
    validate_against(finding, "finding")
    problems = FD.check_traceability(finding, store, by_id)
    write_json(run / "finding_bundle.json", finding)
    write_json(run / "stage_manifest.json", {"run_id": run_id, "company": ident, "stages": finding["stage_provenance"], "traceability_problems": problems, "claims_path": str(claims_path), "evidence_path": str(evidence_path), "inputs_path": str(inputs_path),
                                             "network_used": bool(catalog_path and allow_network), "catalog_path": str(catalog_path) if catalog_path else None, "model_used": fr["f1"]["execution"] == "real"})
    return finding, problems

def verification_table(f):
    """Human-readable answer to 'which inputs are verified, and how'."""
    rows = [f"{'input':44} {'key':3} {'outcome':20} {'level':22} indep  claim (extraction status)"]
    for a in f.get("audit_trail", []): rows.append(f"{a['input_name'][:44]:44} {'Y' if a['key'] else '-':3} {a['effective_outcome'] + (' !CONFLICT' if a['conflict'] else ''):20} {a['effective_level']:22} {a['independent_confirming_groups']:^5}  {a['claim_id'][-10:]} ({a['claim_extraction_status']})")
    rows.append(f"=> {f['finding_status']} / {f['evidence_strength']}" + ("".join(f"\n   - {r}" for r in f.get("downgrade_reasons", []))))
    return "\n".join(rows)

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--company", required=True); ap.add_argument("--claims", required=True); ap.add_argument("--evidence", default=str(ROOT / "data" / "processed_step6" / "evidence.jsonl"))
    ap.add_argument("--inputs", required=True); ap.add_argument("--run-dir", required=True); ap.add_argument("--registry"); ap.add_argument("--simulate-llm", action="store_true")
    ap.add_argument("--catalog"); ap.add_argument("--allow-network", action="store_true"); ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args(argv)
    try: f, problems = run_pipeline(a.company, a.claims, a.evidence, a.inputs, a.run_dir, registry_path=a.registry, simulate_llm=a.simulate_llm, catalog_path=a.catalog, allow_network=a.allow_network, synthetic=a.synthetic)
    except (OSError, ValueError, KeyError) as e:
        print(f"Pipeline error: {type(e).__name__}: {e}", file=sys.stderr); return 2
    print(verification_table(f))
    print(json.dumps({"finding_status": f["finding_status"], "evidence_strength": f["evidence_strength"], "rank_score": f["rank_score"], "headline": f["headline"], "traceability_problems": problems}, indent=1))
    return 0 if not problems else 1

if __name__ == "__main__": raise SystemExit(main())
