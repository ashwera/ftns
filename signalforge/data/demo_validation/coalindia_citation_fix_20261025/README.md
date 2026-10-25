# Coal India citation-fix verification

These are actual exports from the resumed run `research_20261025T000129_2ecbfd3ad81c`, not a new run or a synthetic success case.

- `reproduction.json` records the old/new validator errors, original hash and live model quote result.
- `model_quote.json` contains the live model's longer contiguous source quotation.
- `resume_*_verification.json` record the three recovery attempts, durations and unchanged cached artifact hashes. One attempt encountered provider HTTP503; the first completed report exposed an invalid duplicate sum that was subsequently withheld.
- `investigation.json`, `investigation_report.md` and `investigation_review.json` are the final report and fresh semantic review after that rejection.
- `investigation_final_recovery.json` retains the rejected duplicate calculation and its precise reason.
- `verification_summary.json` records the final checks, accepted claim IDs and limitations.

Outcome: investigation and semantic review complete; three issuer-backed observations; no accepted calculations; inconclusive / Weak; no independent corroboration or established novelty. JSON and Markdown exports and actual browser rendering were checked. The original PDF and complete immutable raw histories remain in the ignored local run directory; these portable exports alone do not bundle original source bytes. See the root `ARSHIA_DEMO_HANDOVER.md` for details.
