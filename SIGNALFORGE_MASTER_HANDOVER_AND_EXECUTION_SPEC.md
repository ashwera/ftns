# SIGNALFORGE — MASTER PROJECT HANDOVER, REPOSITORY AUDIT & EXECUTION SPECIFICATION

> **Project:** Find the Next Signal (FTNS) / SignalForge  
> **Document version:** 1.0 — 24 October 2026 (Asia/Kolkata)  
> **Finals deadline stated in contest brief:** 25 October 2026  
> **Repository:** https://github.com/ashwera/ftns  
> **Intended reader:** A new coding/research agent with a fresh checkout of the repository and no access to these chats.  
> **Goal of this document:** Explain the *entire intended product*, establish the difference between **claimed, documented, coded, tested, and demonstrated** work, and give the next agent precise executable tasks and acceptance criteria.

---

## 0. READ THIS FIRST — NON-NEGOTIABLE INSTRUCTIONS FOR THE NEXT AGENT

**This is both a specification and an audit checklist, NOT a statement that everything below already exists.** Start by cloning/pulling the repo and checking the code. The contents of `README.md`, `AGENTS.md`, `CLAUDE.md`, `COORDINATION.md`, `signalforge/PIPELINE_COMPLETION_REPORT.md`, saved manifests and test results are the reference points, not substitutes for executable verification.

**Do not declare the product finished just because `pipeline.py` produces `finding_bundle.json`.** The contest requires a *working autonomous research agent* and **one completed, defensible discovery** for the assigned track/prompt, including public-source links, a documented research process, independent support, chronology, alternative explanations, and a falsification test. As of the repo material inspected for this handover, the demonstrated NTPC case remains **`provisional_hypothesis` / `Weak`**; live F1, live R1, independent source corroboration, and unknown-company generalization have important gaps.

### 0.1 What the next agent MUST do first

1. `git fetch --all --prune`, record branch, HEAD commit, working tree state and open PRs. Determine whether the latest changes on `main` supersede the 18–19 October notes. Do **not** discard changes.
2. Read the root `AGENTS.md`, `CLAUDE.md`, `COORDINATION.md`, `README.md`, and `signalforge/PIPELINE_COMPLETION_REPORT.md`. Respect file ownership. **Never commit/push or overwrite another agent's work without explicit authorization.**
3. Run backend tests, frontend tests, typecheck/build, and inspect current manifests. Record *current results*, not the historical results in this document.
4. Locate original NTPC PDF(s), generated Step 6 evidence, full-archive claim stores, reviewed-input specs, source catalog, run manifests, and the *currently displayed* UI finding. Many large inputs are intentionally not tracked in Git.
5. Produce a discrepancy table: requirement → referenced file/function → current behavior → test/evidence → missing work. Distinguish `implemented`, `partially implemented`, `tested with synthetic fixtures`, `blocked`, `missing`, `not reproducible locally`.
6. Work on the highest-priority blockers below; do not start by creating another decorative landing page.

### 0.2 Status vocabulary (keep these separate)

- **Evidence ingestion status:** parsed/unparsed, issuer identification verified/unverified, human `pending_review`/`approved`/rejected.
- **Claim extraction status:** `extracted` / `ambiguous` / `needs_review` / none. Extracted is **not verified**.
- **Claim verification status:** existing claim rows remain `unverified`; separate verification results carry outcomes/levels.
- **Finding status:** e.g. `provisional_hypothesis`, `no_defensible_signal`, or codebase-supported final states; consult actual schema for exact enum.
- **Evidence strength:** Strong / Moderate / Weak. Never elevate merely because the UI looks complete.
- **Execution provenance:** `real`, `simulated`, `blocked`, `not_executed`. Log it *per stage*, not only per run.
- **Build status:** source exists ≠ code works ≠ tests pass ≠ network/model ran ≠ finding corroborated.

### 0.3 Evidence behind this handover

