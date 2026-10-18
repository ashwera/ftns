# SignalForge — Tested Review Branch Report

Date: 2026-10-18
Workspace: `/Users/ashwera/Documents/ftns`
Branch: `codex/signalforge-evidence-gate-review`
Base local HEAD: `f71df5e5d70c50b2ea51a27fb9f0aca0e3ae425e`

## Scope and safety

Read `AGENTS.md`, `README.md`, `COORDINATION.md`, and `signalforge/SIGNALFORGE_CODEX_1H_EXECUTION_PLAN.md`. Before branch creation the tree was on `main...origin/main`, had no staged changes, 21 modified tracked files, and 30 untracked entries. The dedicated branch was created at the existing local HEAD; all existing modifications and untracked artifacts remain in the worktree. No pre-existing branch was checked out. `.env` and credentials were not read or inspected. No API or source-retrieval call was made, and no evidence review fields were changed.

Generated run outputs, the PDF, archives, data files, frontend public-data output, `node_modules`, `dist`, and the execution plan are excluded from staging. Frontend public-data modifications and their coupled test adjustment are not included because the data's provenance points to a different run than the newer bounded run.

## PDF and source verification

- Configured document: `signalforge/data/Annual Report 2024-25_1.pdf`
- SHA-256: `28f32ae3803bc5aec87b49176df1e056d0cc9cf2c2a8d78f9144bc72c1b7cbbd`
- Result: exact match to the expected hash.
- The saved bounded PDF verification run is `signalforge/data/runs/scratch_ntpc_catalog_probe_20261019/run_offline_pdf_verify_context_fix_20261019/`.
- Its manifest records real source verification, no network/model use, seven reviewed inputs, six primary-source checks, and one extracted-text-only check. All seven effective outcomes remain `partially_supported`.
- There are 14 verification records (text extraction and PDF checks for seven inputs). The `re_under_implementation_group` value 14.5 GW is partially supported; its basis and statement-status checks remain unresolved. The primary-source check for 13,791 MW is `unable_to_verify` because that value does not appear with a unit in the selected passage. The run does not contain an assertion for 725 MW.
- The calculations preserve 709 MW as a derived residual. It must not be described as directly reported or reconciled with 725 MW. Prior visual review identifies 725 MW as directly reported in the parent-owned implementation table, but this bounded run did not directly assert/verify that value.
- Run finding remains `provisional_hypothesis` / `Weak`; all claims in its input set remain unverified. Its manifest reports F1 `blocked` and R1 `not_executed`; `network_used=false`, `model_used=false`.

## Evidence review gate

`signalforge/data/runs/run_20261018_evidence_review_prep_01/review_manifest.json` still has three records with `current_review_status: pending_review` and all approval fields unset:

- `ev_252ddc5ca75aa6a8bc871cb1`
- `ev_2484a0e981c95b1829d91ac3`
- `ev_fcde1c84df4f8b650bb1afdd`

The F1 code path requires a schema-valid record, exact verified company identity, parsed non-empty text, `review_status="approved"`, and non-empty `reviewed_by`, timezone-aware `reviewed_at`, and `review_note`. It bounds lines, eligible record count, and serialized payload size. The review manifest still says the original PDF is missing; that source-status note is stale after the PDF was added. I left it and all underlying review metadata unchanged. A human must inspect the records and record any decisions.

## Gemini client and R1 ownership

The current client uses the OpenAI Python SDK with Google's Gemini OpenAI-compatible endpoint, the existing `SIGNALFORGE_API_KEY` environment variable, JSON-object response mode, 60-second timeout, and two retries. JSON parsing fails closed, request errors redact the configured key, missing credentials and unsupported providers fail before SDK use. Offline mocks cover those paths. Current default model is `gemini-3.8-flash`; Google documentation lists this model and shows the same OpenAI-compatible endpoint and Chat Completions path ([model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [OpenAI compatibility guide](https://ai.google.dev/gemini-api/docs/openai)). This is documentation compatibility only; no live credential or request was tested.

