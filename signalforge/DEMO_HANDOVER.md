# SignalForge — Arshia's demo handover

> Historical handover from the other machine's16GB/Ollama session. Installed-model,420-second timeout and test-count statements below describe that recorded session, not the current8GB Arshia Mac. Use the root `ARSHIA_DEMO_HANDOVER.md` and `SIGNALFORGE_DEMO_DAY_QUICK_REFERENCE.md` for the final integrated audit, current hosted-provider commands and successful fresh Coal India run. Ollama is unavailable on the current demo machine.

Run commands from the repository root. This is a local research demonstration:
completion does not mean a red flag has been proven. A neutral or evidence-gap
report is a valid outcome. The saved NTPC dashboard is a separate historical case.

## Prerequisites on this Mac

- Python virtual environment `.venv`, Node/npm, and Ollama running locally.
- Install Python dependencies with `.venv/bin/python -m pip install -r signalforge/requirements.txt`.
- Install frontend dependencies with `npm install --prefix signalforge/web`.
- `ollama list` must show `qwen3:8b` or the existing `qwen3:4b-instruct`.
  No cloud inference quota is required. Preserve existing ignored `.env` keys;
  optional Gemini search/URL hints have independent configuration.
- The local source CSV is optional company context only and is never an issuer
  join merely because its filename says NTPC. The current F1 loader expects the
  repository quote CSV to exist; a missing CSV is a configuration error.

## Start the app

Terminal 1 (skip if Ollama is already running):

```bash
ollama serve
```

Create the configured model from already installed weights, once:

```bash
ollama create signalforge-qwen8b -f signalforge/Modelfile.qwen3-8b
```

The 8B Q4 model was configured with a 32,768-token context on this 16 GB Mac
and passed a JSON/exact-quotation smoke test. The existing 4B model is retained:

```bash
ollama create signalforge-qwen -f signalforge/Modelfile.qwen3-4b
```

Terminal 2, backend:

```bash
SIGNALFORGE_PROVIDER=ollama SIGNALFORGE_MODEL=signalforge-qwen SIGNALFORGE_BASE_URL=http://127.0.0.1:11434/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
```

The explicit base URL matters: `/v1p` is invalid and caused an observed 404.
Use `/v1` exactly. The command overrides the endpoint without editing credentials.
The 4B model is the default because the full 8B investigation request timed out
at 420 seconds despite passing its 11-second quotation smoke test. The 8B model
is installed and configured, but its smoke success did not establish end-to-end
reliability. No timeout was increased. The 4B model also needed strict quotation
repairs, so a defensible gap report remains an expected outcome.

Terminal 3, frontend:

```bash
cd signalforge/web
npm run dev -- --host 127.0.0.1 --port 5173
```

Open **http://127.0.0.1:5173/**. Backend API runs at **127.0.0.1:8765**;
Vite proxies `/api/agent/`. Use port 5173: the localhost origin allowlist is deliberate.
The production build is checked, but `vite preview` alone does not provide the
local research API/data middleware; use the development server for tomorrow.

## Investigate an unfamiliar company

1. In **Start research**, enter the company's full legal name and the assigned
   question. Replace the default NTPC name. A registry/catalog entry is not needed
   to enter live discovery. Submit once and keep the displayed run ID.
2. Observe discovery, retrieval, issuer onboarding and evidence eligibility in
   **Run execution record**. Search hits are leads. Original PDF identity requires
   an issuer name, labelled equity ISIN and immutable source hash. An external
   identity conflict stops acceptance. A Wikidata lookup being unavailable is
   explicitly recorded; a PDF self-declaration is not exchange authentication.
3. F1 ranks research questions. If its schema-valid response has no usable
   recommendation or reports an unreliable ranking, a deterministic planning
   fallback counts matching eligible evidence for the three contest angles.
   Its rule, reason and real evidence IDs are saved in `f1_fallback.json` and
   exposed in the run events. It cannot create verified financial findings.
4. R1 produces a research plan; investigation performs further source and
   counterevidence retrieval. Local model calls can take several minutes and
   may make one validation repair. There is no meaningful fixed completion time.
