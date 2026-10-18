# Archive evaluation, run_20261018_archive

Fresh run over the full Step 6 corpus (8,241 page-block records). Historical outputs (`claims_step1/`, `claims_table_step1/`, `claims_table_xy/`) were not touched. No network, no model, no verification. All claims are `unverified`.

## Gate
- Full unit suite: 125 tests OK. Golden harness: 34 PASS / 0 FAIL / 1 accepted XFAIL (GC-27) across 35 case-by-extractor runs. Matches the handoff.
- Inputs hashed in `run_manifest.json` (evidence.jsonl sha256 `d7a4808c…`, source_records.jsonl, ingestion_report.json, claim schema). Both commands exited 0.

## Results
| | prose-only (parser 0.2.0) | table-aware (Layer 1.5 + Feature Y) |
|---|---|---|
| chunks / failed / schema failures | 8,241 / 0 / 0 | 8,241 / 0 / 0 |
| claims | 4,423 | 40,942 (37,843 table rows + 3,099 prose) |
| extracted / ambiguous / needs_review | 6 / 100 / 4,317 | 15 / 15,791 / 25,136 |
| missing metric / unit / period / entity | 79% / 2.6% / 59% / 99.9% | 6.2% / 81% / 68% / 38.5% |
| missing source chunk, page, excerpt | 0 / 0 / 0 | 0 / 0 / 0 |
| claim_verification_status values | unverified only | unverified only |

- Table-aware output is byte-identical to Codex's earlier `claims_table_xy/claims.jsonl`, so the run is reproducible.
- Chunk classes: 4,379 tabular, 2,036 prose, 1,826 uncertain. Table rows seen 34,612; 14,322 rejected because the label is in another chunk; 17,594 rows produced no claim; 701 tabular chunks have no header. Reversed rows repaired: see `table_aware/extraction_report.json`.
- Prose-only differs from the historical 4,423-claim baseline (51 extracted): parser 0.2.0 leaves 6 of the old 51 as extracted.
- Duplicates (`duplicate_claim_groups.jsonl`): 5,629 groups of the same metric/value/unit/period; 3,063 span several documents. All are marked `independent_corroboration: false` (one issuer's repeated disclosures).

## Manual audit (`claim_audit_sample.jsonl`, `claim_audit_results.csv`)
64 claims, deterministic stratified sample (seed 20261018), judged by reading the extracted source row/excerpt and header. This is one reviewer's reading of extracted text, not a check against original PDFs.
- All 15 `extracted` claims audited: 7 correct, 8 correct-but-overconfident (fuel-mix rows `Coal,94.02%` etc., the known GC-27 gap: the parent row `% break-up` is missing from the metric). Structural alignment 15/15; fully specified metric 7/15.
- Of 49 non-extracted claims: 30 appropriately flagged, 7 aligned and correctly flagged, 4 wrong-but-flagged (wrapped-label guess, comparative period, stock-price rows), 2 wrong with an `ambiguous` status that does not expose the error:
  1. `Units of electricity sold (MUs) 2,40,204` was given unit `INR crore`; the `(MUs)` label is not recognised and a chunk-level crore declaration was applied.
  2. `Profit for the year … 11.88` under a `Book value per share (₹)` column was given `INR crore`.
  Both are in `table_extraction.py` (Codex, Feature Y in progress); request logged in `COORDINATION.md`.
- Nothing in the sample showed a prose or table claim wrongly promoted to `extracted` other than the eight GC-27 rows.

## GC-27 analysis
`Coal,94.02%,95.09%` sits under the section row `% break-up,,` (a label with only empty value cells). The table parser treats that row as a label-only row and then reads the following rows as independent. A safe fix is local: remember the most recent label-only row whose value cells are all empty and, for later rows in the same chunk with no intervening header, append it to `raw_metric_text` or cap the claim at `ambiguous` ("label lacks parent section row"). It needs a regression test and changes the claim set for 8 rows. I did not change it: `table_extraction.py` is Codex's in-progress file and GC-27 stays the accepted XFAIL.

## What this corpus can and cannot support
15 of 40,942 claims are `extracted`; downstream stages must work from reviewed `ambiguous` claims plus the source passage, and say so.
