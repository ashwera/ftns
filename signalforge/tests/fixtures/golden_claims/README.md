# Golden claim fixtures (shared by the prose and table extractors)

Hand-labelled test cases for claim extraction from NTPC filings. The shared JSONL contract was accepted in `COORDINATION.md`; the additive Feature Y fields below extend it without changing the existing expected outputs. Labels are one reviewer's reading of the extracted text, not an independent audit or verification against original filings.

## Files
- `chunks.jsonl` – 30 evidence records. 23 are **verbatim copies** of records in `signalforge/data/processed_step6/evidence.jsonl` (plus `source_sha256` from `source_records.jsonl` and `document_has_both_standalone_and_consolidated`, computed over the full archive so tests need not load it). 7 are **synthetic** (`synthetic: true`, `source_path` starts with `SYNTHETIC/`).
- `cases.jsonl` – 31 cases (26 real-chunk, 5 synthetic). Fields: `case_id`, `category`, `synthetic`, `applies_to` (`prose` and/or `table`), `target_company{name,aliases}`, `chunk_ids` (primary records), `context_chunk_ids` (supporting records), `expected`, `explanation`, optional `xfail` and `order_by_page`.
- `REPORT.md` – case-by-case actual vs expected, regenerated with `PYTHONPATH=signalforge/src:signalforge/tests python3 signalforge/tests/golden_harness.py --detail > signalforge/tests/fixtures/golden_claims/REPORT.md`.
- Consumers: `signalforge/tests/golden_harness.py` (shared) and `signalforge/tests/test_golden_claims.py`.

## Semantics of `expected`
- `claims[]` – per figure: `focus` (verbatim snippet identifying the sentence/row), `value`, `unit`, `metric`/`raw_metric_contains`, `period_type`, `period_text`, `as_of_date`, `entity` (`"target"`, a name, or `null`), `status_allowed`, `ideal_status`.
  - `status_allowed` is a **confidence ceiling**: an extractor may be more conservative but never more confident. If it is exactly `["extracted"]` the claim must be present and unit/period/as-of/entity must match. For any `must_emit` claim, the declared fields are checked at every allowed review status too; otherwise non-extracted claims must not carry a *different* specific metric.
- Feature Y continuation expectations may add `must_emit: true`, `source_chunk_id` (the row's evidence record), and `source_header_chunk_id` (the record supplying the matched header; `null` means no prior header may be attached). The table tests check these provenance links in `extraction_report` diagnostics because the claim schema has no cross-chunk header ID field. For `order_by_page: true`, the table harness orders the referenced records by their `page_number` before extraction; a deliberately scrambled reference list checks this behavior.
- `forbidden_extracted[]` – values that must never appear with status `extracted` (they may be absent, `ambiguous` or `needs_review`).
- `no_extracted_claims` – no claim of the case may be `extracted`.
- `reason` – why the plausible-looking extraction is rejected; `explanation` – why the expected result is correct.
- `xfail` – accepted known gap, reported but not failing (the suite fails if it starts passing).
- Every claim must also validate against `claim.schema.json`, stay `unverified`, and keep `source_chunk_id`/`source_path` provenance.

## Selection criteria
Cases were chosen from the failure patterns found in manual review (`signalforge/data/claims_table_step1/manual_review_sample.md`): forward-looking targets, national figures, subsidiary/JV figures, detached or missing units/scales, unstated reporting basis, multi-number sentences, partial/under-implementation/awarded capacity, plus table-specific cases (clean table, header/data split across chunks, reversed rows, stacked cells, entity-named columns, unresolved entity).

| Case | Category | Real source (chunk, page, file) |
|---|---|---|
| GC-01..05, 10 | historical prose, group vs standalone, national comparator, growth %, JV acquisition | `ev_252ddc5c…` p90, Annual Report 2024-25 (Directors' Report highlights) |
| GC-06, 11, 13 | target, under-implementation incl. JV, interleaved detached unit | `ev_2484a0e9…` p91, Annual Report 2024-25 |
| GC-07 | target and plan | `ev_fcde1c84…` p112, Annual Report 2024-25 |
| GC-08 | national figure | `ev_b0922244…` p105, Annual Report 2024-25 |
| GC-09 | subsidiary (NEEPCO, BRBCL) | `ev_f2c3ef5a…` p92, Annual Report 2024-25 |
| GC-12 | detached scale | `ev_b5ea1c5d…` p22, quarterly filing Q1 FY26 |
| GC-14 | partial commissioning, project list | `ev_bc2c2060…` p137, Annual Report 2024-25 |
| GC-15 | awarded retrofit capacity | `ev_7a1ccae4…` p152, Annual Report 2021-22 |
| GC-20 | clean table | `ev_8182a41c…` p138, Annual Report 2017-18 |
| GC-21 | split header/data | `ev_6cf80854…` p90 (+ context `ev_252ddc5c…`), Annual Report 2024-25 |
| GC-22 | reversed text | `ev_215ffc72…` p312, Annual Report 2022-23 (identity unresolved) |
| GC-23 | stacked cells | `ev_b1266a74…` p258, Annual Report 2017-18 |
| GC-24 | entity columns, negatives | `ev_76e5c063…` p503, Annual Report 2019-20 |
| GC-25 | flattened number run | `ev_1562a609…` p339, Annual Report 2024-25 |
| GC-26 | unresolved entity, unstated basis | `ev_7b29bace…` p28, Annual Report 2025-26 (identity unresolved) |
| GC-27 | label lacks parent row | `ev_2531a889…` p97, Annual Report 2017-18 |
| GC-30..33 | **synthetic**: unseen company, forward-looking, subsidiary, NTPC as third party | n/a |
| GC-34 | real adjacent split header/data, net other income (FY 2022–23 / FY 2021–22), unit absent | `ev_dc2aee4…` → `ev_1fe8cca…` p189, Annual Report 2022–23 |
| GC-35 | real three-block table: period header then two financial rows | `ev_5e77b87…` → `ev_53a534…` → `ev_c9f1d…` p191, Annual Report 2022–23 |
| GC-36 | **synthetic** page-order case; references are intentionally scrambled | n/a |
| GC-37 | real page 447 project-completion schedule followed by a same-width, distinct CWIP table | `ev_b403287…` p447 → `ev_a346a8…` p448, Annual Report 2021–22 |

## Known limits
- One reviewer, not independent; expected values were derived from the extracted text only, so a "correct" label does not mean the figure is true.
- GC-04/13 deliberately allow downgrades (`status_allowed` includes `ambiguous`/`needs_review`) because a conservative extractor is acceptable there; only fully explicit statements (GC-01 59,413 MW, GC-02 77.44%, GC-20 percent rows, GC-30) require `extracted`.
- GC-27 is an accepted table-extractor gap (section-row context not modelled).
- GC-34/35 use real source text whose Step 6 records have unresolved company identity and no explicit unit; expected values and periods are recovered only as unverified, review-only candidates.
- GC-36 is synthetic because a clean page-boundary continuation with unambiguous table identity was not available in the preserved real chunks. It is not an NTPC fact.
- GC-37 deliberately shares a six-column shape across two adjacent-page tables. The first is a project completion schedule; the next is an intangible-asset CWIP aging table. The prior header must not be reused.
