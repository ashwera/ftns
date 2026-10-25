# Arshia demo handover — 25 October 2026

## Latest targeted citation recovery

Original run **`research_20261025T000129_2ecbfd3ad81c`** now completes investigation and a fresh semantic review. It was resumed in place; no new run ID was created. Its onboarding, F1, R1, eligible evidence, completed discovery/follow-up/opposition searches and PDF were reused, with all eight input hashes unchanged. The original failed reports and raw model attempts are preserved in recovery snapshots/audits.

The original 14-character quote was reproduced against the previous validator; current feedback correctly identifies a length failure. A live Gemini probe selected a longer exact contiguous quotation on physical PDF page 80 that identifies JCRL, its progress percentage and its expected commissioning. The page was visually inspected; no table text was reconstructed or stitched. The repaired initial investigation validated on its first response, retaining issuer-backed observations and omitting the unsupported 68.5/100 calculation.

Review then exposed another issue: the model summed the same 1,600 MW project twice, and its first skeptical review missed this. A targeted duplicate-operand gate now refuses that sum. Recovery withholds the optional calculation, records the rejection, revalidates all remaining observations and requires fresh semantic review. It does not treat a matching quote as proof of an additional project.

Final result: **inconclusive / Weak** with three source-backed issuer observations: Patan solar commissioning, the future renewable-capacity target, and the Jharkhand thermal-development project. No calculation was accepted; independent corroboration and novelty remain absent. The counterargument distinguishes future targets from presently due commissioning obligations. Same-project independent COD/schedule records and reporting-perimeter matching remain research leads, not acquired evidence.

Gemini `gemini-3.1-flash-lite` handled this recovery with the fuller saved context and without Groq fallback, avoiding the latter's account input quota. The final successful recovery took **30.559 seconds**. Earlier recoveries took 43.511 seconds and 27.580 seconds (the latter hit Gemini HTTP503); total recovery execution was **101.650 seconds**, excluding the separate 22.448-second quote probe and time editing/testing code. This is a recovered saved case, not a fresh unattended discovery benchmark.

Backend: **355 tests OK, two skipped**. Browser rendering, the counterargument, the withheld-calculation decision log and JSON/Markdown downloads passed; the JSON export's `investigation` object exactly equals the saved report. Portable proof exports are in `signalforge/data/demo_validation/coalindia_citation_fix_20261025/`; screenshot: `signalforge/outputs/coalindia-citation-fix-result.png`. Earlier sections below retain their measured historical outcomes.

## Verified checkout and environment

Repository: `https://github.com/ashwera/ftns.git`. The initial local commit was `9dd5fc5b86074c8938d17cc45837a88b154efdb1` on `main`, with a clean working tree. Fetch found three newer commits; the checkout was fast-forwarded to `6893f33634dde700dc6a2e7051460756ac8d8202`. Ashwera's later onboarding, Ollama, resume, borderline-search fallback and PDF-table changes exist on the remote. The remote did not contain this handover or Groq failover. Its Hindalco manifest was still marked running, with an evidence-gap artifact and paths to `/Users/ashwera/Documents/ftns`; that is not a completed portable investigation.

This machine is an Apple M2 Mac with 8 GB RAM, Python 3.14.3 and Node 24.21.0. `.venv`, frontend dependencies and the OpenAI-compatible SDK are installed. Ollama is not installed or listening. No local model was downloaded: hosted inference is available and avoids allocating a model on this 8 GB machine.

## Architecture and evidence boundaries

The local Python service accepts a company and question, runs bounded public search, attempts an original annual-report download, resolves a run-local issuer identity, checks original PDF hashes and exact passages, executes F1 selection and R1 planning, follows the plan with source retrieval, searches counterevidence, validates quotations and Decimal calculations, then challenges the conclusion in a separate model pass. React polls the saved run and displays its report, sources, alternative explanation, falsification and export controls.

The model proposes and interprets; Python checks source bytes, quoted spans, citation IDs, schemas and numeric operations. Semantic challenge uses a model, not a human auditor. A CIN is an explicitly labelled corporate identifier and is never presented as an inferred equity ISIN. A self-declaration in an annual report does not establish current NIFTY membership or authenticate every financial claim. NIFTY/sector eligibility still needs a current constituent source.

