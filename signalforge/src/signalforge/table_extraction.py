"""Layer 1.5: table-aware claim extraction (opt-in; the Layer 1 baseline is untouched).

Pipeline: A) classify chunk -> B) parse/reconstruct rows (incl. conservative reversed-text repair)
-> C) build claims from row label + column header + cell -> D) report. Extraction only: every claim
stays claim_verification_status "unverified"; nothing here verifies, approves, or feeds the F1 gate.
"""
import argparse
import csv
import io
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import claim_extraction as L1
from .config import ROOT

csv.field_size_limit(10**8)
TABLE_PARSER_VERSION = "layer1.5-table-0.2.0"
CLAIM_SCHEMA_VERSION = "1.1"

@dataclass(frozen=True)
class TableConfig:
    min_rows: int = 3                 # fewer non-blank rows cannot be called a table
    min_width: int = 3                # modal field count needed for tabular
    width_consistency: float = 0.6    # share of rows at the modal width
    numeric_frac: float = 0.25        # numeric cells / non-empty cells
    long_cell: int = 120              # chars; a cell this long is prose-like
    tabular_max_long_frac: float = 0.3
    prose_min_long_frac: float = 0.5
    reversal_min_evidence: int = 2    # reversed-word/number tells required in a row
    reversal_ratio: float = 3.0       # reversed evidence must be >= ratio * forward evidence
    max_excerpt: int = 800

NUM = rf"(?:{L1.NUM})"
NUMCELL = re.compile(rf"^\s*(?P<open>\()?\s*(?P<neg>[-−–])?\s*(?P<cur>₹|`|Rs\.?)?\s*(?P<num>{NUM})\s*(?P<close>\))?\s*(?P<pct>%)?\s*$")
DASH = re.compile(r"^\s*[-−–—]+\s*$")
SERIAL = re.compile(r"^\s*(?:\(?[0-9]{1,3}\)?[.)]?|\(?[ivxIVX]{1,5}\)?[.)]?|\(?[a-zA-Z]\)|[a-zA-Z]\.)\s*$")
YEAR_RANGE = re.compile(r"\b(?:19|20)\d{2}\s?[-–/]\s?\d{2,4}\b")
QFY = re.compile(r"(?i)\bQ[1-4]\s?(?:FY\s?)?\d{2,4}\b")
BARE_DATE = re.compile(L1.DATE, re.I)
HEADER_WORD = re.compile(r"(?i)^\s*(?:particulars\b.*|description|notes?(?:\s*no\.?)?|sl\.?\s*no\.?|s\.?\s*no\.?|amounts?|nature of .*|name of .*|number of shares|value\s*\(.*\)|schedule|ref\.?|as (?:at|on)\b.*|for the (?:year|quarter|period)\b.*)$")
NOTE_COL = re.compile(r"(?i)^\s*(?:notes?(?:\s*no\.?)?|sl\.?\s*no\.?|s\.?\s*no\.?|schedule|ref\.?)\s*$")
ORG_LABEL = re.compile(r"(?i)\b(?:limited|ltd\.?|pvt\.?|nigam|vidyut)\b")
GENERIC_LABEL = re.compile(r"(?i)^\s*(?:grand\s+|sub[- ]?)?total\.?\s*$|^\s*net\.?\s*$|^\s*others?\.?\s*$")
DECL = re.compile(r"(?i)(?P<cur>₹|`|rs\.?|inr)\s*(?:in\s+)?(?P<scale>crores?|lakhs?|millions?|billions?|cr\b)|\bin\s+(?P<cur2>₹|`|rs\.?|inr)(?!\w)\s*(?P<scale2>crores?|lakhs?|millions?|billions?)?|\b(?P<scale3>crores?|lakhs?)\b")
UNIT_CELL = re.compile(r"(?i)^\s*(MW|GW|kW|MWh|GWh|MU|BU|MMT|million units|numbers?|nos\.?|no\.|%|per ?cent)\s*$")
UNIT_CELL_CANON = {"million units": "MU", "mu": "MU", "number": "count", "numbers": "count", "nos": "count", "nos.": "count", "no.": "count", "%": "percent", "percent": "percent", "per cent": "percent", "percent ": "percent"}
LABEL_UNIT = re.compile(r"\(\s*(?:in\s+)?(MW|GW|kW|MWh|GWh|MU|BU|MMT|%|per cent|percent)\s*\)|\b(MW|GW|MU|BU)\b")
LEXICON = frozenset("""total balance year ended march particulars amount revenue income expenses profit loss tax equity share shares capital reserves reserve
surplus liabilities liability assets asset current non borrowings financial interest depreciation dividend cash flow flows operations operating other comprehensive
retained earnings general bonds debentures payable receivable trade employee benefit benefits finance cost costs fuel power generation sales energy capacity notes note
statement changes period april june september december january february august july october november provision provisions investments investment property plant equipment
intangible deferred loans advances inventories fund funds paid issued subscribed authorised number name nature relationship transactions during with from for and the less
add net gross before after items exceptional including excluding quarter half audited unaudited standalone consolidated""".split())
REV_NUM = (re.compile(r"^\s*[%)]\s*[\d.,]+"), re.compile(r"[\d.,]+\s*\(\s*$"), re.compile(r"^\s*\d+\.\d+,\d"))
FWD_GROUPED = re.compile(r"^\s*\(?-?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?\)?%?\s*$")
SCALE_CANON = {"cr": "crore", "crore": "crore", "crores": "crore", "lakh": "lakh", "lakhs": "lakh", "million": "million", "millions": "million", "billion": "billion", "billions": "billion"}

def collapse(s): return re.sub(r"\s+", " ", s or "").strip()

