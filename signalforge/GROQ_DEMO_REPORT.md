# Groq demo validation — 25 October 2026

This records real API and application checks. A passing provider smoke test is
not a verified financial finding. No evidence gates were relaxed.

## Implementation

- Dedicated `GROQ_API_KEY`, official `https://api.groq.com/openai/v1`, existing
  OpenAI SDK Chat Completions. Groq is selected automatically when its key exists
  and no provider is explicitly selected. Private local provider assignments now
  select Groq; other credential assignments are preserved.
- Preferred model `openai/gpt-oss-120b`; `openai/gpt-oss-20b` was explicitly selected
  for recovery after the 120B daily allowance was insufficient. No silent model,
  Ollama, xAI or paid-service fallback. Deprecated Compound IDs are refused.
- Search calls use only `browser_search`, never JSON response_format. Structured
  calls use JSON schema and unchanged local schema/quotation/evidence validators.
  Conditional/optional schemas use best-effort provider mode; local validation
  remains mandatory. A known provider JSON-validation failure can use the same
  single application repair; transport, authentication and 429 never auto-retry.
- 18 KB request cap, 2,048 output-token cap (1,024 for search), 60-second SDK
  timeout, zero SDK retries, low reasoning and conservative 60-second pacing.
  One search request per discovery stage. Internal Groq tool calls cannot be
  hard-capped by this adapter; the provider's returned usage is retained.
- Whole originals and full evidence remain on disk. The bounded model payload
  uses contiguous excerpts with real IDs and explicitly describes omitted context.
  Repair feedback survives payload/schema slimming. Deterministic calculations,
  exact quotes, identity, provenance, contradiction and adjudication gates remain.
- Tool/citation URLs become unresolved leads. Underlying pages are retrieved
  through the existing public-source policy. Browser errors can fall back once
  to public search; 429 does not. Issuer copies never acquire independent lineage.
- A stopped pre-F1 run can retry onboarding against completed saved discovery.
  An ambiguous annual-report PDF may be inspected for issuer identity; a search
  rejection is never evidence for a financial claim. Wrong-company/noise results
  cannot enter this identity-probe path. Previous reports are archived first.

## Real provider checks

Authenticated model list included both GPT-OSS models. Initial 120B connectivity
request succeeded: 102 prompt + 27 completion = **129 tokens**. The first schema
draft had a stitched quotation and was rejected. Corrected schema/quotation smoke
passed separately: **1,295** and **488** total tokens respectively.

An initial browser probe returned HTTP 500. NHPC's actual application request
then succeeded with browser_search: **524,799 prompt + 702 completion = 525,501
reported tokens**, including 98,048 cached prompt tokens. These are the provider's
tool-session usage numbers, not an invoice or a claim of billable cost. This large
session prompted the explicit low-reasoning/one-search instruction change.

120B Hindalco recovery received HTTP 429. A tiny later diagnostic succeeded, but
the bounded investigation still exceeded the daily remaining allowance. The safe
audit reported **tokens per day: limit 200,000; used 199,458; requested 3,080**;
`retry-after: 1097` seconds at 05:50 UTC. No automatic retry or upgrade occurred.

20B initially returned HTTP 400 on a schema smoke. A later bounded preflight
passed its representative draft and separate exact quote: **1,207** and **488**
tokens. It is an authenticated, live-tested alternative, not a mocked result.

Local audit directories (ignored): `outputs/groq_preflight/`,
`outputs/groq_schema_quote_repair_20261025/`,
`outputs/groq_20b_bounded_validation_20261025/`.

## Genuine uncached-company attempt: NHPC Limited

Run **research_20261025T053759_4d060577ed01** started through the application's
POST API. No NHPC registry entry, curated catalog or prepared PDF was supplied.

- One live Groq browser request exposed 34 distinct tool/citation URLs; the
  adapter returned its bounded five leads. Strict filtering accepted four and
  rejected one. Zero strict-filter fallback candidates (strict matches existed).
- Three normal document retrievals failed: NSE robots verification, BSE HTTP403,
  Moneycontrol HTTP403. A saved ambiguous NHPC annual-report PDF lead was then
  downloaded during identity acquisition, without repeating discovery.
- That original did not expose a matching name/labelled equity-ISIN declaration.
  The unrelated Hindalco drop-folder PDF also failed the NHPC identity check.
  **Zero eligible NHPC evidence items.** No F1, R1, semantic investigation,
  calculations or independent corroboration ran for NHPC.
- The same run finished with **evidence_gap / inconclusive / Weak** and a usable
  report. This is a genuine uncached-company workflow attempt, not a completed
  financial investigation. Source access/extractable issuer identity remains a
  real blocker. Rejected results establish no adverse fact about NHPC.