Prepared NTPC and Power Grid catalogs are clearly labelled cached/operator sources. Their presence does not establish unseen-company performance. A live unfamiliar-company run must disclose whether any catalog or drop-folder PDF was used. Multiple copies of an issuer's disclosure do not add independent confirmation. No-evidence outcomes have no financial claims and are **Not rated**.

## Start the app

From this checkout, in one terminal:

```bash
cd /Users/arshiadang/Desktop/fns
PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
```

In another:

```bash
cd /Users/arshiadang/Desktop/fns/signalforge/web
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173/`. Backend: `http://127.0.0.1:8765/api/agent/health`. That endpoint reports configuration and process status; it explicitly does not claim cloud inference was probed. Use the health command below for an actual request.

## Credentials and model routing

Keys belong only in ignored `signalforge/.env` (mode 600). Edit it locally with `nano signalforge/.env`; do not print it or copy it into a report. `.env.example` contains variable names only. The current literal loader does not execute shell expressions. Existing Gemini credentials are preserved separately from `GROQ_API_KEY`. Groq never receives the Gemini key. Ollama uses its local placeholder credential only.

The following are configuration examples, not credential values:

```dotenv
SIGNALFORGE_PROVIDER=groq
SIGNALFORGE_MODEL=openai/gpt-oss-120b
SIGNALFORGE_BASE_URL=https://api.groq.com/openai/v1
GROQ_API_KEY=
SIGNALFORGE_FALLBACK_PROVIDERS=gemini
SIGNALFORGE_GEMINI_MODEL=gemini-3.1-flash-lite
SIGNALFORGE_GROQ_MODEL=openai/gpt-oss-120b
SIGNALFORGE_OLLAMA_MODEL=signalforge-qwen
SIGNALFORGE_REQUEST_TIMEOUT=60
```

For Gemini, select `gemini`, its tested model, and its default compatibility URL (leave `SIGNALFORGE_BASE_URL` blank). For Ollama, select `ollama`, an actually installed model, and `http://127.0.0.1:11434/v1`; run `ollama serve` only on a machine with Ollama installed. An 8B model is not recommended as an untested last-minute download on this machine. This checkout's example Modelfiles do not imply those models are installed.

Check authentication, listed model and a minimal JSON response without printing keys:

```bash
PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.provider_health --all --probe
```

Measured checks: Gemini `gemini-3.1-flash-lite` passed JSON in 15.206 seconds but later returned HTTP 503 on a research request. Groq listed `openai/gpt-oss-20b` and `openai/gpt-oss-120b`; the tested 20B model passed minimal JSON in 0.580 seconds and a real F1 selection on four eligible NTPC passages in 4.63 seconds. That F1 test was a bounded evidence replay, not live discovery. Groq's observed account limit is 8,000 tokens/minute; advertised model context (131,072 tokens) does not override that quota. Large inputs returned HTTP 413; closely spaced calls returned HTTP 429. Ollama is unavailable here.

Failover is ordered and explicit. Each transport attempt has a bounded timeout and zero SDK retries. Auth/quota/availability/connection/timeouts may advance to the next configured provider. One short Groq-directed quota reset of at most 45 seconds can be honored once before moving on; every actual attempt and wait is recorded. Duplicate providers are removed, so there is no infinite provider loop. Groq's token-quota HTTP 413 can advance to an explicitly configured Gemini route; it is not repeatedly resent on Groq. Invalid JSON and evidence/schema failures go through the existing bounded validation-repair path; they cannot become accepted research by changing provider. Full request/response and validation audits remain per invocation. F1 uses a bounded model view after validating full original evidence; investigation keeps whole passages, and final review preserves every cited passage even if that requires a larger request. Missing context is a limitation, not evidence of non-disclosure.

An actual Ollama-unavailable → Groq JSON fallback passed, with both provider attempts recorded in `signalforge/outputs/arshia_provider_failover.json`. Gemini quota → Groq, schema failures, missing provider credentials, request limits and bounded exhaustion are also covered by focused automated tests. A real Gemini-503 → Groq attempt was observed in the Coal India audit, but that fallback request exceeded the Groq account quota; it was not a successful investigation. Do not describe every fallback path as live-verified.

## Manual switch and resume

Once the current worker has stopped, restart the backend with an explicit override, for example:

```bash
SIGNALFORGE_PROVIDER=groq SIGNALFORGE_MODEL=openai/gpt-oss-120b SIGNALFORGE_BASE_URL=https://api.groq.com/openai/v1 SIGNALFORGE_FALLBACK_PROVIDERS=gemini PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
```

