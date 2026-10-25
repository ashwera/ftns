# SignalForge: five-minute judge Q&A and reserve defence

Audited25 October2026 on `df71552`, branch `codex/arshia-demo-readiness`; see `SIGNALFORGE_FEATURE_CHEATSHEET.md` for the full evidence inventory. Arshia Dang handles product/demo scope, Ashwera Hasan handles implementation/validation, and Samaira Sharma handles financial methodology/evidence. These are speaking assignments, not authorship assertions.

## The ten most consequential questions, ranked

The ten spoken answers below are designed for roughly20–25 seconds each. With short judge questions and two brief follow-ups they fill about five minutes; do not recite the technical notes. Answer the question first, then show one item of evidence if requested. Reserve questions follow.

### 1. Has this actually produced a novel, independently corroborated financial discovery?

**Samaira — spoken:** “No. The strongest completed run produced issuer-backed operating observations and a checked project-capacity ratio, but not an independently corroborated novel financial discrepancy. It finished inconclusive with weak evidence. We distinguish completing an investigation from proving a discovery, and we can show exactly what records are still missing.”

**Support/evidence:** Fresh `research_20261025T051452_b844776593ba/investigation.json` has three supported issuer claims, no independent flags, novelty=false; `investigation_review.json` completed. No market-knowledge novelty corpus is implemented. **Avoid:** “We discovered hidden fraud,” “new alpha,” “a verified investment signal.”

### 2. If the result is inconclusive, what actually works?

**Arshia — spoken:** “The workflow acquired an issuer report, established a source-declared identity, selected an angle, generated a plan, investigated original passages, searched for opposing evidence and completed a separate semantic review. The fresh browser run took about ninety-five seconds. The unsupported part is the proposed material discrepancy, not the fact that those stages executed.”

**Support/evidence:** Fresh manifest lists discovery through adjudication as real; F1/R1/review artifacts exist;16 machine-eligible records. Contrast evidence-gap run `research_20261024T234754_a378b8365612`, whose final review did not complete. **Avoid:** “Every terminal completed status proves successful semantic review.”

### 3. What stops the model inventing a number or approving bad arithmetic?

**Ashwera — spoken:** “Models propose the claims; Python checks supplied source IDs, exact quoted spans and explicit numerical operands before calculating. A previous attempt invented a denominator, and another counted the same sixteen-hundred-megawatt project twice. Those calculations were withheld. The second model reviewer missed the duplication, which is why deterministic checks remain necessary.”

**Support/evidence:** `investigation.check_citation/calculate`, `test_investigation.py`; citation recovery bundle's `investigation_final_recovery.json`. Fresh200/300 ratio was recomputed from the saved source. **Avoid:** “The model reviewer guarantees numerical truth” or “all financial reconciliation is automated.”

### 4. What counts as independent corroboration?

**Samaira — spoken:** “A separately attributed origin must support the same operating claim on a matching project and period. Two URLs, an exchange-hosted issuer filing, or a newspaper repeating management do not automatically qualify. We group copies and related disclosures by lineage. This Coal India result has one issuer lineage, so independent corroboration is explicitly absent.”

**Support/evidence:** Live `collect_sources/adjudicate`; legacy `claim_verification.assess_independence`; reviewer flags and `independent_groups` in the report. Government-domain classification is a hint, not proof. **Avoid:** “Three sources means three independent confirmations.”

### 5. Why did an exact14-character quote fail a15-character rule?

**Ashwera — spoken:** “The text really matched, but our checker also required a minimum amount of quotation context. It incorrectly reported that short-span rejection as a mismatch. We fixed the diagnosis and repair instructions, retained the rule, and tested an exact longer passage naming the railway project and percentage. The original and corrected behavior are preserved.”

**Support/evidence:** `check_citation`; `test_exact_short_quote_gets_actionable_length_error_not_mismatch`; `data/demo_validation/coalindia_citation_fix_20261025/reproduction.json`. Actual Gemini longer-quote probe passed; repaired run reached fresh final review. **Avoid:** “The quote was hallucinated,” “we lowered the threshold to make the demo pass,” or “length alone proves meaning.”