# ---------- Stage B (part 1): CSV-level row parsing, preserving raw row text ----------
def parse_rows(text):
    text = text.replace("\r\n", "\n"); lines = text.split("\n"); rows = []; prev = 0
    try:
        reader = csv.reader(io.StringIO(text), strict=False)
        for cells in reader:
            end = reader.line_num
            rows.append({"cells": cells, "raw": "\n".join(lines[prev:end]), "line_start": prev, "line_end": end}); prev = end
    except csv.Error as e: return rows, f"csv parse error: {e}"
    return rows, None

# ---------- Stage A: classification ----------
def classify_chunk(text, cfg=TableConfig()):
    rows, err = parse_rows(text)
    rows = [r for r in rows if any(c.strip() for c in r["cells"])]
    cells = [c for r in rows for c in r["cells"] if c.strip()]
    f = {"rows": len(rows), "parse_error": err}
    if err: return "uncertain", ["csv parse error; structure unreliable"], f
    if not rows: return "uncertain", ["no non-blank rows"], f
    widths = Counter(len(r["cells"]) for r in rows); modal, mcount = widths.most_common(1)[0]
    f.update(modal_width=modal, width_consistency=round(mcount / len(rows), 3))
    f["numeric_cell_frac"] = round(sum(bool(NUMCELL.match(c)) for c in cells) / max(len(cells), 1), 3)
    f["long_cell_frac"] = round(sum(len(c) >= cfg.long_cell for c in cells) / max(len(cells), 1), 3)
    f["header_signal"] = any(_header_like(c) for c in cells[:60])
    reasons = [f"rows={len(rows)} modal_width={modal} consistency={f['width_consistency']} numeric_frac={f['numeric_cell_frac']} long_frac={f['long_cell_frac']} header_signal={f['header_signal']}"]
    if (len(rows) >= cfg.min_rows and modal >= cfg.min_width and f["width_consistency"] >= cfg.width_consistency
            and (f["numeric_cell_frac"] >= cfg.numeric_frac or f["header_signal"]) and f["long_cell_frac"] <= cfg.tabular_max_long_frac):
        return "tabular", reasons + ["consistent multi-column rows with numeric cells or header signal"], f
    if modal <= 2 or f["long_cell_frac"] >= cfg.prose_min_long_frac and f["numeric_cell_frac"] < cfg.numeric_frac:
        return "prose", reasons + ["narrow rows or long text cells dominate"], f
    return "uncertain", reasons + ["signals conflict or too little structure"], f

def _header_like(cell):
    c = collapse(cell)
    if not c or NUMCELL.match(c) or DASH.match(c): return False
    return bool(HEADER_WORD.match(c) or L1._periods(c) or YEAR_RANGE.search(c) or QFY.search(c) or BARE_DATE.search(c) or re.search(r"(?i)\bFY\s?\d", c))

# ---------- Stage B (part 2): reversed-text detection ----------
def cell_evidence(cell):
    fwd = rev = 0
    for w in re.findall(r"[A-Za-z]{3,}", cell):
        lw = w.lower()
        fwd += lw in LEXICON; rev += len(lw) >= 4 and lw[::-1] in LEXICON
    if any(p.search(cell) for p in REV_NUM): rev += 1
    elif FWD_GROUPED.match(cell): fwd += 1
    return fwd, rev

def reversal_decision(cells, cfg=TableConfig()):
    fwd = rev = 0
    for c in cells:
        a, b = cell_evidence(c); fwd += a; rev += b
    reversed_ = rev >= cfg.reversal_min_evidence and rev >= cfg.reversal_ratio * fwd
    return {"reversed": reversed_, "forward_evidence": fwd, "reverse_evidence": rev}

def repair_cells(cells): return [c[::-1] for c in cells]

# ---------- numbers / periods / units ----------
def parse_cell_value(cell):
    m = NUMCELL.match(cell)
    if not m: return None
    if bool(m.group("open")) != bool(m.group("close")): return None
    value = L1._number(m.group("num"))
    notes = []
    if m.group("neg") or m.group("open"):
        value = -value; notes.append("negative value from minus sign or parentheses (accounting notation)")
    return {"value": value, "percent": bool(m.group("pct")), "cur": m.group("cur"), "notes": notes}

def header_period(text):
    """Return (period dict | None, notes). Dates are normalized only when a single unambiguous period is present."""
    t = collapse(text); found = {}; spans = []
    for p in L1._periods(t):
        found[p["raw"]] = p; spans.append(p["pos"])
    for m in BARE_DATE.finditer(t):
        if any(a <= m.start() < b for a, b in spans): continue
        iso = L1._date(m)
        found[m.group(0)] = {"type": "point_in_time", "end": None, "as_of": iso, "raw": m.group(0), "invalid_date": iso is None, "bare": True}; spans.append(m.span())
    for rx in (YEAR_RANGE, QFY):
        for m in rx.finditer(t):
            if any(a <= m.start() < b for a, b in spans): continue
            found[m.group(0)] = {"type": "quarter" if rx is QFY else "financial_year", "end": None, "as_of": None, "raw": m.group(0), "invalid_date": False}
    if not found: return None, []
    if len(found) > 1: return None, [f"column header contains several periods ({'; '.join(sorted(found))}); not assigned"]
    p = next(iter(found.values())); notes = []
    if p.get("invalid_date"): notes.append("header date is invalid or unparseable; dates left null")
    if p.get("bare"): notes.append("header is a bare date; whether it is a point-in-time balance or a period end is not stated")
    return p, notes

def unit_declarations(texts):
    """Distinct (unit, currency_kind, raw) declarations in the given non-data texts."""
    out = {}
    for t in texts:
        for m in DECL.finditer(collapse(t)):
            cur = m.group("cur") or m.group("cur2"); scale = m.group("scale") or m.group("scale2") or m.group("scale3")
            sc = SCALE_CANON.get(scale.lower()) if scale else None
            if cur:
                kind = "backtick" if cur == "`" else "rupee"
                unit = f"INR {sc}" if sc else "INR"
            elif sc: kind, unit = "scale_only", None
            else: continue
            out[(unit, kind)] = m.group(0).strip()
    return out

