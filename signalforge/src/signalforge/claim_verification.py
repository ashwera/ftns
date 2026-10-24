"""Source verification, separate from extraction.

An assertion (value/unit/period/basis/status/label terms, normally derived from a claim and sometimes supplied by an
analyst) is checked against the cited source passage. A matching number alone is never enough: entity, unit/scale,
metric definition, period, basis and actual-vs-target status are each checked, and every outcome carries a rationale.
The level is `extracted_text_review` unless the passage comes from a retrieved primary source (`primary_source`).
Claims themselves are never modified.
"""
import re

from . import claim_extraction as L1
from .pipeline_contract import OUTCOMES, collapse, sha256_text, validate_against

SOURCE_LIMITS = {"extracted_text_review": ["The passage is the project's own text extraction of the filing; the original PDF/official URL was not checked. This is not primary-source verification."],
                 "primary_source": []}
def _blank(result="unresolved", detail=""): return {"result": result, "detail": detail}

def _numbers_in(text):
    out = []
    for m in L1.QTY.finditer(text):
        if not m.group("cur") and not m.group("unit"): continue
        v = L1._number(m.group("num"))
        if v is not None: out.append((m.start(), m.end(), v, m.group("unit"), m))
    return out

def _unit_matches(want, raw_unit, cur):
    if want is None: return None
    raw = (raw_unit or "")
    norm = L1.UNIT_NORMAL.get(raw.lower(), L1.UNIT_NORMAL.get(raw, raw))
    if want.startswith("INR"):
        scale = want.split(" ", 1)[1] if " " in want else None
        if not cur and not re.search(r"(?i)rs|₹|inr|`", raw): return False
        return True if scale is None else raw.lower().rstrip("s") == scale
    return norm == want or raw == want

def _sentence_span(text, position):
    """Return the sentence and its bounds for a character position in collapsed text."""
    cursor = 0
    for sentence in L1._sentences(text):
        start = text.find(sentence, cursor)
        if start < 0:
            continue
        end = start + len(sentence)
        if start <= position < end:
            return start, end, sentence
        cursor = end
    start = max(0, position - 160); end = min(len(text), position + 160)
    return start, end, text[start:end]

def _label_proximity(sentence, number_pos, label_terms):
    """Rank sentence-local value hits by label coverage, then nearest label distance."""
    distances = []
    low = sentence.lower()
    for term in label_terms:
        term_low = term.lower()
        positions = [m.start() for m in re.finditer(re.escape(term_low), low)]
        if positions:
            distances.append(min(abs(p - number_pos) for p in positions))
    return (-len(distances), min(distances, default=float("inf")))