### 6. Can it handle every eligible NIFTY50 company?

**Arshia — spoken:** “That has not been demonstrated. The generic input and onboarding path worked online for Coal India without a prepared company catalog. Hindalco needed a supplied original, and the Power Grid run stopped at its evidence gate. Current index and sector eligibility also need external confirmation. We are demonstrating a reusable path with measured coverage limits.”

**Support/evidence:** Run matrix in the cheat sheet; `company_onboarding.onboard`, run-local registry; no constituent-refresh service. Coal India was already tested previously, so the fresh audit run is not a new holdout-company experiment. **Avoid:** “All NIFTY companies work” or calling a CIN index-membership verification.

### 7. What happens if live search returns nothing or the demo runs slowly?

**Arshia — spoken:** “The search attempts and rejected results stay visible. Issuer navigation can still acquire an original, as it did in our smoke run despite zero accepted RSS hits. Otherwise the agent records an evidence gap. We keep a separately labelled saved report open, so the presentation can continue without pretending that it is the new live result.”

**Support/evidence:** Fresh discovery/follow-through/opposition reports:3+2+2 queries, zero retained hits; onboarding origin `model_navigation_hint+annual_report_page`; two-tab browser rehearsal. **Avoid:** “No result means no disclosure” or silently switching companies/results.

### 8. How do you reconcile units, periods, standalone and consolidated figures?

**Samaira — spoken:** “We retain those distinctions and refuse to equate a target with an operating asset. The reviewed-input signal engine has explicit unit, date, basis and status compatibility rules. The live investigation checks operands and relies partly on semantic review for the comparison basis. That is a real limitation: it is not a universal automatic financial-statement reconciliation engine.”

**Support/evidence:** `signals.py`, `pipeline.verify_inputs`, `claim_verification.py`, `capacity_timeline.compare_project`; live `calculate` and review's `calculation_basis_valid`. **Avoid:** claiming every legacy compatibility check runs in the live model path, or treating JV capacity as parent economic ownership.

### 9. How does F1 choose between possible investigations?

**Samaira — spoken:** “It receives eligible company evidence and proposes testable angles, scoring financial significance, evidence availability, testability, non-obviousness and cross-validation potential. Python recomputes the weighted arithmetic. Our fresh run produced one reliable candidate, so it did not demonstrate a broad contest between many hypotheses. If ranking is unusable, a separately labelled rules-based planning fallback can operate.”

**Support/evidence:** `f1_research_angle_selector.WEIGHTS/run/normalize_f1_scores/deterministic_angle_fallback`; weights30/25/20/7.5/17.5%; fresh F1, historical Hindalco fallback. **Avoid:** “An F1 score is an investment confidence probability” or “every run evaluated many angles.”

### 10. What happens when Groq reaches quota, and how does failover work?

**Ashwera — spoken:** “The shared client can advance through explicitly configured providers on authentication, availability, quota or connection failures, with bounded waits and recorded attempts. Schema and evidence failures cannot become success by changing provider. Groq has an observed eight-thousand-token-per-minute account limit here. We recommend Gemini for today's fuller context, with saved reports and a tested manual provider-switch recovery.”

**Support/evidence:** `llm_client.routes/generate_json/_generate_once`, `provider_health`, `test_provider_failover.py`; actual unavailable-Ollama→Groq trace. Current JSON probes: Groq0.660s, Gemini1.072s; fresh full Gemini run94.74s. **Avoid:** guaranteed failover, equating model context with account quota, or claiming every transition worked live. Today's backend has Gemini primary and no automatic fallback configured; the capability is optional.

## Reserve questions: use only when asked

### 11. Why separate F1 and R1?

**Ashwera — spoken:** “Selection and execution planning have different contracts. F1 chooses a research question using the evidence available; R1 says what must be checked next, which supplied passages matter and what sources are missing. The service then invokes an executor. Keeping them separate makes a plan visibly different from a completed investigation.”

