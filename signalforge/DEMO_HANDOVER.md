# SignalForge — Arshia's demo handover

Run commands from the repository root. This is a local research demonstration:
completion does not mean a red flag has been proven. A neutral or evidence-gap
report is a valid outcome. The saved NTPC dashboard is a separate historical case.

## Prerequisites and current provider status

- Python virtual environment `.venv` and Node/npm. Ollama is optional.
- `.venv/bin/python -m pip install -r signalforge/requirements.txt` installs the
  existing OpenAI-compatible SDK (2.x); no additional provider SDK is used.
- Install frontend dependencies with `npm install --prefix signalforge/web`.
- xAI inference uses a dedicated `XAI_API_KEY`. Gemini/search credentials remain
  separate. An xAI key never substitutes for a Gemini or OpenAI key.
- The repository quote CSV must still exist for F1 inspection. It is context
  only and never becomes the target company's data without a verified join.

**Live validation is blocked:** the supplied private credential was rejected by
xAI's model-list endpoint with HTTP 400 (API-key error). Model access and Grok
inference have not been verified. No Grok JSON/quotation smoke or Hindalco model
resume succeeded. Automated provider/schema/quote checks use mocks. The prior
Hindalco Weak evidence-gap report is preserved; it is not a Grok result.

## Configure the xAI key securely

In the backend terminal, enter a valid xAI API key through zsh's hidden prompt:

```bash
read -s "XAI_API_KEY?xAI API key (hidden): "; export XAI_API_KEY
```

The key is not placed in shell history or command arguments. This applies to the
current shell; repeat it in a new terminal, or maintain `XAI_API_KEY` in the ignored
`signalforge/src/signalforge/.env` using a local editor. Do not paste credentials
into chat, commit them, or overwrite existing `SIGNALFORGE_API_KEY`/Gemini values.
An explicit shell export takes precedence over the private file.

## Verify access before investigation

After replacing the rejected key, run this bounded preflight from repository root
with a fresh output directory:

```bash
SIGNALFORGE_PROVIDER=xai SIGNALFORGE_MODEL=grok-4.7 SIGNALFORGE_BASE_URL=https://api.x.ai/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.xai_smoke --run-dir signalforge/data/research_runs/research_20261024T210811_fa86eb3121a1 --output-dir signalforge/outputs/xai_preflight_new
```

It requests the authenticated model list, verifies the requested ID (or a listed
compatible fallback), makes one tiny schema request and one representative draft
request quoting a revalidated original passage. It records response status and
returned token usage, then applies local schema and exact-passage checks. Failed
transport/authentication/rate-limit calls are not automatically retried. A schema
repair during normal agent execution remains bounded to one additional call.
Only proceed when the summary says `passed`; use its `selected_model` if it differs
from the requested model. No paid inference was reached in tonight's live check.

## Start the app with Grok

Backend terminal, from repository root, after configuring the key:

```bash
SIGNALFORGE_PROVIDER=xai SIGNALFORGE_MODEL=grok-4.7 SIGNALFORGE_BASE_URL=https://api.x.ai/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
```

Frontend terminal:

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
SIGNALFORGE_PROVIDER=xai SIGNALFORGE_MODEL=grok-4.7 SIGNALFORGE_BASE_URL=https://api.x.ai/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.resume_run --run-id research_20261024T210811_fa86eb3121a1
```

Resume only after the xAI preflight passes. The previous report is archived under the run’s `recovery_history/` before recovery. Completed discovery/counterevidence audits are reused; proposed new queries are explicitly recorded as unexecuted. Returned provider usage is saved alongside the model audits.

Do not start another model call or investigation while one is active. The resume
command refuses an active manifest. Check the process before recovering a stale
running state; saved artifacts and raw rejected responses must be preserved.
On xAI 400/401/403 authentication errors, correct `XAI_API_KEY`; other provider keys are not interchangeable. On 404, check the selected model against the authenticated list and use `https://api.x.ai/v1`. On 429, stop and inspect account rate limits; on timeout or provider failure, inspect the saved audit before retrying. No silent fallback to Ollama occurs. Do not increase timeouts or download alternatives
to hide schema/evidence failures. A scanned PDF without usable text may require
a different public original; OCR is not automatically supplied by this flow.

## Prior local-model validation case

Hindalco run ID: `research_20261024T210811_fa86eb3121a1`.
It required a cached local PDF from `data/demo_drop/` for issuer onboarding;
it did **not** prove fully online unseen-company acquisition. The PDF has no
established URL/date in that run. Sixteen passages became machine eligible.
F1 used the labelled planning fallback, and R1 produced a validated model plan.
Live follow-through and counterevidence retrieval ran. Parent/issuer web pages
are not established independent corroboration. Inspect the current saved report
and execution record for the final model-review outcome rather than assuming
that earlier planning completion was a complete investigation.

Prior saved outcome: a **evidence-gap / inconclusive / Weak** report.
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

## Optional Ollama alternative

Only when explicitly selected, start `ollama serve`, then use:

```bash
SIGNALFORGE_PROVIDER=ollama SIGNALFORGE_MODEL=signalforge-qwen SIGNALFORGE_BASE_URL=http://127.0.0.1:11434/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
```

This uses the prior 4B configuration. Its semantic investigation did not complete
in the Hindalco case. The installed 8B passed a small smoke but timed out on the
full request. These limitations do not constitute validation of Grok.

xAI uses the Responses API with schema output (`text.format`), `store=false`,
a bounded 8,192-token output, the existing 60-second cloud timeout and zero SDK
retries. Grok 4.7 uses supported medium reasoning; Ollama's parameters are not
sent. Application schema, quotation, arithmetic, provenance and adjudication
checks remain mandatory. See [xAI's Responses migration guide](https://docs.x.ai/developers/model-capabilities/text/comparison)
and [structured output documentation](https://docs.x.ai/developers/model-capabilities/text/structured-outputs).
