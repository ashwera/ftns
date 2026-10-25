# Final demo rescue — 25 October 2026

## Result

Original run `research_20261024T210811_fa86eb3121a1` finished with a saved
**evidence-gap / inconclusive / Weak** report, three planning leads and zero
accepted financial claims. This is a genuine saved application result, **not**
a successful complete model investigation or verified financial discovery.

| Stage | Actual outcome |
|---|---|
| Discovery | Live Bing RSS with bounded provider fallback; initial search found zero strict matches |
| Onboarding | Cached local Hindalco PDF, not a live annual-report download; issuer self-declaration on physical page 185, ISIN INE038A01020; external identity lookup unavailable |
| Eligibility | 16 original-PDF identity/hash/page/passage records passed the machine policy; claim meaning remained unverified |
| F1 | Real 4B response was schema valid, unreliable, zero candidates; explicitly recorded deterministic planning fallback produced the three contest angles |
| R1 | Real model plan eventually passed the unchanged schema and evidence allowlist after prompt correction |
| Follow-through | Live search/retrieval; reused the completed checkpoint during recovery |
| Counterevidence | Live search and three successful document fetches; reused the saved checkpoint on the final resume |
| Claim validation | 4B responses failed literal-quotation validation. No gate was bypassed. 8B full request timed out before a usable response |
| Semantic investigation review | Not executed: no valid draft was available |
| Final adjudication | Deterministic, fail-closed evidence-gap decision; no financial conclusion accepted |
| Report and UI | JSON/Markdown saved, real run selected in the actual browser; evidence-gap status, project passages, limitations and model-review-not-executed visible; no browser errors |

## Root cause and repairs

The F1 model conflated dataset readiness with research-angle selection. Its raw
response treated missing company-joined rows in the quote CSV as absence of usable
company evidence. The F1 request actually contained 16 Hindalco PDF excerpts
(55,469 excerpt characters); slimming had preserved their useful text. The
available NTPC quote CSV has no verified Hindalco join and remains context only.
Missing rows cannot establish absence of financial activity.

The corrected prompt separates the evidence lanes. The fallback ranks the three
contest research questions using explicit evidence-match counts and published
weights; IDs, passages and source facts are never synthesized. Its use/reason/
method are recorded in the manifest and UI. It cannot turn a hypothesis into a
financial finding or establish source independence.

Investigation also needed the exact F1 passages carried into its own source IDs.
Those excerpts now require the same original hash/path and machine checks.
Context is bounded without modifying original excerpts. Strict quotations and
calculations remain mandatory. Repeated URLs and normalized document copies
cannot multiply corroborating sources. Unsupported model headlines are withheld
after adverse review. Saved searches/responses can be resumed with revalidation.

Zero strict discovery matches now enable at most three distinct penalized leads
(35 points), with content inspection and explicit unverified status. Noise,
login/search-engine and confirmed wrong-company results remain excluded. Issuer
identity and normal evidence acceptance still run separately. Missing evidence
or invalid model output produces an explicit no-finding report.

## Discovery metrics and corroboration

| Search stage | Raw returned | Strict rejected | Strict retained | Penalized fallback leads | Successful fetches |
|---|---:|---:|---:|---:|---:|
| Initial | 30 | 30 | 0 | 0 (before fallback change) | 0 |
| R1 follow-through | 10 | 2 | 8 | 0 | 2 of 3 attempts |
| Counterevidence | 20 | 20 | 0 | 3 | 3 of 3 attempts |

The five successful fetches include repeated pages. Final source selection has
three distinct sources: the cached PDF plus Aditya Birla's Hindalco company page
and aluminium innovation page. The retrieved Hindalco price page did not become
an accepted investigation source. The two parent-company pages retain unresolved
lineage; **no independent corroboration was established**. The annual report is
issuer-only. Different snapshots or hosts were not counted as independence.

## Defensible lead