**Support/evidence:** F1 output schema; `r1_research_investigator.run/validate_plan`; `research_session.execute`. **Avoid:** calling standalone R1 an autonomous retrieval engine.

### 12. How are structured claims generated?

**Ashwera — spoken:** “There are two paths. Historical document text uses deterministic prose and table parsers to emit candidate value, unit, period, entity and source fields. Live investigation uses schema-constrained model drafts with exact citations. Both preserve uncertainty; an extracted or well-formed record is not automatically a verified financial claim.”

**Support/evidence:** `claim_extraction`, `table_extraction`, `DRAFT_SCHEMA`, `structured_generation.generate_validated`. **Avoid:** saying the model performs all extraction or all deterministic candidates are approved.

### 13. Is this just summarizing an annual report?

**Samaira — spoken:** “The implemented workflow goes beyond summary: it selects a testable question, plans missing evidence, attempts follow-up and opposition searches, checks claim quotations and calculations, and challenges the conclusion. The present evidence coverage is still thin, so we do not claim every run delivers a non-obvious discovery. Its value here is a traceable investigation with explicit stopping points.”

**Support/evidence:** `run_investigation`, fresh stage artifacts, review and decision log. **Avoid:** claiming novelty merely because multiple stages or models were used.

### 14. How does it know a finding is non-obvious?

**Samaira — spoken:** “It does not know that reliably yet. F1 includes a non-obviousness criterion and final review has a novelty flag, but there is no systematic market-knowledge comparison behind them. The audited results correctly leave novelty false. Establishing novelty would require dated prior disclosures, market knowledge and an independently reviewed comparison.”

**Support/evidence:** F1 scoring weights; `REVIEW_SCHEMA`; all complete run novelty flags. **Avoid:** “Novel wording means a novel signal” or fabricated novelty benchmarks.

### 15. What if an annual report contradicts an exchange disclosure?

**Samaira — spoken:** “We should first match issuer, project, unit, cutoff and operating definition, then determine whether one filing revises the other. We preserve conflicting sources and lower confidence rather than average incompatible figures. The reviewed-input verifier has explicit discrepancy handling; live semantic comparison still requires careful analyst scrutiny when revisions or scope are ambiguous.”

**Support/evidence:** `pipeline.verify_inputs`, `claim_verification.combine_results`, `findings.adjudicate`; live skeptical review prompt. **Avoid:** “The newest date always wins” or “an exchange host independently confirms an issuer statement.”

### 16. How do you distinguish narrative from operating reality?

**Samaira — spoken:** “We label a target as a target and commissioning as a specific milestone. A statement in an annual report establishes what the issuer disclosed. Operating reality needs matching independent records, such as a regulator or operator's own commissioning evidence. For this case that independent step is missing, so the conclusion remains weak and inconclusive.”

**Support/evidence:** Fresh claim texts, their dates and independence flags; source relationships. **Avoid:** “The issuer said it, therefore it is independently true.”

### 17. What exactly does the66.7% calculation tell an investor?

**Samaira — spoken:** “It says the issuer reported two hundred megawatts commissioned out of three hundred for that named project at the stated date. It does not tell us whether a deadline was missed, how much revenue was lost, or what the project is worth. Those questions need schedule commitments, operating output, tariffs, costs and ownership data.”

**Support/evidence:** Fresh `calculations[0]`, same passage and200/300 operands, `calculate`. **Avoid:** extrapolating revenue or equating uncommissioned capacity with loss.

### 18. How is context kept manageable?

**Ashwera — spoken:** “Original records remain intact while inference receives a bounded selection. F1 caps records and payload size; provider-specific views remove duplicated metadata or limit passages. Investigation keeps whole selected passages and preserves cited inputs for review. The report must disclose that omitted text is not evidence of absence. Context reduction trades coverage for latency, not integrity.”

**Support/evidence:** F1 payload limits/slimming; `model_sources/bound_source_passages`; initial request audits. **Avoid:** “Every annual-report page is always in the model context.”

### 19. Why Groq, Gemini and Ollama instead of one model?

