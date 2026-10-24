
# SignalForge — One-Hour Codex Execution Plan

**Purpose:** Give Codex one bounded, mostly autonomous work session in the existing VS Code workspace. Protect the current work first, then validate and fix the most important evidence-safety and model-client issues, test every meaningful step, and leave a reliable handoff.

**Repository:** `https://github.com/ashwera/ftns`  
**Expected local workspace:** repository root `ftns/`  
**Time budget:** about 60 minutes. Prioritize a correct, tested small result over trying to finish the entire product.  
**Authority:** This plan does not authorize a reset, cleanup, branch switch, pull/rebase, staging, commit, push, evidence approval, secret access, or paid/live model calls.

---

## 0. The operating instructions for Codex

Work in the **already-open local workspace** and preserve its current dirty working tree. The user has explicitly asked you to work independently, avoid interrupting them unless necessary, complete and test each step, and stop when the repo or task becomes confusing.

- Read `AGENTS.md`, `COORDINATION.md`, and `README.md` before editing anything. Treat the live files as authoritative for ownership and project-specific instructions.
- Inspect before editing. At every checkpoint, know which files you changed and which tests cover them.
- Do not ask routine preference questions. Make a conservative choice, document it, and continue with independent safe work.
- Do ask/stop when continuing would require guessing about evidence semantics, overwriting work, exposing a secret, approving a claim, changing a shared schema without a contract, performing a destructive Git action, or using paid/networked resources.
- Do not wait for the user for ordinary read-only inspections or local tests that are clearly safe under the existing Codex permission mode.
- Do not run a broad autonomous agent loop that starts changing random modules to fill the hour. Work in the exact order below.
- If an item cannot be completed safely, mark it **BLOCKED**, include the specific reason, and continue to the next independent item.
- If a test fails before your edits, record it as a baseline failure. Do not claim your changes caused it and do not spend the whole hour repairing unrelated failures.

### Absolute no-go actions

Do not run or ask to run any of these:

```text
git reset --hard
git clean -fd
git stash
git checkout <branch>
git switch <branch>
git pull
git rebase
git add .
git add -A
git commit
git push
```

Do not use `npm ci` (it can remove the existing `node_modules` tree), blindly run `npm install`, delete generated data, overwrite any existing run directory, replace the source archive, or overwrite a pre-existing report file. Do not switch to a new worktree: the user wants the current local, uncommitted workspace preserved.

Never print `.env` contents, API keys, tokens, private URLs containing credentials, or environment-variable values for secrets. It is okay to check whether a key is present using a Boolean result, without displaying it. No real F1/R1 model inference or external-source retrieval during this session.

---

## 1. Project goal and current state

SignalForge is a research workflow for the **Find the Next Signal** contest, Energy, Power & Renewables track. It should use public disclosures to produce a non-obvious, falsifiable financial discovery—or honestly say the evidence is insufficient. A good final discovery needs a clear claim, why it matters, independent sources where available, a timeline, reproducible calculations, a counterargument, falsification conditions, evidence-strength label, and clickable provenance.

Pipeline layers include document intake and page provenance, claim extraction, human review/eligibility, F1 research-angle selection, R1 planning, source catalog/retrieval/verification, calculations/signals, finding generation, and the frontend. **Extraction is not verification. A successful pipeline run is not proof that a discovery is true.**

### Last user-reported local Git state

The user ran `git status --short --branch`, `git branch --show-current`, `git remote -v`, and `git diff --stat`. At that point:

- Branch: `main`; upstream shown as `origin/main`.
- Remote: `https://github.com/ashwera/ftns.git` for fetch/push.
- Working tree contained many **uncommitted local changes**. Re-run status because it may have changed since the list below.
- The ChatGPT GitHub connection can read permitted **committed** repository content, but it cannot see this local dirty workspace. GitHub `main` is known to differ from local edits.

Tracked files shown modified:

```text
COORDINATION.md
README.md
signalforge/.env.example
signalforge/schemas/evidence_record.schema.json
signalforge/src/signalforge/config.py
signalforge/src/signalforge/evidence_ingestion.py
signalforge/src/signalforge/f1_research_angle_selector.py
signalforge/src/signalforge/llm_client.py
signalforge/tests/test_f1_schema.py
signalforge/tests/test_pipeline_bridge_retrieval_e2e.py
signalforge/tests/test_pipeline_catalog_audit.py
signalforge/tests/test_public_sources.py
signalforge/web/index.html
signalforge/web/public/data/finding/SOURCE.json
signalforge/web/public/data/finding/audit_trail.json
signalforge/web/public/data/finding/calculations.json
signalforge/web/public/data/finding/finding_bundle.json
signalforge/web/public/data/finding/source_catalog_status.json
signalforge/web/public/data/finding/stage_manifest.json
signalforge/web/public/data/finding/verification_results.json
signalforge/web/src/signal.test.tsx
```