Physical page 21, evidence `ev_f6bf8fc87e968143f61c184e`, states:

> Downstream capacity to increase from 430 KT to more than 600 KT with commissioning of 170KT FRP by the end of FY 2026

This supports asking whether later dated project records reconcile the target
with actual commissioning on the same scope/basis. It does not prove a missed
target. The same excerpt also states a Silvassa extrusion facility was commissioned
in FY2023-24; other passages describe future projects. Timing, project identity,
definitions and reporting perimeter are viable counterarguments. Confidence is
Weak. No independent operating record, defensible financial impact calculation
or novelty assessment was established. Source publication date is unestablished;
the local filename must not be used as a verified reporting period.

## Models, checks and remaining blockers

- `qwen3:8b` became available during this session. Configured
  `signalforge-qwen8b` at 32,768 tokens on the 16 GB Mac. Its JSON/exact-quotation
  smoke test passed in 11.13 seconds; the full request hit the existing 420-second
  timeout. An earlier resume used an invalid `/v1p` endpoint and returned 404;
  explicit `/v1` fixed that configuration problem. No timeout was increased.
- Tomorrow's startup defaults to the retained `signalforge-qwen` 4B baseline.
  Its F1/R1 calls worked but exact-quote investigation responses failed. A complete
  live model investigation remains unproven; neutral evidence-gap reporting works.
- Final backend: **338 tests run, 336 passed, 2 skipped**. Frontend: **43 passed**.
  TypeScript `tsc -b` and Vite production build passed. `git diff --check` passed.
- Generic onboarding/discovery without catalogs is covered by regression fixtures.
  Hindalco required a cached original, so fully online arbitrary-company evidence
  acquisition was not demonstrated. Robots/provider failures, scanned PDFs and
  inaccessible originals remain practical limitations.
- No model quota dependency was added. Existing credentials were preserved and
  excluded from staging. Source/provenance/identity/contradiction/falsification
  requirements were not weakened.

## Files integrated during this rescue

Some earlier changes were included in the separate user commit `6893f33` while
this session was running. The subsequent commit preserves that history.

```text
.gitignore
README.md
COORDINATION.md
signalforge/.env.example
signalforge/.gitignore
signalforge/requirements.txt
signalforge/Modelfile.qwen3-4b
signalforge/Modelfile.qwen3-8b
signalforge/DEMO_HANDOVER.md
signalforge/DEMO_RESCUE_REPORT.md
signalforge/prompts/f1_research_angle_selector.md
signalforge/prompts/r1_research_investigator.md
signalforge/src/signalforge/company_onboarding.py
signalforge/src/signalforge/f1_research_angle_selector.py
signalforge/src/signalforge/investigation.py
signalforge/src/signalforge/llm_client.py
signalforge/src/signalforge/machine_evidence.py
signalforge/src/signalforge/pipeline.py
signalforge/src/signalforge/research_session.py
signalforge/src/signalforge/resume_run.py
signalforge/src/signalforge/source_discovery.py
signalforge/src/signalforge/structured_generation.py
signalforge/tests/test_company_onboarding.py
signalforge/tests/test_f1_schema.py
signalforge/tests/test_investigation.py
signalforge/tests/test_ollama_provider.py
signalforge/tests/test_pipeline_catalog_audit.py
signalforge/tests/test_research_service.py
signalforge/tests/test_resume_run.py
signalforge/tests/test_source_discovery.py
signalforge/web/src/investigation.tsx
signalforge/web/src/investigation.test.tsx
```

The existing Hindalco manifest, events, report JSON and Markdown were finalized
locally. Raw model requests/responses, retrieval snapshots and originals remain
preserved. No new dependency tree, cache or downloaded PDF is staged by this
final integration. The separate user commit already contains earlier generated
artifacts; it is preserved without rewriting remote history.

See [DEMO_HANDOVER.md](DEMO_HANDOVER.md) for exact launch and recovery commands.
