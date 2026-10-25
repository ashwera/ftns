# xAI migration completion report — 25 October 2026

## Outcome and external blocker

The provider integration is implemented and automated checks pass. The local
application is configured for `xai`, `grok-4.7`, `https://api.x.ai/v1` and the
dedicated private `XAI_API_KEY` setting. Ollama remains explicitly selectable.

**Live Grok inference is not verified.** The supplied credential was rejected
by the authenticated model-list endpoint with **HTTP 400, an API-key error**.
One bounded preflight and one redacted diagnostic model-list request reached
the provider; neither authenticated. An earlier sandbox connection failure did
not establish access. No generation request was made, no model IDs were verified
for this key, and no token/usage information was returned. `grok-4.7` is the
configured preferred model, not a model successfully used in this session.

The application needs a valid xAI API key to complete live validation. Do not
substitute an OpenAI, Gemini, Groq, web-session or Ollama credential. Do not add
prefixes to an invalid key or repeatedly retry it. The current failure is not
evidence that Grok produced or validated any financial analysis.

## Implementation decisions

- Use the installed OpenAI SDK (2.54.0 in this environment), with its
  `client.responses.create` interface. Requirements now specify SDK 2.x; no new
  SDK or package was installed for this migration.
- Pass the existing application schema using `text.format` with JSON Schema and
  strict output. All existing local schema, exact-passage, evidence identity,
  provenance, arithmetic, contradiction, falsification and adjudication checks
  remain mandatory. The API cannot waive them.
- Use `store=false`, an 8,192-token output cap, the existing 60-second cloud
  timeout and zero SDK transport retries. Normal application schema repair is
  still limited to one extra call. Grok 4.7 receives supported medium reasoning;
  other configurable models do not inherit that setting. No Ollama context or
  reasoning-effort parameter is sent to xAI.
- `XAI_API_KEY` is separate from `SIGNALFORGE_API_KEY`. Missing xAI credentials
  fail explicitly. Cloud failures never silently select Ollama. SDK error bodies
  and headers are omitted from xAI exceptions; both configured keys are redacted
  from audits and repair feedback.
- Runtime configuration supports xAI defaults when its key is present and no
  provider override exists. Shell values take precedence over literal ignored
  dotenv assignments. Inference configuration loading does not globally change
  another run's provider/key. Existing independent Gemini search configuration is
  preserved; a Grok inference model cannot become a Gemini search model.
- Add a generic bounded live preflight: authenticated model list, model-ID
  selection, tiny JSON-schema request, representative investigation-draft schema,
  and exact quotation check against a revalidated saved original. Actual provider
  status and returned usage are saved when available. This preflight stopped at
  authentication in this session; later steps did not run live.
- Recovery archives the previous manifest/report under `recovery_history/`,
  revalidates saved F1/R1, rehashes originals, reuses completed discovery and
  counterevidence searches, and records proposed new queries as unexecuted.
  Provider usage artifacts are collected in the manifest if calls complete.
- The frontend displays the saved run's recorded provider/model. Merely changing
  the backend configuration does not relabel an old Ollama result as Grok.

These request choices follow the official [Responses migration guide](https://docs.x.ai/developers/model-capabilities/text/comparison),
[structured output documentation](https://docs.x.ai/developers/model-capabilities/text/structured-outputs)
and [Grok 4.7 model reference](https://docs.x.ai/developers/models/grok-4.7).
Public model documentation does not establish access for this credential.

## Hindalco and frontend verification

Original run: `research_20261024T210811_fa86eb3121a1`.

No fresh discovery, retrieval or investigation was started after authentication
failed. Its saved artifacts are unchanged from the prior commit. Its existing
inconclusive / Weak evidence-gap report, three planning leads, original eligible
passages and retrieval/counterevidence audits remain available.

No Grok exact-quote response, semantic review, financial-input verification,
calculation, adjudication or report generation completed. No new financial
claim or scrutiny finding passed verification. Independent corroboration remains
unestablished. Prior local-model F1/R1 and live retrieval are not Grok execution.

The actual browser selected the original saved run after the backend was
restarted with xAI configuration. The evidence-gap report and “model review:
not_executed” were visible, its recorded Ollama model was visible in the execution
record, and no browser errors were observed.

## Automated verification

- Backend: **348 tests run; 346 passed, 2 skipped**.
- Focused xAI provider tests: **8 passed**. These use SDK mocks, including schema
  passing, usage extraction, exact valid/invalid quotation handling, missing-key
  handling, malformed-key 400, 401/403, 429, timeout, parsing and secret redaction.
- Existing Ollama and Gemini tests passed in the full suite.
- Frontend: **44 tests passed**.
- TypeScript (`tsc -b`) and Vite production build: **passed**.
- `git diff --check`: **passed**.
- Live authenticated model list: **failed, HTTP 400 API-key error**.
- Live generation/schema/quotation checks: **not run because authentication failed**.
- Live token usage: **unavailable; none returned by the failed model-list calls**.

## Files changed

```text
COORDINATION.md
README.md
signalforge/.env.example
signalforge/.gitignore
signalforge/DEMO_HANDOVER.md
signalforge/XAI_MIGRATION_REPORT.md
signalforge/requirements.txt
signalforge/src/signalforge/company_onboarding.py
signalforge/src/signalforge/config.py
signalforge/src/signalforge/investigation.py
signalforge/src/signalforge/llm_client.py
signalforge/src/signalforge/research_session.py
signalforge/src/signalforge/resume_run.py
signalforge/src/signalforge/source_discovery.py
signalforge/src/signalforge/structured_generation.py
signalforge/src/signalforge/xai_smoke.py
signalforge/tests/test_pipeline_catalog_audit.py
signalforge/tests/test_resume_run.py
signalforge/tests/test_source_discovery.py
signalforge/tests/test_xai_provider.py
signalforge/web/src/investigation.test.tsx
signalforge/web/src/ui.tsx
```

Private credential/provider assignments were configured only in the ignored
local dotenv file. No credential, downloaded document, dependency tree, cache
or new research-run artifact is part of the migration commit. The prior
Hindalco manifest/report/evidence were preserved rather than overwritten.

## Next local step and startup

From repository root, in the backend terminal, use a valid key through a hidden
zsh prompt:

```bash
read -s "XAI_API_KEY?xAI API key (hidden): "; export XAI_API_KEY
```

Then run the bounded preflight command in [DEMO_HANDOVER.md](DEMO_HANDOVER.md).
Only after it passes, resume the saved run with the documented xAI command.
This avoids repeating completed discovery and preserves the earlier report.

Backend:

```bash
SIGNALFORGE_PROVIDER=xai SIGNALFORGE_MODEL=grok-4.7 SIGNALFORGE_BASE_URL=https://api.x.ai/v1 PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
```

Frontend, in another terminal:

```bash
cd signalforge/web
npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173/ and select the saved Hindalco run to inspect the
preserved result. For a new company, enter its legal name and question in
**Start research** after provider preflight succeeds. Report exports and exact
passages are in the saved investigation view; full artifacts remain under
`signalforge/data/research_runs/<run_id>/`.