def metric_key(label):
    s = re.sub(r"\([^)]*\)", " ", label.lower()); s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:80] or None

# ---------- Stage B/C: table model and claims ----------
@dataclass
class Ctx:
    cfg: TableConfig = field(default_factory=TableConfig)
    doc_bases: dict = field(default_factory=dict)
    diag: Counter = field(default_factory=Counter)
    classes: dict = field(default_factory=dict)
    class_reasons: dict = field(default_factory=dict)
    reversal_log: list = field(default_factory=list)
    row_reject_examples: dict = field(default_factory=dict)
    row_outcomes: Counter = field(default_factory=Counter)
    header_history: dict = field(default_factory=dict)
    recent_context: dict = field(default_factory=dict)
    input_order: int = 0
    continuation_matches: list = field(default_factory=list)
    continuation_rejects: list = field(default_factory=list)

def document_bases(records):
    out = {}
    for r in records:
        t = (r.get("excerpt_or_fact") or "").lower(); d = out.setdefault(r.get("source_path"), {"standalone": 0, "consolidated": 0})
        d["standalone"] += "standalone" in t; d["consolidated"] += "consolidated" in t
    return {k: v["standalone"] >= 2 and v["consolidated"] >= 2 for k, v in out.items()}

def _row_kind(cells):
    nums = [i for i, c in enumerate(cells) if NUMCELL.match(c) and not DASH.match(c)]
    heads = [i for i, c in enumerate(cells) if _header_like(c)]
    if heads and not nums: return "header", nums
    if nums: return "data", nums
    if any(re.search(r"[A-Za-z]{3,}", c) for c in cells): return "text", nums
    return "blank", nums

def _header_contexts(record, document_id, order, cfg):
    """Describe local table headers for later chunks without changing the source record."""
    text = record.get("excerpt_or_fact") or ""
    rows, err = parse_rows(text)
    if err: return []
    rows = [dict(r, cells=[c.strip() for c in r["cells"]]) for r in rows if any(c.strip() for c in r["cells"])]
    contexts, pending, title_cells = [], [], []

    def flush():
        nonlocal pending, title_cells
        if not pending: return
        width = max(len(r["cells"]) for r in pending)
        cols = [collapse(" ".join(r["cells"][j] for r in pending if j < len(r["cells"]) and r["cells"][j])) for j in range(width)]
        raw = "\n".join(r["raw"] for r in pending)
        title = collapse(" ".join(title_cells))
        has_period = any(header_period(col)[0] is not None for col in cols)
        if width < cfg.min_width or not (has_period or _header_like(cols[0] if cols else "")):
            pending = []; title_cells = []; return
        contexts.append({
            "document_id": document_id, "source_path": record.get("source_path"),
            "chunk_id": record.get("evidence_id"), "page": record.get("page_number"),
            "order": order, "cols": cols, "width": width, "raw": raw[:cfg.max_excerpt],
            "unreliable": [any(r.get("reversed") and j < len(r["cells"]) and "\n" in r["cells"][j] for r in pending) for j in range(width)],
            "unit_declarations": unit_declarations([title, raw]),
            "title": title[:cfg.max_excerpt],
            "family_tokens": _family_tokens(" ".join([title, *cols])),
        })
        pending = []; title_cells = []

    for row in rows:
        dec = reversal_decision(row["cells"], cfg)
        row["cells"] = repair_cells(row["cells"]) if dec["reversed"] else row["cells"]
        row["reversed"] = dec["reversed"]
        kind, _ = _row_kind(row["cells"])
        if kind == "header":
            pending.append(row)
        else:
            flush()
            if not contexts and kind == "text":
                title_cells.extend(c for c in row["cells"] if c)
    flush()
    return contexts

def _family_tokens(text):
    generic = LEXICON | {"fy", "q1", "q2", "q3", "q4", "inr", "rs", "mw", "gw", "mwh", "gwh", "mu", "bu"}
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in generic and not w.isdigit()}

def _foreign_entity_mentions(text, target):
    """Conservatively detect entity-like names in context; never use a company lookup list."""
    target_norm = re.sub(r"[^a-z0-9]+", " ", (target or "").lower()).strip()
    found = set()
    legal = re.compile(r"\b(?:[A-Z][\w&'.-]*\s+){0,5}(?:Limited|Ltd\.?|Corporation|Corp\.?|Company|Co\.?|LLP|Pvt\.? Ltd\.?)\b")
    for match in legal.finditer(text or ""):
        name = collapse(match.group(0))
        norm = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
        if norm and norm != target_norm and norm not in target_norm and target_norm not in norm:
            found.add(name)
    # Short all-caps names count only beside a generic organization/financial cue.
    acronym = re.compile(r"\b[A-Z][A-Z0-9&-]{2,}\b")
    cues = re.compile(r"(?i)\b(?:financials?|results?|subsidiar\w*|joint venture|associate|segment|company|limited|ltd\.?)\b")
    target_tokens = set(re.findall(r"[A-Z][A-Z0-9&-]{2,}", target or ""))
    for match in acronym.finditer(text or ""):
        token = match.group(0)
        if token in target_tokens: continue
        around = (text or "")[max(0, match.start() - 40):match.end() + 40]
        if cues.search(around): found.add(token)
    return sorted(found)

