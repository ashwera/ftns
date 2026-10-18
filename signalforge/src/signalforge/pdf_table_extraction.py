"""PDF-native table extraction (Layer 1.6, additive, opt-in).

The text-chunk extractors work on text that has already lost its geometry: two-column report pages come out interleaved and a table's
values no longer sit next to their row labels. This module reads the PDF's own text positions instead. A page is reduced to a
`layout` (blocks -> lines with bounding boxes and bold flags, from PyMuPDF `get_text("dict")`); everything after that is plain Python and is
tested on committed layout fixtures, so the logic needs no PDF at test time.

What it reconstructs, using geometry and typography only:
  * tables: a header row whose later cells carry a unit or a period (`Capacity (MW)`), then the rows below it inside the header's x-range;
  * rows: a label (wrapped labels are joined by shared block or indentation) and one value per value column;
  * sections: label-only rows (`I Owned by your Company`) that scope the rows under them;
  * totals: a total row is checked against the sum of the rows it closes (and a grand total against its section totals).

What it will not do: decide that a value belongs to an entity because nearby text mentions that entity. Ownership scope comes only from the
table's own section heading (or from a total that arithmetically combines section totals) and is `unresolved` otherwise. Every claim is
`unverified`; a claim is `extracted` only when unit, scope, period and (for totals) arithmetic are all structurally resolved, else `ambiguous`
or `needs_review`. Extraction is not source verification and approves nothing.
"""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

