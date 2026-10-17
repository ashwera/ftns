"""Layer 1: deterministic structured claim extraction from ingested evidence chunks.

Extracts candidate claims only. It does not verify, approve, reconcile, rank, or compute anything,
and it never feeds the F1 eligibility gate. Claims always carry claim_verification_status "unverified".
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .config import ROOT, Config
from .f1_research_angle_selector import validate_output

RANK = {"extracted": 0, "ambiguous": 1, "needs_review": 2}
PARSER_VERSION = "layer1-deterministic-0.2.0"
SCHEMA_VERSION = "1.0"
OUTPUT_FILES = ("claims.jsonl", "extraction_report.json", "review_queue.jsonl")

NUM = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?"
UNITS = r"(?i:percentage points?|percent|per cent|basis points|crores?|lakhs?|million units|million tonnes|million|billion)|%|bps|MWe|MWh|GWh|kWh|MW|GW|kW|MUs?|BU|MMT|MT"
QTY = re.compile(rf"(?<![A-Za-wyz0-9_.,])(?P<cur>₹|`|Rs\.?|INR)?[ ]?(?P<open>\()?(?P<neg>[-−–])?(?P<num>{NUM})(?P<close>\))?[ ]?(?P<unit>{UNITS})?(?!\w)")
MONTH = r"(?i:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
DATE = rf"(?:(?P<d>\d{{1,2}})(?:st|nd|rd|th)?[ ,]*(?P<m>{MONTH})[a-z]*\.?[ ,]*(?P<y>\d{{4}})|(?P<m2>{MONTH})[a-z]*\.?[ ]*(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?,?[ ]*(?P<y2>\d{{4}})|(?P<dd>\d{{1,2}})[./-](?P<mm>\d{{2}})[./-](?P<yy>\d{{4}}))"
PHRASE = re.compile(rf"(?P<kind>as on|as at|as of|(?:quarter|half[\s-]?year|six months|nine months|year|period) ended(?: on)?)[\s:,]*{DATE}", re.I)
FY = re.compile(r"(?i:\bFY\.?\s?|financial year\s+|F\.Y\.\s?)(?P<fy>\d{4}\s?[-–/]\s?\d{2,4}|\d{2}\s?[-–/]\s?\d{2}|\d{4}|\d{2})(?!\d)")
MONTHS = {m: i for i, m in enumerate(["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}
ABBREVIATIONS = ["S.No.","Rs.","No.","Ltd.","Pvt.","Dr.","Sr.","St.","Mr.","Ms.","Smt.","Co.","approx.","i.e.","e.g.","vs.","w.e.f."]
SCOPE_WORDS = re.compile(r"\b(India|Indian|nationwide|national average|world|global|sector|industry|country)\b")
OTHER_ENTITIES = re.compile(r"\b(NEEPCO|THDC|NGEL|NTPC Green Energy|BRBCL|NVVN|NSPCL|NTECL|PUVNL|Ayana|ASHVINI|NPCIL|SECI|DVC|TPCL|NESCL|NTPC [A-Z][A-Za-z]+ (?:Limited|Ltd))\b")

CAP, GEN, MONEY, RATIO = {"MW","GW","kW","MWe"}, {"MU","BU","MWh","GWh","kWh"}, "INR", {"percent"}
# (metric key, regex, expected unit family). Order breaks distance ties: more specific labels first.
METRICS = [
    ("capacity_addition", r"capacity addition|\badded\b|addition of", CAP),
    ("commercial_capacity", r"commercial capacity", CAP),
    ("installed_capacity", r"installed generation capacity|installed capacity", CAP),
    ("capacity_under_construction", r"under construction|under implementation|under development", CAP),
    ("capacity_awarded", r"letter of award|\bLoA\b|awarded", CAP),
    ("capacity_commissioned", r"commissioned|commercial operation|\bCOD\b", CAP),
    ("capacity", r"\bcapacity\b", CAP),
    ("generation", r"gross generation|net generation|generation|generated", GEN),
    ("revenue", r"revenue from operations|total income|total revenue|turnover|\brevenue\b", MONEY),
    ("profit", r"profit after tax|profit before tax|net profit|profit for the (?:year|period)|\bPAT\b|\bprofit\b", MONEY),
    ("dividend", r"dividend", MONEY),
    ("borrowings", r"borrowings?|total debt|\bdebt\b|debentures?|\bbonds?\b", MONEY),
    ("net_worth", r"net worth", MONEY),
    ("capital_expenditure", r"capital expenditure|\bcapex\b", MONEY),
    ("plant_load_factor", r"plant load factor|\bPLF\b", RATIO),
    ("availability_factor", r"availability factor|\bavailability\b", RATIO),
    ("coal_production", r"coal production|coal mined", None),
]
METRIC_RES = [(k, re.compile(p, re.I if k not in {"capacity_awarded","capacity_commissioned","profit","plant_load_factor"} else 0), fam) for k, p, fam in METRICS]
UNIT_NORMAL = {"mus":"MU","mu":"MU","million units":"MU","%":"percent","percent":"percent","per cent":"percent","percentage point":"percentage_points","percentage points":"percentage_points","bps":"basis_points","basis points":"basis_points","million tonnes":"million tonnes"}

def _sentences(text):
    flat = re.sub(r"\s+", " ", text).strip()
    for a in ABBREVIATIONS: flat = flat.replace(a, a.replace(".", "\x00"))
    parts = re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9•(`\"“‘])|\s*(?=•)", flat)
    return [p.replace("\x00", ".").strip() for p in parts if p and p.strip()]

def _number(raw):
    digits = raw.replace(",", "")
    try: d = Decimal(digits)
    except InvalidOperation: return None
    return int(d) if "." not in digits else float(d)

def _date(m):
    try:
        g = m.groupdict()
        if g.get("d"): d, mo, y = int(g["d"]), MONTHS[g["m"][:3].lower()], int(g["y"])
        elif g.get("d2"): d, mo, y = int(g["d2"]), MONTHS[g["m2"][:3].lower()], int(g["y2"])
        else: d, mo, y = int(g["dd"]), int(g["mm"]), int(g["yy"])
        return dt.date(y, mo, d).isoformat()
    except (ValueError, KeyError, TypeError): return None

def _periods(sentence):
    found = []
    for m in PHRASE.finditer(sentence):
        kind = re.sub(r"[\s-]+", " ", m.group("kind").lower()); iso = _date(m)
        ptype = "as_of" if kind.startswith("as ") else "quarter" if kind.startswith("quarter") else "duration"
        found.append({"type": ptype, "end": iso if ptype != "as_of" else None, "as_of": iso if ptype == "as_of" else None, "raw": m.group(0).strip(), "pos": (m.start(), m.end()), "invalid_date": iso is None})
    for m in FY.finditer(sentence):
        found.append({"type": "financial_year", "end": None, "as_of": None, "raw": m.group(0).strip(), "pos": (m.start(), m.end()), "invalid_date": False})
    return sorted(found, key=lambda p: p["pos"])

def _quantities(sentence):
    out = []
    for m in QTY.finditer(sentence):
        if not m.group("cur") and not m.group("unit"): continue
        out.append(m)
    return out

def _pick_period(sentence, qm, quantities, periods):
    """Nearest period phrase with no other quantity between it and the number; None plus a note otherwise."""
    s, e = qm.start(), qm.end(); others = [q for q in quantities if q is not qm]
    def clear(a, b): return not any(a <= q.start() and q.end() <= b for q in others)
    after = [p for p in periods if p["pos"][0] >= e and p["pos"][0] - e <= 80 and clear(e, p["pos"][0])]
    if after: return after[0], None
    before = [p for p in periods if p["pos"][1] <= s and s - p["pos"][1] <= 80 and clear(p["pos"][1], s)]
    if before: return before[-1], None
    if len({p["raw"] for p in periods}) == 1: return periods[0], None
    if periods: return None, "multiple period phrases in sentence; none unambiguously attached to this number"
    return None, None

PARALLEL = frozenset("against compared to with from vs as and of in the previous year than over on a an basis consolidated standalone group level at stood reached was were is are by respectively while whereas up rose increased increasing decreasing decreased reaching rising".split())
STOCK = frozenset({"installed_capacity", "commercial_capacity", "capacity", "capacity_under_construction", "capacity_awarded", "capacity_commissioned", "capacity_pipeline", "net_worth"})
FORWARD = re.compile(r"(?i)\b(?:target(?:s|ed)?|aim(?:s|ed|ing)?|ambitio\w+|plan(?:s|ned|ning)?(?!\s+assets)|propos(?:e|es|ed|al|als)|expect(?:s|ed|ing)?|will|shall|would|likely|envisag\w+|intend\w*|aspir\w+|endeavou?r\w*|goal|vision|roadmap|pipeline|upcoming|forecast\w*|projected|yet to be|scheduled|to be (?:commissioned|installed|added|developed)|by (?:the end of )?(?:FY\s?)?(?:19|20)\d{2}(?:[-–]\d{2})?|by FY\s?\d{2})\b")
JV_WORDS = re.compile(r"(?i)\b(?:joint[- ]ventures?|JVs?|subsidiar\w+|associates?|affiliates?|wholly[- ]owned)\b")
GROUP_WORDS = re.compile(r"(?i)\b(?:group(?:[- ]level)?|consolidated)\b")
STANDALONE_WORDS = re.compile(r"(?i)\bstand-?alone\b")
CHANGE_WORDS = re.compile(r"(?i)\b(?:growth|grew|increase[ds]?|decrease[ds]?|rise|rose|declin\w+|reduction|improv\w+|y-?o-?y|year[- ]on[- ]year|cagr|up by|down by)\b")
RELATIVE_PERIOD = re.compile(r"(?i)\b(?:during the year|in the year|this year|(?:the )?(?:previous|preceding|last|current|corresponding)\s+(?:financial\s+)?(?:year|quarter|period))\b")
SCALE_WORD = re.compile(r"(?i)\b(?:crores?|lakhs?|million|billion)\b")
FRACTION = re.compile(r"\(\s*\d+\s*/\s*\d+")
EMBEDDED_START = re.compile(r"[a-z0-9,;)]\s+(?:The|This|These|It|Its|In|As|During|Your|Our|Additionally|Notably|With|Some of)\s+[a-z]")
FURNITURE = re.compile(r"INTEGRATED ANNUAL REPORT|\b[A-Z][A-Z ]+LIMITED\s*\|\s*\d+|\|\s*INTEGRATED")
SCOPE_LOCAL = re.compile(r"(?i)\b(?:india|indian|all[- ]india|national|nationwide|country|world|global|sector|industry|market)\b")
ORG_SUFFIX = r"(?:Limited|Ltd\.?|Private Limited|Pvt\.? Ltd\.?|Corporation|Corp\.?|Authority|Board|Commission|Nigam|Inc\.?|PLC|LLP)"
ORG_RE = re.compile(rf"((?:[A-Z][A-Za-z0-9&.\-]*\s+(?:\([A-Za-z]\)\s+)?){{1,6}}{ORG_SUFFIX})(?![A-Za-z])")
ACRONYM_RE = re.compile(r"\b[A-Z]{3,}\b")
ACRONYM_STOP = frozenset("""MW GW KW MWH GWH KWH MU BU MMT MT FY PLF CAPEX EBITDA IPO PAT PBT EPS ROE ROCE GST VAT TDS CSR ESG GHG SDG RE AGM EGM SEBI NSE BSE ISIN LODR INR USD CIN PAN DPE CAG IBC NCLT IND AS ASS FGD DSI PSP BESS HEPP LOA COD PPA MOU MOUS CRM CSI NIL TOTAL ANNUAL REPORT INTEGRATED PHWR MWE""".split())
LEAD_STOP = frozenset("The Your Our In As With This That During Notably Additionally Presently Further Also For At On By From Its Their It Both All Each".split())
LEGAL_SUFFIX = re.compile(r"(?i)[\s,]*\b(?:limited|ltd\.?|pvt\.?|private|corporation|corp\.?|inc\.?|plc|llc|llp)\b\.?\s*$")

@dataclass(frozen=True)
class TargetCompany:
    """The company the extraction is about. Supplied by the caller (or derived from a verified evidence record); never assumed."""
    name: str
    aliases: tuple = ()
    @property
    def names(self):
        short = self.name
        while True:
            t = LEGAL_SUFFIX.sub("", short).strip()
            if t == short or not t: break
            short = t
        return tuple(dict.fromkeys(n for n in (self.name, short, *self.aliases) if n and len(n) >= 2))

def _norm_name(t): return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()

def derive_target(record, aliases=()):
    if record.get("company_identity_status") == "verified" and record.get("company_name"): return TargetCompany(record["company_name"], tuple(aliases))
    return None

def registry_aliases(registry_path, name):
    try: registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    except (OSError, ValueError): return ()
    for e in registry.get("companies", []):
        if e.get("canonical_name") == name: return tuple(e.get("aliases", []))
    return ()

def _self_ref_regex(target):
    parts = [rf"\b{re.escape(n)}\b" for n in target.names] if target else []
    generic = r"\b(?:your|our|the|this)\s+(?:company|corporation)\b|\b(?:we|our|ours|us)\b"
    return re.compile("|".join(parts + [generic]), re.I)

def named_other_entities(text, target):
    """Organization-like phrases (suffix-based) and ALL-CAPS acronyms that are not the target. No company allowlist."""
    own = {_norm_name(n) for n in (target.names if target else ())}
    found = []
    for m in ORG_RE.finditer(text):
        toks = m.group(1).split()
        while toks and toks[0] in LEAD_STOP: toks = toks[1:]
        phrase = " ".join(toks)
        if phrase and _norm_name(phrase) not in own and not re.fullmatch(ORG_SUFFIX, phrase): found.append((m.start(), phrase))
    own_up = {n.upper() for n in (target.names if target else ())}
    for m in ACRONYM_RE.finditer(text):
        a = m.group(0)
        if a in ACRONYM_STOP or a in own_up or any(a in n.upper().split() for n in (target.names if target else ())): continue
        if any(m.start() >= pos and m.start() < pos + len(ph) + 40 and a in ph for pos, ph in found): continue
        found.append((m.start(), a))
    return found

def _label(sentence, qm, unit, quantities=()):
    """Nearest metric label. A label on the far side of another quantity is rejected unless the text between is a parallel construction."""
    s, e = qm.start(), qm.end(); best = None; keys = set(); others = [q for q in quantities if q is not qm]
    def clean(mid):
        for q in others: mid = mid.replace(q.group(0), " ")
        for p in _periods(mid): mid = mid.replace(p["raw"], " ")
        return mid
    def parallel(a, b, label_before):
        """The label governs the nearest figure; this figure shares it only through a short connector (against/from/and/on a basis ...)."""
        inside = [q for q in others if a <= q.start() and q.end() <= b]
        if label_before:
            first_gap = sentence[a:inside[0].start()]; tail = sentence[inside[-1].end():b]
        else:
            first_gap = sentence[inside[-1].end():b]; tail = sentence[a:inside[0].start()]
        if len(first_gap) > 70: return False
        return all(w.lower() in PARALLEL or re.fullmatch(r"(?:FY)?\d+", w) for w in re.findall(r"[A-Za-z0-9]+", clean(tail)))
    for idx, (key, rx, fam) in enumerate(METRIC_RES):
        for m in rx.finditer(sentence, max(0, s - 120), min(len(sentence), e + 60)):
            if m.end() <= s: dist, pref, a, b = s - m.end(), 0, m.end(), s
            elif m.start() >= e: dist, pref, a, b = m.start() - e, 1, e, m.start()
            else: continue
            if any(a <= q.start() and q.end() <= b for q in others) and not parallel(a, b, pref == 0): continue
            cand = (dist, pref, idx, key, m.group(0), fam)
            if best is None or cand < best: best = cand
            if dist <= 80: keys.add(key)
    if "capacity" in keys and any(k.startswith("capacity_") or k in ("installed_capacity", "commercial_capacity") for k in keys): keys.discard("capacity")
    return best, sorted(keys)

def _unit_family_ok(fam, unit):
    if fam is None or unit is None: return True
    if fam == MONEY: return unit.startswith("INR")
    return unit in fam

def claim_id(chunk_id, sentence_idx, start, raw_value, raw_unit):
    return "cl1_" + hashlib.sha256("\x1f".join((chunk_id, str(sentence_idx), str(start), raw_value, raw_unit or "")).encode()).hexdigest()[:24]

def _segments(sentences):
    """Segment text per sentence index. Bullets share one subject context; paragraphs and any pre-bullet intro are judged sentence by sentence."""
    if not any(sn.startswith("•") for sn in sentences): return list(sentences)
    out, i = [], 0
    while i < len(sentences):
        if not sentences[i].startswith("•"): out.append(sentences[i]); i += 1; continue
        j = i + 1
        while j < len(sentences) and not sentences[j].startswith("•"): j += 1
        group = " ".join(sentences[i:j]); out += [group] * (j - i); i = j
    return out

def _nearest(sentence, s, e, rx, span=100):
    best = None
    for m in rx.finditer(sentence, max(0, s - span), min(len(sentence), e + span)):
        d = s - m.end() if m.end() <= s else m.start() - e if m.start() >= e else 0
        if d >= 0 and (best is None or d < best[0]): best = (d, m.group(0))
    return best

def extract_claims(record, document_id, target="derive"):
    """Return candidate claim dicts for one evidence record. Raises ValueError if provenance is unusable.
    `target` is the company the claims must be about (TargetCompany); the default derives it from a verified record.
    A claim is `extracted` only when subject, metric, value, unit, period and temporal status are all explicit."""
    chunk_id, path, text = record.get("evidence_id"), record.get("source_path"), record.get("excerpt_or_fact")
    if not chunk_id or not path: raise ValueError("record lacks evidence_id or source_path; provenance cannot be preserved")
    if not isinstance(text, str) or not text.strip(): return []
    if target == "derive": target = derive_target(record)
    self_rx = _self_ref_regex(target) if target else None
    verified = record.get("company_identity_status") == "verified" and record.get("company_name")
    page = record.get("page_number") if isinstance(record.get("page_number"), int) else None
    sentences = _sentences(text); chunk_periods = []
    for sn in sentences: chunk_periods += _periods(sn)
    distinct_chunk = {p["raw"]: p for p in chunk_periods}
    scale_in_chunk = bool(SCALE_WORD.search(text))
    seg_text = _segments(sentences)
    claims = []
    for si, sn in enumerate(sentences):
        quantities = _quantities(sn); periods = _periods(sn); segment = seg_text[si]
        for qm in quantities:
            notes = []; status = "extracted"; subject_ok = True
            def flag(note, level="needs_review", subject=False):
                nonlocal status, subject_ok
                notes.append(note)
                if subject: subject_ok = False
                if RANK[level] > RANK[status]: status = level
            cur, raw_unit = qm.group("cur"), qm.group("unit"); num_raw = qm.group("num"); s0, e0 = qm.start(), qm.end()
            raw_value = (qm.group(0)[:qm.start("num") - qm.start()] + num_raw + (qm.group("close") or "")).strip()
            value = _number(num_raw)
            if qm.group("neg") or (qm.group("open") and qm.group("close")):
                value = -value if value is not None else None; notes.append("negative value from minus sign or parentheses (accounting notation); sign not otherwise verified")
            lowered = raw_unit.lower() if raw_unit else None
            unit = None
            if lowered in {"crore","crores","lakh","lakhs","million","billion"}:
                scale = lowered.rstrip("s")
                if cur: unit = f"INR {scale}"
                else: flag("scale word without a currency marker; unit left null")
            elif cur and raw_unit is None:
                unit = "INR"
                if scale_in_chunk: flag("currency amount has no scale of its own although the chunk mentions crore/lakh/million elsewhere; scale not unambiguous", "ambiguous")
            elif raw_unit: unit = UNIT_NORMAL.get(lowered, UNIT_NORMAL.get(raw_unit, raw_unit))
            if cur and raw_unit and unit and not unit.startswith("INR"): flag(f"currency marker {cur!r} next to non-monetary unit {raw_unit!r}")
            if cur == "`": flag("currency glyph is a backtick (likely PDF rupee-symbol substitution); INR is not confirmed by the source text")
            before = sn[:s0]
            if re.search(r"\d\s*[x×]\s*$", before, re.I): flag("number is part of a multiplicative expression (e.g. 4x700); product not computed")
            if re.search(r"\d\s*[-–]\s*$", before) or re.match(r"\s*(?:to|[-–])\s*\d", sn[e0:]): flag("number appears to be part of a range")
            if FRACTION.search(sn[max(0, s0 - 2):e0 + 70]) or re.match(r"\s*/\s*\d", sn[e0:]) or re.search(r"\d\s*/\s*$", before): flag("number is part of a fraction (e.g. 10/23 commissioned); partial status")
            win = sn[max(0, s0 - 80):e0 + 80]
            if len(re.findall(NUM, win)) >= 4 and sum(c.isalpha() for c in win) / max(len(win), 1) < 0.35: flag("numeric run looks like a table fragment; label association unreliable")
            if FURNITURE.search(sn): flag("page furniture inside the sentence indicates column interleaving; word order unreliable", "ambiguous")
            elif EMBEDDED_START.search(sn): flag("a capitalized sentence start appears mid-sentence, which indicates two-column interleaving; word order and the subject are unreliable", "ambiguous", True)
            # --- subject attribution (no company allowlist: the target is supplied; others are found structurally)
            if target is None: flag("no target company supplied or verified; subject cannot be attributed", "ambiguous", True)
            else:
                if re.match(r"(?:It|Its|They|Their|These|Those)\b", sn): flag("sentence begins with a pronoun; subject is in earlier text not examined", subject=True)
                elif not self_rx.search(segment): flag(f"subject is not stated: no reference to the target ({target.name}) in the sentence or its bullet", "ambiguous", True)
            local_lo, local_hi = max(0, s0 - 150), min(len(sn), e0 + 80)
            others = sorted({ph for pos, ph in named_other_entities(sn, target) if local_lo <= pos <= local_hi})
            if others: flag(f"other organization(s) named near the figure ({', '.join(others)}); the figure may be theirs", subject=True)
            if SCOPE_LOCAL.search(sn[max(0, s0 - 60):s0]): flag("national/industry-scope wording directly before the figure; not the company's figure", subject=True)
            elif SCOPE_LOCAL.search(sn): notes.append("sentence contains national/industry-scope wording elsewhere")
            jv = _nearest(sn, s0, e0, JV_WORDS)
            if jv: flag(f"joint venture/subsidiary wording near the figure ({jv[1]}); it may include or belong to them", subject=True)
            grp, sta = _nearest(sn, s0, e0, GROUP_WORDS), _nearest(sn, s0, e0, STANDALONE_WORDS)
            if grp and (not sta or grp[0] < sta[0]): flag(f"group/consolidated basis ({grp[1]}); not the target's own (standalone) figure", "ambiguous", True)
            # --- metric
            lab, label_keys = _label(sn, qm, unit, quantities); metric = raw_metric = None; fam = None
            if lab:
                metric, raw_metric, fam = lab[3], lab[4], lab[5]
                if not _unit_family_ok(fam, unit): flag(f"unit {unit!r} does not match the unit family expected for {metric}")
                if metric == "capacity": flag("capacity status is not stated (installed, commissioned, under implementation, awarded, target?); generic 'capacity' is not specific enough", "ambiguous")
                if len(label_keys) > 1: flag(f"competing metric labels near the number ({', '.join(label_keys)}); chosen label is only the nearest", "ambiguous")
                if re.search(r"\bagainst\s*$", sn[max(0, s0 - 15):s0]): notes.append("preceded by 'against': likely a comparative figure")
            else: flag("no recognised metric label near the number (or another figure sits between them); label may be in another chunk or column")
            if unit == "percent":
                if CHANGE_WORDS.search(sn[max(0, s0 - 50):s0]) or CHANGE_WORDS.match(sn[e0:e0 + 25].lstrip(" ,")): flag("percent looks like a change rate, not a level"); metric = None
                elif lab and fam is not RATIO and fam is not None: flag(f"percent value attached to level metric {metric}; may be a change rate")
            # --- temporal status
            fwd = FORWARD.search(sn)
            if fwd:
                flag(f"forward-looking wording ({fwd.group(0)}): a target, plan or expectation, not a historical actual", "ambiguous")
                if metric and (metric in STOCK or metric.startswith("capacity")): metric = "capacity_target"
            period, pnote = _pick_period(sn, qm, quantities, periods); ptype, pstart, pend, asof, rawp = "unknown", None, None, None, None
            if period:
                ptype, pend, asof, rawp = period["type"], period["end"], period["as_of"], period["raw"]
                if period["invalid_date"]: flag("period phrase has an unparseable or invalid date; dates left null")
                if pnote: flag(pnote, "ambiguous")
            elif pnote: flag(pnote, "ambiguous")
            else:
                if len(distinct_chunk) == 1:
                    period = next(iter(distinct_chunk.values())); ptype, pend, asof, rawp = period["type"], period["end"], period["as_of"], period["raw"]
                    flag("period taken from elsewhere in the chunk, not from this sentence", "ambiguous")
                else:
                    flag("no period stated for this figure in its sentence" + ("; chunk contains several different period phrases" if distinct_chunk else ""), "ambiguous")
                if RELATIVE_PERIOD.search(sn): notes.append("relative period wording (e.g. 'during the year', 'previous year') without a date")
            if metric in STOCK and ptype != "as_of" and period is not None: flag("stock-type metric (capacity/net worth) needs an 'as on/at <date>'; a period range does not define it", "ambiguous")
            if page is None: flag("source page number missing in evidence record")
            if not verified: notes.append("entity not associated: evidence record has no verified company identity")
            ex = sn if len(sn) <= 500 else sn[max(0, s0 - 250):e0 + 250]
            if status == "extracted" and value is None: status = "needs_review"
            entity = target.name if (target and subject_ok and status == "extracted") else None
            claims.append({"schema_version": SCHEMA_VERSION, "claim_id": claim_id(chunk_id, si, qm.start(), raw_value, raw_unit), "entity": entity,
                "entity_identity_status": "verified" if verified else "unresolved", "metric": metric, "raw_metric_text": raw_metric, "value": value, "raw_value_text": raw_value or num_raw,
                "unit": unit, "raw_unit_text": raw_unit, "period_type": ptype, "period_start": pstart, "period_end": pend, "as_of_date": asof, "raw_period_text": rawp,
                "source_document_id": document_id, "source_path": path, "source_page": page, "source_chunk_id": chunk_id, "source_excerpt": ex, "extraction_status": status,
                "ambiguity_notes": "; ".join(dict.fromkeys(notes)) if notes else None, "claim_verification_status": "unverified", "parser_version": PARSER_VERSION})
    return claims

def _read_jsonl(path):
    items, errors = [], []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        try: items.append(json.loads(line))
        except json.JSONDecodeError as e: errors.append({"line": n, "error": str(e)})
    return items, errors

def run_extraction(input_dir, output_dir, extractor=extract_claims, overwrite=False):
    inp, out = Path(input_dir), Path(output_dir)
    if inp.resolve() == out.resolve(): raise ValueError("Output directory must differ from the input evidence store")
    evidence_path = inp / "evidence.jsonl"
    if not evidence_path.is_file(): raise FileNotFoundError(f"Evidence file not found: {evidence_path}")
    existing = [f for f in OUTPUT_FILES if (out / f).exists()]
    if existing and not overwrite: raise ValueError(f"{out} already contains {existing}; pass --overwrite to replace these generated files")
    records, bad_lines = _read_jsonl(evidence_path)
    doc_ids = {}
    sr_path = inp / "source_records.jsonl"
    if sr_path.is_file():
        for sr in _read_jsonl(sr_path)[0]:
            if sr.get("evidence_id") and sr.get("source_sha256"): doc_ids[sr["evidence_id"]] = "doc_" + sr["source_sha256"][:16]
    claims, queue, seen = [], [], set()
    c = dict.fromkeys(("processed", "failed", "zero_empty", "zero_no_claims", "with_claims", "schema_failures", "duplicates", "chunks_with_rejected_claims"), 0)
    errors = []
    for b in bad_lines:
        c["failed"] += 1; queue.append({"kind": "input_error", "source_chunk_id": None, "claim_id": None, "reason": f"invalid JSON at line {b['line']}: {b['error']}"}); errors.append(f"line {b['line']}: invalid JSON")
    for rec in records:
        cid = rec.get("evidence_id") if isinstance(rec, dict) else None
        try:
            if not isinstance(rec, dict): raise ValueError("evidence record is not an object")
            doc = doc_ids.get(cid) or ("doc_" + hashlib.sha256(str(rec.get("source_path")).encode()).hexdigest()[:16])
            produced = extractor(rec, doc)
        except Exception as e:
            c["failed"] += 1; msg = f"{type(e).__name__}: {e}"; errors.append(f"{cid}: {msg}")
            queue.append({"kind": "chunk_failure", "source_chunk_id": cid, "claim_id": None, "reason": msg}); continue
        c["processed"] += 1
        if not produced:
            if not str(rec.get("excerpt_or_fact") or "").strip() or rec.get("parsing_status") in ("empty", "failed", "ocr_required"): c["zero_empty"] += 1
            else: c["zero_no_claims"] += 1
            continue
        accepted, rejected = 0, 0
        for cl in produced:
            try:
                if not isinstance(cl, dict): raise ValueError("extractor output is not an object")
                validate_output(cl, ROOT / "schemas" / "claim.schema.json")
                if cl["source_chunk_id"] != cid or cl["source_path"] != rec.get("source_path") or cl["source_page"] != rec.get("page_number"): raise ValueError("claim provenance does not match its source evidence record")
            except Exception as e:
                rejected += 1; c["schema_failures"] += 1
                queue.append({"kind": "invalid_claim", "source_chunk_id": cid, "claim_id": cl.get("claim_id") if isinstance(cl, dict) else None, "reason": str(e)[:500]}); continue
            if cl["claim_id"] in seen: c["duplicates"] += 1; continue
            seen.add(cl["claim_id"]); claims.append(cl); accepted += 1
            if cl["extraction_status"] != "extracted":
                queue.append({"kind": "claim_review", "source_chunk_id": cid, "claim_id": cl["claim_id"], "reason": cl["ambiguity_notes"], "extraction_status": cl["extraction_status"], "source_excerpt": cl["source_excerpt"]})
        if rejected: c["chunks_with_rejected_claims"] += 1
        if accepted: c["with_claims"] += 1
    status_counts = {s: sum(1 for x in claims if x["extraction_status"] == s) for s in ("extracted", "ambiguous", "needs_review")}
    report = {"run_status": "completed" if not c["failed"] and not c["schema_failures"] else "completed_with_failures", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "parser_version": PARSER_VERSION, "schema_version": SCHEMA_VERSION, "extractor": "deterministic regex; no model, no network",
        "input": {"evidence_path": str(evidence_path), "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(), "source_records_path": str(sr_path) if sr_path.is_file() else None},
        "output_dir": str(out), "input_record_count": len(records) + len(bad_lines), "processed_chunk_count": c["processed"], "failed_chunk_count": c["failed"],
        "chunks_with_claims": c["with_claims"], "chunks_with_zero_claims": c["zero_empty"] + c["zero_no_claims"], "zero_claims_empty_or_unparsed": c["zero_empty"], "zero_claims_no_extractable_claim": c["zero_no_claims"],
        "total_claims": len(claims), "claims_by_status": status_counts, "claims_needing_attention": status_counts["ambiguous"] + status_counts["needs_review"],
        "schema_validation_failures": c["schema_failures"], "chunks_with_rejected_claims": c["chunks_with_rejected_claims"], "duplicate_claims_skipped": c["duplicates"],
        "review_queue_entries": len(queue), "error_summary": errors[:50], "error_summary_truncated": len(errors) > 50,
        "notes": ["Claims are extracted candidates and carry claim_verification_status 'unverified'; extraction is not verification.", "Entity is copied from the evidence record and not independently certified."]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "claims.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in claims), encoding="utf-8")
    (out / "review_queue.jsonl").write_text("".join(json.dumps({"review_id": f"rv_{i:06d}", **q}, ensure_ascii=False) + "\n" for i, q in enumerate(queue, 1)), encoding="utf-8")
    (out / "extraction_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return claims, report

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", default=str(ROOT / "data" / "processed_step6")); p.add_argument("--output-dir", default=str(ROOT / "data" / "claims_step1"))
    p.add_argument("--overwrite", action="store_true", help="Replace existing claims.jsonl, extraction_report.json and review_queue.jsonl in the output directory")
    a = p.parse_args(argv)
    try: claims, rep = run_extraction(a.input_dir, a.output_dir, overwrite=a.overwrite)
    except (OSError, ValueError) as e:
        print(f"Claim extraction error: {e}", file=sys.stderr); return 2
    print(f"{rep['run_status']}: {rep['input_record_count']} chunks, {rep['total_claims']} claims ({rep['claims_by_status']}), {rep['chunks_with_zero_claims']} zero-claim chunks, {rep['failed_chunk_count']} failed, {rep['schema_validation_failures']} schema failures. Report: {Path(a.output_dir) / 'extraction_report.json'}")
    return 0 if rep["run_status"] == "completed" else 1

if __name__ == "__main__": raise SystemExit(main())
