# SignalForge

SignalForge is an initial research workflow foundation for the Energy, Power & Renewables contest track. F1 selects and ranks evidence-led research angles; R1 specifies how to investigate the selected angle. The current repository dataset is an NTPC daily equity quote export, so it supports market-data analysis only.

## Current status

- F1 loader, metadata inspection, optional model client, prompt, JSON Schema validation and CLI are implemented.
- The available CSV has no company/ticker column and is not joined to NTPC based on its filename. NTPC Limited's canonical identity, NSE symbol, ISIN, and BSE scrip code are verified from an NSE-hosted filing; that does not identify the CSV rows.
- Bounded public URL retrieval and local document parsing are implemented. Retrieval is caller-directed, respects robots policy and rate limits, and does not discover sources or perform broad web research.
- Company-specific F1 can use registry-verified ingested disclosures or rows with a verified identifier. The current CSV alone is insufficient, and no F1 result has been generated.
- R1 remains a research-plan prompt only. It does not perform external research.
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

F1 includes company-filtered rows, data-quality warnings, the readiness matrix, and the configured weights in its model input. Dataset-wide statistics are explicitly labeled context and cannot be presented as company-specific evidence. The current quote CSV has no company column, so company-filtered F1 and company-scoped readiness cannot run on it. R1 will require company filings/annual reports, exchange disclosures, investor materials, regulatory/project commissioning records, and credible independent reporting as relevant; no external research is performed by the current prompt.

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

Only entries marked verified in the registry and backed by a verification source are joinable. F1 reads company-matching verified ingested evidence from this store and keeps it separate from dataset-level context. R1 can cite supplied evidence IDs; it remains a plan-only prompt without live source discovery.

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

Copy `signalforge/.env.example` to `signalforge/.env`, set `SIGNALFORGE_API_KEY`, and optionally set `SIGNALFORGE_PROVIDER`, `SIGNALFORGE_MODEL`, and `SIGNALFORGE_BASE_URL`. Export those variables in your shell or load the file with your preferred environment manager; the app does not implicitly load `.env`. The current client supports an OpenAI-compatible chat completions endpoint. No model call occurs without a configured API key. With the current CSV, F1 reports that no company-specific verified evidence is available unless disclosures have been retrieved and ingested.

## Tests

```bash
PYTHONPATH=signalforge/src python -m unittest discover -s signalforge/tests -v
```

Tests use synthetic CSV fixtures and do not need paid API access.

## R1 and next steps

`signalforge/prompts/r1_research_investigator.md` turns an F1 recommendation and evidence IDs into a testable research checklist and evidence ledger requirements. It is a prompt specification only. Live claim research still requires choosing and retrieving relevant primary disclosures, reviewing extracted evidence and table structure, then independently corroborating claims. For renewable mix, commissioned capacity, supplier/customer relationships, and financial statements, the currently available market quote export provides no substantive evidence.