**Ashwera — spoken:** “Provider support is about operational continuity and deployment options. Groq has been fast on bounded requests, Gemini handled our fuller completed investigation, and the Ollama adapter supports local inference when an installed model works. Ollama is unavailable on this Mac. Using several providers does not create independent financial corroboration or guarantee successful review.”

**Support/evidence:** Current health probe and shared client; older16GB Ollama report is machine-specific. **Avoid:** claiming installed local inference, provider consensus or guaranteed latency.

**If asked about the newer GitHub xAI code:** “That migration arrived on main after we froze the tested demo branch. Its own report records failed authentication and no live generation. It is not part of the version we are presenting, and we do not claim Grok works here.” Upstream commit: `8630a67`; this is a code/report inspection, not a local xAI inference test.

### 20. Do counterarguments actually change the outcome?

**Samaira — spoken:** “They can. The review contract checks whether the alternative was addressed, and independent corroboration and conclusion support affect adjudication. Earlier scope checks downgraded a claim that selected excerpts proved a whole-report omission. In the fresh case the counter-search acquired nothing independent, and possible grid or land causes remain hypotheses rather than established explanations.”

**Support/evidence:** `adjudicate`, historical Coal India c2, fresh search logs/review. **Avoid:** equating generated counterargument text with acquired counterevidence.

### 21. What do Strong, Moderate, Weak and Not rated mean?

**Ashwera — spoken:** “They are transparent policy labels, not calibrated probabilities. The live path can give Moderate when the accepted key conclusion has separately attributed corroboration and the alternative is addressed; otherwise it remains Weak. It deliberately cannot award Strong automatically. Not rated applies to a no-claim gap report. The historical reviewed-input pipeline has a separate stricter Strong rubric.”

**Support/evidence:** `investigation.adjudicate/evidence_gap_report`, `findings.RUBRIC/evidence_strength`. **Avoid:** treating both rubrics as identical or asserting a probability of correctness.

### 22. How much is autonomous versus rules-based?

**Ashwera — spoken:** “The model proposes angles, plans, interpretations and review judgments. Code controls jobs and budgets, retrieves and hashes sources, checks schemas and quotations, computes arithmetic and applies final policy. A fallback may generate deterministic planning priorities. The agent is autonomous within those bounded stages; source access, dataset preparation and interpretation limits still matter.”

**Support/evidence:** Architecture diagram; `research_session.execute`, shared client and deterministic helpers. **Avoid:** “Everything is AI” or “no human preparation was ever used.”

### 23. What accuracy benchmark can you show?

**Ashwera — spoken:** “We can show the current test counts and the exact live runs, not a general financial accuracy percentage. The backend ran three hundred fifty-nine tests with two skips, and forty-four frontend tests passed. The golden cases are hand-labelled extraction fixtures with known scope limits. They are not an independent benchmark of investment discovery.”

**Support/evidence:** Current test logs; `tests/fixtures/golden_claims/README.md`; source/PDF skip conditions. **Avoid:** converting test pass rate into financial accuracy or treating skipped original-file checks as passed.

### 24. How would you measure accuracy properly?

**Ashwera — spoken:** “We would separate issuer matching, source retrieval relevance, extraction fields, citation validity, numeric compatibility, semantic entailment and final conclusion quality. A held-out set of companies and independently labelled claims would measure precision, recall and unsupported-claim rates at each stage. We would also measure completion, refusal quality and latency, rather than report one misleading overall score.”

**Support/evidence:** Existing field-level golden tests and stage artifacts provide instrumentation; proposed holdout study is future work. **Avoid:** presenting proposed metrics or targets as achieved results.

### 25. What would you improve first with more time?

**Samaira — spoken:** “First, reliable acquisition of authoritative independent operating and schedule records. Second, project-level reconciliation across revisions, dates, scope and milestones. Third, a held-out evaluation of semantic errors, including weak planning leads and falsification statements. Additional models or interface polish would not fix those evidence-quality problems on their own.”

**Support/evidence:** Fresh search scarcity, missing corroboration, F23 audit limits. **Avoid:** promising universal coverage or a near-term accuracy number without evaluation.

