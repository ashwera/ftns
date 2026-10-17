"""Shared interfaces for the downstream pipeline (claims -> bundle -> verification -> signals -> findings).

Status vocabularies stay separate and are never merged:
  extraction_status  (existing claim schema)   extracted | ambiguous | needs_review
  claim_verification_status (existing, const)  unverified - claims are never mutated by later stages
  verification outcome (verification_result)   confirmed | contradicted | partially_supported | unresolved | unable_to_verify
  verification_level                           extracted_text_review | primary_source
  finding_status (finding schema)              supported_finding | provisional_hypothesis | no_defensible_signal
"""
import hashlib
import json
import re
from pathlib import Path

from .claim_extraction import TargetCompany
from .config import ROOT
from .f1_research_angle_selector import validate_output

SCHEMAS = ROOT / "schemas"
OUTCOMES = ("confirmed", "contradicted", "partially_supported", "unresolved", "unable_to_verify")
LEVELS = ("extracted_text_review", "primary_source")

def read_jsonl(path): return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]

def write_json(path, obj):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8"); return p

def validate_against(obj, schema_name):
    return validate_output(obj, SCHEMAS / f"{schema_name}.schema.json")

def sha256_text(t): return hashlib.sha256(t.encode("utf-8")).hexdigest()

def collapse(s): return re.sub(r"\s+", " ", s or "").strip()

class ClaimStore:
    """Read-only index over a claims.jsonl. Refuses claims that are not `unverified` (later stages must not mutate claims)."""
    def __init__(self, claims):
        bad = [c["claim_id"] for c in claims if c.get("claim_verification_status") != "unverified"]
        if bad: raise ValueError(f"claims must stay unverified in the store; offending ids: {bad[:3]}")
        self.claims = list(claims); self.by_id = {c["claim_id"]: c for c in claims}
        if len(self.by_id) != len(self.claims): raise ValueError("duplicate claim_id in claim store")
    @classmethod
    def load(cls, path): return cls(read_jsonl(path))
    def get(self, claim_id):
        if claim_id not in self.by_id: raise KeyError(f"unknown claim_id {claim_id!r}")
        return self.by_id[claim_id]
    def resolve_suffix(self, suffix):
        hits = [c for c in self.claims if c["claim_id"].endswith(suffix)]
        if len(hits) != 1: raise KeyError(f"claim id suffix {suffix!r} matched {len(hits)} claims")
        return hits[0]

def citation(claim=None, record=None, excerpt=None, url=None):
    """Citation object for the frontend. Points at the stored chunk/page; a URL is included only if one really exists."""
    src = record or {}
    return {"source_chunk_id": (claim or {}).get("source_chunk_id") or src.get("evidence_id"), "source_path": (claim or {}).get("source_path") or src.get("source_path"),
            "page": (claim or {}).get("source_page", src.get("page_number")), "locator": src.get("source_locator"),
            "excerpt": collapse(excerpt if excerpt is not None else (claim or {}).get("source_excerpt") or ""), "url": url or src.get("source_url")}

def target_from_registry(registry_path, name_or_alias):
    """Resolve the target from configuration only. Returns (TargetCompany, identity_status)."""
    reg = json.loads(Path(registry_path).read_text(encoding="utf-8")) if registry_path and Path(registry_path).is_file() else {"companies": []}
    key = name_or_alias.casefold()
    for e in reg.get("companies", []):
        names = [e.get("canonical_name"), *e.get("aliases", []), *e.get("identifiers", [])]
        if any(str(n).casefold() == key for n in names if n):
            ok = e.get("verification_status") == "verified" and bool(e.get("verification_source"))
            return TargetCompany(e["canonical_name"], tuple(e.get("aliases", []))), ("registry_verified" if ok else "config_only")
    return TargetCompany(name_or_alias, ()), "config_only"