Untracked paths shown included:

```text
node_modules/
package-lock.json
package.json
signalforge/data/.DS_Store
signalforge/data/CSV.zip
signalforge/data/claims_step1/review_queue.jsonl
signalforge/data/claims_table_step1/
signalforge/data/claims_table_xy/
signalforge/data/intake/
signalforge/data/processed_step6/category_readiness.json
signalforge/data/processed_step6/source_records.jsonl
signalforge/data/runs/run_20261018_archive/prose_only/
signalforge/data/runs/run_20261018_archive/table_aware/
signalforge/data/runs/run_20261018_evidence_review_prep_01/
signalforge/data/runs/run_20261018_full_e2e_ntpc_01/
signalforge/data/runs/run_20261018_full_e2e_ntpc_01_upstream/
signalforge/data/runs/run_20261018_full_e2e_ntpc_02/
signalforge/data/runs/run_20261018_full_e2e_ntpc_02_upstream/
signalforge/data/runs/run_20261018_ntpc_slice/bundle/
signalforge/data/runs/run_20261018_ntpc_slice/research/
signalforge/data/runs/run_20261018_second_company_nodata/bundle/
signalforge/data/runs/run_20261018_second_company_synthetic/bundle/
signalforge/data/runs/run_20261018_second_company_synthetic/research/
signalforge/data/runs/run_20261019_ntpc_slice_audit/bundle/
signalforge/data/runs/run_20261019_ntpc_slice_audit/research/
signalforge/data/runs/scratch_ntpc_catalog_probe_20261019/
signalforge/tests/test_llm_client.py
signalforge/web/dist/
signalforge/web/node_modules/
```

These are a snapshot, not a guarantee of current status. Preserve all of them. In particular, the generated outputs, intake archive, claim outputs, and run bundles are research artifacts—not disposable caches. `node_modules/` and `dist/` are also not to be deleted in this task.

### Previously reported test state (must be rechecked locally)

A prior Codex report said: backend suite 193 passed; focused suite 44 passed; frontend 22 passed; TypeScript passed; production build passed in scratch; `git diff --check` passed. No live inference or original-PDF verification was performed. These are **reported history, not current test results**. Re-run the relevant checks before relying on them.

### Current factual/evidence constraints

- The `SIGNALFORGE_API_KEY` was absent at the previous check. That means no live model call was made. Never reveal the key if the user later supplies one.
- The local config/client edits reportedly aim to support Gemini through Google's OpenAI-compatible API. Inspect the local code and tests; do not blindly replace it with the older version committed on GitHub.
- The original NTPC FY2024–25 annual-report PDF was not found in the previous project-wide search. Do not claim PDF-level verification or claim its SHA-256 was checked unless the exact file is present and its digest is computed and verified now.
- `signalforge/data/processed_step6/` contains PDF-to-text page blocks, not the original PDFs. Text/page/table extraction can lose structure.
- Review-prep outputs were reported to contain three review records, all `pending_review`, parsed and document-identity-verified, with no approvals. The required review fields were `review_status`, `reviewed_by`, `reviewed_at`, and `review_note`. Confirm current local files before relying on counts. **Do not fill these fields or approve anything automatically.**
- An earlier F1 bundle reportedly contained 21 records, 18 unrelated to the seven reviewed claim candidates. Wrong-company evidence must never be silently passed to F1.
- The latest pipeline finding is `provisional_hypothesis` / `Weak`, not a confirmed discovery. Preserve that status unless the evidence itself supports a justified change.
- Do not force these figures to reconcile: 725 MW printed parent-owned table value; 709 MW derived residual; 13,791 MW JV/subsidiary figure; approximately 14.5 GW implementation wording; 14,516 MW detailed group pipeline. They may use different scopes/bases/rounding. Keep each figure with its own source, units, date, definition and derivation.

---

## 2. One-hour work plan at a glance

Use the time budget as a guide, not a reason to skip safety or tests.