def verify_assertion(assertion, passage, *, source=None, level="extracted_text_review", verification_id, input_name, claim_id=None, reviewer=None, cross_checks=()):
    """Check an assertion against passage text. Returns a verification_result dict (schema-validated)."""
    text = collapse(passage); a = assertion
    src = {"source_chunk_id": None, "source_path": None, "page": None, "url": None, "publisher": None, "publication_date": None, "retrieved_at": None, "document_family": None}; src.update(source or {})
    src.update({"passage": text[:4000], "passage_sha256": sha256_text(text)})
    checks = {k: _blank() for k in ("entity", "value", "unit_scale", "metric_definition", "period", "basis", "statement_status")}
    discrepancies = []
    hits = [h for h in _numbers_in(text) if abs(h[2] - a["value"]) < 1e-9 * max(1, abs(a["value"]))]
    if not hits:
        # same label near a different number for the same period => contradiction; otherwise unable to verify
        others = []
        for pos, end, v, unit, m in _numbers_in(text):
            ctx = text[max(0, pos - 120):end + 40].lower()
            if a["label_terms"] and all(t.lower() in ctx for t in a["label_terms"]) and (not a["period_text"] or a["period_text"].lower() in ctx): others.append(v)
        if others:
            checks["value"] = _blank("mismatch", f"passage gives {sorted(set(others))} for the same label/period, not {a['value']}"); discrepancies.append(f"value {a['value']} vs passage {sorted(set(others))}")
            outcome, why = "contradicted", f"The passage states {sorted(set(others))} for the asserted label and period, which differs from {a['value']}."
        else:
            checks["value"] = _blank("unresolved", "asserted value not found in the passage"); outcome, why = "unable_to_verify", f"The value {a['value']} does not appear with a unit in the cited passage."
        return _finish(a, src, checks, discrepancies, outcome, why, level, verification_id, input_name, claim_id, reviewer, [])
    # Select within each value's own sentence so names and labels in adjacent
    # sentences cannot change entity attribution. Prefer label coverage, then
    # the occurrence closest to the asserted metric label.
    best, best_rank, best_ctx, best_sentence = None, None, "", ""
    for pos, end, v, unit, m in hits:
        sentence_start, _, sentence = _sentence_span(text, pos)
        ctx = text[max(0, pos - 160):end + 160]
        rank = _label_proximity(sentence, pos - sentence_start, a["label_terms"])
        if best_rank is None or rank < best_rank:
            best, best_rank, best_ctx, best_sentence = (pos, end, v, unit, m), rank, ctx, sentence
    pos, end, v, unit, m = best; before, after = text[max(0, pos - 160):pos], text[end:end + 160]
    checks["value"] = _blank("match", f"{a['value']} found in the passage")
    # unit/scale
    if a["unit"] is None: checks["unit_scale"] = _blank("not_applicable", "no unit asserted")
    else:
        ok = _unit_matches(a["unit"], unit, m.group("cur"))
        if ok is True: checks["unit_scale"] = _blank("match", f"unit {unit!r} next to the number supports {a['unit']}")
        elif ok is False: checks["unit_scale"] = _blank("mismatch", f"passage unit {unit!r} does not support {a['unit']}"); discrepancies.append(f"unit {unit!r} != {a['unit']}")
        else: checks["unit_scale"] = _blank("unresolved", "no unit evaluated")
    # metric definition: asserted label terms must appear near the number
    if a["label_terms"]:
        missing = [t for t in a["label_terms"] if t.lower() not in best_sentence.lower()]
        checks["metric_definition"] = _blank("match", f"label terms {a['label_terms']} appear near the figure") if not missing else _blank("mismatch", f"label terms {missing} not found near the figure"); 
        if missing: discrepancies.append(f"label terms missing near value: {missing}")
    # period
    if a["as_of_date"] or a["period_text"]:
        periods = L1._periods(text[max(0, pos - 200):end + 200])
        want_date, want_text = a["as_of_date"], (a["period_text"] or "").lower()
        found_dates = {p["as_of"] or p["end"] for p in periods if (p["as_of"] or p["end"])}; found_raw = [p["raw"].lower() for p in periods]
        if (want_date and want_date in found_dates) or (want_text and any(want_text in r or r in want_text for r in found_raw)) or (want_text and want_text in best_ctx.lower()):
            checks["period"] = _blank("match", f"period {a['as_of_date'] or a['period_text']} appears with the figure")
        elif found_dates or found_raw:
            checks["period"] = _blank("mismatch", f"passage period(s) {sorted(found_dates) or found_raw} do not include {a['as_of_date'] or a['period_text']}"); discrepancies.append("period differs")
        else: checks["period"] = _blank("unresolved", "no period phrase near the figure")
    else: checks["period"] = _blank("not_applicable", "no period asserted")
    # basis
    grp, sta = L1._nearest(text, pos, end, L1.GROUP_WORDS, span=110), L1._nearest(text, pos, end, L1.STANDALONE_WORDS, span=110)
    jv = L1._nearest(text, pos, end, L1.JV_WORDS, span=110)
    near_basis = None if not (grp or sta) else ("group" if (grp and (not sta or grp[0] < sta[0])) else "standalone")
    if a["basis"] in (None, "not_applicable"): checks["basis"] = _blank("not_applicable", "no basis asserted")
    elif a["basis"] == "standalone":
        if near_basis == "standalone": checks["basis"] = _blank("match", "'standalone' is the nearest basis word")
        elif near_basis == "group": checks["basis"] = _blank("mismatch", f"nearest basis word is {grp[1]!r}"); discrepancies.append("basis: group/consolidated, not standalone")
        else: checks["basis"] = _blank("unresolved", "no basis word near the figure")
    elif a["basis"] in ("consolidated", "group"):
        if near_basis == "group": checks["basis"] = _blank("match", f"{grp[1]!r} is the nearest basis word")
        elif near_basis == "standalone": checks["basis"] = _blank("mismatch", "nearest basis word is 'standalone'"); discrepancies.append("basis: standalone, not group")
        else: checks["basis"] = _blank("unresolved", "no basis word near the figure")
    elif a["basis"] == "jv_subsidiary_part":
        checks["basis"] = _blank("match", f"{jv[1]!r} wording near the figure") if jv else _blank("unresolved", "no joint-venture/subsidiary wording near the figure")
    # statement status (actual vs target etc.)
    sent, cursor = best_ctx, 0
    for cand in L1._sentences(text):
        at = text.find(cand, cursor)
        if at < 0: continue
        if at <= pos < at + len(cand): sent = cand; break
        cursor = at + len(cand)
    fwd = L1.FORWARD.search(sent)   # forward-looking wording counts only inside the figure's own sentence
    st = a["statement_status"]
    if st is None: checks["statement_status"] = _blank("not_applicable", "no status asserted")
    elif st in ("target", "forecast"):
        checks["statement_status"] = _blank("match", f"forward-looking wording {fwd.group(0)!r}") if fwd else _blank("unresolved", "no target/forecast wording near the figure")
    elif fwd and st in ("actual", "commissioned", "under_implementation", "awarded") and not re.search(r"(?i)under implementation|under construction|awarded|commissioned", best_ctx):
        checks["statement_status"] = _blank("mismatch", f"forward-looking wording {fwd.group(0)!r} near a figure asserted as {st}"); discrepancies.append(f"status: forward-looking, not {st}")
    elif st == "under_implementation":
        checks["statement_status"] = _blank("match", "under implementation/construction wording present") if re.search(r"(?i)under (?:implementation|construction)|ongoing|on-going", best_ctx) else _blank("unresolved", "no implementation-status wording near the figure")
    elif st == "commissioned":
        checks["statement_status"] = _blank("match", "commissioned/commercial wording present") if re.search(r"(?i)commissioned|commercial|installed|operational", best_ctx) else _blank("unresolved", "no commissioning wording")
    else: checks["statement_status"] = _blank("match" if not fwd else "unresolved", "no forward-looking wording near the figure" if not fwd else f"forward wording {fwd.group(0)!r} present")
    # entity
    ent = a.get("entity")
    if not ent: checks["entity"] = _blank("not_applicable", "no entity asserted")
    else:
        own = {re.sub(r"[^a-z0-9]+", " ", n.lower()).strip() for n in a.get("entity_names", [ent])}
        target = L1.TargetCompany(ent, tuple(a.get("entity_names", ())))
        entity_ctx = best_sentence
        # Keep the existing nearby self-reference behavior where the value
        # sentence names no organization; explicit attribution stays sentence-local.
        if not L1.named_other_entities(entity_ctx, target) and not L1._self_ref_regex(target).search(entity_ctx):
            entity_ctx = best_ctx
        others = [p for _, p in L1.named_other_entities(entity_ctx, target)]
        has_self = bool(L1._self_ref_regex(target).search(entity_ctx))
        if others and not has_self: checks["entity"] = _blank("mismatch", f"other organization(s) named near the figure and no reference to the target: {sorted(set(others))[:4]}"); discrepancies.append("entity: other organization near figure")
        elif others: checks["entity"] = _blank("unresolved", f"both the target and other organization(s) {sorted(set(others))[:4]} are named near the figure; whose figure it is is not settled")
        elif has_self: checks["entity"] = _blank("match", "target/self-reference near the figure")
        else: checks["entity"] = _blank("unresolved", "no explicit subject near the figure")
    # cross-checks inside the passage (same-document internal consistency; never independent)
    cc = []
    for c in cross_checks:
        m2 = re.search(c["label_regex"] + r"\D{0,25}?(\d[\d,]*(?:\.\d+)?)", text)
        found = float(m2.group(1).replace(",", "")) if m2 else None
        cc.append({"description": c["description"], "expected_value": c["expected_value"], "found_value": found, "ok": found is not None and abs(found - c["expected_value"]) < 1e-9, "independent": False})
    bad = [k for k, v in checks.items() if v["result"] == "mismatch"]; unres = [k for k, v in checks.items() if v["result"] == "unresolved"]
    if bad: outcome, why = "contradicted", f"The passage contradicts the assertion on {bad}: " + "; ".join(discrepancies)
    elif unres:
        outcome = "partially_supported" if checks["value"]["result"] == "match" and checks["unit_scale"]["result"] in ("match", "not_applicable") else "unresolved"
        why = f"Value found, but {unres} could not be established from the passage."
    else: outcome, why = "confirmed", "Value, unit/scale, label terms, period, basis, status and entity are each supported by the cited passage."
    return _finish(a, src, checks, discrepancies, outcome, why, level, verification_id, input_name, claim_id, reviewer, cc)

