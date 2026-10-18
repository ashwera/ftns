# SignalForge pipeline completion report (2026-10-18)

Scope: advance every stage from claims to a frontend-ready finding on the existing code. Nothing here is committed. Labels used throughout: **real** (executed, no stand-in), **simulated** (deterministic stand-in, no model/network), **blocked** (needs an unavailable credential or service), **not executed**.

## 1. Architecture and actual data flow
```
processed_step6 (8,241 page blocks)                         [Claude Step 6 / Codex ingestion]  real
  -> claim_extraction (prose, 0.2.0) + table_extraction (Layer 1.5 + Codex Feature Y)             real
  -> claims.jsonl (all unverified)  + archive_evaluation (manifest, audit, duplicates)            real
  -> research_bridge.select_bundle -> F1 (existing gate) -> R1 (plan only)                         simulated (live blocked: no API key)
  -> source_retrieval (catalog-driven adapter over public_sources)                                 implemented + fixture-tested, not executed
  -> claim_verification (separate results; level extracted_text_review)                            real, NOT primary-source
  -> signals (deterministic calculators with traces)                                               real
  -> findings (adjudication, provisional rubric, traceability check)                               real
  -> finding_bundle.json (frontend contract, schema finding.schema.json)                           real
```
Status vocabularies are kept apart (`pipeline_contract.py`): `extraction_status` (existing), `claim_verification_status` (const `unverified`, never mutated), verification `outcome` + `verification_level`, `finding_status` + `evidence_strength`.

## 2. Reused
Claim, evidence and F1/R1 schemas; the F1 eligibility gate and credential guard (unchanged); `public_sources.retrieve_urls`; the registry; extractors; golden fixtures and harness; Codex's table continuation work.

## 3. Implemented (all new files)
`archive_evaluation.py`, `pipeline_contract.py`, `research_bridge.py`, `source_retrieval.py`, `claim_verification.py`, `signals.py`, `findings.py`, `pipeline.py`; schemas `verification_result`, `signal_calculation`, `finding`; five test files (`test_pipeline_*.py`, 43 new tests); run directories under `signalforge/data/runs/`; reviewed-input specs under `signalforge/data/pipeline_inputs/`; a contract sample under `signalforge/data/finding_contract_sample/`.

## 4. Tested and executed
- Full suite: 168 tests OK (125 earlier + 43 new). Golden harness: 34 PASS / 0 FAIL / 1 accepted XFAIL (GC-27), unchanged.
- Archive run `run_20261018_archive`: both extractors over all 8,241 chunks, 0 failures, 0 schema failures, table-aware output byte-identical to Codex's `claims_table_xy`. Prose-only 4,423 claims (6 extracted / 100 ambiguous / 4,317 needs_review); table-aware 40,942 (15 / 15,791 / 25,136). See `archive_evaluation_report.md`.
- Manual audit (64 claims, my reading of extracted text, not PDFs): all 15 `extracted` structurally aligned, 8 of them overconfident (GC-27 gap); 2 non-extracted claims carry wrong units with an `ambiguous` status (both in `table_extraction.py`, requested of Codex).

## 5. End-to-end result (real data, NTPC; run `run_20261018_ntpc_slice`)
Finding status **provisional_hypothesis**, evidence strength **Weak**, rank 49.0 (capped; provisional rubric).
- 4.6% of NTPC Limited's own under-implementation pipeline is renewable (bounds 4.3 to 4.9%) versus 75.4% of the JV and subsidiary pipeline; 95.1% of the group's 14.5 GW renewable pipeline sits in JVs/subsidiaries. Group pipeline is 42.1% of installed capacity; installed plus pipeline renewables cover 35.5% of the 60 GW 2032 target (a target, labelled as such).
- Inputs come from pages 90, 91 and 112 of the FY2024-25 annual report text. Table cell cross-checks (Total (I) 15,376; Total (II) 18,295; Total on-going 33,671; RE parent 725) all match in the same chunk, and 14.5 GW minus 13,791 MW = 709 MW lies within rounding of 725 MW. These are internal consistency checks of one filing, not independent corroboration.
- Why only provisional: no input was checked against the original PDF or an exchange filing (level `extracted_text_review`); 6 of 7 inputs are `partially_supported` (basis, period or status not fully resolved in the interleaved text); corroboration is a single issuer. The finding must not be presented as verified.
- Every headline number maps to an input or calculation and every input to a stored claim and chunk (`traceability_problems: []`).

