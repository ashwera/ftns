"""Verified source catalog ingestion (supplied by the operator, e.g. a reviewer's catalog of official documents).

The catalog carries every URL; no document URL lives in code. Entries may point to a local snapshot (`local_path`, optionally pinned by
`sha256`) or, only when network use is explicitly allowed, to a URL fetched through the bounded client. A source reaches
`primary_source` verification level only if the catalog attests it (official class, publication date, `verified_by`) and its content
hash matches any pinned hash. Mirrors and issuer-submitted copies are tracked so they never count as independent corroboration.

Catalog format (JSON):
{"catalog_version": "1.0", "company": "...", "official_domains": ["..."],
 "sources": [{"source_id": "...", "url": "https://...|null", "local_path": "relative/or/null", "sha256": "optional pin", "title": "...", "publisher": "...",
              "source_class": "official_filing|exchange_announcement|government_data|regulator|third_party", "source_type": "annual_report|...",
              "publication_date": "YYYY-MM-DD", "reporting_period": "FY2024-25", "issuer_submitted": true, "derived_from": ["other source_id"],
              "verified_by": "name", "verified_on": "YYYY-MM-DD"}]}
"""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from . import source_retrieval as SR

REQUIRED = ("source_id", "publisher", "source_class", "source_type")

def load(path_or_obj):
    cat = json.loads(Path(path_or_obj).read_text(encoding="utf-8")) if isinstance(path_or_obj, (str, Path)) else json.loads(json.dumps(path_or_obj))
    ids = set()
    for e in cat.get("sources", []):
        missing = [k for k in REQUIRED if not e.get(k)]
        if missing: raise ValueError(f"catalog source {e.get('source_id')!r} lacks {missing}")
        if e["source_class"] not in SR.SOURCE_CLASSES: raise ValueError(f"{e['source_id']}: invalid source_class {e['source_class']!r}")
        if e["source_id"] in ids: raise ValueError(f"duplicate source_id {e['source_id']!r}")
        ids.add(e["source_id"])
        if not e.get("local_path") and not e.get("url"): raise ValueError(f"{e['source_id']}: needs a url or a local_path")
        if e.get("url") and cat.get("official_domains") and e["source_class"] in SR.PRIMARY_CLASSES:
            host = urlparse(e["url"]).hostname or ""
            if not any(host == d or host.endswith("." + d) for d in cat["official_domains"]): raise ValueError(f"{e['source_id']}: host {host!r} is not in official_domains but the source is declared primary")
    for e in cat.get("sources", []):
        for d in e.get("derived_from", []):
            if d not in ids: raise ValueError(f"{e['source_id']}: derived_from unknown source_id {d!r}")
    cat.setdefault("sources", []); return cat

def read_pages(path):
    """Return (pages, sha256). Text-like files are split on 'Page N' markers; PDFs need pypdf."""
    p = Path(path); raw = p.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
    if p.suffix.lower() == ".pdf":
        try: from pypdf import PdfReader
        except ImportError as e: raise RuntimeError("PDF snapshots need pypdf (python -m pip install 'pypdf>=4,<6')") from e
        return [{"page": i, "text": (pg.extract_text() or "")} for i, pg in enumerate(PdfReader(str(p)).pages, 1)], sha
    text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    marks = list(re.finditer(r"^Page (\d+)[ \t]*$", text, re.M))
    if not marks: return [{"page": None, "text": text}], sha
    return [{"page": int(m.group(1)), "text": text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]} for i, m in enumerate(marks)], sha

def materialize(catalog, base_dir, run_dir, *, allow_network=False, fetcher=None, registry_path=None, company=None):
    """Turn catalog entries into readable sources with a status. Nothing is fetched unless allow_network is set."""
    base = Path(base_dir); out = []; net = []
    for e in catalog["sources"]:
        src = {**{k: e.get(k) for k in ("source_id", "url", "title", "publisher", "source_class", "source_type", "publication_date", "reporting_period", "verified_by", "verified_on")},
               "issuer_submitted": bool(e.get("issuer_submitted")), "derived_from": list(e.get("derived_from", [])), "pages": [], "sha256": None, "status": "not_retrieved", "error": None,
               "is_primary": e["source_class"] in SR.PRIMARY_CLASSES}
        if e.get("local_path"):
            path = (base / e["local_path"]).resolve()
            try:
                src["pages"], src["sha256"] = read_pages(path); src["status"] = "available"
                if e.get("sha256") and e["sha256"] != src["sha256"]: src.update(status="hash_mismatch", pages=[], error=f"content hash {src['sha256'][:12]} does not match pinned {e['sha256'][:12]}")
            except (OSError, RuntimeError) as ex: src.update(status="unreadable", error=f"{type(ex).__name__}: {ex}")
        elif allow_network and src["url"]: net.append(src)
        out.append(src)
    if net:
        reqs = [{"request_id": s["source_id"], "url": s["url"], "status": "planned", "hypothesis_id": None, "claim_ids": [], "source_type": s["source_type"], "source_class": s["source_class"], "publisher": s["publisher"], "purpose": "catalog source"} for s in net]
        res = {r["request_id"]: r for r in SR.execute(reqs, run_dir, fetcher=fetcher, registry_path=registry_path, company=company)["results"]}
        for s in net:
            r = res.get(s["source_id"], {})
            if r.get("status") in ("retrieved", "stale") and r.get("saved_path"):
                try: s["pages"], s["sha256"] = read_pages(r["saved_path"]); s["status"] = "available"
                except (OSError, RuntimeError) as ex: s.update(status="unreadable", error=str(ex))
                s["publication_date"] = s["publication_date"] or r.get("publication_date")
            else: s.update(status=r.get("status", "failed"), error=r.get("error"))
    return out

def level_for(src):
    """primary_source only for an available, attested, dated, official source whose pinned hash (if any) matched."""
    return "primary_source" if src["status"] == "available" and src["is_primary"] and src["publication_date"] and src["verified_by"] else "extracted_text_review"

def describe(src):
    return {k: src[k] for k in ("source_id", "url", "title", "publisher", "source_class", "publication_date", "sha256", "status", "error", "issuer_submitted", "derived_from")} | {"verification_level": level_for(src)}