def _finish(a, src, checks, discrepancies, outcome, why, level, vid, name, claim_id, reviewer, cross):
    assert outcome in OUTCOMES
    res = {"schema_version": "1.0", "verification_id": vid, "input_name": name, "claim_id": claim_id,
           "assertion": {k: a.get(k) for k in ("value", "unit", "period_type", "as_of_date", "period_text", "basis", "statement_status", "label_terms", "entity")},
           "outcome": outcome, "verification_level": level, "source": src, "checks": checks, "cross_checks": cross, "discrepancies": discrepancies, "rationale": why,
           "reviewer": reviewer or {"kind": "automated_passage_check", "id": "claim_verification.verify_assertion", "note": None}, "limitations": list(SOURCE_LIMITS[level])}
    validate_against(res, "verification_result"); return res

# ---------- table-cell claims (extraction_method == pdf_native_table)
_MARK = re.compile(r"^(?:[a-z]|\d{1,2})[\)\.]\s+", re.I)
_NUM = r"\(?-?\d[\d,]*(?:\.\d+)?\)?"
_ASON = re.compile(r"(?i)\bas\s+(?:on|at)\s+(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})")

def _flex(text):
    return r"\s*".join(re.escape(w) for w in text.split())

def _as_on_dates(text):
    import datetime as dt
    months = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
    out = []
    for m in _ASON.finditer(text):
        if m.group(2).lower() in months:
            try: out.append((m.start(), dt.date(int(m.group(3)), months[m.group(2).lower()], int(m.group(1))).isoformat()))
            except ValueError: pass
    return out

