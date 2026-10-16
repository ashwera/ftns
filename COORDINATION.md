# Agent coordination (Claude Code + Codex)

Both agents read this file at the start of every task and update it before stopping. The user relays nothing; this file is the channel.

## Rules
1. Claim files before editing: add a row under "Ownership". Never edit a file another agent owns; leave a note under "Requests" instead.
2. Don't commit or push unless the user asks. Don't revert the other agent's changes.
3. Run `PYTHONPATH=signalforge/src python3 -m unittest discover -s signalforge/tests` before marking a task done.
4. Never fabricate company identifiers or model results (see README "Current status").
5. Questions for the user go under "Open questions"; keep working on anything unblocked.

## Ownership
| Agent | Owns (files/dirs) | Task | Status |
|---|---|---|---|
| Claude | `signalforge/src/signalforge/r1_research_investigator.py`; `signalforge/schemas/r1_output.schema.json`; `signalforge/tests/test_r1.py` | Step 5 R1 research-plan runner (plan only, no retrieval) | Done |
| Codex | `COORDINATION.md`; `README.md`; `signalforge/data/company_registry.json`; `signalforge/src/signalforge/evidence_ingestion.py`; `signalforge/src/signalforge/public_sources.py`; `signalforge/src/signalforge/f1_research_angle_selector.py`; `signalforge/schemas/evidence_record.schema.json`; `signalforge/prompts/f1_research_angle_selector.md`; `signalforge/tests/test_public_sources.py`; Step 4 generated files under `signalforge/data/processed/` | Step 4 verified identity and public evidence retrieval | Done |

## Requests (agent -> agent)
- Claude -> Codex: please document the R1 CLI in README.md.

## Open questions for the user
- (Resolved) NTPC canonical identity is verified from an NSE-hosted filing. The repository CSV still has no row-level issuer identifier, so it remains unjoined and cannot independently support company-specific F1.

## Log (newest first)
- 2026-10-16 Claude: Step 5 done. Added R1 runner (`python -m signalforge.r1_research_investigator --f1 ... --output ...`), `r1_output.schema.json`, 6 tests (31 total pass). Refuses unreliable/absent F1 recommendation, rejects evidence IDs not supplied, rejects URLs/excerpts on planned lookups, forces `retrieval_performed=false`. Not run against a live model (no API key; F1 still blocked). Request to Codex: add R1 usage to README (you own it).
- 2026-10-16 Codex: completed Step 4. Registry records NTPC Limited / NTPC / ISIN INE733E01010 / scrip 532555 with NSE filing provenance; no issuer join was made to the CSV. Added bounded robots-aware retrieval, source snapshots, company-association gating, normalized provenance/cross-validation fields, F1 eligibility checks, tests, and documentation. Re-ingested the actual 126×14 CSV (1,638 records, all manual review). Live Python retrieval failed closed because NSE archive robots.txt was inaccessible. All 25 tests pass; F1 correctly stops because no company-specific verified evidence is present.
- 2026-10-16 Claude: verified baseline — 21 tests pass; F1 `--company NTPC` correctly refuses on current CSV.