No credential-presence check was done for this task. `signalforge/src/signalforge/r1_research_investigator.py` remains Claude-owned and was not edited. The existing coordination request remains for R1 to use the parsed/approved evidence gate and for pipeline status to report both missing credentials and ineligible evidence. The saved run did not execute F1 or R1.

## Dashboard audit

`signalforge/web/public/data/finding/SOURCE.json` and its `finding_bundle.json` both identify `run_20261018_full_e2e_ntpc_02`; the dashboard bundle is internally consistent but older than the bounded PDF verification run. It therefore does not reflect that newer run's six primary-source checks. I did not regenerate or stage generated frontend data. The dashboard still shows the earlier run's provisional/Weak status and blocked/not-executed F1/R1 states. This is a demo freshness limitation, not evidence that the newer run was integrated.

The current staged scope excludes all public-data JSON and the changed `signal.test.tsx`, whose updated assertions are coupled to the modified working-tree data. `signalforge/web/index.html` contains an unrelated external-font change and is also excluded.

## Code changes in the proposed branch

The existing dirty source/test changes were reviewed as one scoped F1/Gemini follow-up:

- F1 evidence eligibility and bounded/schema-validated parsing in `f1_research_angle_selector.py`.
- New Step 6 evidence defaults to pending human review; the schema accepts `null` only as a no-decision state.
- Regression tests cover pending/unparsed/malformed/duplicate/oversized evidence, identity and reviewer metadata checks, and blocked real evidence even when test simulation is requested.
- The Gemini-compatible client/config defaults and offline tests cover endpoint routing, explicit overrides, JSON parsing, missing key, unsupported provider, failures, and redaction.
- README and `.env.example` document the Gemini configuration and F1 review boundary.
- `COORDINATION.md` records ownership, current findings, and the Claude-owned R1 follow-up.

## Validation

Focused commands from `signalforge/` (all pass):

```text
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_f1_schema.py'        # 11 passed
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_public_sources.py'   # 6 passed
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_pipeline_bridge_retrieval_e2e.py' # 12 passed
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_llm_client.py'       # 6 passed
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_pipeline_catalog_audit.py' # 13 passed
```

One initial focused invocation used dotted test module names that this repository does not expose; it exited 1 with five unittest import-loader errors and ran no tests. The corrected discovery commands above passed.

Full backend suite from `signalforge/`:

```text
PYTHONPATH=src python3 -m unittest discover -s tests
Ran 201 tests — OK, exit 0
```

Frontend checks from `signalforge/web/`:

```text
npm test -- --run                         # 3 files, 22 tests passed, exit 0
npx tsc -b --pretty false                 # passed, exit 0
npm exec vite -- build --outDir /private/tmp/signalforge_review_build_20261018
# Vite production build passed, exit 0; existing dist/ was not touched
```

The Vite build warned that the external output directory is outside the project root and will not be emptied. No frontend browser visual test was performed. Final `git diff --check` and `git diff --cached --check` both passed after the commits; the index is empty.

## Publication

Code commit SHA: `05d9e46fc2eaee9959d2381f2edccc056255ceec`
Branch: `codex/signalforge-evidence-gate-review` (pushed to `origin`)
Draft PR URL: https://github.com/ashwera/ftns/pull/1

No merge or approval of a PR is authorized. No main branch update is intended.

## Remaining blockers and next actions

1. Human review is still required for the three pending evidence records; do not run genuine F1 against them until decisions are recorded.
2. Claude must address the R1 evidence eligibility request before R1 is considered safe for these real records.
3. The dashboard needs a separately reviewed sync from the bounded PDF run if that run is intended to be displayed; generated output is excluded here.
4. No live Gemini call or credential-presence check was performed by design. Live F1 remains conditional on configured credentials and approved evidence.

Next action: have a human review the three pending evidence records before any genuine F1 request; R1 requires the owning agent's evidence-gate fix first.