def _continuation_shape(text, cfg):
    """Return structural features only for headerless, table-like row chunks."""
    rows, err = parse_rows(text)
    rows = [r for r in rows if any(c.strip() for c in r["cells"])]
    if err or not rows: return None
    widths = Counter(len(r["cells"]) for r in rows)
    width, count = widths.most_common(1)[0]
    cells = [c for r in rows for c in r["cells"] if c.strip()]
    if width < cfg.min_width or count / len(rows) < cfg.width_consistency: return None
    if sum(bool(NUMCELL.match(c)) for c in cells) / max(len(cells), 1) < cfg.numeric_frac: return None
    if sum(len(c) >= cfg.long_cell for c in cells) / max(len(cells), 1) > cfg.tabular_max_long_frac: return None
    if any(_row_kind(r["cells"])[0] == "header" for r in rows): return None
    data_rows = []
    for r in rows:
        kind, nums = _row_kind(r["cells"])
        if kind != "data" or not nums: continue
        first_num = nums[0]
        label = next((j for j in range(first_num) if re.search(r"[A-Za-z]{3,}", r["cells"][j]) and not SERIAL.match(r["cells"][j])), None)
        if label is not None:
            data_rows.append({"label": collapse(r["cells"][label]), "numeric_positions": tuple(nums), "width": len(r["cells"]), "raw": r["raw"]})
    if not data_rows: return None
    pos_counts = Counter(r["numeric_positions"] for r in data_rows)
    return {"width": width, "width_consistency": count / len(rows), "numeric_positions": pos_counts.most_common(1)[0][0],
            "position_consistency": pos_counts.most_common(1)[0][1] / len(data_rows), "labels": [r["label"] for r in data_rows],
            "family_tokens": _family_tokens(" ".join(r["label"] for r in data_rows)), "data_rows": data_rows}

def _match_header(record, document_id, order, shape, ctx, cfg):
    """Return a uniquely supported recent header; weak or competing candidates fail closed."""
    history = ctx.header_history.get(document_id, [])
    page = record.get("page_number") if isinstance(record.get("page_number"), int) else None
    plausible = []
    for header in history:
        gap = order - header["order"]
        if gap < 1 or gap > 4 or header["document_id"] != document_id or header["source_path"] != record.get("source_path"):
            continue
        hpage = header.get("page")
        if page is not None and hpage is not None and abs(page - hpage) > 2: continue
        if shape["width"] != header["width"]: continue
        period_positions = tuple(j for j, label in enumerate(header["cols"]) if header_period(label)[0] is not None)
        numeric_positions = shape["numeric_positions"]
        if period_positions and tuple(numeric_positions) != period_positions: continue
        score = 4  # exact modal width, within a single document/path, ordered and bounded
        if period_positions and tuple(numeric_positions) == period_positions: score += 3
        elif not period_positions and len(numeric_positions) == len([c for c in header["cols"] if c]): score += 1
        if page is not None and hpage is not None: score += 1 if page == hpage or page == hpage + 1 else 0
        if gap == 1: score += 1
        overlap = shape["family_tokens"] & header["family_tokens"]
        if overlap: score += min(2, len(overlap))
        plausible.append((score, header))
    plausible.sort(key=lambda item: (-item[0], item[1]["order"]))
    if not plausible: return None, "no recent header has compatible provenance and row structure"
    if len(plausible) > 1: return None, "multiple preceding headers remain structurally plausible"
    score, header = plausible[0]
    if score < 7: return None, f"header match is weak (structural score {score})"
    return header, f"unique structural match (score {score})"

def _table_context_candidate(text):
    text = collapse(text)
    if not text or len(text) > 240: return False
    if unit_declarations([text]): return True
    if re.search(r"(?i)\b(?:standalone|consolidated)\b", text): return True
    return bool(re.search(r"(?i)\b(?:statement of (?:profit|cash|changes)|balance sheet|segment(?:al)? results?|financial results?|installed capacity|revenue from operations)\b", text)
                and text.count(".") <= 1)

def _table_title_boundary(text):
    text = collapse(text)
    if not text: return False
    return bool(re.search(r"(?i)\b(?:statement of (?:profit|cash|changes)|balance sheet|segment(?:al)? results?|financial results?|installed capacity|revenue from operations)\b", text)
                and text.count(".") <= 1)