def table_cell_candidates(text, claim):
    """Occurrences of the claim's row label immediately followed by a number. Returns [(position, number)]."""
    out = []
    for raw in dict.fromkeys([claim.get("raw_metric_text") or "", claim.get("row_label_first_line") or ""]):  # a wrapped label may read in order only up to its first line
        label = _MARK.sub("", " ".join(raw.split()), count=1)
        if not label: continue
        rx = re.compile(r"(?i)" + _flex(label) + r"\s{0,3}(" + _NUM + ")")
        out += [(m.start(), L1._number(m.group(1).strip("()"))) for m in rx.finditer(text) if (m.start(), L1._number(m.group(1).strip("()"))) not in out]
    return out

def verify_table_cell(a, claim, passage, *, source=None, level="extracted_text_review", verification_id, input_name, claim_id=None, reviewer=None):
    """Check a PDF-native table-cell claim against a source passage in reading order: the row label must be followed by the value, the
    column header (carrying the unit) and the table title must precede it, the nearest preceding section heading must be the claimed one,
    and an 'as on' date and implementation wording must precede the table. Nothing here uses the claim's own coordinates, so it is a check
    of the source text, not a replay of the extraction. The entity stays unresolved: a table row carries no explicit entity statement."""
    text = collapse(passage)
    src = {"source_chunk_id": None, "source_path": None, "page": None, "url": None, "publisher": None, "publication_date": None, "retrieved_at": None, "document_family": None}; src.update(source or {})
    src.update({"passage": text[:4000], "passage_sha256": sha256_text(text)})
    checks = {k: _blank() for k in ("entity", "value", "unit_scale", "metric_definition", "period", "basis", "statement_status")}
    discrepancies, headings = [], [h for h in (claim.get("table_section_headings") or []) if h]
    want_head = claim.get("section_heading")
    def heading_before(pos):
        best = None
        for h in headings:
            for m in re.finditer(_flex(h), text):
                if m.start() < pos and (best is None or m.start() > best[0]): best = (m.start(), h)
        return best[1] if best else None
    cands = table_cell_candidates(text, claim)
    exact = [(p, v) for p, v in cands if abs((v or 0) - a["value"]) < 1e-9]
    placed = [c for c in exact if want_head is None or heading_before(c[0]) == want_head]
    if placed: pos = placed[0][0]
    elif exact:
        pos = exact[0][0]; under = heading_before(pos)
        checks["value"] = _blank("match", f"{a['value']} follows the row label")
        if under is None: checks["basis"] = _blank("unresolved", f"no known section heading precedes the value in this passage (claimed heading {want_head!r}); a passage that starts below the heading cannot settle the scope")
        else: checks["basis"] = _blank("mismatch", f"the value sits under heading {under!r}, not {want_head!r}"); discrepancies.append(f"scope: value under {under!r}, not {want_head!r}")
    else:
        same_section = [(p, v) for p, v in cands if want_head is None or heading_before(p) == want_head]
        if same_section:
            checks["value"] = _blank("mismatch", f"row label is followed by {sorted({v for _, v in same_section})} under the claimed heading, not {a['value']}"); discrepancies.append(f"value {a['value']} vs {sorted({v for _, v in same_section})}")
            return _finish(a, src, checks, discrepancies, "contradicted", f"The row label is followed by a different number under the same heading: {discrepancies[-1]}.", level, verification_id, input_name, claim_id, reviewer, [])
        checks["value"] = _blank("unresolved", "row label followed by the asserted value not found in the passage")
        return _finish(a, src, checks, discrepancies, "unable_to_verify", f"The row '{claim.get('raw_metric_text')}' followed by {a['value']} does not appear in the cited passage.", level, verification_id, input_name, claim_id, reviewer, [])
    if checks["value"]["result"] != "match": checks["value"] = _blank("match", f"{a['value']} follows the row label '{claim.get('raw_metric_text')}'")
    checks["metric_definition"] = _blank("match", "the asserted row label is immediately followed by the value")
    head_cell = (claim.get("source_header_text") or "").split(" | ")
    title, col = (head_cell[0], head_cell[-1]) if len(head_cell) > 1 else (None, head_cell[0] if head_cell and head_cell[0] else None)
    hdr = re.compile(_flex(f"{title} {col}") if title else _flex(col)) if col else None
    hdr_hits = [m for m in hdr.finditer(text) if m.start() < pos] if hdr else []
    if a["unit"] is None: checks["unit_scale"] = _blank("not_applicable", "no unit asserted")
    elif hdr_hits and re.search(r"\(\s*" + re.escape(a["unit"]) + r"\s*\)", hdr_hits[-1].group(0)): checks["unit_scale"] = _blank("match", f"column header {hdr_hits[-1].group(0)!r} precedes the value and declares {a['unit']}")
    elif hdr_hits: checks["unit_scale"] = _blank("mismatch", f"column header {hdr_hits[-1].group(0)!r} does not declare {a['unit']}"); discrepancies.append("unit: header differs")
    else: checks["unit_scale"] = _blank("unresolved", "column header not found before the value")
    table_start = hdr_hits[-1].start() if hdr_hits else max(0, pos - 1500)
    window = text[max(0, table_start - 1800):table_start]
    dates = _as_on_dates(text[max(0, table_start - 1800):pos + 200])
    if a["as_of_date"] is None: checks["period"] = _blank("not_applicable", "no period asserted")
    elif dates and dates[-1][1] == a["as_of_date"]: checks["period"] = _blank("match", f"'as on' date {a['as_of_date']} precedes the table")
    elif dates: checks["period"] = _blank("mismatch", f"nearest 'as on' date is {dates[-1][1]}"); discrepancies.append("period differs")
    else: checks["period"] = _blank("unresolved", "no 'as on' date before the table")
    st = a["statement_status"]
    if st is None: checks["statement_status"] = _blank("not_applicable", "no status asserted")
    elif st == "under_implementation": checks["statement_status"] = _blank("match", "'under implementation' wording precedes the table") if re.search(r"(?i)under (?:implementation|construction)|on-?going", window + " " + text[table_start:pos]) else _blank("unresolved", "no implementation wording before the table")
    else: checks["statement_status"] = _blank("unresolved", f"status {st!r} not testable from table position")
    scope_expected = {"standalone": "parent_owned", "jv_subsidiary_part": "jv_subsidiary", "group": "group", "consolidated": "group"}.get(a["basis"])
    if checks["basis"]["result"] == "unresolved" and checks["basis"]["detail"].startswith("no known section heading"): pass
    elif checks["basis"]["result"] != "mismatch":
        if scope_expected and claim.get("ownership_scope") not in (None, scope_expected): checks["basis"] = _blank("mismatch", f"asserted basis {a['basis']!r} implies {scope_expected}, table scope is {claim.get('ownership_scope')}"); discrepancies.append("basis differs from table scope")
        elif want_head is not None and heading_before(pos) == want_head: checks["basis"] = _blank("match", f"nearest preceding section heading is {want_head!r}")
        elif want_head is None and claim.get("ownership_scope") == "group": checks["basis"] = _blank("match", "total row names both sections")
        else: checks["basis"] = _blank("unresolved", "section heading not located before the value")
    checks["entity"] = _blank("unresolved", "a table row carries no explicit entity statement; the reporting entity is only implied by the document")
    bad = [k for k, v in checks.items() if v["result"] == "mismatch"]; unres = [k for k, v in checks.items() if v["result"] == "unresolved"]
    if bad: outcome, why = "contradicted", f"The passage contradicts the assertion on {bad}: " + "; ".join(discrepancies)
    elif unres: outcome, why = "partially_supported", f"Row, value and unit found, but {unres} could not be established from the passage."
    else: outcome, why = "confirmed", "Row label, value, unit, period, scope heading and status are each supported by the cited passage."
    return _finish(a, src, checks, discrepancies, outcome, why, level, verification_id, input_name, claim_id, reviewer, [])


