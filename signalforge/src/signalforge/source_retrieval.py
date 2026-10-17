"""Stage D: retrieval adapter over the existing bounded, robots-aware client in public_sources.

No discovery or search: URLs come from an operator-supplied catalog (official sources the operator permits), matched to the
planned lookups of an R1 plan. Results keep provenance, deduplicate mirrors by content hash, classify sources, and report
failures, empty and stale results. A search snippet is never treated as a checked primary source.
"""
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from . import public_sources
from .pipeline_contract import write_json

SOURCE_CLASSES = ("official_filing", "exchange_announcement", "government_data", "regulator", "third_party")
PRIMARY_CLASSES = ("official_filing", "exchange_announcement", "government_data", "regulator")

def load_catalog(path_or_obj):
    cat = json.loads(Path(path_or_obj).read_text(encoding="utf-8")) if isinstance(path_or_obj, (str, Path)) else path_or_obj
    for e in cat.get("sources", []):
        if e.get("source_class") not in SOURCE_CLASSES: raise ValueError(f"catalog entry {e.get('url')!r} has invalid source_class")
        host = urlparse(e["url"]).hostname or ""
        if cat.get("official_domains") and e["source_class"] in PRIMARY_CLASSES and not any(host == d or host.endswith("." + d) for d in cat["official_domains"]):
            raise ValueError(f"{e['url']} is declared a primary source but its host is not in official_domains")
    return cat

def plan_requests(r1_plan, catalog, claim_ids, hypothesis_id):
    """One request per (planned lookup, matching catalog source). Missing catalog coverage is reported, never invented."""
    reqs = []
    for i, item in enumerate(x for x in r1_plan.get("evidence_ledger", []) if x["status"] == "planned_lookup"):
        matches = [s for s in catalog.get("sources", []) if s.get("source_type") == item["source_type"] or s.get("source_type") == "any"]
        if not matches: reqs.append({"request_id": f"req_{i}_none", "url": None, "status": "no_catalog_source", "hypothesis_id": hypothesis_id, "claim_ids": list(claim_ids), "source_type": item["source_type"], "purpose": item["claim_supported"]}); continue
        for j, s in enumerate(matches): reqs.append({"request_id": f"req_{i}_{j}", "url": s["url"], "status": "planned", "hypothesis_id": hypothesis_id, "claim_ids": list(claim_ids), "source_type": item["source_type"],
                                                  "source_class": s["source_class"], "publisher": s.get("publisher"), "purpose": item["claim_supported"]})
    return reqs

def execute(requests, run_dir, *, fetcher=None, registry_path=None, company=None, max_age_days=800, today=None):
    """Fetch planned requests. fetcher(urls, run_dir) -> retrieval report (default: public_sources.retrieve_urls). Returns structured results."""
    today = today or dt.date.today()
    todo = [r for r in requests if r["status"] == "planned"]; results = [dict(r) for r in requests if r["status"] != "planned"]
    if todo:
        urls = list(dict.fromkeys(r["url"] for r in todo))
        fetch = fetcher or (lambda u, d: public_sources.retrieve_urls(u, d, registry_path=registry_path, company=company))
        try: report = fetch(urls, str(run_dir))
        except Exception as e: report = {"sources": [{"requested_url": u, "retrieval_status": "failed", "error": f"{type(e).__name__}: {e}"} for u in urls]}
        by_url = {s["requested_url"]: s for s in report.get("sources", [])}
        for r in todo:
            s = by_url.get(r["url"], {"retrieval_status": "failed", "error": "no result returned"}); out = dict(r)
            if s.get("retrieval_status") != "retrieved": out.update(status="failed", error=s.get("error", "unknown"))
            else:
                pub = s.get("publication_date"); stale = bool(pub) and (today - dt.date.fromisoformat(pub[:10])).days > max_age_days
                out.update(status="stale" if stale else "retrieved", source_url=s.get("canonical_url") or r["url"], source_sha256=s.get("source_sha256"), publication_date=pub, retrieved_at=s.get("retrieved_at"), document_title=s.get("document_title"),
                           company_association=s.get("company_association_status"), warnings=s.get("warnings", []), is_primary=r["source_class"] in PRIMARY_CLASSES)
                if not pub: out["warnings"] = out["warnings"] + ["publication date unknown; cannot be used as a dated primary source until established"]
            results.append(out)
    seen, final = {}, []
    for r in results:
        h = r.get("source_sha256")
        if h and h in seen: r = {**r, "status": "duplicate_mirror", "duplicate_of": seen[h]}
        elif h: seen[h] = r["request_id"]
        final.append(r)
    summary = {"requested": len(requests), "retrieved": sum(r["status"] == "retrieved" for r in final), "failed": sum(r["status"] == "failed" for r in final), "stale": sum(r["status"] == "stale" for r in final),
               "duplicate_mirrors": sum(r["status"] == "duplicate_mirror" for r in final), "no_catalog_source": sum(r["status"] == "no_catalog_source" for r in final)}
    write_json(Path(run_dir) / "retrieval_results.json", {"summary": summary, "results": final}); return {"summary": summary, "results": final}

def source_descriptor(result):
    """Independence metadata for claim_verification.assess_independence."""
    return {"publisher": result.get("publisher"), "document_family": result.get("source_sha256"), "sha256": result.get("source_sha256"), "derived_from": result.get("derived_from", [])}

def verification_level_for(result):
    return "primary_source" if result.get("is_primary") and result.get("status") == "retrieved" and result.get("publication_date") and result.get("company_association") == "verified" else "extracted_text_review"
