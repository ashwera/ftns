# Manual review of Layer 1.5 output (hand-labelled, not pipeline-generated)

Reviewer: Claude (AI), reading each claim's source row/excerpt and header. This is NOT an independent human audit and NOT verification:
"correct" means the label, value, unit and period match what the extracted source text states, not that the figure is true.
Original PDFs were not available. Run: 37,881 claims, 31 `extracted`. Chunk ids/claim ids below are suffixes of the full IDs in `claims.jsonl`.

## 1. All 31 `extracted` claims
| Group | n | Structurally correct | Notes |
|---|---|---|---|
| Table-derived | 11 | 11 | 8 are fuel-mix percentages (`Coal,94.02%,95.09%`, FY 2017-18 / FY 2016-17, p97 of 2017-18 file). Aligned, but the row label "Coal" lacks its parent ("% break-up" of fuel cost), so the metric is under-specified. 3 are "Total R&D expenditure as a percentage of PAT" (2015-16..2017-18, p138), correct. |
| Prose-derived (unchanged Layer 1 logic) | 20 | 11 correct, 1 partial, 8 incorrect | Strict precision 55% (11/20). |
| All | 31 | 22 correct (71%), 1 partial, 8 incorrect | |

Prose failures (all in the baseline path, not introduced by this layer):
- `75f4ec` "increase RE capacity to 60GW by 2032" is a target, extracted as capacity 60 GW.
- `e9f26e` "RE installed capacity has crossed 172 GW" is India-wide capacity (interleaved text, no scope word), attributed to NTPC.
- `b252cf` / `769f90` national CEA pipeline / storage targets read as company capacity / generation.
- `bcab6b` "RE capacity of 12 GW" from interleaved two-column text; value/label pairing unreliable.
- `c1cea5` "23 MW Solapur ... (10/23 commissioned)" read as commissioned 23 MW.
- `823cf3` / `fa74f9` `Capital Expenditure ₹ 4,000.00` unit "INR" with no scale although the filing says "in Rs. crore" elsewhere (page 22, quarterly filing).
Correct examples: `0ae587`/`27230b` captive coal 35.64 MMT FY24 and 45.82 MMT FY25 (p90); `7e44bb`/`4edf45` installed capacity 59,413 MW as on 31 March 2025 and 59,078 MW as on 31 March 2024 (p91, interleaved sentence, numbers and dates correct); `43b65f` 79,930 MW as on 31 March 2025 ("consolidated basis" is in the sentence but not captured as a field).

## 2. Random sample of 30 `ambiguous` table claims that have a period (seed 7, population 9,021)
Checked: row label <-> value <-> column header/period alignment, using the original row and header text.
Result: 30/30 aligned to the correct row and column period. 0 mis-pairings.
Residual hazards seen in the sample (the reason they are `ambiguous`, not `extracted`):
- no unit declared in the chunk (30/30; `unit` stays null);
- standalone vs consolidated basis not stated while the document has both;
- bare-date headers (stock vs flow not stated);
- column qualifiers (segment such as "Others"/"Total", or a sub-category label like "Female" whose parent is in an earlier row) live only in `source_header_text` / `source_row_text`, not in the metric;
- unit embedded in the label, e.g. "(gm/kWh)", is not parsed.

## 3. Defects found by an earlier sample and fixed before the final run
- A data row without a label was paired with the preceding label-only row (e.g. column captions "Current Non-current ..." became the metric). Now `needs_review`.
- Labels starting with "Value ..." were treated as header cells and skipped. Fixed.
- Header cell "Particulars (₹ in crore)" was not recognised as a header unless a period was present. Fixed.

## 4. What this does not show
30 + 31 claims is a small sample; with 30/30 the 95% lower bound for table alignment precision is roughly 88%. Text-column ordering errors in reversed multi-line cells are routed to `needs_review`, so they are not in this sample.
