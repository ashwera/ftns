# SignalForge — Arshia's demo handover

Run commands from the repository root. This is a local research demonstration:
completion does not mean a red flag has been proven. A neutral or evidence-gap
report is a valid outcome. The saved NTPC dashboard is a separate historical case.

## Prerequisites and current provider status

- Python virtual environment `.venv` and Node/npm. Ollama is optional.
- `.venv/bin/python -m pip install -r signalforge/requirements.txt` installs the
  existing OpenAI-compatible SDK (2.x); no additional provider SDK is used.
- Install frontend dependencies with `npm install --prefix signalforge/web`.
- Groq inference uses a dedicated `GROQ_API_KEY`. Existing xAI/Gemini/search
  credentials remain separate. No paid provider fallback is used for Groq.
- The repository quote CSV must still exist for F1 inspection. It is context
  only and never becomes the target company's data without a verified join.

**Groq verified live:** authenticated model list includes `openai/gpt-oss-120b`;
connectivity, JSON schema and a separate exact-passage smoke test passed. The
first draft's stitched quotation was rejected; a corrected bounded request passed.
The NHPC app run successfully used `browser_search` (an earlier probe returned
HTTP 500). See [actual validation outcomes](GROQ_DEMO_REPORT.md) before presenting
any completed financial claim. Model access does not imply a verified finding.

The 120B model then reached its free daily token allowance. **The completed
Hindalco recovery used the explicitly selected `openai/gpt-oss-20b` model**, whose
schema/quotation smoke also passed. Startup below uses that tested configuration.
120B remains the preferred configured default on a fresh allowance; select it by
replacing the model argument with `openai/gpt-oss-120b` after checking quota.

## Configure the Groq key securely

In the backend terminal, enter the Groq API key through zsh's hidden prompt:

```bash
read -s "GROQ_API_KEY?Groq API key (hidden): "; export GROQ_API_KEY
```

The key is not placed in shell history or command arguments. This applies to the
current shell; repeat it in a new terminal, or maintain `GROQ_API_KEY` in the ignored
`signalforge/src/signalforge/.env` using a local editor. Do not paste credentials
into chat, commit them, or overwrite existing `SIGNALFORGE_API_KEY`/Gemini values.
An explicit shell export takes precedence over the private file.

## Verify access before investigation

If saved Hindalco originals are present, run this bounded preflight from repository root
with a fresh output directory:

```bash
SIGNALFORGE_PROVIDER=groq SIGNALFORGE_MODEL=openai/gpt-oss-20b SIGNALFORGE_BASE_URL=https://api.groq.com/openai/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.groq_smoke --run-dir signalforge/data/research_runs/research_20261024T210811_fa86eb3121a1 --output-dir signalforge/outputs/groq_preflight_new
```

It requests the authenticated model list, verifies the exact requested ID, makes
one representative schema draft request and a separate quotation request against
a revalidated original passage. It records actual usage and applies local schema
and exact-passage checks. Search is never combined with JSON response_format.
Failed transport/authentication/rate-limit calls are not automatically retried.
Normal schema/quote repair is bounded to one additional call. Only proceed when
the summary says `passed`. No new SDK or subscription is required.

## Start the app with Groq

Backend terminal, from repository root, after configuring the key:

```bash
SIGNALFORGE_PROVIDER=groq SIGNALFORGE_MODEL=openai/gpt-oss-20b SIGNALFORGE_BASE_URL=https://api.groq.com/openai/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
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

1. Open **Live research**, then in **Start research** enter the company's full legal name and the assigned
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
   counterevidence retrieval. Groq calls are paced at least 60 seconds apart in
   one process. Keep one run active across terminals; stages may make one validation repair.
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
SIGNALFORGE_PROVIDER=groq SIGNALFORGE_MODEL=openai/gpt-oss-20b SIGNALFORGE_BASE_URL=https://api.groq.com/openai/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.resume_run --run-id research_20261024T210811_fa86eb3121a1
```

Resume only after the Groq preflight passes. Previous reports are archived under
the run's `recovery_history/`. Completed discovery/counterevidence audits are reused;
new proposed queries are recorded as unexecuted. For a terminal run that stopped
before eligible evidence/F1, `resume_run --run-id <id> --retry-onboarding` reuses
the completed discovery and retries identity acquisition. It cannot repeat F1.
An ambiguous annual-report PDF lead may be probed for issuer identity; it remains
unverified until the original name/ISIN/hash and exact passages pass all gates.

Do not start another model call or investigation while one is active. The resume
command refuses an active manifest. Check the process before recovering a stale
running state; saved artifacts and raw rejected responses must be preserved.
On Groq 401/403 authentication errors, correct `GROQ_API_KEY`; provider keys are not
interchangeable. On 404 check the authenticated model list and official endpoint.
On 429 stop and wait for the free-tier reset; the SDK performs zero retries. This
account reported 8,000 tokens/minute. Requests are limited to 18 KB and 2,048 output
tokens; full originals and validation remain on disk. A local request cap error
requires reducing supplied context, not bypassing evidence checks. Search uses one
request per stage and low reasoning; Groq controls internal tool calls, so their
token usage can exceed the external prompt size. Inspect provider usage audits.
Browser failures can fall back once to public Bing/DuckDuckGo search; 429 never
triggers another provider call. No paid upgrade or inference fallback occurs.
On timeout/provider failure inspect the audit before retrying. Do not increase timeouts or download alternatives
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

Prior saved outcome: an **evidence-gap / inconclusive / Weak** report.
4B investigation responses failed exact quotation validation; 8B passed a small
smoke test but timed out on the full investigation. Counterevidence retrieval
completed; semantic model review, validated final financial claims and financial
calculations did not complete. The report exposes the source-grounded planning
leads separately. Do not present this as a verified end-to-end financial discovery.

The subsequent **Groq 20B recovery completed exact-passage validation, semantic
review, counterevidence reconciliation, final adjudication and report generation**.
Its result is an investigation / inconclusive / Weak report: two issuer project
announcements are supported, but actual commissioning remains unresolved and the
broader proposed headline was rejected. No independent corroboration, financial
discrepancy or calculation was established. Saved stage labels distinguish reused
F1/R1/searches from the new model review. Read this completed run without starting
another investigation. NHPC's uncached run ends earlier with an identity/evidence
gap; it is not a successful financial investigation.

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
full request. These local-model limitations do not replace Groq validation.

Groq uses the existing OpenAI SDK Chat Completions interface, a 60-second cloud
timeout, zero SDK retries and no Ollama-specific parameters. Strict schemas are
used where the existing schema permits them; conditional F1/R1 schemas use best
effort JSON schema with unchanged local validation. Application quotation,
arithmetic, provenance and adjudication gates remain mandatory. See official
[browser search](https://console.groq.com/docs/tool-use/built-in-tools/browser-search)
and [structured output](https://console.groq.com/docs/structured-outputs) documentation.
xAI remains optional but requires a separately valid key and credits; it is not
part of tomorrow's zero-budget startup path.