def extract_table_claims(record, document_id, ctx, prior_header=None):
    chunk_id, path, text = record["evidence_id"], record["source_path"], record["excerpt_or_fact"]
    verified = record.get("company_identity_status") == "verified" and record.get("company_name")
    page = record.get("page_number") if isinstance(record.get("page_number"), int) else None
    raw_rows, _ = parse_rows(text); rows = []
    chunk_has_reversal = False
    for i, r in enumerate(raw_rows):
        if not any(c.strip() for c in r["cells"]): continue
        dec = reversal_decision(r["cells"], ctx.cfg); cells = r["cells"]
        if dec["reverse_evidence"] or dec["reversed"]:
            ctx.reversal_log.append({"evidence_id": chunk_id, "row_index": i, "original": r["raw"][:300], "reconstructed": ",".join(repair_cells(cells))[:300] if dec["reversed"] else None, **dec})
        if dec["reversed"]: cells = repair_cells(cells); chunk_has_reversal = True; ctx.diag["reversed_rows"] += 1
        else: ctx.diag["reversal_candidates_kept"] += bool(dec["reverse_evidence"])
        rows.append({**r, "idx": i, "cells": cells, "reversed": dec["reversed"], "fwd": dec["forward_evidence"], "rev": dec["reverse_evidence"]})
    kinds = [(_row_kind(r["cells"])) for r in rows]
    # headers: consecutive header rows merge column-wise; a later header block replaces the active one (repeated header)
    header = prior_header; pending = []; claims = []; prev_label_row = None; seen_header = False
    chunk_text_l = text.lower()
    entity_context = " ".join(filter(None, [text, (prior_header or {}).get("title"), (prior_header or {}).get("raw")]))
    other_entities = sorted({m.group(0) for m in L1.OTHER_ENTITIES.finditer(entity_context)})
    foreign_entities = _foreign_entity_mentions(entity_context, record.get("company_name"))
    if foreign_entities: verified = False
    decl_texts = [c for r, (k, _) in zip(rows[:10], kinds[:10]) if k != "data" for c in r["cells"]]
    decl_texts += [lab for r, (k, _) in zip(rows, kinds) if k == "header" for lab in r["cells"]]
    decls = unit_declarations(decl_texts)
    if prior_header:
        decls = {**prior_header.get("unit_declarations", {}), **decls}
    doc_both_bases = ctx.doc_bases.get(path, False)
    def finalize(pend):
        width = max(len(r["cells"]) for r in pend)
        cols = [collapse(" ".join(r["cells"][j] for r in pend if j < len(r["cells"]) and r["cells"][j].strip())) for j in range(width)]
        unreliable = [any(r["reversed"] and j < len(r["cells"]) and "\n" in r["cells"][j] for r in pend) for j in range(width)]
        return {"cols": cols, "width": width, "raw": "\n".join(r["raw"] for r in pend), "unreliable": unreliable}
    for pos, (r, (kind, nums)) in enumerate(zip(rows, kinds)):
        cells = r["cells"]; ctx.diag["table_rows_seen"] += 1
        if kind == "header":
            if not (pos > 0 and kinds[pos - 1][0] == "header"):
                if seen_header: ctx.diag["repeated_headers"] += 1
                pending = []
            pending.append(r); header = None; seen_header = True; ctx.diag["header_rows"] += 1; continue
        if pending and header is None: header = finalize(pending); pending = []
        if kind == "blank": ctx.diag["blank_rows"] += 1; continue
        if kind == "text":
            prev_label_row = r; ctx.diag["label_only_rows"] += 1; ctx.row_outcomes["label_only_row"] += 1; continue
        # data row: label = first text cell left of the first numeric cell, skipping serial/index cells
        first_num = nums[0]; label_idx = next((j for j in range(first_num) if re.search(r"[A-Za-z]{3,}", cells[j]) and not SERIAL.match(cells[j]) and not _header_like(cells[j])), None)
        wrapped = False
        if label_idx is None:
            if prev_label_row is not None and pos > 0 and rows[pos - 1] is prev_label_row:
                lab_cells = [c for c in prev_label_row["cells"] if re.search(r"[A-Za-z]{3,}", c)]
                label_raw = collapse(" ".join(lab_cells)); wrapped = True; label_idx = -1
            else:
                ctx.row_outcomes["rejected_no_label"] += 1; ctx.row_reject_examples.setdefault("rejected_no_label", (chunk_id, r["raw"][:120])); continue
        else: label_raw = collapse(cells[label_idx])
        prev_label_row = None
        value_cols = [j for j in nums if j > label_idx]
        if not value_cols: ctx.row_outcomes["rejected_no_value_right_of_label"] += 1; continue
        row_flags = []   # (level, text)
        def flag(level, text): row_flags.append((level, text))
        if wrapped: flag("needs_review", "label taken from the preceding label-only row (wrapped label or continuation); pairing is a guess and may be column captions")
        if header is None: flag("needs_review", "no header row precedes this row in the chunk; column meaning and period are unknown")
        elif len(cells) != len(header["cols"]): flag("needs_review", f"column count mismatch (row has {len(cells)} cells, header has {len(header['cols'])}); index alignment not guaranteed")
        if r["reversed"]: flag("ambiguous", "row text was reconstructed from reversed characters; original preserved in source_row_text")
        elif chunk_has_reversal and r["fwd"] == 0: flag("needs_review", "chunk contains reversed rows and this row has no forward-orientation evidence; it may also be reversed")
        if r["reversed"] and label_idx >= 0 and "\n" in cells[label_idx].strip(): flag("needs_review", "label comes from a multi-line reversed cell; word order is unreliable")
        stacked = [j for j in range(label_idx + 1, len(cells)) if len([l for l in cells[j].split("\n") if NUMCELL.match(l)]) >= 2]
        if stacked: flag("needs_review", "row contains stacked multi-line cells (several values in one cell); row/label alignment is unreliable")
        if GENERIC_LABEL.match(label_raw): flag("ambiguous", "generic total/subtotal/other label; what it totals is not stated in this row")
        if ORG_LABEL.search(label_raw): flag("needs_review", "label looks like an entity name; row may describe a counterparty or subsidiary, not a metric")
        if other_entities: flag("ambiguous", f"chunk mentions other entities ({', '.join(other_entities)}); table may describe a subsidiary or counterparty")
        if foreign_entities: flag("needs_review", f"table context names other legal entity or entity-like acronym ({', '.join(foreign_entities)}); parent-company attribution is not established")
        if re.search(r"(?i)subsidiar|joint venture|associate", text) and not other_entities: flag("ambiguous", "chunk mentions subsidiaries/joint ventures; table owner not established")
        if header is not None and ORG_LABEL.search(" ".join(header["cols"])): flag("needs_review", "header columns name legal entities (subsidiaries/JVs); the figures belong to those entities, not necessarily the filer")
        label_unit = LABEL_UNIT.search(label_raw); label_decl = unit_declarations([label_raw])
        between = [cells[j].strip() for j in range(max(label_idx, -1) + 1, value_cols[0]) if cells[j].strip()]
        cell_unit = UNIT_CELL.match(between[0]) if len(between) == 1 else None
        cell_decl = unit_declarations(between[:1]) if len(between) == 1 and not cell_unit and len(between[0]) <= 24 else {}
        for j in value_cols:
            cell = cells[j].strip(); pv = parse_cell_value(cell)
            if pv is None: ctx.diag["malformed_numeric_cells"] += 1; continue
            col_text = header["cols"][j] if header and j < len(header["cols"]) else None
            if col_text is not None and NOTE_COL.match(col_text): ctx.diag["note_reference_columns_skipped"] += 1; continue
            flags = list(row_flags); notes = [t for t in pv["notes"]]
            period, pnotes = (header_period(col_text) if col_text else (None, []))
            if header and j < len(header["unreliable"]) and header["unreliable"][j]:
                period, pnotes = None, []; flags.append(("needs_review", "column header comes from a multi-line reversed cell; word order is unreliable so no period is assigned"))
            for n in pnotes: flags.append(("ambiguous", n))
            if header is not None and not col_text: flags.append(("ambiguous", "no header text above this column"))
            if period is None and col_text and not pnotes: flags.append(("ambiguous", "column header carries no recognizable period"))
            if header is not None and col_text:
                bases = {b for b in ("standalone", "consolidated") if b in col_text.lower()}
                basis_text = " ".join(filter(None, [chunk_text_l, header.get("title", ""), header.get("raw", "")])).lower()
                chunk_bases = {b for b in ("standalone", "consolidated") if b in basis_text}
                if not bases and doc_both_bases and len(chunk_bases) != 1:
                    flags.append(("ambiguous", "reporting basis (standalone vs consolidated) not stated for this column, and the document contains both"))
                if len(bases) > 1: flags.append(("ambiguous", "column header names both standalone and consolidated"))
            # unit: cell % > label unit > label declaration > single chunk declaration; never guessed
            unit = raw_unit = None
            if pv["percent"]: unit, raw_unit = "percent", "%"
            elif cell_unit:
                raw_unit = cell_unit.group(1); unit = UNIT_CELL_CANON.get(raw_unit.lower(), raw_unit)
            elif len(cell_decl) == 1 and next(iter(cell_decl))[0]:
                (unit, kind), raw_unit = next(iter(cell_decl.items()))
                if kind == "backtick": flags.append(("ambiguous", "currency glyph is a backtick (likely PDF rupee-symbol substitution); INR is not confirmed by the source text"))
            elif label_unit:
                raw_unit = label_unit.group(0).strip("() ").strip(); tok = (label_unit.group(1) or label_unit.group(2)); unit = {"%": "percent", "per cent": "percent", "percent": "percent"}.get(tok, tok)
            elif pv["cur"]:
                unit, raw_unit = "INR", pv["cur"]
                if pv["cur"] == "`": flags.append(("ambiguous", "currency glyph is a backtick (likely PDF rupee-symbol substitution); INR is not confirmed by the source text"))
            elif label_decl or decls:
                dd = label_decl or decls
                if len(dd) == 1:
                    (u, kind), raw_unit = next(iter(dd.items()))
                    unit = u
                    if kind == "backtick": flags.append(("ambiguous", "currency glyph is a backtick (likely PDF rupee-symbol substitution); INR is not confirmed by the source text"))
                    if kind == "scale_only": flags.append(("ambiguous", "scale word without a currency marker; unit left null"))
                else: flags.append(("ambiguous", "several different unit declarations in the chunk; none attached to this value"))
            else: flags.append(("ambiguous", "no unit stated for this value in the row, header, or chunk"))
            if unit is None and not any("unit" in t or "scale word" in t for _, t in flags): flags.append(("ambiguous", "no unit stated for this value in the row, header, or chunk"))
            if not verified:
                notes.append("entity not associated: evidence record has no verified company identity" if not foreign_entities
                             else "entity not attributed: table context names a different or unresolved entity")
            level = "needs_review" if any(l == "needs_review" for l, _ in flags) else "ambiguous" if flags else "extracted"
            allnotes = [t for _, t in flags] + notes
            ex = r["raw"] if len(r["raw"]) <= ctx.cfg.max_excerpt else r["raw"][:ctx.cfg.max_excerpt]
            claim = {"schema_version": CLAIM_SCHEMA_VERSION, "claim_id": L1.claim_id(chunk_id, f"t{r['idx']}", j, pv_raw(cell), label_raw[:60]), "entity": record["company_name"] if verified else None,
                "entity_identity_status": "verified" if verified else "unresolved", "metric": metric_key(label_raw), "raw_metric_text": label_raw, "value": pv["value"], "raw_value_text": cell,
                "unit": unit, "raw_unit_text": raw_unit, "period_type": period["type"] if period else "unknown", "period_start": None,
                "period_end": period.get("end") if period else None, "as_of_date": period.get("as_of") if period else None, "raw_period_text": period["raw"] if period else (col_text or None),
                "source_document_id": document_id, "source_path": path, "source_page": page, "source_chunk_id": chunk_id, "source_excerpt": ex, "extraction_status": level,
                "ambiguity_notes": "; ".join(dict.fromkeys(allnotes)) if allnotes else None, "claim_verification_status": "unverified", "parser_version": TABLE_PARSER_VERSION,
                "extraction_method": "table_row", "chunk_class": "tabular", "source_row_text": ex, "source_header_text": header["raw"][:ctx.cfg.max_excerpt] if header else None,
                "row_index": r["idx"], "column_index": j, "reversal_applied": bool(r["reversed"])}
            if claim["metric"] is None: claim["extraction_status"] = "needs_review"; claim["ambiguity_notes"] = (claim["ambiguity_notes"] or "") + "; label has no usable text"
            claims.append(claim); ctx.diag["table_cells_to_claims"] += 1
        # per-row outcome
        rc = [c for c in claims if c["row_index"] == r["idx"]]
        ctx.row_outcomes["row_with_extracted_claim" if any(c["extraction_status"] == "extracted" for c in rc) else "row_flagged_only" if rc else "row_no_claim"] += 1
    if not seen_header: ctx.diag["tabular_chunks_without_header"] += 1
    return claims