Resume a saved run from the repository root:

```bash
SIGNALFORGE_PROVIDER=groq SIGNALFORGE_MODEL=openai/gpt-oss-120b SIGNALFORGE_BASE_URL=https://api.groq.com/openai/v1 SIGNALFORGE_FALLBACK_PROVIDERS=gemini PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.resume_run --run-id YOUR_SAVED_RUN_ID
```

Resume preserves prior stage outputs in `recovery_snapshots/`, reuses completed search checkpoints and downloaded originals, and rechecks hashes/identity/citations. A saved F1/R1 pair is revalidated before downstream investigation resumes. A run still owned by a live process must not be resumed concurrently. Reload/select the saved run in the browser to observe recovery. Actual provider/model/latency, usage when returned, fallback reason and validation outcome are in `model_calls` in the manifest and the UI's **Models used in this run** section.

## Live demo sequence and narration

Enter the judge's company in the **Company text field** within Start research. The separate saved-workspace dropdown is historical data navigation. Enter the assigned question and click **Start research**. Inspect the actual run ID and stages. When a report appears, inspect its headline and rating, claims and exact quotes, source passages, chronology, calculations, counterargument and falsification. Export investigation JSON and Markdown. Reload and select that run to demonstrate persistence. A previously completed prepared case must be introduced as a saved demonstration.

Suggested narration: “SignalForge turns public disclosures into testable research questions. It follows an evidence plan, checks original passages and calculations, searches for competing explanations, and challenges its proposed conclusion. The report shows what the evidence supports and what remains unresolved. If the available sources cannot establish a claim, it produces an evidence-gap report.”

Likely judge questions: Independence is grouped by document lineage, not URL count. Exact quotations establish traceability, not economic truth. Targets, trial operation and COD are different milestones. Decimal arithmetic does not resolve mismatched periods or ownership scope. Unknown-company coverage is limited by reachable documents, identity declarations, model availability and bounded research budgets; a discovery is not guaranteed.

## Troubleshooting

| Symptom | Meaning | Recovery |
|---|---|---|
| Ollama connection refused | No local server/model | Use configured hosted provider; install/start Ollama only if needed |
| Groq missing credential / 401 | Provider configuration/authentication | Set `GROQ_API_KEY` locally and run the health command |
| Groq 413 / 429 | Account input-token/rate quota | Do not repeatedly resubmit; allow the configured larger-input Gemini route or wait for the indicated quota reset |
| Gemini 503 | Hosted model availability | Ordered fallback, or a tested alternate model; retain successful earlier artifacts |
| Invalid JSON / failed quotation | Model content failed validation | Inspect its audit; only the bounded repair is allowed; an evidence-gap report is valid |
| No relevant URLs / robots / 403 | Search or source retrieval failure | Inspect discovery and onboarding reports; a different inference key does not make the source accessible |
| Backend port already in use | Existing local process | Reuse the running service or stop that owned terminal with Ctrl-C before restarting |
| Frontend cannot connect | Wrong backend/proxy/port | Start localhost 8765 and Vite 5173; inspect `/api/agent/health` |
| Saved run says interrupted | No active worker owns that saved job | Inspect artifacts, then use the resume command |
| Report absent after recovery | Browser still showing an earlier saved state | Reload/select the recovered run; compare its ID to the manifest |

## Portability and current verification

`CSV.zip`, normalized archive data and some large source files are now tracked upstream. Other catalogs still reference ignored local snapshots, and Hindalco's committed evidence references the previous machine's absent PDF. A clone cannot reproduce those particular prepared cases without their original files. The generic onboarding path does not require the anonymous NTPC quote file as financial evidence, a prepared catalog, or Ashwera's PDF; it does require reachable issuer documents and supported identity declarations.

Baseline after fetching main: 334 backend tests, two skips; 42 frontend tests and production build passed. Post-fix backend: **351 tests run, OK, two skipped**. Frontend: **43 tests pass**, TypeScript and production build pass. Original snapshot hashes, physical-page passages and every exported claim quote were checked again against source bytes. Browser source drilldown, JSON and Markdown downloads and reload persistence passed for the completed recovery run.

## Completed unfamiliar-company investigation

Company: **Coal India Limited**. Run: `research_20261024T232238_39445100e7e3`. Started through the browser using only company and research question. No Coal India catalog or drop-folder PDF was supplied. Initial source-intake and inference failures exposed genuine defects; four recorded recoveries preserved earlier reports and reused search/snapshot checkpoints.