## Saved Hindalco recovery

Run **research_20261024T210811_fa86eb3121a1** retains its original F1 planning
fallback and validated R1. The original cached issuer PDF was rehashed and its
machine eligibility rechecked. Completed follow-through and counterevidence
search checkpoints were reused; no new Hindalco discovery or retrieval was run.

Original discovery metrics: 60 raw results, 52 strict rejections, three fallback
leads, five successful fetches including repeats; 16 machine-eligible excerpts.
Recovery deduplicated these to three unique originals (issuer PDF and two
Aditya Birla pages), with 17 investigation passages. No independent lineage was
established. Exact quotes alone do not verify a financial interpretation.

**Completed with Groq 20B at 05:59 UTC:** initial draft needed one exact-quote
repair; final draft passed on its first attempt; semantic review passed its
schema on its first attempt. Counterevidence reconciliation, deterministic
adjudication and final JSON/Markdown report generation completed. The old local
model reports are preserved in recovery history.

Result: **investigation / inconclusive / Weak**, rather than the previous
model-failure evidence-gap report. Two issuer-announcement claims were supported;
actual commissioning remains unresolved. The proposed broader headline failed
semantic review and is explicitly labelled rejected. The model incorrectly
suggested independent support in two review flags; the unchanged deterministic
lineage gate overrode both: **zero independently corroborated claims**.
No financial discrepancy, lost revenue, misconduct or novelty was established.
No calculation was proposed, so arithmetic is explicitly not applicable.

The strongest defensible lead is to check the target commissioning against
dated operational records. Actual issuer passage (physical page locator retained
under `src_c240197af9376407_ev_f6bf8fc87e968143f61c184e`):

> Copper and E‑waste recycling project with a capacity of 50 KTPA to be commissioned at Pakhajan, Bharuch District, Gujarat by 2026

This is a recycling-capacity announcement, not renewable-generation capacity or
proof of delay. The counterargument is that forward-looking project milestones
can remain under development; absent independent records do not prove a material
gap. Confidence in the announcement's exact wording is distinct from Weak
confidence in actual commissioning/financial implications. Dated issuer updates
and attributable regulator/operator records for the same project, unit and period
are still needed. Source publication date was not established from the filename.

Four recovery calls (including the rejected initial quotation) used **17,388 total
tokens**: 4,123 initial, 5,702 repair, 4,017 final, 3,546 review. Largest actual
request was 17,719 bytes. Provider elapsed times were 2.899, 2.341, 2.072 and 0.707
seconds, separately from conservative pacing and original revalidation time.

## Original F1 cause

The local model confused missing company-matched CSV rows with absent financial
activity, despite identity-checked PDF excerpts being present. The CSV is an
unjoined NTPC equity export and cannot represent Hindalco or NHPC. Dataset
readiness and evidence-led angle selection are separate. Existing deterministic
fallback scores only real eligible evidence across the three contest angles and
creates research questions/retrieval requirements, never financial discoveries.

## Verification and handover

Final checks: **365 backend tests: 363 passed, two skipped; 55 frontend tests
passed; `tsc -b` and Vite production build passed.** A focused socket test first
failed inside the sandbox and passed outside it; the final full backend run used
the required socket permissions. No skipped assertion or evidence gate was removed.

Real Chrome verified NHPC/Hindalco saved run IDs, Groq model labels, actual reports
and limitations; zero page errors. The completed Hindalco recovery display was
rechecked after report generation. Frontend contributions from the other coding agent are
preserved, including live-run contracts/polling and the separate saved NTPC tab.

See [DEMO_HANDOVER.md](DEMO_HANDOVER.md) for exact secure key entry, startup,
company submission, saved-report inspection and recovery commands. Generated
PDFs, raw tool sessions, private configuration and caches are not committed.

Changed source/config/test files: `src/signalforge/{config,llm_client,
structured_generation,groq_provider,groq_smoke,research_session,company_onboarding,
investigation,resume_run}.py`; `tests/{test_groq_provider,test_company_onboarding,
test_investigation,test_research_service,test_pipeline_catalog_audit}.py`;
`.env.example`, `.gitignore`. Frontend files integrated: `web/src/{ui.tsx,
live-run.ts,demo-run.ts,live-run.test.tsx,ui.test.tsx,signal.test.tsx,
investigation.test.tsx}`. Documentation: this report, `DEMO_HANDOVER.md`, root
`README.md`, `COORDINATION.md`. Existing tracked Hindalco report/manifest/event
artifacts are updated to reflect the real recovery; bulky new artifacts stay local.