## 6. Second-company generalization (PARTIAL)
- No real source data exists in the repository for any second company, so no real second-company finding was produced and none is claimed.
- `run_20261018_second_company_synthetic`: a clearly SYNTHETIC "Meridian Power Limited" with a synthetic registry entry exercises the same code with target resolved from configuration (name + alias), real extractors, verification, signals and adjudication: provisional/Weak, 20.0% vs 60.0%, traceable. It shows the code is not NTPC-specific; it does not show performance on real filings.
- `run_20261018_second_company_nodata`: "Power Grid Corporation of India Limited" configured by name only (no identifiers invented, `config_only`) with no data: F1 blocked, result `no_defensible_signal`.
- Known generalization limits: the renewable-pipeline role names and the reviewed-input specification are written per company by an analyst; metric label patterns in the extractor are English/Indian-filing oriented.

## 7. Blockers (exact)
1. Live F1/R1: `SIGNALFORGE_API_KEY` is not set; the guard is intact and was not bypassed. F1/R1 ran only as simulated stand-ins (their outputs say SIMULATED).
2. Live retrieval and primary-source verification: no operator catalog of permitted official URLs exists for NTPC and the repository run did not use the network. The adapter is tested with fakes only. Earlier, live NSE retrieval failed closed on robots.txt.
3. `table_extraction.py` defects (Codex, Feature Y in progress): unit `INR crore` applied to an electricity-units value and to a per-share value; GC-27 parent-section context. Logged in `COORDINATION.md`.
4. Frontend: contract and sample delivered; Codex has not yet consumed them.

## 8. Readiness
| # | Stage | Rating | Evidence / limitation | Blocks demo? |
|---|---|---|---|---|
| 1 | Input ingestion | PASS | 8,241 schema-valid blocks, identity at document level | no |
| 2 | Claim extraction | PARTIAL | 0 failures, but only 15 of 40,942 claims `extracted`; 8 of those overconfident; 2 wrong units seen in audit | partly |
| 3 | Schema validity | PASS | 0 schema failures; 3 new schemas validated | no |
| 4 | Claim provenance | PASS | every claim has chunk, page, path, excerpt; table claims keep row/header; no URLs/dates exist in source | no |
| 5 | Entity and accounting-basis resolution | PARTIAL | basis resolved only in sentence-local cases; document-level identity only; analyst assertions needed for basis/status | partly |
| 6 | F1 selection | PARTIAL | gate works and was exercised; live blocked; simulated stand-in only | yes for live |
| 7 | R1 planning | PARTIAL | plan schema/ids validated; simulated; no retrieval | yes for live |
| 8 | Source retrieval | PARTIAL | adapter + 5 fixture tests; never run live | yes |
| 9 | Source verification | PARTIAL | independent check logic tested on 13 cases; applied at text-review level only; no primary source | yes for Strong/Moderate |
| 10 | Financial calculations | PASS | 4 families, 15 tests, traces, bounds, incompatibility refusals | no |
| 11 | Corroboration and contradiction handling | PARTIAL | independence rules tested; contradictions block; no independent source exists in the data | yes |
| 12 | Finding adjudication and ranking | PARTIAL | rubric implemented and tested (strong/weak/contradicted/duplicate/missing); provisional, uncalibrated | no |
| 13 | Frontend integration | NOT_TESTED | contract + sample provided; Codex has not connected it | no |
| 14 | Second-company generalization | PARTIAL | synthetic company and no-data refusal only | yes for "unseen company" claim |
| 15 | Reproducible end-to-end execution | PASS | one command; deterministic apart from run id; 168 tests | no |

Overall classification: **Ready for hypothesis generation**, and for manual triage. Not yet ready for source-backed research (no live retrieval or primary-source verification run) or evidence-backed findings (Weak at best), and not demonstrated on a real unseen company.