The original issuer FY2025-26 PDF was discovered through public website navigation and downloaded. Its CIN was read on physical page 67 and pinned; no ISIN was manufactured. One eligible original source reached the final investigation; no independent corroboration was obtained. F1 and R1 completed, followed by initial investigation, follow-up and opposing searches, final draft, model challenge and deterministic policy adjudication. No comparative financial calculation was justified by the missing matched inputs, so none was invented.

The final result is **inconclusive / Weak**. It retains an issuer-supported operational statement, marks a broad document-wide absence claim unresolved, and refuses to establish a material commissioning gap. A model's approval was overridden by the deterministic scope/deadline checks: selected excerpts cannot prove what an entire report omits; awarded capacity without a due date does not establish underdelivery. Raw model output, original review and the pre-policy report are preserved. The final JSON/Markdown show the applied policy and missing independent support.

Actual inference varied by stage: F1 ultimately used Gemini after Groq quota errors; R1 used both Groq 20B and Gemini across validation attempts; the initial investigation used Groq 20B; the final draft used Groq 120B (3.492 seconds, 5,889 total tokens); the final model challenge used Gemini (1.754 seconds, 3,402 total tokens) after Groq quota failures. Separate NTPC replay verified genuine Groq 20B F1 plus R1 (four plan steps). Model-dependent stages therefore share the production interface and do not require one provider throughout a run.

Recommended configured route on this machine: **Groq `openai/gpt-oss-120b` with Gemini `gemini-3.1-flash-lite` fallback**. Gemini is working with availability/quota limitations. Groq is working with an 8K TPM account limit. Ollama is unavailable. Automatic transport failover and bounded quota handling were exercised; content and evidence gates remain mandatory. Full investigations can take several minutes under this quota; a sub-minute discovery is not guaranteed.

Current readiness: **CONDITIONAL GO for an honest research-application demonstration**. A completed investigation can be shown, but this run does **not** establish a novel independently corroborated financial discovery. Current NIFTY/sector membership is not automatically verified. The earlier unresolved discovery requirement must not be claimed complete. If judges require a guaranteed supported discovery on an unseen company, that outcome remains unproven.

## Final unattended rehearsal

`research_20261024T234754_a378b8365612` was started from the browser after the fixes, with no manual recovery or prepared Coal India catalog. It completed in approximately **173 seconds**. Issuer intake, F1, R1, initial investigation and counterevidence search ran. The final model tried to calculate commissioned thermal capacity as zero without a source stating zero. Both bounded validation attempts failed the operand-evidence check. The application correctly produced **evidence_gap / inconclusive / Not rated**, with semantic review explicitly marked incomplete. Its report rendered in the browser and its JSON export matched the run. This proves normal execution and refusal behavior; it does not prove a successful financial finding or completed semantic review on every unattended run.

The selected weak/inconclusive completed investigation and the unattended evidence-gap example are both retained. Portable validation exports are under `signalforge/data/demo_validation/arshia_20261025/`; they include the actual reports, unattended manifest, F1/R1 and real provider-failover trace. Full raw execution directories and downloaded originals remain local and ignored. Their URLs and SHA-256 hashes are recorded; missing PDF files are not silently replaced with fabricated evidence. The original tracked starter CSV remains an incidental loader dependency, although its rows are never attributed to Coal India as financial evidence.

Changes are on branch **`codex/arshia-demo-readiness`**, based on upstream `6893f33`. Use `git log -1 --format='%H %s'` to identify the commit containing this handover. No push to `main` is part of this takeover. The configured local servers are running at the URLs above.

### Genuine remaining limitations, in priority order

1. A novel, independently corroborated financial discovery is not established by these runs. Obtain same-project, same-period independent records; retain an inconclusive result until they support the claim.
2. Model output still sometimes proposes unsupported quotations or numerical assumptions. The strict gates now expose/refuse these; they cannot guarantee a substantive report for a new company.
3. Current NIFTY/sector eligibility is not an automatic verified service. Confirm the judge's assignment against a dated authoritative constituent source.
4. Search coverage and document accessibility are variable; Groq's account quota and Gemini availability affect latency. Keep the completed saved investigation as an explicitly labelled backup and allow several minutes for live research.
5. Ollama remains uninstalled/unverified on this Mac. It is optional while hosted routes work; local F1/R1 inference has not been demonstrated here.