### 26. Why is it useful beyond this hackathon?

**Arshia — spoken:** “An analyst can inspect what was found, what calculation was made, which assumptions survived review and what evidence is missing. Saved source and model audits also make a failed or inconclusive case reusable. The useful product direction is reducing opaque research work and making handover easier; we have not measured analyst time saved or investment performance yet.”

**Support/evidence:** Saved reports, exports, immutable attempts and recovery case. **Avoid:** invented productivity or return-on-investment claims.

### 27. Does a CIN prove the company is eligible or the report authentic?

**Samaira — spoken:** “No. This run read an explicitly labelled corporate identifier beside the company name in an original issuer report and pinned the file hash. That supports a source-declared identity mapping. It does not independently authenticate the document, verify every operating fact or establish current index membership. Those are separate checks, and the report records the distinction.”

**Support/evidence:** `read_identity`, run-local registry, physical-page67 onboarding metadata; CIN-only external cross-check label. **Avoid:** calling a CIN an equity ISIN or current NIFTY proof.

### 28. Are the sidebar's claims and research angles from the live company?

**Arshia — spoken:** “Those lower workspace panels browse historical archive outputs. The live or selected run is identified separately in the report above them. The Research angles archive panel can still show a refusal even after a live F1 succeeds, so we use the actual run record for current status. Unifying those scopes is an interface improvement we have documented.”

**Support/evidence:** `ui.tsx` App/Angles/StartResearch; read-only Vite file mapping; browser audit. **Avoid:** silently attributing NTPC archive counts or the static refusal banner to Coal India.

### 29. Is this secure or production deployed?

**Ashwera — spoken:** “This is a local prototype. The service binds loopback, restricts accepted local origins, validates run IDs and payloads, and loads credentials from ignored configuration. Hosted inference still sends the selected public-source context to the configured provider. There is no multiuser authentication, production deployment or complete security review behind the demo.”

**Support/evidence:** `research_service.HOSTS/ORIGINS`, `local_config`, credential redaction and `.gitignore`. **Avoid:** “Enterprise secure,” “all inference is local,” exposing `.env` or claiming credentials are included in the repository.

### 30. Can I recover a failed run without starting over?

**Ashwera — spoken:** “Yes, through the resume command when the original files and valid earlier stages are available. Recovery preserves snapshots, revalidates saved F1/R1 and source hashes, and repeats only necessary work. Our citation case retained eight unchanged cached inputs. A changed search question now gets a new checkpoint instead of being misrepresented as an already completed search.”

**Support/evidence:** `resume_run.resume`, `draft_result`, topic check in `run_investigation`, citation verification bundle. **Avoid:** claiming recovery is a one-click UI feature, universally automatic, or robust cross-process production scheduling.

### 31. Does the generated falsification statement prove the hypothesis is testable?

**Samaira — spoken:** “Not by itself. It is a proposed research test and can be too broad. In this run, exceeding a distant portfolio target is not the correct test for a particular project's deadline. A defensible falsifier must identify the same project, capacity, milestone, reporting cutoff and valid revised commitment. We keep that limitation separate from the supported issuer observations.”

**Support/evidence:** Fresh report's falsification, `adjudicate` scope/deadline heuristics, `capacity_timeline.compare_project`; F23 audit. **Avoid:** presenting free-form falsification as a fully validated causal or schedule proof.

## Evidence and fallback navigation

Current primary case: `research_20261025T051452_b844776593ba`. Citation recovery: `research_20261025T000129_2ecbfd3ad81c`. Refusal: `research_20261024T234754_a378b8365612`. Real JSON/Markdown and model/source audits are under the corresponding `signalforge/data/research_runs/` directories; portable examples are under `signalforge/data/demo_validation/`.

If pressed for an unsupported detail, say: “That is not established by this run; the corresponding audit/limitation is here.” Do not substitute a generic answer for a missing financial fact. A publisher repeating an issuer, a model repeating itself, a schema-valid response and a code-test pass each provide different kinds of evidence; none alone proves investment insight.
