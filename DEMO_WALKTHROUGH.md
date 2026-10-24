# Presentation walkthrough

Open http://127.0.0.1:5173 and select Signal.

1. Research question: where does NTPC's renewable pipeline sit across parent-owned projects and JVs/subsidiaries? The assigned contest prompt is absent from the repository, so this is the saved investigation question.
2. Discovery: the saved table comparison allocates 725 of 14,516 MW to parent-owned projects (5.0%) and 13,791 MW to JVs/subsidiaries (95.0%), as of 31 March 2025. Describe this as a provisional observation.
3. Evidence: expand an input to show its excerpt, page, claim identifier, verification results and passage hash. Open the source catalog to show the official document URL and recorded availability. Six inputs received primary-source checks in the saved run; all seven effective outcomes remain partial.
4. Reasoning: show denominator-specific ratios and a calculation trace. Parent renewable / parent all-technology pipeline is 4.7%, whereas JV/subsidiary renewable / JV/subsidiary all-technology pipeline is 75.4%. These use different denominators. Explain why the rounded 14.5 GW residual yields 709 MW while the direct table reports 725 MW.
5. Counterargument: legal entity allocation does not establish economic exposure. Consolidated subsidiaries can still belong economically to NTPC; ownership percentages, minority interests and consolidation treatment are needed. Pipeline capacity also does not establish commissioned capacity or future delivery.
6. Test the interpretation: inspect ownership and consolidation disclosures and compare prior-year composition. A stable split could reflect reporting structure rather than a new transition. This check remains open.
7. Execution: show pipeline provenance and decision log. The displayed run used deterministic calculations and stored source checks. F1 is blocked and R1 did not execute. The Run research control currently reports that no execution API exists.

## Reproducible execution available in this clone

The fresh run `signalforge/data/runs/run_20261024_reproducibility` executes verification, calculations and adjudication on the explicitly synthetic Meridian fixture. It has zero traceability problems. It tests execution; it is not another real-company discovery.

## Remaining dependencies

- `SIGNALFORGE_API_KEY` is not configured in the current environment.
- Human approval of the pending evidence records is required by the F1 contract.
- Source archive `CSV.zip` is absent, but the included page-block evidence successfully rebuilt 40,942 claims. The original PDF was recovered from NTPC into `data/recovered_20261024_large/sources/28f32ae3803b_4c280573.pdf`; its SHA-256 matches prior provenance.
- Independent corroboration and a real second-company run have not been completed.
- The exact assigned prompt is absent, so assignment compliance cannot yet be established.

Fresh real run: `signalforge/data/runs/run_20261024_ntpc_recovered`. This run is now synchronized to the dashboard. Six primary-source checks, seven partial effective outcomes, zero traceability problems. The government corroboration retrieval attempt is preserved in `data/corroboration_20261024/retrieval_report.json` (HTTP 403); it does not contribute to the verdict.