def pv_raw(cell): return collapse(cell)

# ---------- routing ----------
def make_extractor(ctx, target="derive"):
    def extractor(record, document_id):
        ctx.input_order += 1
        order = ctx.input_order
        text = record.get("excerpt_or_fact")
        if not record.get("evidence_id") or not record.get("source_path"): raise ValueError("record lacks evidence_id or source_path; provenance cannot be preserved")
        if not isinstance(text, str) or not text.strip(): ctx.classes[record["evidence_id"]] = "empty"; return []
        cls, reasons, feats = classify_chunk(text, ctx.cfg); ctx.classes[record["evidence_id"]] = cls; ctx.class_reasons[record["evidence_id"]] = reasons[-1]
        local_headers = _header_contexts(record, document_id, order, ctx.cfg)
        shape = None if local_headers else _continuation_shape(text, ctx.cfg)
        if cls != "tabular" and (shape is not None or local_headers):
            cls = "tabular"; ctx.classes[record["evidence_id"]] = cls
            ctx.class_reasons[record["evidence_id"]] = "local table header detected" if local_headers else "headerless rows match a recent table structure; continuation review attempted"
        if cls == "tabular":
            prior_context = [r for r in ctx.recent_context.get(document_id, [])
                if order - r["order"] <= 3 and r["source_path"] == record.get("source_path")
                and (not isinstance(record.get("page_number"), int) or not isinstance(r.get("page"), int) or abs(record["page_number"] - r["page"]) <= 2)]
            for header in local_headers:
                header["context_sources"] = [{"chunk_id": r["chunk_id"], "page": r.get("page"), "text": r["text"][:ctx.cfg.max_excerpt]} for r in prior_context]
                context_declarations = {}
                for r in prior_context: context_declarations.update(unit_declarations([r["text"]]))
                header["unit_declarations"] = {**context_declarations, **header.get("unit_declarations", {})}
                if prior_context:
                    header["title"] = collapse(" ".join([*(r["text"] for r in prior_context), header.get("title", "")]))[:ctx.cfg.max_excerpt]
                    header["family_tokens"] = _family_tokens(" ".join([header["title"], *header["cols"]]))
            prior_header = None
            match_reason = None
            if not local_headers and shape is not None:
                prior_header, match_reason = _match_header(record, document_id, order, shape, ctx, ctx.cfg)
                if prior_header:
                    ctx.diag["continuation_matches"] += 1
                else:
                    ctx.diag["continuation_rejects"] += 1
                    if len(ctx.continuation_rejects) < 100:
                        ctx.continuation_rejects.append({"row_chunk_id": record["evidence_id"], "document_id": document_id,
                            "source_path": record.get("source_path"), "page": record.get("page_number"), "reason": match_reason})
            claims = extract_table_claims(record, document_id, ctx, prior_header=prior_header)
            if prior_header:
                ctx.header_history[document_id] = [prior_header]
                ctx.continuation_matches.append({"header_chunk_id": prior_header["chunk_id"], "header_page": prior_header.get("page"),
                    "row_chunk_id": record["evidence_id"], "row_page": record.get("page_number"), "reason": match_reason,
                    "claim_ids": [c["claim_id"] for c in claims], "header_text": prior_header["raw"],
                    "header_context_sources": prior_header.get("context_sources", [])})
            elif local_headers:
                # A new local header is a table boundary. It replaces older context in this document.
                ctx.header_history[document_id] = local_headers[-4:]
            elif cls == "tabular" and shape is not None:
                # A table-shaped chunk with no defensible match must not leave a stale header active.
                ctx.header_history[document_id] = []
        else:
            claims = L1.extract_claims(record, document_id, target=target)
            for c in claims:
                c.update(schema_version=CLAIM_SCHEMA_VERSION, extraction_method="prose_regex", chunk_class=cls)
                if cls == "uncertain":
                    c["ambiguity_notes"] = "; ".join(filter(None, [c["ambiguity_notes"], "chunk classified uncertain (layout may be tabular or interleaved prose)"]))
                    if c["extraction_status"] == "extracted": c["extraction_status"] = "ambiguous"
            if _table_context_candidate(text):
                ctx.recent_context.setdefault(document_id, []).append({"order": order, "source_path": record.get("source_path"),
                    "chunk_id": record.get("evidence_id"), "page": record.get("page_number"), "text": collapse(text)[:ctx.cfg.max_excerpt]})
                ctx.recent_context[document_id] = ctx.recent_context[document_id][-4:]
                if _table_title_boundary(text):
                    # A new title can separate two same-width tables even if the next chunk omits its header.
                    ctx.header_history[document_id] = []
        for c in claims: c.setdefault("schema_version", CLAIM_SCHEMA_VERSION)
        return claims
    return extractor

