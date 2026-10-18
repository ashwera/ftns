# SignalForge

SignalForge is an initial research workflow foundation for the Energy, Power & Renewables contest track. F1 selects and ranks evidence-led research angles; R1 specifies how to investigate the selected angle. The current repository dataset is an NTPC daily equity quote export, so it supports market-data analysis only.

## Current status

- F1 loader, metadata inspection, optional model client, prompt, JSON Schema validation and CLI are implemented.
- The available CSV has no company/ticker column and is not joined to NTPC based on its filename. NTPC Limited's canonical identity, NSE symbol, ISIN, and BSE scrip code are verified from an NSE-hosted filing; that does not identify the CSV rows.
- Bounded public URL retrieval and local document parsing are implemented. Retrieval is caller-directed, respects robots policy and rate limits, and does not discover sources or perform broad web research.
- Company-specific F1 can use registry-verified ingested disclosures or rows with a verified identifier. The current quote CSV alone is insufficient, and no F1 result has been generated. Do not point F1 at `processed_step6` until a review gate excludes unreviewed page fragments; those records are not approved evidence.
- R1 is a research-plan runner only. It does not perform external research.
- No genuine F1 model result is included. Output JSON files and credentials are ignored by Git.

## Structure

```text
signalforge/
  data/                 Data notes; source CSV remains at repository root
  prompts/              F1 and R1 specifications
  schemas/              F1 JSON Schema
  src/signalforge/      Python loader, configuration, model client and CLI
  tests/                Offline unit tests with synthetic CSVs
  outputs/              Generated local results (ignored)
```

## Data files that are not in the repository

Large source and generated data are deliberately not committed (GitHub rejects files over 100 MB and the outputs are reproducible). If you clone this repository, **ask the maintainer for the source archive**, or regenerate the outputs from it.

| Missing path | What it is | How to get it |
|---|---|---|
| `signalforge/data/CSV.zip` | Source archive: 30 PDF-to-text CSVs (9 NTPC annual reports FY2017-18 to FY2025-26 and 21 quarterly/results filings). About 2 MB. | Ask the maintainer. It is the only input the rest depends on. Do not edit it. |
| `signalforge/data/intake/CSV/` | The same files, unzipped (macOS `__MACOSX` and `.DS_Store` removed). | `unzip signalforge/data/CSV.zip -x "__MACOSX/*" "*.DS_Store" -d signalforge/data/intake` |
| `signalforge/data/processed_step6/` | 8,241 page-block evidence records (`evidence.jsonl`, `source_records.jsonl`, reports). Some of its files may be absent from a clone. | `PYTHONPATH=signalforge/src python3 -m signalforge.document_text_ingestion --input-dir signalforge/data/intake/CSV --output-dir signalforge/data/processed_step6` |
| `signalforge/data/claims_step1/`, `claims_table_step1/`, `claims_table_xy/` | Historical claim outputs from earlier extractor versions (about 8 MB, 72 MB, 84 MB). | Ask the maintainer, or regenerate with the extraction commands above. Counts will differ if extractor versions differ. |
| `signalforge/data/runs/*/prose_only/` and `table_aware/` | Full claim files from the archive evaluation run. | `PYTHONPATH=signalforge/src python3 -m signalforge.archive_evaluation --run-dir signalforge/data/runs/<new_run_id>` (the run directory must not already exist). |
| `signalforge/web/node_modules/`, `web/dist/` | Frontend dependencies and build output. | `cd signalforge/web && npm install && npm run build` |

The repository does contain the code, schemas, tests, the golden fixtures (`signalforge/tests/fixtures/golden_claims/`), the reviewed-input specs (`signalforge/data/pipeline_inputs/`), and the small run artifacts (reports, manifests, audit sample, findings). Some tests skip themselves when the large files are absent (for example the real-NTPC end-to-end test).

Without `CSV.zip` you can still run the unit tests, the golden harness and the synthetic-company pipeline run, but you cannot reproduce the NTPC archive results. Model credentials (`SIGNALFORGE_API_KEY`) are also not included; see "Model provider".