PARSER_VERSION = "pdf-native-table-0.1.0"
NUMBER = re.compile(r"^\(?[-–]?\d[\d,]*(?:\.\d+)?\)?$")
UNIT_HEADER = re.compile(r"\(\s*(MW|GW|kW|MWh|GWh|MU|BU|MMT|%|₹\s*crore|`\s*crore|Rs\.?\s*crore|crore)\s*\)", re.I)
UNIT_CANON = {"mw": "MW", "gw": "GW", "kw": "kW", "mwh": "MWh", "gwh": "GWh", "mu": "MU", "bu": "BU", "mmt": "MMT", "%": "percent"}
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
AS_ON = re.compile(r"(?i)\bas\s+(?:on|at)\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})")
SECTION_MARK = re.compile(r"^(?:[IVX]{1,4}|[A-H])[\.\)]?\s{1,}(?=\S)")
ITEM_MARK = re.compile(r"^(?:[a-z]|\d{1,2})[\)\.]\s+")
POINTER = re.compile(r"(?i)\b(?:as under|as follows|given below|details? (?:are|is) (?:as )?(?:under|below|given)|as per detail)")
TOTAL_LABEL = re.compile(r"(?i)^(sub-?total|total)\b")
SCOPE_PATTERNS = [
    ("parent_owned", re.compile(r"(?i)\bowned by (?:your|the) company\b|\bstandalone\b|\bparent[- ]owned\b|\bowned by the parent\b")),
    ("jv_subsidiary", re.compile(r"(?i)\bjoint ventures?\b|\bsubsidiar(?:y|ies)\b|\bJVs?\b")),
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def layout_from_page(page):
    """Reduce a PyMuPDF page to the minimal layout used here (text, bbox, bold flag per line)."""
    d = page.get_text("dict")
    blocks = []
    for bi, b in enumerate(d["blocks"]):
        if b.get("type") != 0:
            continue
        lines = []
        for l in b["lines"]:
            text = "".join(s["text"] for s in l["spans"]).rstrip()
            if not text.strip():
                continue
            bold = all(bool(s["flags"] & 16) or "bold" in s["font"].lower() for s in l["spans"] if s["text"].strip())
            lines.append({"text": text, "bbox": [round(v, 1) for v in l["bbox"]], "bold": bold})
        if lines:
            blocks.append({"id": bi, "bbox": [round(v, 1) for v in b["bbox"]], "lines": lines})
    return {"width": round(page.rect.width, 1), "height": round(page.rect.height, 1), "blocks": blocks}


def printed_labels(layout):
    """Printed page numbers of a spread, read from footer lines (`178 | REPORT NAME` at the left, `NAME | 179` at the right)."""
    out = {}
    for b in layout["blocks"]:
        for l in b["lines"]:
            if l["bbox"][1] < layout["height"] * 0.9:
                continue
            m = re.search(r"(?:^|\|)\s*(\d{1,4})\s*(?:\||$)", l["text"].strip())
            if m:
                out["left" if (l["bbox"][0] + l["bbox"][2]) / 2 < layout["width"] / 2 else "right"] = m.group(1)
    return out


def _items(layout):
    items = []
    for b in layout["blocks"]:
        for l in b["lines"]:
            items.append({"text": l["text"].strip(), "x0": l["bbox"][0], "y0": l["bbox"][1], "x1": l["bbox"][2], "y1": l["bbox"][3], "bold": l["bold"], "block": b["id"], "block_bbox": b["bbox"]})
    return items


def _num(text):
    t = text.strip()
    neg = t.startswith("(") and t.endswith(")") or t[:1] in "-–"
    core = re.sub(r"[^\d.]", "", t)
    if not core:
        return None
    v = float(core)
    return -v if neg else v


def _cluster_rows(items, tol=3.0):
    rows = []
    for it in sorted(items, key=lambda i: (i["y0"], i["x0"])):
        if rows and abs(rows[-1][0]["y0"] - it["y0"]) <= tol:
            rows[-1].append(it)
        else:
            rows.append([it])
    return rows


def find_tables(layout):
    """A header is one text block holding a label cell and, on the same line, one or more unit/period cells (`Description  Capacity (MW)`).
    Anchoring on the block keeps neighbouring text columns of a two-column page out of the table; rows are the contiguous lines beneath
    the header inside its x-range. Pages whose generator splits a header across blocks are not recognised (reported as no table)."""
    items = _items(layout)
    by_block = {}
    for it in items:
        by_block.setdefault(it["block"], []).append(it)
    tables = []
    for bid, lines in sorted(by_block.items(), key=lambda kv: min(i["y0"] for i in kv[1])):
        for row in _cluster_rows(lines):
            row = sorted(row, key=lambda i: i["x0"])
            if len(row) < 2 or UNIT_HEADER.search(row[0]["text"]) or not any(UNIT_HEADER.search(c["text"]) for c in row[1:]):
                continue
            label_head, value_heads = row[0], row[1:]
            x_left, x_right = label_head["x0"], max(c["x1"] for c in value_heads)
            zone = [i for i in items if i["y0"] > label_head["y1"] - 1 and i["x0"] >= x_left - 2 and i["x1"] <= x_right + 14]
            region, last_bottom = [], label_head["y1"]
            for r in _cluster_rows(zone):
                top = min(i["y0"] for i in r)
                if top - last_bottom > 22:
                    break
                # a line that starts left of the label column is body text, not a table row
                if any(i["x0"] < x_left - 1.5 for i in r):
                    break
                region.append(r)
                last_bottom = max(i["y1"] for i in r)
            tables.append({"header": row, "label_head": label_head, "value_heads": value_heads, "x_left": x_left, "x_right": x_right, "rows": region})
    return tables


def _assign_column(value_item, value_heads):
    cx = (value_item["x0"] + value_item["x1"]) / 2
    best, dist = None, 1e9
    for idx, h in enumerate(value_heads):
        d = 0 if h["x0"] - 24 <= cx <= h["x1"] + 24 else min(abs(cx - h["x0"]), abs(cx - h["x1"]))
        if d < dist:
            best, dist = idx, d
    return best if dist < 40 else None


def _strip_marks(text):
    t = SECTION_MARK.sub("", text.strip(), count=1) if SECTION_MARK.match(text.strip()) else text.strip()
    return ITEM_MARK.sub("", t, count=1).strip()


def build_table(tbl):
    """Rows -> structured rows with sections and totals. Pure geometry/typography; no entity inference beyond the section heading."""
    rows, section_row, warnings = [], None, []
    for cluster in tbl["rows"]:
        cluster = sorted(cluster, key=lambda i: i["x0"])
        values, labels = {}, []
        for it in cluster:
            col = _assign_column(it, tbl["value_heads"]) if NUMBER.match(it["text"]) else None
            if col is not None:
                if col in values:
                    warnings.append(f"two values in one cell at y={it['y0']}: {values[col]['text']!r} and {it['text']!r}")
                values[col] = it
            else:
                labels.append(it)
        label_text = " ".join(" ".join(i["text"].split()) for i in labels)
        label_block = labels[0]["block"] if labels else None
        if not values:
            if not labels:
                continue
            prev = rows[-1] if rows else None
            # a wrapped label line overlaps the line above it (tight leading); a new row has a positive gap
            continuation = prev is not None and prev["kind"] != "section" and (labels[0]["block"] == prev["label_block"] or labels[0]["x0"] > tbl["x_left"] + 6) and labels[0]["y0"] - prev["label_y1"] < 0
            if continuation:
                prev["label_raw"] += " " + label_text; prev["wrapped"] = True; prev["y1"] = max(prev["y1"], max(i["y1"] for i in labels)); prev["label_y1"] = max(i["y1"] for i in labels)
                continue
            rows.append({"kind": "section", "label_raw": label_text, "label_block": label_block, "numeral": (SECTION_MARK.match(label_text.strip()) or [None])[0], "y0": cluster[0]["y0"], "y1": max(i["y1"] for i in labels), "label_y1": max(i["y1"] for i in labels), "bold": all(i["bold"] for i in labels), "values": {}})
            section_row = len(rows) - 1
            continue
        total = bool(TOTAL_LABEL.match(_strip_marks(label_text)))
        rows.append({"kind": "total" if total else "item", "label_raw": label_text, "label_first_line": label_text, "label_block": label_block, "y0": min(i["y0"] for i in cluster), "y1": max(i["y1"] for i in cluster), "values": values, "section_row": section_row, "label_y1": max(i["y1"] for i in labels) if labels else max(i["y1"] for i in cluster), "wrapped": False, "bold": all(i["bold"] for i in cluster if i in values.values())})
    # a wrapped label can sit one line below its value; merge label-only rows that share a block with a value row (handled above) done.
    return rows, warnings


def classify_scope(section_label):
    if not section_label:
        return None, None
    hits = [(name, m.group(0)) for name, rx in SCOPE_PATTERNS for m in [rx.search(section_label)] if m]
    names = {n for n, _ in hits}
    if len(names) == 1:
        return hits[0]
    return ("unresolved", None) if names else (None, None)


def parse_as_on(text):
    m = AS_ON.search(text or "")
    if not m or m.group(2).lower() not in MONTHS:
        return None
    try:
        return dt.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
    except ValueError:
        return None


def _intro_text(layout, tbl):
    """The block directly above the table in the same column (structural adjacency, not a text search of the page)."""
    top = tbl["label_head"]["y0"]
    cands = [b for b in layout["blocks"] if b["bbox"][3] <= top + 2 and b["bbox"][3] > top - 60 and b["bbox"][0] < tbl["x_right"] and b["bbox"][2] > tbl["x_left"]]
    if not cands:
        return None
    b = max(cands, key=lambda c: c["bbox"][3])
    return " ".join(l["text"].strip() for l in b["lines"])


def _status_from_text(text):
    t = (text or "").lower()
    if "under implementation" in t or "under construction" in t:
        return "under_implementation"
    return None


def table_structure(layout, *, printed=None):
    out = []
    for ti, tbl in enumerate(find_tables(layout)):
        rows, warns = build_table(tbl)
        sections = [r for r in rows if r["kind"] == "section"]
        mid = (tbl["x_left"] + tbl["x_right"]) / 2
        side = "left" if mid < layout["width"] / 2 else "right"
        printed = printed if printed is not None else printed_labels(layout)
        out.append({"index": ti, "title": tbl["label_head"]["text"], "column_headers": [h["text"] for h in tbl["value_heads"]], "bbox": [tbl["x_left"], tbl["label_head"]["y0"], tbl["x_right"], max((r["y1"] for r in rows), default=tbl["label_head"]["y1"])],
                    "printed_page_label": printed.get(side), "intro_text": _intro_text(layout, tbl), "rows": rows, "n_sections": len(sections), "warnings": warns, "_tbl": tbl})
    return out


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "unlabelled"


def _tolerance_equal(a, b, tol=0.51):
    return abs(a - b) <= tol


def tie_out(rows):
    """Arithmetic checks on totals, per value column. A grand total equals the sum of the section totals above it; any other total
    equals the sum of the item rows of its own section. A check is evidence about table structure, never about truth."""
    checks, items_by_section, section_totals, totals_seen = {}, {}, {}, set()
    for i, r in enumerate(rows):
        if r["kind"] == "item":
            items_by_section.setdefault(r["section_row"], []).append((i, r))
    for i, r in enumerate(rows):
        if r["kind"] != "total":
            continue
        checks[i] = {}
        for col, cell in r["values"].items():
            v = _num(cell["text"])
            if v is None:
                continue
            prior = section_totals.get(col, [])
            if len(prior) >= 2 and _tolerance_equal(sum(x for _, x in prior), v):
                checks[i][col] = {"kind": "sum_of_section_totals", "components": [j for j, _ in prior], "sum": sum(x for _, x in prior), "ok": True}
                continue
            if (r["section_row"], col) in totals_seen:
                # a second total under one heading is not that heading's total; without the grand-total tie-out its owner is unknown
                checks[i][col] = {"kind": "second_total_in_section", "components": [], "sum": None, "ok": False}
                continue
            totals_seen.add((r["section_row"], col))
            comp = [(j, _num(x["values"][col]["text"])) for j, x in items_by_section.get(r["section_row"], []) if col in x["values"]]
            if comp:
                total = sum(c for _, c in comp)
                checks[i][col] = {"kind": "section_sum", "components": [j for j, _ in comp], "sum": total, "ok": _tolerance_equal(total, v)}
                if checks[i][col]["ok"]:
                    section_totals.setdefault(col, []).append((i, v))
    return checks


def claims_from_table(table, *, doc, pdf_page_index, entity, entity_status, linked_evidence_id=None, evidence_records=(), layout=None):
    rows = table["rows"]
    checks = tie_out(rows)
    sections = [r for r in rows if r["kind"] == "section"]
    claims = []
    unit_cells = {i: UNIT_HEADER.search(h) for i, h in enumerate(table["column_headers"])}
    for ri, r in enumerate(rows):
        if r["kind"] == "section":
            continue
        for col, cell in sorted(r["values"].items()):
            notes = list(table["warnings"])
            header = table["column_headers"][col]
            um = unit_cells.get(col)
            unit = UNIT_CANON.get(um.group(1).lower().replace(" ", "")) if um else None
            if um and unit is None:
                unit = "INR crore" if "crore" in um.group(1).lower() else None
            if unit is None:
                notes.append("column header carries no recognised unit")
            value = _num(cell["text"])
            if value is None:
                notes.append("cell text is not a parseable number")
            sec = rows[r["section_row"]] if r.get("section_row") is not None else None
            grand = False
            chk = checks.get(ri, {}).get(col)
            if r["kind"] == "total" and chk and chk["kind"] == "section_sum" and chk["ok"] and sec is not None and re.search(r"\(\s*[IVX]+\s*\)\s*\+\s*\(\s*[IVX]+\s*\)", r["label_raw"]):
                notes.append("label names a combination of sections but the value equals its own section's sum")
            scope, scope_evidence = (None, None)
            if r["kind"] == "total" and chk and chk["kind"] == "sum_of_section_totals" and chk["ok"]:
                scope, scope_evidence, grand = "group", "total equals the sum of the section totals above it" + (" (and its label names both sections)" if re.search(r"\(\s*[IVX]+\s*\)\s*\+\s*\(\s*[IVX]+\s*\)", r["label_raw"]) else ""), True
            elif sec is not None and r["kind"] == "total" and chk and chk["kind"] == "second_total_in_section":
                scope = "unresolved"
            elif sec is not None:
                s, ev = classify_scope(sec["label_raw"])
                scope, scope_evidence = s, (f"section heading {sec['label_raw'].strip()!r} matched {ev!r}" if ev else None)
                if s == "unresolved":
                    notes.append(f"section heading {sec['label_raw'].strip()!r} names both parent and JV/subsidiary wording")
                if s is None:
                    scope = "unresolved"; notes.append(f"section heading {sec['label_raw'].strip()!r} does not identify an owner")
            else:
                scope = "unresolved"; notes.append("row is not under a section heading, so its ownership scope is not stated by the table")
            if r["kind"] == "total" and chk is None:
                notes.append("total row could not be tied out against its components")
            elif chk and chk["kind"] == "second_total_in_section":
                notes.append("second total under the same heading that is not the sum of the section totals; its owner cannot be determined")
            elif chk and not chk["ok"]:
                notes.append(f"total does not equal the sum of its components ({chk['sum']} vs {value})")
            period_unsure = False
            period = parse_as_on(r["label_raw"]); period_src = "row label"
            intro_points_here = bool(POINTER.search(table.get("intro_text") or ""))
            if not period:
                period = parse_as_on(table.get("intro_text")); period_src = "paragraph directly above the table"
                if period:
                    notes.append("period taken from the paragraph directly above the table, not from the table itself")
                    if not intro_points_here:
                        notes.append("that paragraph does not point at the table ('as under', 'given below'), so the period may not apply to it"); period_unsure = True
            if not period:
                notes.append("no 'as on' date found in the row label or the paragraph above the table")
            status_word = _status_from_text(table.get("intro_text"))
            raw_label = " ".join(r["label_raw"].split())
            ok = unit and value is not None and not period_unsure and scope in ("parent_owned", "jv_subsidiary", "group") and period and (not chk or chk["ok"]) and not table["warnings"]
            status = "extracted" if ok else ("ambiguous" if value is not None and (unit or scope not in (None, "unresolved")) else "needs_review")
            if scope == "jv_subsidiary":
                notes.append("JV and subsidiary figures are combined in this table; they are not NTPC's economic ownership share and cannot be split")
            cid = "pdfn_" + hashlib.sha256(f"{doc['sha256']}|{pdf_page_index}|{table['index']}|{ri}|{col}|{cell['text']}".encode()).hexdigest()[:24]
            x0, y0, x1, y1 = cell["x0"], cell["y0"], cell["x1"], cell["y1"]
            claims.append({
                "schema_version": "1.2", "claim_id": cid, "entity": entity, "entity_identity_status": entity_status, "metric": _slug(_strip_marks(raw_label)),
                "raw_metric_text": raw_label, "value": value, "raw_value_text": cell["text"], "unit": unit, "raw_unit_text": header,
                "period_type": "as_of" if period else "unknown", "period_start": None, "period_end": None, "as_of_date": period, "raw_period_text": (AS_ON.search(r["label_raw"]) or AS_ON.search(table.get("intro_text") or "") or [None])[0],
                "source_document_id": doc["document_id"], "source_path": doc["path"], "source_page": pdf_page_index, "source_chunk_id": linked_evidence_id or link_by_value(evidence_records, Path(doc["path"]).stem, pdf_page_index, cell["text"]),
                "source_excerpt": f"{' '.join(r['label_first_line'].split())} {cell['text']}",
                "extraction_status": status, "ambiguity_notes": "; ".join(notes) or None, "claim_verification_status": "unverified", "parser_version": PARSER_VERSION,
                "extraction_method": "pdf_native_table", "chunk_class": "tabular", "source_row_text": f"{raw_label} {cell['text']}", "source_header_text": f"{table['title']} | {header}", "row_index": ri, "column_index": col, "reversal_applied": False,
                "source_sha256": doc["sha256"], "printed_page_label": table["printed_page_label"], "table_title": table["title"], "section_heading": " ".join(sec["label_raw"].split()) if sec is not None and not grand else None,
                "table_section_headings": [" ".join(x["label_raw"].split()) for x in sections], "row_label_first_line": " ".join(r["label_first_line"].split()), "ownership_scope": scope, "scope_evidence": scope_evidence, "project_status": status_word, "row_kind": r["kind"],
                "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                "tie_out": ({"kind": chk["kind"], "sum": chk["sum"], "ok": chk["ok"]} if chk else None), "period_source": period_src if period else None})
    return claims


def extract_pages(pdf_path, pages, *, entity, entity_status, evidence_records=(), pdf_sha256=None):
    """Extract claims from 1-based PDF page indexes. `evidence_records` links a claim to the existing Step 6 evidence chunk of the same
    document stem and page when exactly one such record exists (needed for downstream verification); otherwise the link stays null."""
    try:
        import pymupdf
    except ImportError as e:
        raise RuntimeError("PDF-native extraction needs PyMuPDF (python -m pip install pymupdf)") from e
    p = Path(pdf_path); sha = pdf_sha256 or sha256_file(p)
    doc = {"sha256": sha, "path": p.name, "document_id": "pdfdoc_" + sha[:16]}
    pdf = pymupdf.open(str(p)); out, report = [], {"pdf": p.name, "sha256": sha, "pages": []}
    for pn in pages:
        layout = layout_from_page(pdf[pn - 1])
        link = _linked_evidence(evidence_records, p.stem, pn)  # page-level link, reported only; each claim is linked by its own value
        tables = table_structure(layout)
        report["pages"].append({"pdf_page_index": pn, "printed_labels": printed_labels(layout), "tables": [{"title": t["title"], "headers": t["column_headers"], "rows": len(t["rows"]), "sections": t["n_sections"], "printed_page_label": t["printed_page_label"], "warnings": t["warnings"]} for t in tables], "linked_evidence_id": link})
        for t in tables:
            out += claims_from_table(t, doc=doc, pdf_page_index=pn, entity=entity, entity_status=entity_status, evidence_records=evidence_records, layout=layout)
    seen, uniq = set(), []
    for c in out:
        if c["claim_id"] in seen:
            continue
        seen.add(c["claim_id"]); uniq.append(c)
    report["claims_linked_to_evidence"] = sum(bool(c["source_chunk_id"]) for c in uniq); report["claims"] = len(uniq); report["duplicates_dropped"] = len(out) - len(uniq)
    return uniq, report


def link_by_value(records, stem, page, raw_value):
    """The Step 6 evidence chunk of the same document stem and page whose text contains this cell's printed value, if exactly one does.
    A page can have several chunks; a value that appears in none or in more than one is left unlinked rather than guessed."""
    rx = re.compile(r"(?<![\d,.])" + re.escape(raw_value.strip()) + r"(?![\d,]|\.\d)")
    hits = [r["evidence_id"] for r in records if Path(str(r.get("source_path") or "")).stem == stem and r.get("page_number") == page and rx.search(r.get("excerpt_or_fact") or "")]
    return hits[0] if len(hits) == 1 else None


def _linked_evidence(records, stem, page):
    hits = [r["evidence_id"] for r in records if Path(str(r.get("source_path") or "")).stem == stem and r.get("page_number") == page]
    return hits[0] if len(hits) == 1 else None


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdf", required=True); ap.add_argument("--pages", required=True, help="comma-separated 1-based PDF page indexes, e.g. 90,91,112")
    ap.add_argument("--company", required=True); ap.add_argument("--registry"); ap.add_argument("--evidence", help="Step 6 evidence.jsonl, used only to link a claim to its page's evidence chunk")
    ap.add_argument("--expected-sha256", help="refuse to run if the PDF hash differs"); ap.add_argument("--output-dir", required=True)
    a = ap.parse_args(argv)
    out_dir = Path(a.output_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"{out_dir} exists and is not empty; choose a new output directory")
    sha = sha256_file(a.pdf)
    if a.expected_sha256 and sha != a.expected_sha256:
        raise SystemExit(f"PDF hash {sha} != expected {a.expected_sha256}")
    status, canonical = "unresolved", a.company
    if a.registry:
        from .evidence_ingestion import load_registry, verify_company
        canon, _, st = verify_company(a.company, load_registry(a.registry))
        if st == "verified": status, canonical = "verified", canon
    recs = [json.loads(l) for l in Path(a.evidence).read_text(encoding="utf-8").splitlines() if l.strip()] if a.evidence else []
    claims, report = extract_pages(a.pdf, [int(x) for x in a.pages.split(",")], entity=canonical, entity_status=status, evidence_records=recs, pdf_sha256=sha)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "claims.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in claims), encoding="utf-8")
    report["status_counts"] = {s: sum(c["extraction_status"] == s for c in claims) for s in ("extracted", "ambiguous", "needs_review")}
    (out_dir / "extraction_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(claims)} claims from {len(report['pages'])} page(s): {report['status_counts']}; all unverified. Output: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