def assertion_from_claim(claim, *, basis=None, statement_status=None, label_terms=None, entity_names=()):
    return {"value": claim["value"], "unit": claim["unit"], "period_type": claim["period_type"], "as_of_date": claim["as_of_date"], "period_text": claim["raw_period_text"], "basis": basis,
            "statement_status": statement_status, "label_terms": list(label_terms if label_terms is not None else ([claim["raw_metric_text"]] if claim.get("raw_metric_text") else [])), "entity": claim["entity"], "entity_names": list(entity_names)}

# ---------- locating the passage for an assertion inside a source document
def _indian(n):
    s = f"{int(n)}"
    if len(s) <= 3: return s
    head, tail = s[:-3], s[-3:]; parts = []
    while len(head) > 2: parts.insert(0, head[-2:]); head = head[:-2]
    if head: parts.insert(0, head)
    return ",".join(parts + [tail])

def value_variants(value):
    """Textual forms of a number as filings print it (western or Indian grouping, with/without trailing zeros)."""
    out = set()
    if float(value).is_integer():
        n = int(value); out |= {f"{n:,}", _indian(n), str(n)}
    else:
        for d in (1, 2, 3):
            out.add(f"{value:,.{d}f}".rstrip("0").rstrip(".") if f"{value:.{d}f}".rstrip("0") != f"{value:.{d}f}" else f"{value:,.{d}f}"); out.add(f"{value:.{d}f}")
        out.add(str(value))
    return sorted(out, key=len, reverse=True)