## Setup

Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r signalforge/requirements.txt
```

Set `PYTHONPATH=signalforge/src` for the commands below, or export it for your shell session. The source CSV is currently `Quote-Equity-NTPC-EQ-15-04-2026-15-10-2026.csv` in the repository root. Change the path with `--csv` or `SIGNALFORGE_CSV_PATH`.

Inspect the real dataset:

```bash
PYTHONPATH=signalforge/src python -m signalforge.f1_research_angle_selector --inspect
```

## Dataset audit and research readiness

Run the Step 2 audit from the repository root:

```bash
PYTHONPATH=signalforge/src python -m signalforge.dataset_audit --csv-path "Quote-Equity-NTPC-EQ-15-04-2026-15-10-2026.csv"
```

Optional output directory and company filter:

```bash
PYTHONPATH=signalforge/src python -m signalforge.dataset_audit --csv-path "/path/to/data.csv" --output-dir signalforge/outputs --company "Company Name"
```

The command writes `dataset_audit.json` (file/field profile, quality checks, safe sample rows, and limitations) and `research_readiness.json` (category-by-category evidence matrix and current F1 weights). Their schemas are in `signalforge/schemas/`. Readiness levels progress from `not_ready` to `limited_screening`, `preliminary_analysis`, and `defensible_conclusion`; a field-name match alone cannot establish substantive evidence. The audit currently assigns no higher level than the actual records and fields support.

F1 includes company-filtered rows, data-quality warnings, the readiness matrix, and configured weights in its model input. Dataset-wide statistics are explicitly labeled context and cannot be presented as company-specific evidence. The current quote CSV has no company column, so company-filtered F1 and company-scoped readiness cannot run on it. R1 requires a reliable F1 recommendation and supplied evidence IDs; it prepares a research plan and performs no retrieval.

## Evidence ingestion

The local ingestion layer accepts CSV, PDF, plain text, Markdown, and HTML. It does not discover sources. Original source files remain untouched; parsed source records (`source_records.jsonl`), normalized evidence (`evidence.jsonl`), and reports are written under `signalforge/data/processed/` by default (ignored by Git). Raw source records are kept separate from normalized evidence. Each normalized record has a deterministic `evidence_id`, source path or URL, optional dates and metric context, identity status, extraction status, and warnings. Duplicate files are reported rather than removed; conflicting reported values are retained for review. PDF extraction uses `pypdf`; page-level provenance is recorded, and pages without text are marked for OCR/manual review. Tables may lose structure during basic text extraction and require visual checking.

The company registry is `signalforge/data/company_registry.json`. It records the NTPC identity mapping and its NSE filing provenance. The CSV remains unassociated because it has no issuer identifier. A registry entry verifies an identity mapping; it does not prove the issuer of an unrelated file.

Ingest the available repository CSV:

```bash
PYTHONPATH=signalforge/src python -m signalforge.evidence_ingestion --source "Quote-Equity-NTPC-EQ-15-04-2026-15-10-2026.csv" --registry signalforge/data/company_registry.json
```

Ingest local disclosures, then inspect normalized evidence:

```bash
PYTHONPATH=signalforge/src python -m signalforge.evidence_ingestion --input-dir /path/to/disclosures --output-dir signalforge/data/processed --registry signalforge/data/company_registry.json
PYTHONPATH=signalforge/src python -m signalforge.evidence_ingestion --inspect --output-dir signalforge/data/processed
PYTHONPATH=signalforge/src python -m signalforge.evidence_ingestion --inspect --company "Verified Company Name" --output-dir signalforge/data/processed
```

Only entries marked verified in the registry and backed by a verification source are joinable. F1 reads company-matching verified ingested evidence from this store and keeps it separate from dataset-level context. R1 can cite supplied evidence IDs; it remains plan-only without live source discovery.

For the preserved PDF-to-CSV text extracts in `signalforge/data/intake/CSV/`, use the page-marker-aware Step 6 parser rather than the generic CSV evidence loader:

```bash
PYTHONPATH=signalforge/src python -m signalforge.document_text_ingestion --input-dir signalforge/data/intake/CSV --output-dir signalforge/data/processed_step6
```

These outputs retain document and page-block identity for review. All current Step 6 records require manual review and none are approved; they are not F1-eligible evidence.

F1 now enforces that gate: ingested records must be identity-verified, parsed, non-empty, and explicitly marked `review_status: "approved"` with `reviewed_by`, `reviewed_at`, and `review_note`. Ingestion defaults to `pending_review`; it never marks records approved. F1 fails before a model call when no eligible evidence is available, and limits a request to 40 evidence records and 250,000 UTF-8 bytes. The current Step 6 store has no human approvals, so adding `SIGNALFORGE_API_KEY` alone will not make F1 eligible. The documented configuration remains to export `SIGNALFORGE_API_KEY` and, if needed, `SIGNALFORGE_PROVIDER`, `SIGNALFORGE_MODEL`, and `SIGNALFORGE_BASE_URL` in the environment; `.env` is not loaded implicitly.

## Experimental table-aware extraction

The optional Layer 1.5 extractor parses table-shaped records from Step 6 and can carry a uniquely supported table header into a nearby continuation chunk in the same source document. It checks page/order, source path, column width, period columns, row structure, and label similarity; ambiguous matches stay under review. Every output claim remains `unverified`. This is an experimental extraction path, not a review or approval step, and it does not change F1/R1 eligibility.

Run it separately from the preserved Layer 1.5 baseline:

```bash
PYTHONPATH=signalforge/src python3 -m signalforge.table_extraction \
  --input-dir signalforge/data/processed_step6 \
  --output-dir signalforge/data/claims_table_xy \
  --baseline-dir signalforge/data/claims_step1