**[B] Brief:** Attached `Notion-Doc.txt` (the actual contest/problem statement).  
**[C] Chat history:** Available FTNS/SignalForge project conversations through 19 October: contest research plan, Feature 1, Step 6/layer 1, table-aware extraction, NTPC case study, dashboard/design revisions, report/presentation and coding-agent handoff discussion. This record does **not** claim to have independently inspected every attachment from older conversations.  
**[R] GitHub:** Public rendered repo pages inspected on 24 October 2026: [README](https://github.com/ashwera/ftns/blob/main/README.md), [coordination](https://github.com/ashwera/ftns/blob/main/COORDINATION.md), [pipeline completion report](https://github.com/ashwera/ftns/blob/main/signalforge/PIPELINE_COMPLETION_REPORT.md), [Codex review report](https://github.com/ashwera/ftns/blob/main/CODEX_1H_EXECUTION_REPORT.md), [NTPC source register](https://github.com/ashwera/ftns/blob/main/signalforge/data/pipeline_inputs/ntpc_source_register.md), [Samaira source catalog](https://github.com/ashwera/ftns/blob/main/signalforge/data/pipeline_inputs/samaira_catalog.json), and selected source-code pages. **Git could not be cloned into the artifact-writing environment (network DNS disabled), so no fresh local test execution was performed here.** A new agent must independently verify the actual checkout.

**Source-of-truth precedence:** current executable code + current tests + source files + current run provenance > current repository documentation > dated execution reports > chat recollection > this intended-product specification. If documents disagree, log the conflict, do not silently choose one.

---

## 1. EXACT PROBLEM TO SOLVE

The competition asks for an **autonomous financial research agent** that accepts any judge-assigned **NIFTY 50 company within one chosen sector track**, searches public information, and discovers a **non-obvious, evidence-backed financial insight**. The system must not require bespoke hardcoded changes for each company.

**Chosen track: Energy, Power & Renewables.** The brief offers the following three investigation directions:

1. Whether revenue mix shifted toward/away from renewables **earlier or further than the public narrative implies**.
2. Whether **announced capacity additions materially diverge from actually commissioned capacity**.
3. Whether a significant **supplier, customer, or financing relationship** is buried in filings.

These are research hypotheses, not prewritten answers. The agent should screen multiple applicable angles and justify why the strongest one wins; if no evidence-backed material discovery survives falsification, it should refuse to overclaim.

### 1.1 Required per-discovery contract (from the contest brief)

- **Discovery:** one clear, defensible, non-obvious sentence.
- **Why it matters:** three to five company-specific implications.
- **Evidence:** multiple **independent** supporting sources with working links and granular locations.
- **Timeline:** dates on which development/announcement/commissioning/filing occurred and how the pattern evolved.
- **Numbers:** all and only necessary figures; formulas, units, denominator and reporting perimeter visible.
- **Counterargument:** strongest disconfirming evidence/alternative explanation, not a straw man.
- **Falsification condition:** specific future document/number/event that changes the verdict.
- **Evidence strength:** Strong / Moderate / Weak **with explicit reasons and downgrade conditions**.

### 1.2 End-to-end intended user journey

```text
Judge selects an eligible NIFTY 50 energy company
  -> resolve canonical issuer and identifiers (no guesswork)
  -> independently select 2–4 research angles (F1)
  -> build a search/evidence plan (R1)
  -> discover permitted public sources (currently incomplete)
  -> retrieve annual reports, results, exchange filings, regulator/industry/competitor records
  -> preserve snapshots, dates, links, source independence and provenance
  -> extract numerical/document claims incl. difficult tables
  -> resolve issuer, subsidiary/JV, consolidated vs standalone, periods and units
  -> test competing hypotheses + actively seek contradictory sources
  -> perform reproducible Decimal-based calculations and timeline analysis
  -> independently verify the material claims
  -> adjudicate strongest defensible discovery or reject it
  -> persist full run log and finding bundle
  -> interactive research results page with clickable source evidence and reasoning log
  -> export shareable report and demonstration/video, if needed
```

**Autonomy test:** On an unseen company in the chosen track, a user supplies **company identity**, not a handwritten list of seven expected numbers or exact page/chunk references. Curated NTPC fixtures are acceptable for debugging and fallback replay, **not proof of autonomous financial research**.

---

## 2. PRODUCT IDENTITY, PRINCIPLE AND DIFFERENTIATION

**Name:** SignalForge (project/repository: Find the Next Signal).  
**Concise positioning:** *Financial research that exposes the evidence, calculations and competing explanations behind a potential signal.*  
**What it must not be:** a summarizer of one PDF, a document search box, a chatbot with invented citations, a preprogrammed NTPC slide, a dashboard presenting preliminary calculations as investment insight, or an LLM generating conclusions without verification.

A valid finding is not merely “NTPC renewables operate through NGEL.” That relationship is generally known; a previous project review correctly flagged it as **Weak** from a novelty standpoint. A stronger discovery requires a precise and material delta versus the *company's own narrative, timing, commissioned assets, or reported financial exposure*, backed by independent public evidence. Show **what initially looked promising, what failed, and why the chosen conclusion survived**.

### 2.1 Architecture principles

- Sources first; LLM proposes and interprets hypotheses but cannot invent data.
- Decouple extraction, verification, accounting-basis resolution, calculations and narrative generation.
- Every displayed headline/number links backward through formula → input → source document → page/table/passage → URL or snapshot.
- Evidence independence is by **publisher and document lineage**, not by counting URLs. An exchange-hosted copy of NTPC's report and the same NTPC transcript are not independent witnesses.
- Contradictions are first-class objects; never average inconsistent figures.
- A missing source/date/unit/reporting perimeter blocks or downgrades a finding.
- Audit trail and versioned execution log survive page reloads; snapshots/hashes prevent source drift.
- No hidden manual NTPC-only thresholds disguised as generalizable logic.
- Unknown is a valid outcome; avoid forcing a “winning insight.”

---

## 3. REPO INVENTORY — WHAT APPEARS TO EXIST TODAY

**IMPORTANT:** Status column describes the latest *documented or rendered repository* state, not tests executed by the author of this file. Reinspect on checkout.

| Component / approximate location | Documented state | Required audit or unresolved gap |
|---|---|---|
| `signalforge/src/signalforge/dataset_audit.py` | Dataset schema/quality audit and evidence-readiness matrix | Confirm current CLI, readiness levels, and exclusion of anonymous quote CSV |
| `signalforge/src/signalforge/evidence_ingestion.py` | Local CSV/PDF/TXT/MD/HTML normalization; record IDs/warnings | Verify parser statuses, source provenance and review fields |
| `signalforge/src/signalforge/document_text_ingestion.py` | Step 6 page/block-aware CSV-to-evidence parsing | Needs original 30-file archive to reproduce reported 8,241 blocks |
| `signalforge/src/signalforge/claim_extraction.py` | Layer 1 prose fact extraction | Golden cases, precise entity/basis, ambiguous claims, conservative status |
| `signalforge/src/signalforge/table_extraction.py` | Layer 1.5 table extraction and cross-chunk header continuation | Confirm unit fixes, continuation provenance, GC-27 and overconfident claims |
| `signalforge/tests/fixtures/golden_claims/` and `golden_harness.py` | Shared hand-labeled regression suite | Check remaining XFAIL and fixture realism; do not tune only to NTPC |
| `signalforge/src/signalforge/f1_research_angle_selector.py` | F1 selector, strict evidence review gate, prompt, schema & CLI | **Live model selection on approved real evidence not demonstrated** |
| `signalforge/src/signalforge/r1_research_investigator.py` | R1 research **plan** generator | **Not the autonomous investigator**; check approved-evidence parity with F1 |
| `signalforge/src/signalforge/llm_client.py`, `config.py` | OpenAI-SDK Gemini-compatible configurable model client, offline tests, error redaction | No reliable evidence of a live Gemini call; check actual configured model/endpoint now |
| `signalforge/src/signalforge/public_sources.py` | Bounded/robots-aware retrieval of explicitly supplied URLs | **Does not discover research sources independently** |
| `signalforge/src/signalforge/{research_bridge,source_retrieval,source_catalog,claim_verification}.py` | Candidate/run glue, catalog ingestion, source checks, provenance | Check real catalog execution, network use, source independence and snapshots |
| `signalforge/src/signalforge/{signals,findings,pipeline_contract,pipeline}.py` | Four deterministic signal calculator families, ranking/adjudication and finding bundle | Are thresholds calibrated? Are inputs independently verified? Does CLI show real stage states? |
| `signalforge/schemas/*.schema.json` | Schemas for evidence, claim, F1, R1, verification, calculations, finding | Inspect exact required fields/enums before extending, keep old run compatibility |
| `signalforge/data/company_registry.json` | NTPC canonical identity sourced from NSE filing | Registry verification must not be generalized to an anonymous unrelated CSV |
| `signalforge/data/pipeline_inputs/` | NTPC reviewed-input specs, source catalog/register | Analyst-selected roles and handwritten inputs are **not autonomy** |
| `signalforge/data/runs/` | Manifests, bounded runs, artifacts, synthetic company test, sample finding | Some large files absent from clone; compare run IDs/hashes and UI source manifest |
| `signalforge/web/` | React + TypeScript + Vite, evidence-status UI, signal view, frontend tests | Verify that it displays the actual latest supported run with source clickthrough and full investigation |
| `signalforge/web/scripts/sync-demo-data.mjs` | Static frontend bundle synchronizer per coordination notes | Must not sync stale/partial run while showing current/newer verification claims |
| `README.md`, `COORDINATION.md`, `PIPELINE_COMPLETION_REPORT.md` | Core developer information & task ownership | README opening says foundation/no genuine F1; completion report documents *later* pipeline additions — reconcile by code tests |

### 3.1 Concrete existing source-data story

- Repo root: `Quote-Equity-NTPC-EQ-15-04-2026-15-10-2026.csv` — a daily equity-quote export **without an issuer/ticker column**. It must not be asserted to belong to NTPC merely because of the filename. It does **not** establish capacity or revenue-mix claims.
- Noncommitted source archive per README: `signalforge/data/CSV.zip`, containing approximately **30 PDF-to-text CSVs** (9 NTPC annual reports, FY2017–18 to FY2025–26; 21 quarterly/results disclosures); preserve source archive unmodified.
- Generated `signalforge/data/processed_step6/`: **8,241** page/block evidence records reported historically, initially unapproved. A fresh clone may not include them.
- Generated `claims_step1/`, `claims_table_step1/`, `claims_table_xy/` and `runs/*/{prose_only,table_aware}/`: historical outputs, some large and ignored by Git. Claims remain unverified even when structurally extracted.
- 18 Oct pipeline report cited a full-archive run over 8,241 chunks, extracting **4,423 prose-only** and **40,942 table-aware** candidate rows. The imbalance and ambiguous/needs-review counts mean extraction **volume is not quality**. These historical counts are not acceptance metrics for a fresh run.
- The report documented **34 passing golden evaluations and one accepted XFAIL (GC-27)** at that time, plus two unit-attribution issues; later coordination describes fixes. Verify, do not assume either state remains.
- Human review gate in README: F1 admits only schema-valid, parsed, identity-verified, non-empty evidence with `review_status="approved"`, nonempty `reviewed_by`, timezone-aware `reviewed_at`, and `review_note`; payload bounded by 40 records and 250,000 UTF-8 bytes. Pending/invalid records cannot bypass via simulation.

### 3.2 Existing NTPC candidate/result — **not a finished contest discovery**

- Historical finding identifier: `H1_renewable_pipeline_location` (check actual run JSON).
- Finding: NTPC Group's *under-implementation renewable pipeline* appears predominantly within **JV/subsidiary project reporting**, while the parent-owned construction portfolio has a much smaller renewables share.
- Grounding: NTPC FY2024–25 Integrated Annual Report, Section 9.1, printed p. 91; supplementary material in the source register.
- The strongest **directly reported table quantities** are:

| Reporting bucket (as of 31 March 2025) | Renewable under implementation | All technologies under implementation | Renewable share of that bucket |
|---|---:|---:|---:|
| NTPC parent-owned projects | 725 MW | 15,376 MW | `725 / 15376 * 100 = 4.7151404786680541103…%` |
| Projects under JVs and subsidiaries | 13,791 MW | 18,295 MW | `13791 / 18295 * 100 = 75.3812517081169718502…%` |
| Combined | **14,516 MW** | **33,671 MW** | `14516 / 33671 * 100 = 43.1112827061863324522…%` |

**Important alternative denominator:** share of combined *renewable* projects by project bucket: `13791 / 14516 * 100 = 95.0055111600992008818…%` in JV/subsidiary projects; `725 / 14516 * 100 = 4.9944888399007991182…%` parent-owned. **These are not economic ownership percentages and do not describe the revenue mix.**

**Hard correction:** `14.5 GW` is a **rounded group** figure. `14,500 MW − 13,791 MW = 709 MW` is only a **derived residual from a rounded value**. It must **not** be labeled as the directly reported parent-owned renewable amount, substituted for **725 MW**, or used to claim a substantive discrepancy. The exact report table gives `725 + 13,791 = 14,516 MW`. The repo's older calculations and bounded verification reports discuss this pitfall; newer dashboard tests reportedly distinguish it. Test it again.

**Historical status:** `provisional_hypothesis` / `Weak`, no independent regulator confirmation of key inputs, scope ambiguities for other reviewed values, F1 blocked and R1 not executed in the bounded saved run. The 18 October source register says an analyst visually checked the official NTPC PDF's key table; **that is different from the automated pipeline reaching primary-source confirmation or completing self-directed search**.

**Novelty concern:** The fact that renewables are housed in subsidiaries/NGEL is known. The parent/JV split alone may not be sufficiently **non-obvious**. It is a useful audit case and potential lead, not an automatically winning conclusion.

### 3.3 Chronology and docs may disagree — investigate

- `signalforge/PIPELINE_COMPLETION_REPORT.md` (18 Oct, amended 19 Oct) describes the pipeline, offline source checks and newer catalog logic; earlier portions are historical and mention missing frontend integration that newer commits report completed.
- `CODEX_1H_EXECUTION_REPORT.md` records a **bounded** 19 Oct PDF check over seven inputs: six PDF checks, one text-only, all effective outcomes partially supported; no asserted 725 MW, `709 MW` derived, F1 blocked, R1 not executed; dashboard data based on an older run at the time.
- `COORDINATION.md` documents later UI corrections/PRs and stronger denominator labeling, as well as unresolved source independence and R1 review-parity concerns.
- Current `main`, any open PRs, local uncommitted outputs and selected frontend `SOURCE.json` may be different. **Capture a freshness manifest and only narrate the current inspected state.**

---

## 4. THE REAL TARGET ARCHITECTURE (GAP BETWEEN CURRENT AND REQUIRED)

### 4.1 Control plane and data plane

```text
USER/JUDGE INPUT
 company name or verified ticker + one of the contest research prompts
           |
           v
ENTITY RESOLUTION & SECTOR VALIDATION
 registry + official exchange verification, parent/subsidiary/JV mapping
           |
           v
F1: MULTI-ANGLE SELECTOR
 candidate question, priority, materiality, answerability, opposite hypothesis
           |
           v
R1: INVESTIGATION PLANNER
 source queries, periods, metrics, evidence requirements, stop rules
           |
           v
SOURCE DISCOVERY (MISSING CRITICAL AUTONOMY)
 targeted public search: exchange, issuer, regulator, industry, competitors
           |
           v
SAFE RETRIEVAL + SNAPSHOTS
 URLs, provenance metadata, download hashes, document lineage
           |
           v
DOCUMENT PARSE + CLAIM EXTRACTION
 prose, tables, PDFs, ambiguous review queue, citations
           |
           v
VERIFICATION + COMPARABILITY
 exact source passage, issuer, reporting basis, unit, period, status,
 independent groups, negative evidence, contradictions
           |
           v
DETERMINISTIC CALCULATIONS + TIME SERIES
 Decimal formulas, denominators, source-level input tracing
           |
           v
OPPOSING-HYPOTHESIS / SELF-FALSIFICATION PASS
 strongest competing account, disconfirming facts, what would overturn
           |
           v
ADJUDICATION
 rank credible discoveries; reject weak/non-novel or contradictory claims
           |
           v
IMMUTABLE RUN BUNDLE + INTERACTIVE RESULT
 finding, 3–5 implications, chart, timeline, source graph,
 reasoning/decision log, counterargument, falsification, evidence grade
```

**What currently exists in some form:** most of the parsing and offline adjudication/data contracts.  
**What is not demonstrated:** independent web **discovery**, live end-to-end research without handpicked input assertions, production-safe real-time UI integration, live F1/R1 on approved issuer data, and a **completed** Strong/Moderate, independently evidenced non-obvious result.

### 4.2 Split deterministic processes from models

**Deterministic code:** document parsing; token/period/unit normalization; currency and MW/GW conversions; Decimal calculations; provenance hashes; duplicate/independence grouping; schema validation; contradiction checks; eligibility rules; report export.

**LLM/agent reasoning (observable decisions only):** select hypotheses, identify missing evidence, formulate targeted search strings, classify passages with citations, compare plausible explanations, summarize *already verified* numbers, decide next research steps, draft a readable account. Persist rationale/action logs instead of pretending to expose a private internal reasoning trace.

### 4.3 Source-discovery implementation contract (critical missing feature)

Build a provider-agnostic search adapter (exact SDK/provider based on available credentials and repo conventions; no invented API key). Suggested stages:

1. `search(company, topic, domains, date_window)` generates issuer/regulatory/industry queries (not fixed NTPC URLs).
2. `rank_urls` uses issuer/period/document class and source authority; no search-summary-as-fact.
3. `fetch_url` reuses `public_sources.py` and its robots/rate limits/redirect/size constraints, with permitted-source failure logged; if inaccessible, use allowed operator-supplied snapshots and mark provenance correctly.
4. Classify every hit as primary issuer, exchange-hosted issuer copy, government/regulator, industry, competitor, press/analysis; also record `issuer_submitted`, `derived_from`, publisher and publication date.
5. Ingest original documents with page-location references. Preserve PDF page index **and printed page number**, as they often differ.
6. Deduplicate by hash/document lineage and group dependence. Never treat exchange republication of issuer data as a separate confirming source.
7. Loop based on R1 evidence gaps and contradiction coverage until stopping budget or adequacy criteria.

**Acceptance:** on a company **not named in a code fixture**, a successful real search produces `search_queries`, `search_results`, `retrieval_status`, at least one original issuer source and an independently published source (or a clear explicit failure), with working links and document provenance. Provide a no-network fixture replay, **labeled fixture/replay**.

### 4.4 Evidence review vs true autonomy — do not bypass the gate

Current genuine F1 requires human-approved evidence; an unseen-company finals run may not have preapproved records. Choose an explicit, tested policy:

- **Safe minimum:** show live research stages and a provisional evidence-backed case, with approval and final grade honestly constrained; use a separate genuinely reviewed completed run for the core case study.
- **Better system redesign:** introduce a separate `automatically_cross_checked` evidence state with strict deterministic source matching and machine-verification criteria, never forge `reviewed_by` human metadata, and update F1/R1 contract and test suite for this policy. Restrict Strong/Moderate according to *actual source independence*, not approval labels alone.
- **Never:** set `review_status="approved"` in a batch as a workaround; call the model on unverified chunks while labeling them approved; claim autoapproval is human verification; ignore the gate in production.

---

## 5. RESEARCH METHODOLOGY: HOW IT FINDS SIGNALS RATHER THAN SUMMARIES

### 5.1 Candidate-angle screen

At least evaluate the three competition families where data permits, plus one sector-specific variation:

| Research family | Quantitative question | Necessary evidence | Disconfirming possibility |
|---|---|---|---|
| Renewables mix | How do revenue/earnings/capacity shares move vs public claims? | Segment revenue, subsidiary disclosure, commissioned asset portfolio, comparative periods | Change is accounting/reclassification, not economic shift |
| Announced vs commissioned | What was promised/awarded/under construction and what reached COD by date? | Announcement-date targets; project lists; COD exchange filings; cumulative capacity tables; regulator | Announced is planned/awarded, not committed COD; phase/cutoff changed |
| Hidden relationships | Who is economically material as supplier/customer/lender and how concentrated? | Notes to accounts, RPTs, project finance, tender/PPA disclosures, corporate structure | Relationship is disclosed, immaterial or routine arm's-length |
| Holding-company scope | Does parent-only reporting obscure group project mix or cash/ownership exposure? | Standalone/consolidated financials, JV accounts, minority ownership, subsidiary reports | It is a known presentation choice, not a surprise |

For each candidate persist:

```yaml
hypothesis_id: stable-id
prompt_id: energy_capacity_commissioning | energy_mix | relationships
company_identifier: verified ticker/ISIN/company
hypothesis: explicit testable claim
null_or_alternative: strongest ordinary explanation
metric_and_period: exact definition
required_evidence: [primary, independent, negative]
materiality_screen: rule and data availability
novelty_screen: evidence that market narrative did not already make it obvious
prioritization_rationale: auditable short summary
state: proposed | investigated | rejected | provisional | defensible
```

**F1 weights:** Older discussion mentions exploratory weights `30 / 25 / 20 / 17.5 / 7.5`. They are not empirically justified. Inspect actual config; either document their meaning and sensitivity with test outcomes, or replace with transparent gates / a simple unweighted rule. Never claim they are scientifically calibrated.

### 5.2 Falsification-oriented loop

For each promising hypothesis the agent should *intentionally try to kill it*:

1. Retrieve the claimed fact from the original document, not a quoted snippet.
2. Independently compare period/date, denominator, business perimeter and stage (`awarded`, `planned`, `under implementation`, `commissioned/COD`, `commercial operation`, `installed`, `generation`, `revenue`).
3. Search a competing description and latest update; look for a project cancelled, deferred, transferred, reclassified or commissioned after reporting cutoff.
4. Check competitor/industry/regulator context; if independent records unavailable, record that missingness and grade accordingly.
5. Compare company narrative to *same-basis* numbers. Record contradictory sources even when hypothesis survives.
6. Log accepted/rejected reasons, missing data and the next document needed to overturn the conclusion.

### 5.3 Source hierarchy and independence rules

- **Strong primary:** official company annual/quarterly results; original exchange filings; statutory regulator/project COD records — but copies of the *same issuer disclosure* are one group.
- **Potentially independent:** CEA/other regulator's independently collected project-level data, counterparties' own filings, audited JV/subsidiary accounts, separate industry data collected by a non-issuer process. Independence must be demonstrated at **claim level**.
- **Useful but not a second confirmer:** issuer's investor deck quoting the annual report; exchange-hosted mirror; newspaper repeating a press release; an LLM summary.
- **Counterevidence:** authentic documents with materially inconsistent figures that cannot be explained by different reporting dates/perimeters.

Store `independent_group_id` and the derivation/republication graph. **Every material key input** should know the number of independent confirming groups. Strong currently requires at least two independent groups per key input according to pipeline completion notes; verify the deployed rubric.

### 5.4 Financial/comparability rules

- Exact reporting cutoff and fiscal-year basis; project-level COD dates vs announcement dates; standalone vs consolidated vs JV/subsidiary.
- Capacity measures in MW (convert GW as `×1000` with Decimal); generation in MU/GWh distinct from installed capacity; capacity vs pipeline vs target distinct.
- Headline `%` should expose numerator, denominator, label and period. **Do not round intermediate values.** Display at least two decimals; retain exact decimal strings in machine artifacts. Percentages of the *project pipeline* cannot be marketed as revenue, equity ownership or economic exposure.
- `capacity_achievement = commissioned_MW_by_cutoff / announced_expected_MW_by_cutoff`, only when portfolio/stage/time basis matches.
- `capacity_shortfall_MW = announced_COD_due_MW_by_cutoff − actually_commissioned_MW_by_cutoff`, after handling extensions/cancellations and partial COD.
- `mix_delta_pp = measured_new_share_percent − measured_old_share_percent`, percentage points, not percentage growth.
- `slippage_days = actual_COD_date − scheduled_COD_date`, at project level if dates directly supported.
- Use prior period snapshots to prevent hindsight leakage; never compare figures from different cutoffs without a reconciliation table.

---

## 6. NTPC RESEARCH CASE — WHAT TO VERIFY, EXTEND OR REPLACE

### 6.1 What is genuinely known from the repo's source register

The [NTPC source register](https://github.com/ashwera/ftns/blob/main/signalforge/data/pipeline_inputs/ntpc_source_register.md) and [Samaira catalog](https://github.com/ashwera/ftns/blob/main/signalforge/data/pipeline_inputs/samaira_catalog.json) identify:

- FY2024–25 **NTPC Integrated Annual Report**, official NTPC-hosted PDF (`https://ntpc.co.in/sites/default/files/annual-report/complete-reports/Annual%20Report%202024-25_1.pdf`), FY ending 31 March 2025, report submitted 7 August 2025, printed pp. 90–91 and 220 for relevant context.
- **FY25 results call transcript**, 24 May 2025, company-hosted, historical claim of ~33.7 GW under construction incl. ~14.6 GW renewable at that time (different as-of date/basis).
- **21st Annual Analysts & Institutional Investors Meet deck**, submitted 18 August 2025, uses 30 June 2025 construction figures and broader “visible RE pipeline” terminology; not directly comparable to 31 March 2025.
- Official **CEA quarterly under-construction RE index** and installed-capacity reporting index; an independent source family **was located** but the underlying company-wise/project-level table was **not validated** in the repo review. Do not claim the CEA corroborates any NTPC pipeline value yet.
- Documented internal FY25 table: 725 MW parent RE and 13,791 MW JV/subsidiary RE; 15,376 MW and 18,295 MW respective all-technology denominators.

**Do not silently reinterpret the source register's human/AI-assisted document inspection as fully automated source verification.** Its stated source checks, hash availability and the pipeline's `verification_level` need separate examination.

### 6.2 Recommended route to the **required one completed discovery**

The best contest-aligned **research target** is prompt **#2 — announced additions vs commissioned capacity**. Existing NTPC pipeline-scope work is useful as a starting map of projects, not the answer. The next agent must choose the final headline *only after calculating a time-bounded announcement-to-COD delta* and finding evidence beyond NTPC's repeated disclosures.

**Working question (not an asserted conclusion):** “Across NTPC's energy capacity expansion, did disclosed project commissioning lag/reclassify the previously announced milestones materially, and did group-level updates obscure which assets actually became operational by the stated date?”

**Mandatory investigation actions:**

1. Build project-level/technology-level matrix: project name, owner/SPV/JV, technology, expected MW, announced date, committed/planned COD date, amended schedule, actual COD date, commissioned MW, canceled/deferred MW, evidence links.
2. Search official NTPC/exchange announcements for commissioning declarations, annual reports, recent quarterly results and investor presentations (at least two reporting cutoffs); **pull actual COD events**, not only pipeline tables.
3. Inspect regulator/independent project commissioning records and/or counterparty project-level statements. Verify *specific matched project or capacity claims*, not vague industry totals.
4. Normalize matched scope: same project, same stage, same date, same ownership/perimeter. Exclude targets due after cutoff. Distinguish “announced,” “awarded,” “contracted,” “under construction,” “synchronized,” “COD,” and “commissioned.”
5. Quantify mismatch, timing and possible financial/materiality implications with exact inputs and links. Reject the mismatch hypothesis if it is explained by disclosed schedule revisions or portfolio boundaries.
6. Search for a stronger alternative and a genuine disconfirming source. Include both in final result and log decision rationale.
7. If no defensible new #2 insight emerges, transparently rank #1/#3 alternatives and use the strongest **verified and non-obvious** case. Do not manufacture an insight solely to meet a demo requirement.

**Known candidate sources from earlier chats** (presence in older conversations is not proof they are in current checkout): NTPC FY2024–25/FY2025–26 annual reports, FY26 and FY27 quarterly/results filings, quarterly exchange disclosures, 24 Mar 2025 Kerandari commercial-operation declaration, Ramagundam COD announcement 29 May 2025, NGEL commissioning exchange filing 1 Oct 2026, and other October 2026 filings. Verify exact file, project scope and published dates before use.

### 6.3 Alternative case: project perimeter / renewables in JVs and subsidiaries

If this case remains the primary demo candidate, upgrade it beyond the basic known-NGEL observation by testing the **economic/commissioned capacity implications**, exact period cutoffs, group presentation and standalone vs consolidated ratios. Explain clearly that the exact table evidence is issuer-only; find genuinely independent factual verification where possible. The formal counterargument is: *renewable projects in NGEL/JVs are explicitly disclosed and expected; no economic understatement follows from this organizational structure, and pipeline MW is not consolidated equity ownership or booked revenue.* That alternative may defeat claims of non-obviousness. **Keep Weak if it does.**

### 6.4 Template for final discovery record (fill with actual run output)

```yaml
company: NTPC Limited
prompt: '<exact contest prompt selected>'
run_id: '<actual immutable run directory>'
state: '<from actual adjudication schema>'
evidence_strength: '<Strong | Moderate | Weak>'
one_sentence_discovery: '<ONLY after verifying; do not prefill conclusion>'
why_it_matters: [implication_1, implication_2, implication_3]
key_numbers:
  - metric: '<exact label + scope + cutoff>'
    decimal_value: '<exact, unrounded intermediate>'
    unit: MW
    formula: '<expression>'
    source_input_ids: ['<ids>']
timeline:
  - date: '<ISO date>'
    event: '<announcement / schedule revision / COD / results disclosure>'
    source_ids: ['<ids>']
supporting_sources:
  - url: '<real direct link>'
    publisher: '<verified>'
    document_family: '<lineage group>'
    page_or_table: '<specific locator>'
    verified_claim_ids: ['<ids>']
contradictory_evidence: []
strongest_counterargument: '<real alternative and evidence>'
falsification_condition: '<specific future document and threshold or fact>'
evidence_strength_reason: '<source independence, gaps, and downgrades>'
research_decision_log: '<logged decisions and rejected angles, not invented private thoughts>'
limitations: []
provenance: '<real/simulated/blocked per stage>'
```

Do not claim the displayed example above is a measured output: it is the *target contract*.

---

## 7. WHAT THE LIVE DEMO MUST SHOW — EXACT SEQUENCE

**Required:** one working research agent/application; one actual completed discovery using the chosen contest prompt; the chain of primary and independent evidence; transparent research decisions; a serious counterargument/alternative; a falsification condition; strength and limitations. **These elements must appear *after the result* in the interactive result page**, not be confined to a narrated pitch or hidden export.

### 7.1 Primary flow / screen order

**A. Research launch (working application)**

- Input company and confirm verified NIFTY 50/sector eligibility; show exact selected prompt/question.
- A prominent **Start Research** action triggers actual backend work, not a slide transition.
- Real-time stage indicators: entity resolved, candidate angles, research plan, source search, source fetch, claims extracted, cross-check, calculations, opposition pass, adjudication. Each shows `real / blocked / simulated / not_executed` and counts/time; no fake “agent is thinking” filler.
- Show 2–4 candidate angles and **why the selected investigation outranked alternatives**. Keep a machine-readable `candidate_decisions.json`/equivalent.

**B. Result hero — first evidence-backed answer**

- One-sentence discovery, reporting cutoff, company and chosen prompt.
- Verdict: Strong/Moderate/Weak with specific reasons and status; “Provisional hypothesis” must be plainly visible if applicable.
- 3–5 why-it-matters bullets.
- 2–4 properly scoped key numbers with unit, period, denominator, source icons and exact formula on click.
- Two substantive charts max in hero area; no decorative pseudo-quant plots.

**C. How the agent reached it — visible immediately after the result**

- **Investigation trail / research decision timeline:** research questions, initial lead, evidence sought, sources retrieved/rejected, alternative candidate considered, cross-check result, numeric operations, final selection reason.
- Event log grouped by logical research stages, each backed by stored machine-readable artifacts, with timestamp and `real/simulated/blocked` badges where appropriate.
- Show the **rejected runner-up** and reason (insufficient evidence, non-novel, contradicted or immaterial).
- This is an auditable *summary of reasoning decisions*, not a fabricated word-for-word LLM thought stream.

**D. Evidence trail — mandatory clickable proof**

- Interactive chain: **Discovery → material claim → computation/input → Annual Report → Quarterly Results → Exchange Filing → Independent Industry/Regulator → Competitor/Counterparty** as applicable.
- Every evidence card: publisher, title, publication date, reporting as-of date, source type, independent-group ID, extract, page/table/sentence, verified/unverified state, link to original doc and stored snapshot hash.
- Click a key number → side panel showing formula inputs → click input → highlight original passage/table row. For PDFs, open original file at page if supported or show a verified citation side-by-side; never claim line-level highlighting if unavailable.
- Identify **same-issuer echoes** visibly; distinguish corroboration from republishing.
- Document 404/login/robots denial transparently; use permitted archived snapshot only if provenance recorded.

**E. Numbers + chart + timeline**

- For capacity question, chart scheduled/announced vs actual COD by matched period/project, not pipeline vs capacity on mismatched bases.
- Time axis holds *announcement, deadline, extension, project COD and report publication* as distinct event types.
- Show formula traces and accounting-basis warnings (e.g., parent vs group vs JV). Unrounded machine calculations and at least 2 decimal places in rendered numerical labels.

**F. Counterargument (visible, not just generated prose)**

- Exact strongest alternative interpretation, why it could explain the apparent signal, and relevant supporting documents.
- Separate accepted rebuttal vs still-open question. If not refuted, downgrade confidence or reject.
- Allow user to click opposing evidence, see its passage and compare both sources.

**G. Falsification + confidence**

- “What would change our mind?” with a precise document/next event/threshold. Example structure: if a later regulator COD record and updated issuer project list establish the allegedly delayed MW had already achieved COD before the selected cutoff, the gap claim fails. Exact thresholds should derive from verified finding, not this illustration.
- Strength breakdown: independent groups, verified key inputs, contradictory claims, missing sources, date/basis resolution, novelty and materiality. Surface `downgrade_reasons` from backend.

**H. Full reproducibility**

- Research run ID, run timestamp, version/commit, selected company, prompt ID, actual model name, tool/network usage, source manifest, result schema version, data status. Download real JSON/Markdown/PDF report if implemented, clearly labeled.
- “Show provenance” opens artifact or concise log. No “100% proven” label.

### 7.2 Screen blueprint

```text
+----------------------------------------------------------------------------------+
| SignalForge     Company [NTPC Limited v]    Prompt [Capacity vs COD v] [Research] |
+----------------------------------------------------------------------------------+
| RESEARCH RUN: 2026-...     Source count | verified inputs | stage status         |
| Angle A selected: capacity commissioning gap                                  ... |
+----------------------------------------------------------------------------------+
| DISCOVERY [status / evidence strength]                                            |
| One precise sentence, scoped to reporting dates.                                 |
| Why it matters (3–5)           Key number #1   Key number #2   Key number #3       |
| Matched projects / COD chart          Event/timeline graph                       |
+----------------------------------------------------------------------------------+
| HOW THE AGENT REACHED IT                                                         |
| Questions -> Candidates -> Search -> Checks -> Opposing view -> Verdict           |
| [inspect each step]   [rejected alternatives]                                    |
+----------------------------------------------------------------------------------+
| EVIDENCE EXPLORER                      | ORIGINAL SOURCE DETAIL                   |
| 01 annual report                      | PDF/source URL, date, page/table/quote   |
| 02 exchange filing                    | value/period/entity/basis verification   |
| 03 independent regulator              | snapshot hash and lineage group         |
| 04 counterparty/competitor            | independent vs same-issuer               |
+----------------------------------------------------------------------------------+
| COUNTERARGUMENT / COMPETING EXPLANATION [click opposing source]                   |
| FALSIFICATION CONDITION / WHAT COULD INVALIDATE                                  |
| STRENGTH BREAKDOWN / LIMITATIONS / REPRODUCIBILITY                               |
+----------------------------------------------------------------------------------+
```

### 7.3 UI/art direction (from prior design discussions)

The team repeatedly rejected generic AI-generated aesthetics. Follow the later preference: **royal blue** as accent, understated neutral/charcoal grey, white/off-white backgrounds, **Times New Roman or similarly deliberate editorial serif headings**, square/sharp-corner cards, no gratuitous rounded pills, glassmorphism, neon glows, pastel gradients, floating orbs or decorative chat bubbles. Dense information should still breathe. Finance/research desk aesthetic; disciplined grids, typographic hierarchy, thin dividers and accurate labelled charts. Keep branding modest. Source badges are functional, not confetti.

For any silent demo/product video requested separately: polished cuts, real captured app UI, animated data/formula transitions only when grounded, careful relevant audio/music, **no voiceover**, no speculative screenshots, no simulated research passed off as live.

---

## 8. OUTPUT DATA CONTRACTS — REQUIRED FOR AGENT / UI / EXPORT

**Do not blindly replace existing `finding.schema.json`; inspect and make backward-compatible extensions.** The following is a **proposed minimum semantic contract**; map these fields onto the actual schemas and maintain adapters if current names differ.

### 8.1 Run manifest

```json
{
  "run_id": "<unique persisted run id>",
  "git_commit": "<commit hash>",
  "company": {"canonical_name": "<verified>", "ticker": "<verified or null>", "isin": "<verified or null>"},
  "track": "Energy, Power & Renewables",
  "assigned_prompt_id": "energy_capacity_commissioning",
  "started_at": "<timezone aware UTC/ISO timestamp>",
  "finished_at": "<timezone aware UTC/ISO timestamp>",
  "model": {"provider": "<actual>", "model": "<actual or null>"},
  "stages": [{"name": "source_discovery", "execution": "real", "inputs": [], "outputs": [], "error": null}],
  "source_manifest_path": "<relative path>",
  "finding_bundle_path": "<relative path>",
  "reproducibility_notes": []
}
```

Placeholders are **not** real data, and the sample `execution=real` above is illustrative only.

### 8.2 Source record

`source_id`, canonical issuer, URL/local snapshot, publisher, document title/class, issuer submission vs independent reporter, published date, reporting/as-of date, retrieved date, SHA-256 of snapshot, source family/document lineage, redirects, retrieval status, license/robots outcome, page mapping. Original PDFs or allowed snapshots should be immutable.

### 8.3 Evidence/claim/verification trail

Each material claim: `claim_id`, `evidence_id`, `source_id`, verbatim supporting excerpt, page/table/row/column, entity/parent/JV, metric, `Decimal`-serializable exact string value, unit, time period and status, accounting/reporting basis, extraction state, review state, verification results for every check, independence group and contradiction refs. **Never mark a claim verified because the regex found a value.**

### 8.4 Calculation trail

`calculation_id`, precise expression, numerator/denominator roles, time and perimeter compatibility assertion, exact operands and results (strings), display-format rules, bounds/tolerance where appropriate, source claim IDs. Conflict or missing key input -> refuse calculation or mark invalid; never substitute a rounded inferred value for direct tabular data.

### 8.5 Investigation log (the requested “reasoning process”)

Persist chronological **action/decision summaries**, not hidden chain-of-thought text:

```json
{
  "step_id": "step-012",
  "stage": "counterevidence_search",
  "timestamp": "<ISO>",
  "question": "Could the apparent capacity gap be a reporting-period mismatch?",
  "tool_or_method": "<actual search/retrieval/compare function>",
  "action_summary": "<factual action carried out>",
  "input_artifact_ids": [],
  "output_artifact_ids": [],
  "decision": "retained | modified | rejected | unresolved",
  "decision_basis": "<brief, citation-linked, verifiable rationale>",
  "execution": "real | simulated | blocked | not_executed"
}
```

No fictional searches, dates or model calls. UI should render this log under the result.

### 8.6 Finding/report contract

Adapt existing `finding_bundle.json` to supply the contest's eight content fields, plus `supporting_evidence`, `contradictory_evidence`, `alternative_explanations`, `falsification_conditions`, `calculation_traces`, `source_graph`, `timeline`, `investigation_log`, `missing_evidence`, `limitations`, `decision_log`, `audit_trail`, `downgrade_reasons`, `stage_provenance`, `data_freshness`, `company`, `prompt`, and `run_id`. UI tests must ensure these are not silently omitted.

---

## 9. EXECUTION PLAN — PRIORITIZED, TESTABLE WORK PACKAGES

Statuses here are **tasks to be checked/executed**, not claims that someone has already made the change. Given the 25 Oct stated finals date, prioritize one honest, reproducible source-linked discovery and functional results page over expansive speculative functionality.

### P0 — Baseline, ownership, evidence availability (do first)

**Actions:** inspect current repo/branches/PRs; read coordination; run tests; inventory artifacts; capture git SHA; compare frontend `SOURCE.json` to newest genuine run; verify all original PDFs/hashes; find missing `CSV.zip`; list missing credentials without printing keys. Obtain older local files from team if necessary.

**Deliverable:** `signalforge/data/runs/<audit_run>/REPO_BASELINE.md` or project-appropriate tracked audit (without private files); table of code, tests, artifacts, stage status, mismatches.

**Pass:** every subsequent task anchored to existing file/functions, working tree preserved, no falsely claimed live services.

### P1 — Finish/reproduce the NTPC fact base and choose *one* real case

**Actions:** use official annual PDF plus source catalog; verify printed p. 91 row values and source metadata; inspect direct and derived MW numerators; find source-backed COD/announcement documents and independent facts; compare candidate #2 vs #1; select only if material + non-obvious + supportable. Run actual permitted source checks; save snapshots/hashes. If original PDF unavailable, block and document — do not backfill values from an uncited prompt.

**Acceptance:** all decisive numeric operands found in original sources, company/date/perimeter resolved, at least one falsification/alternative document considered, source lineage documented, findings never stronger than effective verification supports.

### P2 — Genuinely autonomous source discovery

**Actions:** implement provider-agnostic search, URL ranking, safe retrieval, query log, explicit budget/fallback; no hardcoded NTPC project numbers. Reuse current retrieval/caching/catalog code. Integrate output with R1 evidence gaps and `pipeline.py` rather than developing a disconnected “research chat”.

**Acceptance:** one command/company input discovers and ingests permitted authoritative documents; offline fixture tests plus one logged genuine network run; same code exercised on a second issuer. No source count padding by duplicate copies.

### P3 — F1/R1 live model + evidence-policy integration

**Actions:** review current F1 gate; have a human legitimately approve source excerpts where needed or implement a *distinct* stricter machine-cross-check policy; R1 must use exactly eligible claim IDs. Configure model provider via environment using current code; run live candidate selection with real eligible documents; create actual R1 plan; connect plan to discovery loop. Never expose API key or stack trace secrets.

**Acceptance:** saved request metadata (excluding secrets), validated structured F1 and R1 outputs, model executed `real`, provenance IDs correlate to approved/eligible evidence, rejected cases block before SDK call. If no live model credentials, mark blocked and demo only honest deterministic research; never label a fixture as live.

### P4 — Claim verification, contradiction and arithmetic hardening

**Actions:** verify original publication cutoff, parent vs JV basis, exact MWs; test 725 vs 709 regression; resolve wrong-unit cases, GC-27, table context and source passage location; group independent sources and handle contradictory key claims. Re-run golden and real-PDF checks.

**Acceptance:** no source-free key number; correct denominator labels; direct 725 MW cannot be replaced by residual 709 MW; contradictory key inputs reject/downgrade as rubric specifies; separate reporting-date documents not treated as numerical contradictions; negative tests pass.

### P5 — End-to-end final output including real research *decisions*

**Actions:** wire F1 -> R1 -> source discovery/retrieval -> claim checks -> timeline/Decimal calculations -> alternative search -> verdict -> versioned bundle; persist an investigation/action log and rejected hypothesis list. Keep current `finding.schema.json` backward compatible.

**Acceptance:** reproducible `run_id`; all content fields; all key inputs trace to public sources; Strong/Moderate only if evidence justifies; honest no-finding path; tested rerun doesn't depend on archived manually inserted conclusions.

### P6 — Final UX and interactive forensic drill-down

**Actions:** build result-first layout above; show evidence explorer and per-step reasoning log directly after result; real source links/passage; visual comparison and timeline; source independence, counterargument, falsification, grade and downgrades. Integrate only verified current run, capture UI screenshots and verify browser-level interactions.

**Acceptance:** for every hero number, a judge can click to see formula/source; for counterargument, judge can click to opposing document; stale SOURCE.json cannot show a newer check; missing URLs are indicated, not fabricated; no broken/tiny text; official design consistent.

### P7 — Generalization and adversarial testing

**Actions:** run an actual **second company** in the eligible track using same code, separate config/registry from verified public identity. Power Grid is an existing no-data test (not a real successful proof). Choose any genuinely eligible issuer with accessible disclosures; confirm NIFTY 50 constituency as of applicable date. Compare across company using metrics relevant to its operations; capacity metrics cannot be blindly applied to every business model.

**Acceptance:** real second issuer produces a grounded finding or honest no-defensible-signal output using unchanged implementation; capture retrieval/provenance; never pass a synthetic company as real. Document track coverage limitations.

### P8 — Rehearsal and submission artifacts

**Actions:** run clean install; rerun tests; real case live execution or clearly labeled real-run replay; inspect every click; attach source register, markdown report, final deck/demo clips as separate outputs if needed; cross-check every factual screenshot with `run_id` and source.

**Acceptance:** cold-start on a fresh machine, no creds in repo, concise judge-ready walkthrough, demonstrable agency, evidence, reasoning, alternative and falsification; export supported by actual app artifacts, no post-hoc fabricated source slide.

### 9.1 Minimal “finals-ready” cut (if time limited)

**Must ship:** a truthful completed case with multiple source lineages where available, functional research run/agent action trace, attributable formulas, visible counterargument/falsification, clear status, source-click interface and green tests.  
**Can defer:** multi-tenant auth, elaborate search breadth, fancy cinematic video, large multi-company benchmark, network deployment, extra color themes, decorative dashboards.  
**Cannot defer while claiming compliance:** lack of a real research run, missing links, one-source “independent” evidence, fabricated Strong score, absent reasoning/alternative/falsification sections, or a pure pre-canned NTPC answer.

---

## 10. EXACT REPOSITORY CHECK / RUN COMMANDS

**Commands below are repository-documented starting points; first run `--help` and inspect the actual current implementation.** Execute from repo root unless noted. Some commands require excluded source archive, approved data or models.

```bash
# Git baseline
pwd
git remote -v
git fetch --all --prune
git status --short --branch
git rev-parse HEAD
cat AGENTS.md CLAUDE.md
sed -n '1,260p' README.md
sed -n '1,320p' COORDINATION.md

# Python environment
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r signalforge/requirements.txt
export PYTHONPATH=signalforge/src

# Baseline offline backend regression
python3 -m unittest discover -s signalforge/tests -v

# Frontend verification
cd signalforge/web
npm install
npm test -- --run
npx tsc -b --pretty false
npm run build
npm run dev
# Open the actual printed localhost Vite URL and inspect the result interactively.
cd ../..

# Inspect the existing anonymous equity CSV (NOT operational evidence)
python3 -m signalforge.f1_research_angle_selector --inspect
python3 -m signalforge.dataset_audit --csv-path \
  "Quote-Equity-NTPC-EQ-15-04-2026-15-10-2026.csv"

# Regenerate Step 6 ONLY if the source archive is provided
unzip signalforge/data/CSV.zip -x '__MACOSX/*' '*.DS_Store' -d signalforge/data/intake
python3 -m signalforge.document_text_ingestion \
  --input-dir signalforge/data/intake/CSV \
  --output-dir signalforge/data/processed_step6

# Extraction commands; choose fresh output paths or use --overwrite knowingly
python3 -m signalforge.claim_extraction --help
python3 -m signalforge.table_extraction --help
python3 -m signalforge.archive_evaluation \
  --run-dir signalforge/data/runs/<NEW_UNIQUE_ARCHIVE_RUN_ID>

# F1 on legitimately approved NTPC evidence, with credentials configured separately
python3 -m signalforge.f1_research_angle_selector --company NTPC

# Existing R1 is plan-only and requires real F1 output
python3 -m signalforge.r1_research_investigator \
  --f1 signalforge/outputs/f1_output.json \
  --output signalforge/outputs/r1_plan.json

# Existing reviewed NTPC pipeline slice (claims must exist)
python3 -m signalforge.pipeline \
  --company "NTPC Limited" \
  --claims signalforge/data/runs/<REAL_ARCHIVE_RUN>/table_aware/claims.jsonl \
  --inputs signalforge/data/pipeline_inputs/ntpc_renewable_pipeline_reviewed_inputs.json \
  --catalog signalforge/data/pipeline_inputs/samaira_catalog.json \
  --run-dir signalforge/data/runs/<NEW_UNIQUE_RESULT_RUN_ID>

# Network retrieval is opt-in in documented pipeline code. Include --allow-network
# only after verifying intended sources, permissions and robots compliance.
# --simulate-llm explicitly marks model stages as SIMULATED, never live.
```

**Current static UI integration check:** locate `signalforge/web/public/data/finding/SOURCE.json`, `finding_bundle.json`, and `signalforge/web/scripts/sync-demo-data.mjs`; compare `run_id`, source SHA, `stage_provenance`, main story and verified inputs to the actual latest chosen run. Run the sync script only after reviewing its CLI contract and inputs. A source bundle from `run_20261018_full_e2e_ntpc_02` is not evidence that the newer `run_offline_pdf_verify_context_fix_20261019` was presented.

---

## 11. REQUIRED AUTOMATED TEST MATRIX

| ID | Scenario / failure case | Required result |
|---|---|---|
| T01 | Anonymous CSV filename contains NTPC, rows have no issuer ID | No company join; F1 blocked without other eligible verified evidence |
| T02 | Pending, empty, malformed or oversized evidence passed to F1 | Block before model call; meaningful error; no secret leakage |
| T03 | R1 receives approved + pending IDs | Only approved/eligible IDs enter live plan, or explicit validation failure |
| T04 | Cross-chunk table header appears on neighboring page | Header provenance retained; no fabricated unit/period; ambiguity preserved |
| T05 | Table value labeled MUs or ₹/share adjacent to INR crore heading | Correct unit attribution or needs-review; never confidently apply crore |
| T06 | NTPC exact 14,516 MW, 13,791 MW JV RE, 725 MW parent RE | Parent is **725 direct**; 709 residual not used as parent numerator |
| T07 | Denominator alternatives 15,376 / 18,295 / 14,516 MW | Correct scope-specific shares; cannot silently compare incompatible bases |
| T08 | FY25 report vs May/Aug 2025 presentation with different cutoffs | Timeline/scope difference, no false contradiction |
| T09 | Report and exchange mirror same issuer disclosure | Exactly one independent lineage group |
| T10 | Regulator record independently confirms exact matched project | Independent group credited *only* after passage-level verification |
| T11 | Regulator contradicts a material input on matched scope | Finding downgraded/rejected; counterevidence preserved |
| T12 | Link unavailable / robots denial / hash mismatch | Explicit unavailable/failed check; no invented citation or confirmation |
| T13 | No real model credentials | `blocked`, not `real` or `simulated` disguised as real |
| T14 | Synthetic/fixture research run | Mark synthetic/replay at source and UI level |
| T15 | Unseen-company identity only, without handwritten NTPC roles | Real search/planning or defensible no-data result; no NTPC-specific crash |
| T16 | Every final chart/number clicked | Leads to exact formula, inputs and source passage/URL |
| T17 | Counterargument and falsification fields missing from bundle | Schema/UI test fails or displays explicit unavailable state, not silent omission |
| T18 | UI reads run A but narrates newer run B verification | Fail freshness check; show correct run A or intentionally sync B |
| T19 | Two independent confirmations but unresolved key unit/period | No Strong promotion until comparable key fact is resolved |
| T20 | A candidate is obviously known from existing public narrative | Novelty screen flags; evidence strength and selection reflect limitation |
| T21 | Run is interrupted after retrieval | Partial artifacts and stage status retained; safe resume or clear terminal block |
| T22 | Repeated run on identical immutable snapshots | Deterministic financial results and trace IDs (allow run metadata/time to differ) |

### 11.1 Browser-level acceptance walk

On a fresh page, a reviewer should be able to perform without help: select company/prompt → trigger run or open **clearly labeled real prior run** → inspect selected vs rejected research angles → read completed/provisional discovery → click each of its three main values → inspect original passages → inspect independent-source provenance → open timeline event → read strongest competing explanation and its source → read falsification condition → inspect run/version and execution states. If any step requires a verbal promise (“we can build this later”), it does not satisfy this acceptance criterion.

---

## 12. INTEGRATION / CODE OWNERSHIP RULES

The existing root `AGENTS.md`, `CLAUDE.md` and `COORDINATION.md` define a shared coding workflow between Claude Code and Codex. Treat `COORDINATION.md` as an active ownership board, not as historical decoration. At task start, claim files and record dependencies; avoid modifying owned files; ask through its Requests/Open Questions sections if another agent owns a blocker. Execute regressions before closing an item. Only commit/push when authorized. Preserve ignored generated outputs and private keys.

**Historical work allocation from chat:** Samaira gathered datasets, NTPC filings and source materials; Ashwera/Claude concentrated on extraction, table/prose and pipeline engineering; Codex contributed source identity/retrieval gating, tests, verification and UI integrations; other teammates worked on contest research/pitch. Assign **new tasks** by current availability, not by assuming the old owner remains active.

**Recommended work split today:**

| Workstream | Scope | Dependency | Definition of done |
|---|---|---|---|
| Research/evidence | NTPC announcement/COD matching, original PDF/source lineage, regulator or independent corroboration | Data access | A cited, falsification-tested final candidate |
| Backend/agent | source discovery + live F1/R1 + input verification + structured reasoning log | Repo ownership and credentials | End-to-end run manifest, offline and live tests |
| Frontend | result-first source explorer, timeline, counterargument, falsification, freshness | Stable finding bundle | Browser walkthrough and tests |
| QA/review | cross-company, regressions, no-overclaim audit, final rehearsal | All streams | Reproducible run and discrepancy log |

---

## 13. CURRENT BLOCKER REGISTER (UNRESOLVED UNTIL PROVED OTHERWISE)

| Severity | Blocker | Why it matters | Proof needed to close |
|---|---|---|---|
| **P0** | No demonstrated completed, independently evidenced, non-obvious discovery | Central contest deliverable | Final result with exact sources, alternatives, falsification, honest Strong/Moderate *if earned* |
| **P0** | Agent lacks proven autonomous live source **discovery** | Judge assigns unseen company | Live search/retrieval log on at least one not-prewired company |
| **P0** | NTPC demo story may be known/Weak | Novelty/grade risk | Market-narrative benchmark or shift to a genuinely material COD/revenue insight |
| **P0** | Live F1/R1 not evidenced in last bounded run | Agent layer under-demonstrated | Genuine model calls on permissible eligible evidence, stored schema-valid outputs |
| **P0** | Pending human evidence approvals and potential R1 parity gap | Safety/integrity of evidence | Reviewed records or explicitly redesigned separate automatic-verification policy; R1 tests |
| **P0** | Independent claim-level source corroboration missing | Source-count ≠ independent evidence | Valid matched regulator/counterparty passage(s); independence group recorded |
| **P1** | Original source archive and generated large artifacts may not exist in clone | Reproducibility | Source manifest and artifact hashes, regenerate or obtain legally shared archive |
| **P1** | Web demo may show older run than newest verification | Misrepresentation | `SOURCE.json`/bundle/latest chosen run matched and tested |
| **P1** | Parent vs JV/rounded residual/units issues | Quantitative trust | Correct denominator and exact table cases in automated tests |
| **P1** | Research rationale, rejected alternatives, actual counterevidence and falsification may not be exposed prominently | Explicit judge requirements | All rendered *after discovery* with linkable artifacts |
| **P1** | Generality only synthetic/no-data test documented | Finals unseen company | Real second issuer baseline without code changes |
| **P2** | F1 exploratory weights not calibrated | Credibility | Sensitivity study or transparent non-calibrated rule |
| **P2** | No reliable browser-level visual validation noted | User-facing demo quality | Browser interaction test and reviewed screenshot walkthrough |

---

## 14. DEMO STORYBOARD — 3–5 MINUTES WITHOUT MISREPRESENTING WORK

**Opening (15s):** Energy, Power & Renewables prompt appears. Select company. “Researching public filings, not answering from memorized text.” Show authentic input.

**Agent operation (35–45s):** verified issuer; several angles considered; research plan; live/query log; source retrieval, extraction; evidence gates; candidate ranking. Use a **real saved run** only if replay clearly labeled and original run genuinely executed. Show blocked stages, if any, in their true state.

**The finding (30s):** reveal one sentence, 3 material numbers and one compelling period-correct chart. Status and grade unmissable.

**Proof (60s):** click three specific claims, show annual filing + quarterly + exchange + genuinely independent government/counterparty document as available. Demonstrate source lineage, exact units and formula. Do not imply all sources are independent if they are issuer copies.

**Research process (40s):** display decision log, selected and rejected hypotheses, why agent searched for additional evidence, and the contradiction check. This is a documented audit trail, **not a staged internal monologue**.

**Opposition and falsification (30–40s):** show a substantive explanation that could make the discovery disappear, the contradictory/corrective source, and explicit future evidence that would change the verdict.

**Finals resilience (20–30s):** choose another eligible track company; show identical generic architecture, verified identification, source search and an honest result/no-data reason. Close with evidence export/run ID.

**Important:** If the claim remains Weak, title it “provisional hypothesis,” explain why, and do not market it as a completed evidential victory. Either obtain the missing real corroboration or switch the completed case to a stronger supported one.

---

## 15. AGENT EXIT CRITERIA / FINAL CHECKLIST

### Functional

- [ ] Reproduction instructions work from a clean checkout with source archive/snapshots provided.
- [ ] Current backend and frontend checks pass, with exact counts logged.
- [ ] F1 actually selects/ranks candidate angles from real eligible issuer-specific evidence, or honest blocker shown.
- [ ] R1 actually produces a structured plan with correctly gated source IDs; investigation loop genuinely follows it.
- [ ] Public sources discovered and retrieved without manually scripting the whole company-specific evidence set.
- [ ] Run manifest distinguishes every real, simulated, blocked and not-executed stage.
- [ ] Source provenance, duplicates, links, hashes and independence graph are stored.
- [ ] A second real issuer is tried without rewriting the implementation.

### Discovery integrity

- [ ] One assigned prompt and one clear non-obvious case (if the evidence supports it).
- [ ] Material claims linked to primary source passages and multiple truly independent sources.
- [ ] Dates, unit, denominator and group/parent/JV basis reconciled.
- [ ] Key figures reproduce with exact formulas and no premature rounding.
- [ ] Meaningful opposing explanation and actual negative search/evidence included.
- [ ] Falsification condition states precisely what future fact changes the assessment.
- [ ] Strong/Moderate/Weak grading explains source counts, conflicts and missing evidence; no automatic inflation.
- [ ] `709 MW` residual never presented as the 725 MW directly reported parent amount.

### UI, demo and reporting

- [ ] After result: why it matters, investigation log, evidence trail, chronology, calculations, counterargument, falsification, grade and limitations all visibly accessible.
- [ ] Clicking every displayed significant number reaches actual source content.
- [ ] Research status not simulated, mocked, or stale while labeled live.
- [ ] Real selected run ID matches bundle and source metadata.
- [ ] Editorial royal-blue/grey sharp-edged dashboard, accurate graphics, functional source explorer.
- [ ] Demo and report tell the same source-backed story; no cosmetic claim stronger than the pipeline verdict.

### Handoff to the following agent

- [ ] Create a short **`CURRENT_STATE.md`** with checked git SHA, machine/date, exact commands/results, source availability, staged/unstaged changes, last real run ID, displayed UI run ID, and explicit blockers.
- [ ] Update `COORDINATION.md` ownership/log and document any new schema contract.
- [ ] Record next three actions with exact files, tests and expected artifacts.
- [ ] Never write “finished” when only a fixture or partial evidence has passed.

---

## 16. DEFINITIVE REFERENCE MAP

**Problem and design decisions:** `Notion-Doc.txt` (contest brief); project discussions “Contest Research Plan,” “Feature 1,” “SignalForge Pipeline Summary” and branches, 15–19 October 2026 (available excerpts).  
**Repository:** https://github.com/ashwera/ftns  
**Root README:** https://github.com/ashwera/ftns/blob/main/README.md  
**Coding coordination:** https://github.com/ashwera/ftns/blob/main/COORDINATION.md  
**Agent conventions:** https://github.com/ashwera/ftns/blob/main/AGENTS.md and https://github.com/ashwera/ftns/blob/main/CLAUDE.md  
**Pipeline status and commands:** https://github.com/ashwera/ftns/blob/main/signalforge/PIPELINE_COMPLETION_REPORT.md  
**Bounded source review & tests:** https://github.com/ashwera/ftns/blob/main/CODEX_1H_EXECUTION_REPORT.md  
**NTPC evidence register:** https://github.com/ashwera/ftns/blob/main/signalforge/data/pipeline_inputs/ntpc_source_register.md  
**NTPC source catalog:** https://github.com/ashwera/ftns/blob/main/signalforge/data/pipeline_inputs/samaira_catalog.json  
**Main pipeline code:** https://github.com/ashwera/ftns/blob/main/signalforge/src/signalforge/pipeline.py  
**Dashboard signal view:** https://github.com/ashwera/ftns/blob/main/signalforge/web/src/signal.tsx  
**Official NTPC FY25 annual report PDF (source-register link):** https://ntpc.co.in/sites/default/files/annual-report/complete-reports/Annual%20Report%202024-25_1.pdf

**Caveat:** Reference URLs establish *where to verify*, not that all claims have been independently verified at generation time. Every subsequent agent should record its own exact repository revision and actual source-check results.

---

## FINAL INSTRUCTION TO THE NEXT CODING/RESEARCH AGENT

**Make SignalForge a genuine research application, not a beautiful mockup of one.** First verify the repo and fix existing correctness/integration gaps. Then execute a real company-and-prompt research run, discover actual public sources, match and calculate source-backed claims, **attack the leading hypothesis with a serious alternative**, and write a final result whose evidence strength cannot exceed its verifiable inputs. Immediately after the discovery on screen, show the **research decision trail, clickable supporting and opposing evidence, event timeline, actual formulas, counterargument, falsification condition, and reasoned grade**. Demonstrate at least one second eligible company with the same code. If a hypothesis is weak, reject it or label it as weak. Do not turn uncertainty into a stronger claim to impress the judges.