def locate_passages(pages, value, label_terms, window=1200):
    """Sentence passages containing the value, ranked by label proximity."""
    hits = []
    for pg in pages:
        text = collapse(pg["text"])
        for v in value_variants(value):
            for m in re.finditer(r"(?<![\d,.])" + re.escape(v) + r"(?![\d]|,\d)", text):
                sentence_start, _, ctx = _sentence_span(text, m.start())
                number_pos = m.start() - sentence_start
                coverage, distance = _label_proximity(ctx, number_pos, label_terms)
                hits.append((coverage, distance, m.start(), pg["page"], ctx))
    hits.sort(key=lambda h: (h[0], h[1], h[2]))
    seen, out = set(), []
    for coverage, distance, _, page, ctx in hits:
        if (page, ctx[:80]) in seen: continue
        seen.add((page, ctx[:80])); out.append({"page": page, "passage": ctx, "label_score": -coverage, "label_distance": distance})
    return out

def label_windows(pages, label_terms, window=700):
    """Windows around occurrences of ALL label terms (used when the asserted value is absent, to detect a different value for the same label)."""
    out = []
    if not label_terms: return out
    for pg in pages:
        text = collapse(pg["text"]); low = text.lower()
        for m in re.finditer(re.escape(label_terms[0].lower()), low):
            ctx = text[max(0, m.start() - window // 2):m.end() + window // 2]
            if all(t.lower() in ctx.lower() for t in label_terms): out.append({"page": pg["page"], "passage": ctx})
    return out

# ---------- combining per-source results for one input
def combine_results(results):
    """results: verification_result dicts for ONE input (one per source, plus the extracted-text-review baseline).
    Primary-source results decide; a primary confirmation next to a primary contradiction is a conflict (never averaged)."""
    prim = [r for r in results if r["verification_level"] == "primary_source"]
    base = [r for r in results if r["verification_level"] != "primary_source"]
    conf = [r for r in prim if r["outcome"] == "confirmed"]; contra = [r for r in prim if r["outcome"] == "contradicted"]
    part = [r for r in prim if r["outcome"] == "partially_supported"]
    if conf and contra: outcome, level, conflict, why = "partially_supported", "primary_source", True, "primary sources disagree: confirmed by " + ", ".join(r["source"]["document_family"] or "?" for r in conf) + "; contradicted by " + ", ".join(r["source"]["document_family"] or "?" for r in contra)
    elif conf: outcome, level, conflict, why = "confirmed", "primary_source", False, f"confirmed against {len(conf)} primary-source document(s)"
    elif contra: outcome, level, conflict, why = "contradicted", "primary_source", False, "contradicted by a primary source: " + "; ".join(contra[0]["discrepancies"])
    elif part: outcome, level, conflict, why = "partially_supported", "primary_source", False, "primary source supports the value but not every check"
    elif base: outcome, level, conflict, why = base[0]["outcome"], "extracted_text_review", False, "no primary source located the value; only the project's text extraction was reviewed"
    else: outcome, level, conflict, why = "unable_to_verify", "extracted_text_review", False, "no verification result"
    rep = (conf or contra or part or base or [None])[0]
    return {"outcome": outcome, "level": level, "conflict": conflict, "reason": why, "representative": rep, "confirming": [r["verification_id"] for r in conf], "contradicting": [r["verification_id"] for r in contra]}

# ---------- independence and corroboration
def assess_independence(sources):
    """sources: dicts with publisher, document_family, sha256, derived_from, optional issuer_submitted (exchange/regulator-hosted copies of the issuer's own filing).
    Mirrors (same hash), same publisher, issuer-submitted filings and derived-from relationships count once."""
    unique = {}
    for s in sources: unique.setdefault(s.get("sha256") or s.get("document_family") or id(s), s)
    items = list(unique.values()); dropped_mirrors = len(sources) - len(items)
    def group(s): return "__issuer__" if s.get("issuer_submitted") else s.get("publisher")
    chosen = []
    for s in items:
        if not any(group(s) == group(t) or s.get("document_family") in (t.get("derived_from") or []) or t.get("document_family") in (s.get("derived_from") or []) for t in chosen): chosen.append(s)
    return {"distinct_documents": len(items), "mirror_copies_removed": dropped_mirrors, "independent_source_count": len(chosen),
            "note": "Same publisher, issuer-submitted copies and derived-from relationships count once; this is not statistical independence."}