```

The default output is `signalforge/data/claims_table_xy`; the earlier `claims_table_step1` output is not replaced. The command refuses to replace an existing output directory unless `--overwrite` is supplied. Inspect `extraction_report.json` for continuation matches and rejected candidates, plus the individual claim row/header text and review status. A continuation match recovers structural context only; it does not itself establish the entity, unit, reporting basis, or claim validity.

The shared hand-verified cases live in `signalforge/tests/fixtures/golden_claims/`. Cross-chunk table cases are exercised by `test_table_extraction.py`; the fixture's prose cases are owned by the prose-extractor tests.

## Public source retrieval and identity verification

The retrieval client accepts a bounded set of caller-supplied public URLs; it does not search the web. It checks `robots.txt`, fails closed if the policy cannot be established, honors crawl delays, limits each response to 15 MB and ten URLs per run, and saves source snapshots under `signalforge/data/processed/sources/`. Redirect targets are checked against their own robots policy before retrieval. Use only sources you are permitted to access. `--company` associates records only when the company is verified in the registry and the document text contains the canonical name or verified identifier; `--source-relationship` is an explicit operator classification and defaults to `unknown`.

The registry records NTPC Limited as verified from an NSE-hosted integrated governance filing. The source text states its entity name, NSE symbol, ISIN, and scrip code. This registry verification does not join the existing CSV, which still has no issuer identifier.

Verify or refresh an identity mapping from a public source whose retrieved body explicitly contains all supplied identity values:

```bash
PYTHONPATH=signalforge/src python -m signalforge.public_sources \
  --verify-alias NTPC --canonical-name "NTPC Limited" --ticker NTPC --isin INE733E01010 \
  --identity-url "https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_GOVERNANCE_152692_24042026170150_iXBRL_WEB.html" \
  --registry signalforge/data/company_registry.json --output-dir signalforge/data/processed
```

Retrieve selected public documents from a verified company source set:

```bash
PYTHONPATH=signalforge/src python -m signalforge.public_sources \
  --url "https://ntpc.co.in/investors/disclosures-announcements/corporate-announcements" \
  --company NTPC --source-relationship original_disclosure \
  --output-dir signalforge/data/processed --registry signalforge/data/company_registry.json
```

Inspect `retrieval_report.json`, `ingestion_report.json`, and the normalized `evidence.jsonl`. Publication date is populated only from recognized document metadata; retrieval time is never used as a substitute. Source relationships are not inferred from URL or content. Republications do not count as independent corroboration. Claims remain unverified until a source and claim mapping are reviewed.

Run F1 for a company (requires matched rows with a recognized company identifier or verified company-specific ingested evidence, plus configured model credentials):

```bash
PYTHONPATH=signalforge/src python -m signalforge.f1_research_angle_selector --company NTPC
```

To choose paths:

```bash
PYTHONPATH=signalforge/src python -m signalforge.f1_research_angle_selector --inspect --csv /path/to/data.csv
PYTHONPATH=signalforge/src python -m signalforge.f1_research_angle_selector --company NTPC --csv /path/to/data.csv --output /path/to/f1.json
```

## Model provider

The default provider is Gemini through Google's official OpenAI-compatible chat completions endpoint, using the OpenAI SDK already declared as an optional dependency. Defaults are `SIGNALFORGE_PROVIDER=gemini`, `SIGNALFORGE_MODEL=gemini-3.8-flash`, and the official Gemini compatibility URL. `SIGNALFORGE_API_KEY` is the Gemini API key. You may override provider/model/base URL explicitly; `.env` is not loaded implicitly. No model call occurs without the key, and F1 still requires human-reviewed, approved evidence before making a request. With the current quote CSV alone, F1 cannot run without eligible company-specific evidence.

## Tests

```bash
PYTHONPATH=signalforge/src python -m unittest discover -s signalforge/tests -v
```

Tests use synthetic CSV fixtures and do not need paid API access.

## R1 and next steps

`signalforge/src/signalforge/r1_research_investigator.py` turns a reliable F1 recommendation and supplied evidence IDs into a testable research checklist and evidence ledger. It remains a plan-only runner and does not retrieve sources. Run it with:

```bash
PYTHONPATH=signalforge/src python -m signalforge.r1_research_investigator --f1 signalforge/outputs/f1_output.json --output signalforge/outputs/r1_plan.json
```

Live claim research still requires choosing and retrieving relevant primary disclosures, reviewing extracted evidence and table structure, then independently corroborating claims. The current quote dataset cannot support operating or company-specific claims by itself.

## SignalForge research dashboard

The frontend is a separate React + TypeScript application in `signalforge/web/`, built with Vite. Its read-only Vite development middleware serves a fixed allowlist of local audit, readiness, ingestion, evidence, F1, and R1 outputs; it does not execute shell commands or expose credentials. Evidence is read from `signalforge/data/processed_step6/evidence.jsonl` when present. The dashboard labels unavailable outputs, shows extraction warnings, and refuses to present a discovery while the current research remains blocked. No demo finding is mixed with real evidence.

Start the dashboard from the repository root:

```bash
cd signalforge/web
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). The server binds to localhost. To create a static production bundle, run `npm run build` from `signalforge/web`; the read-only local output middleware is development-only, so deploy a separately secured data API before serving real local research files in production.

Frontend checks:

```bash
cd signalforge/web
npm test
npm run build
```