def run_table_extraction(input_dir, output_dir, baseline_dir=None, overwrite=False, cfg=TableConfig()):
    records, _ = L1._read_jsonl(Path(input_dir) / "evidence.jsonl") if (Path(input_dir) / "evidence.jsonl").is_file() else ([], [])
    ctx = Ctx(cfg=cfg, doc_bases=document_bases(records))
    claims, report = L1.run_extraction(input_dir, output_dir, extractor=make_extractor(ctx), overwrite=overwrite)
    out = Path(output_dir)
    status = Counter(c["extraction_status"] for c in claims)
    queue = [json.loads(l) for l in (out / "review_queue.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    reasons = Counter()
    for c in claims:
        if c["extraction_status"] == "extracted": continue
        for n in set(x for x in (c["ambiguity_notes"] or "").split("; ") if x): reasons[re.sub(r"\([^)]*\)|\d+", "#", n)[:90]] += 1
    cls_counts = Counter(ctx.classes.values()); method = Counter(c["extraction_method"] for c in claims)
    def missing(field_, fn=lambda v: v is None): return sum(fn(c[field_]) for c in claims)
    report.update({
        "pipeline": "table-aware with experimental cross-chunk continuation", "parser_version": f"{TABLE_PARSER_VERSION}+{L1.PARSER_VERSION}", "schema_version": CLAIM_SCHEMA_VERSION,
        "extractor": "deterministic rules; no model, no network", "thresholds": cfg.__dict__,
        "chunk_classification": {"counts": dict(cls_counts), "extraction_path_counts": {"table_parser": cls_counts.get("tabular", 0), "prose_regex": cls_counts.get("prose", 0), "prose_regex_flagged_uncertain": cls_counts.get("uncertain", 0), "skipped_empty": cls_counts.get("empty", 0)},
                                 "reason_summary_counts": dict(Counter(ctx.class_reasons.values()))},
        "claims_by_method": dict(method), "claims_flagged_for_review": len(queue_claims(queue)),
        "table_rows": {"rows_seen": ctx.diag["table_rows_seen"], "header_rows": ctx.diag["header_rows"], "repeated_headers": ctx.diag["repeated_headers"], "blank_rows": ctx.diag["blank_rows"],
                       "outcomes": dict(ctx.row_outcomes), "rows_with_extracted_claim": ctx.row_outcomes["row_with_extracted_claim"], "rows_flagged_only": ctx.row_outcomes["row_flagged_only"],
                       "rows_rejected_or_without_claim": sum(v for k, v in ctx.row_outcomes.items() if k.startswith("rejected") or k in ("row_no_claim", "label_only_row")),
                       "tabular_chunks_without_header": ctx.diag["tabular_chunks_without_header"], "malformed_numeric_cells_skipped": ctx.diag["malformed_numeric_cells"],
                       "note_reference_columns_skipped": ctx.diag["note_reference_columns_skipped"], "reject_examples": {k: {"evidence_id": v[0], "row": v[1]} for k, v in ctx.row_reject_examples.items()}},
        "cross_chunk_continuation": {"matched_pairs": ctx.diag["continuation_matches"], "matched_pair_count": len(ctx.continuation_matches),
            "rejected_candidate_count": ctx.diag["continuation_rejects"], "matches": ctx.continuation_matches[:200], "rejects": ctx.continuation_rejects},
        "reversal": {"rows_reversed": ctx.diag["reversed_rows"], "rows_with_some_reverse_evidence_kept_forward": ctx.diag["reversal_candidates_kept"], "diagnostics_sample": ctx.reversal_log[:100], "diagnostics_total": len(ctx.reversal_log)},
        "claims_missing": {"metric": missing("metric"), "value": missing("value"), "unit": missing("unit"), "period": missing("period_type", lambda v: v == "unknown"), "entity": missing("entity")},
        "top_review_reasons": reasons.most_common(15),
        "counting_notes": "claims_flagged_for_review counts each non-extracted claim once. top_review_reasons counts each distinct normalized reason once per non-extracted claim, so one claim can appear under several reasons and the reason counts sum to more than the flagged-claim count. Digits are normalized to '#'."})
    if baseline_dir and (Path(baseline_dir) / "claims.jsonl").is_file(): report["comparison_to_baseline"] = compare_to_baseline(claims, Path(baseline_dir), ctx)
    (out / "extraction_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return claims, report

def queue_claims(queue): return [q for q in queue if q["kind"] == "claim_review"]

def compare_to_baseline(new_claims, baseline_dir, ctx):
    base, _ = L1._read_jsonl(Path(baseline_dir) / "claims.jsonl"); new_ids = {c["claim_id"]: c for c in new_claims}; base_ids = {c["claim_id"]: c for c in base}
    retained = [i for i in base_ids if i in new_ids]
    dropped = [base_ids[i] for i in base_ids if i not in new_ids]
    def dist(cs): return dict(Counter(c["extraction_status"] for c in cs))
    def rates(cs): n = max(len(cs), 1); return {"claims": len(cs), "metric_null_rate": round(sum(c["metric"] is None for c in cs) / n, 3), "unit_null_rate": round(sum(c["unit"] is None for c in cs) / n, 3), "period_unknown_rate": round(sum(c["period_type"] == "unknown" for c in cs) / n, 3)}
    table = [c for c in new_claims if c["extraction_method"] == "table_row"]
    return {"baseline_claims": len(base), "baseline_status": dist(base), "baseline_indicators": rates(base),
            "new_claims": len(new_claims), "new_status": dist(new_claims), "new_indicators": rates(new_claims), "table_claims": len(table), "table_status": dist(table), "table_indicators": rates(table),
            "baseline_claims_retained_same_id": len(retained), "baseline_status_changes_among_retained": dict(Counter(f"{base_ids[i]['extraction_status']}->{new_ids[i]['extraction_status']}" for i in retained if base_ids[i]["extraction_status"] != new_ids[i]["extraction_status"])),
            "baseline_claims_not_reproduced": len(dropped), "baseline_not_reproduced_by_status": dist(dropped),
            "baseline_not_reproduced_chunk_class": dict(Counter(ctx.classes.get(c["source_chunk_id"], "?") for c in dropped)),
            "note": "Yield is not accuracy. Baseline claims from chunks now routed through the table parser are replaced, not carried over; correctness must be judged on the manual sample, not on counts."}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", default=str(ROOT / "data" / "processed_step6")); p.add_argument("--output-dir", default=str(ROOT / "data" / "claims_table_xy"))
    p.add_argument("--baseline-dir", default=str(ROOT / "data" / "claims_step1"), help="Layer 1 baseline for the comparison section (read only)")
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    try: claims, rep = run_table_extraction(a.input_dir, a.output_dir, a.baseline_dir, a.overwrite)
    except (OSError, ValueError) as e:
        print(f"Table-aware extraction error: {e}", file=sys.stderr); return 2
    print(f"{rep['run_status']}: {rep['input_record_count']} chunks {rep['chunk_classification']['counts']}, {rep['total_claims']} claims {rep['claims_by_status']}, {rep['schema_validation_failures']} schema failures, {rep['failed_chunk_count']} failed. Report: {Path(a.output_dir) / 'extraction_report.json'}")
    return 0 if rep["run_status"] == "completed" else 1

if __name__ == "__main__": raise SystemExit(main())