| Time | Work block | Required outcome |
|---|---|---|
| 0–8 min | Safety and project read-in | Baseline recorded; no Git state changed |
| 8–15 min | Baseline tests and local code map | Know what currently passes/fails and the source of the F1 gate |
| 15–35 min | Evidence eligibility gate | Fix or precisely isolate the highest-risk gate defect with regression tests |
| 35–45 min | Gemini/OpenAI-compatible client audit | Provider config is coherent, safely blocked without credentials, and covered by offline tests |
| 45–52 min | Run bundle + UI truth audit | Verify statuses and UI do not imply evidence/retrieval/model work that did not happen |
| 52–60 min | Final checks and handoff | Run final tests, record exact results, leave a clear report and coordination entry |

If setup/test time is greater than expected, prioritize **working-tree safety → evidence review gate → provider tests → honest report**. A partial correct fix is better than a broad risky refactor.

---

## 3. Phase 0 — safe baseline (0–8 minutes)

### Required actions

1. Read `AGENTS.md`, `COORDINATION.md`, `README.md`, and the relevant parts of `signalforge/PIPELINE_COMPLETION_REPORT.md` if present.
2. Read the current ownership/requests section in `COORDINATION.md`. Respect file ownership. The current coordination file itself, README, F1 selector, evidence ingestion, and frontend are listed in earlier notes as Codex-owned, but the **live** coordination file decides.
3. Run non-mutating status commands from repository root:

```bash
git status --short --branch
git branch --show-current
git remote -v
git diff --stat
git diff --name-only
git diff --cached --stat
git diff --check
```

4. Inspect only the diffs relevant to this task. Do not dump all files or any secret config. Start with:

```text
signalforge/src/signalforge/config.py
signalforge/src/signalforge/llm_client.py
signalforge/src/signalforge/f1_research_angle_selector.py
signalforge/src/signalforge/evidence_ingestion.py
signalforge/tests/test_llm_client.py
signalforge/tests/test_f1_schema.py
signalforge/tests/test_pipeline_bridge_retrieval_e2e.py
signalforge/tests/test_pipeline_catalog_audit.py
signalforge/.env.example
```

5. Check whether local `.gitignore` exists and inspect it without changing anything. Do not attempt to resolve every untracked item by adding ignore rules or deleting files.
6. Write a brief baseline section in the **new** report file described in Phase 7; if that file already exists, do not overwrite it—choose a timestamped name instead.

### Safety checks

- Confirm there are no unexpected staged changes. If any exist, do not unstage them; record the state and continue without touching the index.
- Confirm all work is still on the existing branch and no branch switch is needed.
- If a diff contains credential-like values, do not include the values in output. Say only which file/line range needs local secret hygiene.
- Never read or print `signalforge/.env`; do not search by echoing secret values.

**Checkpoint 0:** If preserving the tree is clear, continue. If a destructive action is required to proceed, stop and report the blocker instead.

---

## 4. Phase 1 — establish current test baseline (8–15 minutes)

### Python baseline

From repository root, run the project's full unit suite exactly as documented, unless the live README says otherwise:

```bash
PYTHONPATH=signalforge/src python3 -m unittest discover -s signalforge/tests -v
```

Run targeted suites if full tests are slow, but do not call a targeted pass the full-suite result. Capture exact pass/fail/skip counts and the command in the report.

### Frontend baseline

Inspect the current package manifests before running commands; the local status previously showed untracked root `package.json`/`package-lock.json` as well as `signalforge/web/node_modules/` and `signalforge/web/dist/`. Do not assume which manifest is authoritative.

- Check the existing `scripts` in the relevant package manifest.
- If dependencies already exist, run the existing test and build scripts from the correct directory.
- Do **not** delete/recreate dependencies or run an install just because a command fails. If an install is genuinely needed, record it as blocked and ask the user before changing manifests/lockfiles.
- Run TypeScript only using the project's configured script or existing configuration.

### Baseline failure rule

Record failures before making changes. Fix only a failure related to the task or a small dependency directly blocking the required tests. Do not use the hour for unrelated cleanup or visual restyling.

**Checkpoint 1:** Now identify exact code paths for evidence eligibility, provider selection, F1 payload construction, and pipeline bridge handoff. Continue only after understanding how the live local code works.

---

## 5. Phase 2 — secure the evidence review/eligibility gate (15–35 minutes)