5. A terminal result shows **Completed investigation** or **Evidence-gap report**,
   the actual run ID and evidence strength. A planning-only historical run is
   explicitly marked as lacking a final investigation. Read stage failures even
   when a terminal gap report exists: a saved report does not mean model review ran.
6. Open **Claims and model challenge**, source passages, counterargument,
   falsification, limitations and the decision log. Export JSON/Markdown.

No company-specific curated catalog is required by the flow. Successful online
identity/document acquisition for an arbitrary company is not guaranteed. If no
usable original can be established, the app saves a clear evidence-gap report
before F1. The available CSV cannot substitute for missing company disclosures.

## Read the evidence honestly

- `automatically_cross_checked` means original PDF bytes, issuer declaration and
  literal page passage were checked. Numerical interpretations are still unverified.
- Issuer statements, issuer-hosted pages and copied filings do not independently
  corroborate each other. Different domains alone prove no independence.
- Borderline discovery only runs after zero strict matches. At most three
  distinct leads receive a 35-point relevance penalty and explicit reasons.
  Retrieved content is inspected; leads still require normal identity and evidence
  checks. Wrong-company, noise, search-engine and login results remain excluded.
- Weak/inconclusive is expected without verified independent support. Missing
  evidence, rejected results or model hypotheses are never proof of misconduct.
- Dates/periods come from source text, not filenames or retrieval time. Announced,
  under-construction, commissioned, trial and commercial operation differ.
- A failed model conclusion is withheld or shown as a rejected proposal. Exact
  quotes, real source IDs, calculations, contradictions and falsification checks
  remain mandatory. No fallback adjudicator asserts a financial finding.

## Saved runs and recovery

Choose **Saved investigations** to reopen a run without paying for inference or
starting new searches. Refreshing the page restores the last selected run.

Artifacts live under `signalforge/data/research_runs/<run_id>/`:
`manifest.json`, `events.jsonl`, discovery reports, original snapshots,
`eligible_evidence/evidence.jsonl`, F1/R1 files, immutable model audits,
`investigation.json` and `investigation_report.md` when generated.

For a stopped run with valid saved F1/R1, resume from that stage:

```bash
SIGNALFORGE_PROVIDER=ollama SIGNALFORGE_MODEL=signalforge-qwen SIGNALFORGE_BASE_URL=http://127.0.0.1:11434/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.resume_run --run-id research_20261024T210811_fa86eb3121a1
```

Do not start another model call or investigation while one is active. The resume
command refuses an active manifest. Check the process before recovering a stale
running state; saved artifacts and raw rejected responses must be preserved.
On a 404, check `/v1`; on connection failure, start Ollama and backend; on missing
model, use an installed model. Do not increase timeouts or download alternatives
to hide schema/evidence failures. A scanned PDF without usable text may require
a different public original; OCR is not automatically supplied by this flow.

## Tonight's validation case

Hindalco run ID: `research_20261024T210811_fa86eb3121a1`.
It required a cached local PDF from `data/demo_drop/` for issuer onboarding;
it did **not** prove fully online unseen-company acquisition. The PDF has no
established URL/date in that run. Sixteen passages became machine eligible.
F1 used the labelled planning fallback, and R1 produced a validated model plan.
Live follow-through and counterevidence retrieval ran. Parent/issuer web pages
are not established independent corroboration. Inspect the current saved report
and execution record for the final model-review outcome rather than assuming
that earlier planning completion was a complete investigation.

Final outcome tonight: a saved **evidence-gap / inconclusive / Weak** report.
4B investigation responses failed exact quotation validation; 8B passed a small
smoke test but timed out on the full investigation. Counterevidence retrieval
completed; semantic model review, validated final financial claims and financial
calculations did not complete. The report exposes the source-grounded planning
leads separately. Do not present this as a verified end-to-end financial discovery.

## Checks

```bash
PYTHONPATH=signalforge/src .venv/bin/python -m unittest discover -s signalforge/tests
cd signalforge/web
npm test
npm run build
```

Run artifacts, downloaded originals, dependencies, machine-specific files and
credentials are local and are excluded from the final source commit.
