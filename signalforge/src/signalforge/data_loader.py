"""CSV inspection and bounded company evidence extraction."""
import csv
import datetime as dt
import re
from collections import Counter
from pathlib import Path

COMPANY_NAMES = {"company", "company name", "issuer", "issuer name", "security name", "entity", "entity name", "corporate name"}
TICKER_NAMES = {"ticker", "symbol", "stock symbol", "trading symbol"}
SOURCE_NAMES = {"source", "source url", "url", "citation", "source link"}
DATE_HINTS = ("date", "period", "year", "time")

class DataLoadError(ValueError):
    pass

def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def _parse_date(value):
    value = value.strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try: return dt.datetime.strptime(value, fmt).date()
        except ValueError: pass
    try: return dt.date.fromisoformat(value[:10])
    except ValueError: return None

def load_csv(path, allow_empty=False):
    path = Path(path)
    if not path.is_file(): raise FileNotFoundError(f"CSV file not found: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(8192); f.seek(0)
            try: dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error: dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect, skipinitialspace=True)
            if not reader.fieldnames: raise DataLoadError("CSV has no header row")
            fields = [str(x or "").strip() for x in reader.fieldnames]
            if any(not x for x in fields): raise DataLoadError("CSV contains an empty column name")
            if len({_norm(x) for x in fields}) != len(fields): raise DataLoadError("CSV has ambiguous duplicate column names")
            rows = []
            malformed_rows = []
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    malformed_rows.append(reader.line_num)
                    continue
                rows.append({fields[i]: (v or "").strip() for i, v in enumerate(row.values())})
    except UnicodeDecodeError as e:
        raise DataLoadError(f"CSV is not valid UTF-8 (including UTF-8 BOM): {e}") from e
    except csv.Error as e:
        raise DataLoadError(f"Malformed CSV: {e}") from e
    if not rows and not allow_empty: raise DataLoadError("CSV contains a header but no valid data rows")
    dates = []
    date_cols = [c for c in fields if any(h in _norm(c).split() for h in DATE_HINTS)]
    for col in date_cols:
        found = [d for r in rows if (d := _parse_date(r.get(col, ""))) is not None]
        if found: dates = found; break
    missing = {c: sum(not r.get(c, "").strip() for r in rows) for c in fields}
    duplicate_count = len(rows) - len({tuple(r.get(c, "") for c in fields) for r in rows})
    types = {}
    for c in fields:
        vals = [r[c] for r in rows if r[c]]
        types[c] = "date" if c in date_cols and dates else ("numeric-like" if vals and all(re.fullmatch(r"[-+]?\d[\d,.]*%?", v) for v in vals) else "text")
    company_candidates = [c for c in fields if _norm(c) in COMPANY_NAMES | TICKER_NAMES]
    source_cols = [c for c in fields if _norm(c) in SOURCE_NAMES or "source url" in _norm(c)]
    rowid_cols = [c for c in fields if _norm(c) in {"id", "row id", "record id"}]
    metadata = {"path": str(path.resolve()), "row_count": len(rows), "columns": fields, "types": types, "malformed_record_count": len(malformed_rows), "malformed_record_lines": malformed_rows,
        "date_columns": date_cols, "date_coverage": {"start": min(dates).isoformat(), "end": max(dates).isoformat()} if dates else None,
        "missing_values": missing, "duplicate_rows": duplicate_count,
        "company_identifier_candidates": company_candidates, "source_columns": source_cols, "row_identifier_columns": rowid_cols,
        "company_filtering_available": bool(company_candidates),
        "company_filter_limitation": None if company_candidates else "No recognized company or ticker identifier column exists; filename attribution is not treated as row-level company evidence."}
    return rows, metadata

def filter_company(rows, metadata, company):
    cols = metadata["company_identifier_candidates"]
    if not cols: raise DataLoadError(metadata["company_filter_limitation"])
    matches = [r for r in rows if any(r.get(c, "").strip().casefold() == company.strip().casefold() for c in cols)]
    return matches

def evidence_summary(rows, metadata, company, max_rows=12):
    if not metadata["company_filtering_available"]:
        return {"company": company, "rows": [], "limitation": metadata["company_filter_limitation"], "provenance_columns": metadata["source_columns"] + metadata["date_columns"] + metadata["row_identifier_columns"]}
    relevant = filter_company(rows, metadata, company)
    bounded = relevant[:max_rows]
    return {"company": company, "matched_rows": len(relevant), "rows_shown": len(bounded), "truncated": len(relevant) > len(bounded),
        "rows": [{k: v for k, v in r.items()} for r in bounded], "provenance_columns": metadata["source_columns"] + metadata["date_columns"] + metadata["row_identifier_columns"]}