## 9. Commands
```
PYTHONPATH=signalforge/src python3 -m signalforge.archive_evaluation --run-dir signalforge/data/runs/<new_run_id>
PYTHONPATH=signalforge/src python3 -m signalforge.pipeline --company "NTPC Limited" --claims <claims.jsonl> --inputs signalforge/data/pipeline_inputs/ntpc_renewable_pipeline_reviewed_inputs.json --run-dir signalforge/data/runs/<new_run_id> [--simulate-llm]
PYTHONPATH=signalforge/src python3 -m unittest discover -s signalforge/tests
```

## 10. Next actions (highest first)
1. Obtain the original FY2024-25 annual report PDF / NSE filing for NTPC (operator-supplied catalog), run retrieval, and re-verify the seven inputs at `primary_source` level; this alone can move the finding from Weak to Moderate.
2. Set `SIGNALFORGE_API_KEY` and run live F1/R1 on the bounded bundle.
3. Codex: fix the two unit-assignment defects and consider the GC-27 section-row patch; connect `finding_bundle.json` to the dashboard.
4. Add a real second company's filings and a reviewed-input spec.

## 11. Addendum (2026-10-19): verification integration, independence and audit trail
Unchanged: the four signal calculators and `finding.schema.json` (only additive optional fields were added: `audit_trail`, `decision_log`, `downgrade_reasons`, `rejected_hypothesis`, `verification_summary`).

**Source catalog ingestion (no URL in code).** `--catalog <file>` loads an operator-verified catalog (format in `source_catalog.py`; blank form at `signalforge/data/pipeline_inputs/source_catalog.template.json`). Entries give a `url` and/or a `local_path` snapshot (optionally `sha256`-pinned), publisher, class, publication date, `verified_by`, `issuer_submitted` and `derived_from`. Nothing is fetched unless `--allow-network` is also given. A source reaches `primary_source` level only if it is available, official-class, dated, attested by `verified_by`, and matches any pinned hash. The catalog's company must match the target. Plug in Samaira's catalog by passing her file; no code change.

**Verification integration.** For every input the pipeline now keeps the text-extraction review and adds one check per available source (value located by its printed forms, a rounded GW figure may match a precise MW figure within the claim's rounding, and a different number next to the same label/period is a contradiction, not silence). Results are combined per input: primary confirmation wins, primary contradiction contradicts, a confirmation next to a contradiction is a conflict (never averaged).

**Independence.** Mirrors (same hash), the issuer's own filing, exchange/regulator-hosted copies of it (`issuer_submitted`, or publisher equal to the target) and `derived_from` documents form one group. Strong needs at least 2 independent confirming groups for every key input.

**Key inputs decide.** Spec items carry `key` (default true). A contradicted key input rejects the finding (`no_defensible_signal`, `rejected_hypothesis` preserved, contradiction cited). A conflict, a partial or unresolved key input, or text-only verification downgrades to provisional/Weak with a reason in `downgrade_reasons`. Failed non-key inputs are excluded from calculations and listed but cannot raise strength.

**Audit trail.** `audit_trail` maps each input to its claim and extraction status, every verification result (source, page, passage hash, open checks), effective outcome and level, independent group count and unavailable sources; `decision_log` records how the verdict was reached.

**One command**
```
PYTHONPATH=signalforge/src python3 -m signalforge.pipeline --company "NTPC Limited" \
  --claims signalforge/data/runs/run_20261018_archive/table_aware/claims.jsonl \
  --inputs signalforge/data/pipeline_inputs/ntpc_renewable_pipeline_reviewed_inputs.json \
  --catalog <samaira_catalog.json> [--allow-network] --run-dir signalforge/data/runs/<new_run_id> [--simulate-llm]
```
It prints a table of every input (key, outcome, level, independent groups, claim and extraction status) and the verdict with downgrade reasons. Without `--catalog` the current NTPC result is unchanged: provisional/Weak, all inputs at text-review level (see `run_20261019_ntpc_slice_audit`). Tested on synthetic catalogs only (13 new tests): issuer-only gives Moderate, issuer plus an independent regulator gives Strong, exchange copies and derived decks do not add independence, a conflicting source downgrades, a contradicted key input rejects, a hash mismatch or undated source falls back to text-review, and URL-only entries are not fetched without network permission. It has not been run on a real NTPC catalog because none was available.
