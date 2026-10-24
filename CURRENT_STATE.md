# SignalForge current state — 24 October 2026

Workspace: `/Users/arshiadang/Desktop/fns` (macOS). Branch `main`, inspected HEAD `823d68615a3ce51ee66cd74c803fecda45b00ad7`. `git fetch --all --prune` succeeded. Open PR #4: `sprint2/pdf-native-tables`; inspected as background only. Existing changes were preserved. Nothing staged, committed or pushed by this execution.

## Current requirement audit

| Requirement | Code/artifact and observed result | Status |
|---|---|---|
| Source retrieval and preserved original | `public_sources.py`; recovered official FY25 annual PDF with exact recorded SHA-256; three actual COD/trial PDFs and OERC order downloaded | Executed |
| Search independent of supplied NTPC URLs | `source_discovery.py`: Gemini grounding plus Bing RSS fallback, generic queries, budgets, relevance rejection and action logs | Implemented and exercised; grounding rate-limited, RSS relevance limited |
| Anonymous quote file exclusion | Existing F1 identity tests and loader; no filename-based issuer join | Tested |
| Human approval boundary | New `machine_evidence.py`, F1/schema extension; distinct `automatically_cross_checked` state; original hash/page/issuer/passage rechecked; human approval fields untouched | Implemented and tested |
| Real model access | Saved `.env` config selects `gemini-3.1-flash-lite`; live JSON response succeeded; default model high-demand errors preserved separately | Executed |
| Real F1/R1 | `data/runs/run_20261024_live_research/`: live responses, rejected schema attempts, deterministic scoring correction and validated outputs | Executed on analyst-directed original PDF evidence; R1 remains a plan |
| Repeatable model execution | `live_research.py` and `structured_generation.py`: actual output schema, raw response audit, bounded validation repair, deterministic arithmetic correction | Implemented; see production run manifests for live outcomes |
| Start Research action | `research_service.py` and `research_session.py`; localhost 8765, Vite proxy, real asynchronous search/retrieval and polling | Browser exercised; terminal gate failures visible |
| Saved research persistence | Per-run manifests/events on disk, latest UI run ID restored on reload | Implemented |
| Source-backed opposition | `demo_dossier.py`: OERC original tariff order p132 independently records exclusion of Unit 3 from supply forecast; NTPC trial and COD filings establish distinct milestones | Executed; evidence defeats the stronger surprise claim |
| Decimal/comparability | `capacity_timeline.py`: exact ratios, matched unit/milestone requirements, no trial-as-COD substitution | Tested |
| Dashboard evidence and report | `signal.tsx`, `finding.ts`: optional run-matched dossier, implications, candidates, chronology, opposing documents, falsification, drilldowns, JSON/Markdown export | Implemented and browser inspected |
| Second real issuer | Public search and local service attempted Power Grid using unchanged implementation | Honest no-finding; canonical identity/sector eligibility and qualifying facts not established |
| Completed novel independently corroborated discovery | Original NTPC split remains Weak; the COD investigation rejects an unsupported stronger interpretation | **Not achieved** |
| Full autonomous investigation/adjudication | Search can execute; strict evidence gates stop poor retrieval. Live PDF F1/R1 run is separate. R1 gap loop, generic fact mapping, project reconciliation and final adjudication not fully connected | **Partial** |
| NIFTY/sector eligibility | No dated constituent/sector verification service implemented | Missing |

## Actual runs and data

- Displayed finding: `data/runs/run_20261024_ntpc_recovered`; frontend `public/data/finding/SOURCE.json` matches. Seven partial input outcomes, six primary-source checks, no independent confirmation of the renewable split; zero traceability problems. Historical F1-blocked state describes this saved run, not current credential availability.
- Dossier for that run: `research_dossier.json`; separate COD investigation labelled `no_defensible_signal`. No strengthening of the original finding.
- Live model artifacts: `data/runs/run_20261024_live_research/manifest.json` and `f1.json`, `r1.json`. Model proposal is not a verified financial finding.
- Browser run: `data/research_runs/research_20261024T180705_dfbbc440c8cc/manifest.json`: actual search/retrieval, blocked at machine-evidence gate.
- Power Grid service run: `data/research_runs/research_20261024T181053_848bb50d11b7/manifest.json`: same implementation, blocked at evidence gate.
- Public-source relevance run: `data/runs/run_20261024T181033717044Z_relevance_filtered_search/`: NTPC 7 lexical candidates/3 rejected; Power Grid 0 relevant/10 rejected. These are source candidates, not independent confirmations.
- Fresh extraction: `data/claims_demo_20261024/`: 8,241 blocks, 40,942 candidate claims, zero chunk/schema failures. Original CSV.zip absent; included normalized evidence was sufficient for extraction.
- Downloaded PDF path: `data/recovered_20261024_large/sources/28f32ae3803b_4c280573.pdf`; full SHA-256 `28f32ae3803bc5aec87b49176df1e056d0cc9cf2c2a8d78f9144bc72c1b7cbbd`.
- Independent original: `data/regulator_20261024/sources/2812d3288d24_4e35f8ba.pdf`, OERC order date 13 February 2024 (page 1), relevant paragraph pp131–132. This checks a counterargument, not the 13,791 MW renewable number.
- CEA returned login; ERPC robots disallow the crawler; PIB returned HTTP403; the contractor homepage snapshot did not yield substantive text. None is counted as a verified confirmation.

## Validation

Final main-agent backend command: `PYTHONPATH=signalforge/src .venv/bin/python -m unittest discover -s signalforge/tests`: 264 tests run, OK, one skipped.

Live intake fix: replacement `research_20261024T182946_403b0d7ccfe4` completed discovery, machine evidence, live F1 and live R1. Employment/login results are now excluded. Machine intake scans the full bounded original PDF and can recheck company-matched, SHA-256-pinned official snapshots when discovery finds no eligible PDF. The event trail explicitly labels this cached fallback; it is not fresh discovery or human approval. The original blocked run remains unchanged. Completion means F1 selection and an R1 plan, not a verified financial finding.

Frontend `npm test`: 30 passed. `npm run build`: TypeScript and Vite succeeded. `git diff --check`: clean. Browser verified dossier source links/chronology, real Start Research and honest blocked status. Local API was restarted under `.venv` so PDF/model dependencies are available.

Production live model command completed both F1 and R1 at `data/runs/run_20261024_live_research/production_final/manifest.json`, without runtime adapters: 16 machine-checked passages, 2 candidate angles, F1 validated, R1 validated and retrieval false. Earlier attempts in its parent directory are retained as historical audit. Credential scan across 298 Git-visible files passed; `.env` remains ignored.

## Start locally

```bash
PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
cd signalforge/web
npm run dev
```

Open http://127.0.0.1:5173. Backend and frontend are currently running. Private credentials stay in ignored `signalforge/.env`; no key belongs in tracked files. Large downloaded snapshots and extraction outputs are ignored and must be retained locally or transferred separately for reproduction.

## Next three substantive actions

1. Improve issuer/domain-specific discovery and independently verify eligible issuer identity; tests in `test_source_discovery.py` and `test_research_service.py`; acceptance is qualifying original documents, not a raw hit count.
2. Follow the validated R1 evidence gaps through retrieval into generic matched-project facts with schedule revisions. Integrate `capacity_timeline.py`; reject mixed commissioning/trial/COD definitions.
3. Investigate another material candidate, obtain claim-level independent support and test novelty before final adjudication. Preserve `no_defensible_signal` if the alternative defeats it. The central contest requirement must remain open until this succeeds.