**This is the highest priority engineering task.** F1 must never treat document identity as sufficient proof that an individual evidence record is reviewed, parsed well enough, relevant to the requested company, and appropriate for model input.

### 5.1 Trace the data flow before editing

Read the live local implementations and schemas for:

- `signalforge/src/signalforge/f1_research_angle_selector.py`
- `signalforge/src/signalforge/evidence_ingestion.py`
- pipeline bridge/retrieval code involved in the end-to-end run (for example `research_bridge.py`, `pipeline.py`, `claim_verification.py`, and catalog/audit helpers if present)
- `signalforge/schemas/evidence_record.schema.json`
- schemas for claims, findings and review records that the live code actually uses
- the review manifest/queue currently present under `signalforge/data/runs/run_20261018_evidence_review_prep_01/` if it exists

Map the current fields into a short table in your report: document identity; issuer/company association; parse/extraction status; human review status and reviewer metadata; claim verification status; source relationship/independence; and payload provenance. Do not treat these as interchangeable statuses.

### 5.2 Implement the smallest fail-closed gate that fits the actual schema

Requirements:

1. **Human review must be explicit.** An item with missing review status, `pending_review`, `unverified`, a malformed status, or missing required reviewer metadata is not F1-eligible. Use the canonical statuses and field names in the current schemas/tests; do not invent a second competing review model.
2. A valid approval must have the review decision and the required metadata (`reviewed_by`, `reviewed_at`, `review_note`, or the repository's clearly documented equivalent). Validate timestamps if the existing project contract expects a timestamp format. Do not infer approval from a document-level identity flag.
3. **Never auto-approve.** No code, migration, test fixture, or script may fill review fields to force a run. Existing records stay pending unless a human reviewed them through an explicitly human-controlled path.
4. Reject malformed, empty, unparsed, fragmentary, or failed-extraction records when the actual status fields indicate they are not suitable for review/analysis. Use evidence visible in the record/schema, not guesses from arbitrary text. If the current schema does not represent parse quality adequately, preserve the conservative default and record the schema gap; do not create an uncoordinated broad schema rewrite.
5. Reject evidence for a different/unresolved company. A canonical company name appearing in a document, a URL, or a file name is not enough on its own. Preserve the current verified-identifier/registry rules and add the review check alongside them.
6. Make limits on F1 input explicit and testable. Inspect existing record sizes and any established payload caps first. Bound individual records, total serialized evidence payload, and/or record count as needed, with documented values and tests. If eligible records exceed the supported limit, fail with a clear diagnostic or produce an explicit audited refusal; **do not silently truncate, silently drop inconvenient evidence, or pretend it was all considered**.
7. Keep eligible source provenance and evidence IDs intact. Reject malformed JSON/schema failures visibly rather than silently swallowing records.
8. Keep the no-key path safe: no configured model key means no model/network call and a clear actionable error.
9. Reuse one predicate/helper at the correct shared boundary if the current architecture has one, but avoid a sweeping pipeline refactor.

If two stages disagree about the eligibility contract, stop before inventing a compromise. Record the disagreement in `COORDINATION.md` under Requests/Open questions and leave both paths fail-closed.

### 5.3 Required regression tests

Add or adjust focused tests proving at least:

- A record with verified NTPC identity but `pending_review` is rejected by F1.
- A record with no review fields is rejected.
- A record marked approved but missing required reviewer metadata is rejected.
- A valid, explicitly human-approved, correctly parsed, company-matched record is eligible under the actual contract.
- `unverified` claim-extraction outputs are not automatically equivalent to approved evidence.
- Empty, fragmentary, malformed, failed-parse, or invalid records are rejected according to their represented status fields.
- Wrong-company/unresolved-company material is rejected.
- Oversized record/payload is refused with a clear error; no silent truncation.
- Missing API key blocks before any model client call.
- The gate does not mutate source evidence or populate approval fields.

Use synthetic unit-test inputs and mocks; do not approve or edit the real review queue to satisfy tests. No paid API or live source retrieval.

### 5.4 Test this step before moving on

Run the focused relevant tests, for example:

```bash
PYTHONPATH=signalforge/src python3 -m unittest discover -s signalforge/tests -p 'test_f1_schema.py' -v
```

Use the actual file name and test-discovery conventions in the local repository; if it differs, discover the correct command rather than assuming. Also run the relevant pipeline-bridge/catalog tests. Then run the complete Python suite again after all backend changes in Phase 3.

**Checkpoint 2:** If the approval-field contract cannot be confidently determined from current code/schema/coordination, do not guess. Keep the gate fail-closed, add tests for the unambiguously unsafe states where possible, write down the exact unresolved contract, and move to Phase 3 only if its scope is independent.

---

## 6. Phase 3 — audit the local Gemini/OpenAI-compatible client (35–45 minutes)

The local branch reportedly changes the client to call Gemini's OpenAI-compatible endpoint, while the committed GitHub `main` still has OpenAI-only defaults. Work from **local** code and preserve backward compatibility only where current requirements/tests support it.

### 6.1 Inspect actual config and dependency behavior

Review `config.py`, `llm_client.py`, `.env.example`, `requirements.txt`, README model-provider section and `test_llm_client.py`. Verify:

- provider selection is case/whitespace normalized or deliberately validated;
- `SIGNALFORGE_API_KEY` remains the single documented credential variable unless the project intentionally supports aliases;
- Gemini's default base URL is not accidentally blank when Gemini is selected;
- selecting OpenAI does not accidentally inherit the Gemini endpoint, and vice versa;
- model name and base URL can be overridden by environment variables when appropriate;
- an unsupported provider fails clearly, not via an obscure SDK error;
- the optional SDK is imported lazily if intended and missing dependency has a useful error;
- timeout/retry behavior is finite and tested where practical;
- empty model response, non-JSON response, invalid JSON, SDK errors, and successful JSON response are handled cleanly;
- request configuration and error messages never disclose the API key;
- `response_format={"type":"json_object"}` is either supported for the chosen compatibility path or handled/tested appropriately;
- no accidental client/network call happens at import time.

Official reference for the current Gemini OpenAI-compatible API endpoint, client setup, supported examples and model listing: https://ai.google.dev/gemini-api/docs/openai. The current documentation demonstrates `https://generativelanguage.googleapis.com/v1beta/openai/` and `gemini-3.8-flash`; use configurable settings and confirm against that current reference rather than assuming this will remain the forever-default.

### 6.2 Keep it offline by default

- Do not make a live API request, even if a key happens to be present, during this one-hour run.
- Do not echo or copy an actual key into the report, fixture, command history, or logs.
- Mock the SDK/client in unit tests to verify model/endpoint arguments and return/error handling.
- Verify missing-key behavior blocks before client creation/calls.
- Keep the example file limited to variable names and blank credential values.
- Do not add a second SDK or new dependency unless the current implementation cannot reasonably work with existing requirements and a focused case proves it necessary.

### 6.3 Focused client tests

At minimum test: Gemini provider defaults/endpoint, OpenAI provider behavior if still supported, env overrides, missing-key refusal, unsupported-provider refusal, successful JSON parse using a mocked response, invalid JSON, empty response, and SDK import/request error. Update README and `.env.example` only as required to match the implementation actually tested.

Run the specific client tests and check the diff. Do not alter evidence-gate behavior just to enable a live F1 run.

**Checkpoint 3:** If provider configuration works under mocks and no credential is available, consider this client task complete. A live model request is explicitly out of scope.

---

## 7. Phase 4 — audit the latest run and dashboard for truthful state (45–52 minutes)

Inspect existing outputs only. Do **not** overwrite a prior run, rerun extraction over the full archive, rerun live retrieval, or mutate the review queue during this hour.

### 7.1 Latest full end-to-end run

If present, inspect `signalforge/data/runs/run_20261018_full_e2e_ntpc_02/`, its manifest, stage status, source catalog, audit trail, calculations, verification results and finding bundle. The reported state to confirm—not assume—is:

- F1 was blocked due to missing `SIGNALFORGE_API_KEY`;
- R1 did not execute;
- one source catalog item was unreadable and five sources were not retrieved;
- the finding is still `provisional_hypothesis` / `Weak`;
- no source retrieval or review stage is labeled completed unless its artifacts prove it happened.

If the filenames or states differ, trust the actual JSON plus code and report the discrepancy. Do not write to this run directory. If a safe rerun is necessary for an offline test, use a new, unique scratch directory only after checking that it does not exist and only if time permits; do not run a full pipeline just to regenerate the same outputs.

### 7.2 Original source/PDF check

Check whether the exact FY2024–25 NTPC annual-report PDF is present locally. If absent, record **BLOCKED: original PDF unavailable**. Do not download or retrieve new sources during this run. If present, do not overwrite it; hash it read-only only if you can establish that its exact expected provenance is known. Never claim that a hash matches if the expected full hash is not available.

### 7.3 Frontend truth audit

Inspect the frontend data adapters, tests, Vite development middleware, static assets, and run bundle. Check that:

- F1 and R1 blockers are visible as blockers, not hidden as success;
- unverified claims cannot be presented as validated findings;
- simulated/demo data are clearly labeled and never mixed with real evidence;
- no fake source URLs, fabricated live statuses, or invented metrics appear;
- static mode does not pretend development-only `/api/research/*` routes are available;
- the UI can display missing/unavailable data honestly;
- click-through provenance stays attached to the actual source/page/claim.

Do not restyle the whole dashboard. Only make a narrow fix if the problem is demonstrable, in a Codex-owned file, safe, and can be tested in the time remaining. Otherwise report it as a concrete UI blocker with the path and behavior.

### 7.4 Keep accounting figures separate

Where the bundle or UI mentions capacity values, do not force a reconciliation of 725 MW, 709 MW, 13,791 MW, ~14.5 GW, and 14,516 MW. Confirm each number is visibly attributed to its own reporting scope/source/calculation. If not, document that limitation; do not change the underlying evidence to make it look consistent.

---

## 8. Phase 5 — final test sweep and handoff (52–60 minutes)

Run checks after all edits:

```bash
PYTHONPATH=signalforge/src python3 -m unittest discover -s signalforge/tests -v
git diff --check
git status --short --branch
git diff --stat
git diff --cached --stat
```

For the frontend, use the actual existing package manifest and existing scripts, without installing/deleting dependencies:

```bash
npm test
npm run build
```

Run those from the package directory whose `package.json` actually defines the scripts. Use the project’s TypeScript-check script if present. Record when a check was not run and why. A TypeScript build or frontend test is not a replacement for the Python suite.

After tests:

- Inspect final diffs for accidental changes to evidence status, generated artifacts, package manifests, or `.env.example`.
- Verify no new tracked/staged files appeared accidentally. Do not stage anything.
- Verify the old run outputs, intake archive and claim baselines were not overwritten or deleted.
- Confirm no real model request, live retrieval, review approval, commit or push occurred.

### Final report artifact

Create a new root-level `CODEX_1H_EXECUTION_REPORT.md`. If it already exists, **do not overwrite it**; use a timestamped sibling name. This report is local handoff material and should remain uncommitted unless the user later approves a specific commit.

Include:

1. What you inspected and the initial Git status/branch.
2. The exact file paths you changed and one-sentence reason for each.
3. Eligibility-gate contract as actually implemented and any unresolved schema contract.
4. Provider behavior tested with the mocks; note that no live API call was made.
5. Run bundle status and evidence gaps, with artifact paths.
6. Exact commands for every test/build, pass/fail/skip counts, and baseline-vs-new failures.
7. Original-PDF and source-retrieval status; never claim unavailable verification.
8. A short list of remaining blockers in priority order.
9. Confirmation that no destructive Git operation, evidence approval, live model call, commit or push occurred.
10. What the next agent/user should do next, without inventing a deadline.

Also update `COORDINATION.md` under its current coordination rules with a short log entry: changed files, test results, work left, explicit blocker and handoff. Do not rewrite the full coordination file or remove prior agent history. Respect ownership in the live file; if another agent currently owns a file, log a request instead of editing it.

---

## 9. Coordination: what this run can and cannot automate

The shared goal is for ChatGPT and local Codex to hand off work without the user manually paraphrasing every detail. However, a Markdown task file alone does not connect agent runtimes or share live context.

For this run:

1. Treat `COORDINATION.md` as the repo's coordination log, not a magic live messaging bridge.
2. Create `CODEX_1H_EXECUTION_REPORT.md` as the structured summary of local, uncommitted work. Include exact test results and blockers so the report can be uploaded into the ChatGPT conversation later without the user rewriting it.
3. **Do not commit or push the local working tree just to make ChatGPT see it.** The current ChatGPT GitHub app/connector is read-only, and it sees committed/authorized repository content, not local unsaved or uncommitted VS Code state. Reference: https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt-drease
4. Do not build a custom server, webhook, MCP integration or agent-to-agent bridge during this one-hour task. That is a separate architecture/security task and would distract from the evidence gate.
5. In the report, recommend one next coordination option only after the local tree is safe: (a) user uploads the report for ChatGPT review without committing any code; or (b) later, the user authorizes a specific branch/PR workflow for committed changes; or (c) separately scope an authenticated local MCP/bridge. Do not perform (b) or (c) now.

The goal for this hour is **automated local execution and a clean machine-readable/text handoff**, not a false claim that the two agents are already talking live.

---

## 10. Explicit stop conditions — stop this item if any occur

Stop editing the affected area and report a blocker if:

- the only way forward appears to require resetting, cleaning, stashing, switching branches, pulling or rebasing;
- an existing run/data directory would have to be deleted or replaced;
- the current human-review schema is ambiguous and any implementation would require inventing an approval status;
- an edit requires treating unreviewed or unverified data as approved;
- an important test fails and the cause cannot be isolated within about 5 minutes;
- unrelated concurrent changes mean a shared file cannot be safely edited;
- running a test would require a paid API, credential, remote network call, or writing to a known production data location;
- dependency installation would modify/remove packages or lockfiles and no user approval is available;
- a source, PDF, model result, source URL, date, identity mapping or capacity reconciliation would have to be invented;
- the remaining work starts expanding into a redesign/refactor unrelated to the named objectives.

When one item stops, continue with the next independent safe task. Stop the entire session only if the integrity of the working tree cannot be established or a further command risks irreversible changes.

---

## 11. Out of scope for this one-hour run

Do not attempt to finish all of SignalForge in one sitting. Specifically, do not:

- mark any evidence or claim verified/approved on the user's behalf;
- select a final NTPC discovery merely because the pipeline can produce one;
- retrieve websites or PDFs, scrape sources, perform broad web research, or make a live Gemini/OpenAI request;
- run claim extraction over all 8,241 chunks again or replace any baseline output;
- overwrite any existing run or report directory;
- force capacity figures into agreement;
- fabricate source independence or count republished sources as independent corroboration;
- rebuild the frontend from scratch, add a run API, or create fake data for unavailable API routes;
- add a new model SDK, orchestration framework, custom MCP server, webhook, background daemon, or generic multi-agent platform;
- stage, commit, push, merge or create a PR;
- bulk-ignore, delete, or stage the untracked research data, package folders, dependencies or build artifacts.

These are future tasks only after the evidence gate, sources, approvals and workflow contracts are clear.

---

## 12. Completion criteria

The session is complete when all applicable points are true or explicitly marked blocked:

- [ ] Initial Git state and dirty working tree recorded; no destructive Git operation performed.
- [ ] `AGENTS.md`, `COORDINATION.md`, and README read; ownership respected.
- [ ] Baseline tests recorded before edits.
- [ ] F1 eligibility requires explicit human review and the actual parse/company/payload checks supported by the schemas; unsafe cases have regression tests—or the ambiguous part is left fail-closed and reported.
- [ ] Unreviewed `processed_step6` fragments and extracted claims are not silently F1-eligible.
- [ ] Gemini/OpenAI-compatible configuration is coherent under offline mocks; missing key is safely blocked; no live request occurred.
- [ ] Existing latest run and frontend statuses have been inspected without overwriting run artifacts.
- [ ] The finding remains provisional/Weak unless there is evidence-based support for a change.
- [ ] Full Python suite, focused tests, and relevant frontend/TypeScript/build checks are rerun or their blockers are documented.
- [ ] `git diff --check` passes or its failure is fully reported.
- [ ] `CODEX_1H_EXECUTION_REPORT.md` (or timestamped sibling) exists with exact changes/tests/blockers.
- [ ] `COORDINATION.md` has a concise accurate handoff if ownership permits.
- [ ] No secret exposed, evidence auto-approved, generated run overwritten, files deleted, changes staged, commit created, or push performed.

At the end, give the user **one concise final message** with the report path, test summary, top blocker(s), and whether any decision is actually required. Do not send routine progress chatter during the hour; only interrupt for a real authorization/safety blocker.

---

## Official references

- Gemini OpenAI compatibility API: https://ai.google.dev/gemini-api/docs/openai
- ChatGPT GitHub connection behavior (including read-only repo access): https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt-drease
- VS Code agent permissions and sandboxing overview: https://code.visualstudio.com/docs/agents/run/approvals

**Guiding principle:** move quickly through code, slowly through evidence, and never confuse a candidate, a verified identity, a human review decision, a successful test, and a defensible discovery.
