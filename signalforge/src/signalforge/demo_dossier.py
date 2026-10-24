"""Build an analyst-directed, source-linked investigation dossier from real run files.

This is presentation of an executed case, not autonomous search or model output.
"""
import argparse
import hashlib
import json
from pathlib import Path
from .capacity_timeline import exact_share


def build(root, run):
    root, run = Path(root), Path(run)
    finding = json.loads((run / "finding_bundle.json").read_text())
    cod = [json.loads(line) for line in (root / "data/cod_sources_20261024/evidence.jsonl").read_text().splitlines()]
    regulator = [json.loads(line) for line in (root / "data/regulator_20261024/evidence.jsonl").read_text().splitlines()]
    def cite(row, excerpt):
        if excerpt not in " ".join(row["excerpt_or_fact"].split()):
            raise ValueError("Citation excerpt absent from original extracted page")
        return {"source_chunk_id": row["evidence_id"], "source_path": row["source_path"],
                "page": row.get("page_number"), "locator": row.get("source_locator"),
                "excerpt": excerpt, "url": row.get("source_url")}
    nk = next(r for r in cod if "a41caf" in r["source_path"])
    trial = next(r for r in cod if "eb9a13" in r["source_path"])
    reg = next(r for r in regulator if r.get("page_number") == 132)
    cn = cite(nk, "Hrs. of 15.06.2025.")
    ct = cite(trial, "has successfully completed trial operation and consequently included in the installed capacity of NTPC Limited.")
    cr = cite(reg, "GRIDCO has not considered share of power from Unit #3 in the estimated availability of power.")
    def statement(text, *sources): return {"statement": text, "citations": list(sources)}
    dossier = {
        "schema_version": "1.0", "run_id": finding["run_id"], "finding_id": finding["finding_id"],
        "chosen_prompt": "Whether announced capacity additions materially diverge from actually commissioned capacity (Energy, Power & Renewables).",
        "case_headline": "North Karanpura Unit 3: installed-capacity recognition and commercial operation are separate milestones; a delay headline needs a matched schedule.",
        "case_status": "no_defensible_signal",
        "implications": [
            statement("Treat the 660 MW project as one unit across milestones; do not count trial completion and COD as two additions.", ct, cn),
            statement("Financial timing must use the commercial-operation event and applicable tariff rules; this investigation does not estimate revenue lost.", cn),
            statement("The independent FY2024-25 procurement forecast already excluded Unit 3. A claim of an undisclosed FY25 supply shortfall is not supported by this evidence.", cr),
            statement("A schedule-based slippage calculation requires the last valid committed COD date and revisions. Public milestone dates alone cannot establish management underdelivery.", ct, cn)
        ],
        "candidate_decisions": [
            {"hypothesis": "Parent versus JV renewable pipeline reveals a hidden economic exposure", "decision": "rejected", "reason": "The ownership structure is openly disclosed, pipeline capacity is not equity ownership, and independent key-input confirmation is missing. Retain only as a Weak audit example.", "citations": []},
            {"hypothesis": "Commissioning milestones conceal a commercial-operation gap", "decision": "selected", "reason": "Investigated actual trial/COD filings and independent procurement treatment. The narrower milestone distinction is supported; the stronger underdelivery thesis fails without matched schedules.", "citations": [ct, cn, cr]},
            {"hypothesis": "Revenue mix changed ahead of narrative", "decision": "deferred", "reason": "No verified same-basis segment revenue series was collected in this run.", "citations": []},
            {"hypothesis": "A material financing relationship is hidden", "decision": "deferred", "reason": "No verified transaction-level materiality comparison was established.", "citations": []}
        ],
        "action_log": [
            {"action": "Rebuilt claims from the preserved page-block evidence", "outcome": "40,942 candidates; zero schema/chunk failures; extraction is not verification.", "execution": "real", "citations": []},
            {"action": "Retrieved original NTPC annual report and checked its pinned hash", "outcome": "Exact match; reran seven input checks with zero traceability problems.", "execution": "real", "citations": []},
            {"action": "Searched capacity and COD evidence across issuer, government and counterparties", "outcome": "Retrieved three issuer filings and OERC's original tariff order. CEA redirected to login; ERPC crawler policy prevented retrieval. Neither is counted as verified.", "execution": "real", "citations": [cn, ct, cr]},
            {"action": "Attack the apparent delay interpretation", "outcome": "Trial completion differs from COD; independent procurement planning already excluded Unit 3. Reject the stronger surprise/underdelivery claim.", "execution": "real", "citations": [ct, cn, cr]}
        ],
        "chronology": [
            {"date": "2024-02-13", "event": "OERC tariff order for FY2024-25 records exclusion of Unit 3 from GRIDCO estimated supply; order date checked on PDF page 1.", "citations": [cr]},
            {"date": "2025-03-31", "event": "Cutoff for the older NTPC renewable-pipeline audit example; it measures project portfolio, not COD slippage.", "citations": []},
            {"date": "2025-06-12", "event": "NTPC filing announces completion of trial operation and installed-capacity inclusion for Unit 3.", "citations": [ct]},
            {"date": "2025-06-15", "event": "Effective commercial-operation date for North Karanpura Unit 3, stated in the 13 June filing.", "citations": [cn]}
        ],
        "opposing_evidence": [statement("Independent OERC/GRIDCO supply planning had already excluded Unit 3; absence of FY25 procurement from this unit was not hidden in that forecast.", cr)],
        "counterargument": statement("Milestone terminology and disclosed forecast exclusions can explain an apparent gap. These facts defeat a simple claim of unexpected commercial underdelivery; schedule revisions and tariff treatment remain untested.", ct, cn, cr),
        "falsification": [statement("A schedule-gap finding requires an original, dated, unrevised commitment for the same 660 MW Unit 3 and matching COD definition. If the valid revised commitment is on or after 15 June 2025, a delay relative to that commitment disappears.", cn)],
    }
    model_run = root / "data/runs/run_20261024_live_research/production_final"
    if (model_run / "manifest.json").is_file():
        manifest = json.loads((model_run / "manifest.json").read_text())
        if all(manifest.get("stages", {}).get(stage, {}).get("execution") == "real" for stage in ("f1", "r1")):
            live_f1 = json.loads((model_run / "f1.json").read_text())
            dossier["action_log"].append({
                "action": "Execute live model angle selection and research planning on machine-checked original PDF passages",
                "outcome": f"{manifest['provider']} / {manifest['model']}: {len(live_f1['ranked_candidates'])} candidate angles; F1 and R1 validated. Artifacts: {model_run}. This separate model run proposes research; it does not verify the capacity case or execute R1 retrieval.",
                "execution": "real", "citations": []})
    (run / "research_dossier.json").write_text(json.dumps(dossier, indent=2) + "\n")
    ratios = {"parent_renewable_share": exact_share("725", "15376"), "jv_renewable_share": exact_share("13791", "18295"), "jv_share_of_group_renewable": exact_share("13791", "14516")}
    (run / "exact_ratio_audit.json").write_text(json.dumps(ratios, indent=2) + "\n")
    return dossier


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="signalforge"); ap.add_argument("--run", required=True)
    args = ap.parse_args(); build(args.root, args.run)
