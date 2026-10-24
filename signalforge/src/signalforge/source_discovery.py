"""Bounded public source discovery; run with ``python -m signalforge.source_discovery``.

Ownership/work log (Codex, 2026-10-24): source_discovery.py and
tests/test_source_discovery.py only. Implements spec 4.3/P2 search adapter,
grounding-only URLs, query/result/error audit, fixture replay and safe retrieval.
Coordination ownership/log updated for the 2026-10-25 quality follow-up.
Integration: call discover(..., evidence_gaps=r1_gap_strings), persist its report
beside the pipeline action log, and pass retrieved evidence through existing
review/verification gates. Search classifications are hints, never independence
or identity verification. PDF printed-page mapping remains an ingestion concern.
Public-search follow-up: Bing RSS fallback, XML fixture tests and genuine
NTPC/Power Grid discovery-only reports under data/runs; no identity or finding
is established by these search results. GeminiGoogleSearch() defaults to fallback
without requiring callers such as research_session to change their API usage.
Relevance follow-up: filter every provider's hits before ranking/retrieval;
log raw returned, relevance-accepted, deduplicated relevant and rejected counts
separately. Matches remain lexical hints, never verified identities or facts.
"""

import argparse
import datetime as dt
import ipaddress
import json
import math
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from html.parser import HTMLParser
from typing import Protocol

from . import public_sources


class SearchError(RuntimeError):
    """Safe provider failure: no remote response body or credential included."""


class SearchProvider(Protocol):
    name: str
    execution_mode: str

    def search(self, query: str, *, timeout: float) -> dict:
        """Return results, executed_queries and optional grounding metadata."""


@dataclass(frozen=True)
class Budget:
    max_queries: int = 6
    max_results: int = 20
    max_fetches: int = 5
    max_seconds: float = 120
    request_timeout: float = 20
    max_response_bytes: int = 2 * 1024 * 1024
    max_site_pages: int = 3

    def __post_init__(self):
        for name, ceiling in (("max_queries", 50), ("max_results", 200),
                              ("max_fetches", public_sources.MAX_SOURCES),
                              ("max_site_pages", 10),
                              ("max_response_bytes", 10 * 1024 * 1024)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= ceiling:
                raise ValueError(f"Invalid {name}")
        for name in ("max_seconds", "request_timeout"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"Invalid {name}")


def _public_url(url):
    if not isinstance(url, str) or any(ord(c) < 33 for c in url):
        return False
    try:
        p = urllib.parse.urlsplit(url)
        if p.scheme not in {"https", "http"} or not p.hostname or p.username or p.password:
            return False
        if p.port not in (None, 80, 443) or p.hostname.lower() == "localhost":
            return False
        try:
            return ipaddress.ip_address(p.hostname).is_global
        except ValueError:
            return "." in p.hostname and not p.hostname.lower().endswith((".local", ".localhost", ".internal"))
    except ValueError:
        return False


def _domain(value):
    value = value.lower().strip().rstrip(".")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value) or not _public_url("https://" + value):
        raise ValueError("Domains must be public hostnames, without URL paths")
    return value


def _matches(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)


def build_queries(company, topic, domains=(), date_window=None, evidence_gaps=()):
    """Generate generic issuer, regulatory, industry and contradiction searches.

    domains are search preferences, not a retrieval authorization/allowlist.
    date_window is (inclusive ISO start date, inclusive ISO end date).
    """
    if not company.strip() or not topic.strip():
        raise ValueError("Company and topic are required")
    domains = tuple(_domain(d) for d in domains)
    suffix = ""
    if date_window:
        start, end = (dt.date.fromisoformat(x) for x in date_window)
        if start > end:
            raise ValueError("Date window start is after end")
        suffix = f" after:{start - dt.timedelta(days=1)} before:{end + dt.timedelta(days=1)}"
    # Short brand phrases avoid engines collapsing long legal names to 'Power'.
    brand = re.sub(r"\b(limited|ltd|company|of|india|inc|plc|private|pvt)\b", " ", company, flags=re.I)
    brand = " ".join(brand.split()) or company.strip()
    base = json.dumps(brand)
    terms = _search_terms(topic)
    gaps = [_search_terms(g) for g in evidence_gaps if isinstance(g, str) and g.strip()]
    queries = [f"{base} {gap} filetype:pdf" for gap in gaps[:2]]
    queries += [f"{base} annual report site:{d} filetype:pdf" for d in domains]
    queries += [f"{base} annual report filetype:pdf", f"{base} {terms} filetype:pdf",
                f"{base} {terms} regulator government filetype:pdf",
                f"{base} {terms} delay cancellation contradiction"]
    queries += [f"{base} {gap} filetype:pdf" for gap in gaps[2:]]
    return list(dict.fromkeys(q + suffix for q in queries))


def _search_terms(text):
    """Keep metric/period tokens; do not send a full narrative to the engine."""
    stop = {"what", "which", "does", "did", "how", "has", "have", "is", "are", "the", "a", "an",
            "to", "of", "for", "and", "in", "on", "with", "from", "by", "whether", "company",
            "compare", "comparison", "between", "please", "find", "evidence", "missing"}
    words = [w for w in re.findall(r"[\w.-]+", text) if w.casefold() not in stop]
    if len(" ".join(words)) > 200:
        named = [w for w in words if w[0].isupper() or any(c.isdigit() for c in w)]
        words = list(dict.fromkeys(named + words))
    selected = []
    for word in words:
        if len(" ".join(selected + [word])) > 200:
            continue
        selected.append(word)
    return " ".join(selected)


def r1_evidence_gaps(plan):
    """Extract search intent, never claims, from the checked-in R1 plan contract."""
    gaps = []
    for question in plan.get("research_questions", []):
        gaps.extend(question.get("missing", []))
        if question.get("missing"):
            gaps.append(" ".join(question.get("metrics", []) + question.get("periods", [])))
    for entry in plan.get("evidence_ledger", []):
        if entry.get("status") == "planned_lookup":
            gaps.append(entry.get("claim_supported", ""))
    for step in plan.get("checklist", []):
        gaps.extend([step.get("expected_evidence", ""), *step.get("cross_validation_sources", [])])
    return list(dict.fromkeys(g.strip() for g in gaps if isinstance(g, str) and g.strip()))[:12]


class _ResultLinks(HTMLParser):
    def __init__(self, all_links=False):
        super().__init__(convert_charrefs=True)
        self.current = None
        self.results = []
        self.all_links = all_links

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and (self.all_links or set(attrs.get("class", "").split()) & {"result-link", "result__a"}):
            self.current = {"href": attrs.get("href", ""), "title": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["title"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.results.append(self.current)
            self.current = None


class DuckDuckGoSearch:
    """Public Lite HTML, bounded once; challenges fail, never bypassed/retried."""
    name = "duckduckgo_lite"
    execution_mode = "real"

    def __init__(self, *, opener=None, max_response_bytes=2 * 1024 * 1024):
        self._opener = opener or urllib.request.build_opener(public_sources._NoRedirect())
        self.max_response_bytes = max_response_bytes

    def search(self, query, *, timeout=20):
        url = urllib.parse.urlunsplit(("https", "lite.duckduckgo.com", "/lite/",
            urllib.parse.urlencode({"q": query}), ""))
        try:
            request = urllib.request.Request(url, headers={"User-Agent": public_sources.USER_AGENT,
                                                           "Accept": "text/html"})
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
                status = getattr(response, "status", 200)
            if len(raw) > self.max_response_bytes:
                raise SearchError("DuckDuckGo response exceeded byte budget")
            html = raw.decode("utf-8", "replace")
            if status != 200 or re.search(r"anomaly\.js|challenge-form|anomaly-modal|captcha", html, re.I):
                raise SearchError("DuckDuckGo challenge or unavailable response; not bypassed")
            parser = _ResultLinks()
            parser.feed(html)
            results = []
            for link in parser.results:
                href = urllib.parse.urljoin(url, link["href"])
                parsed = urllib.parse.urlsplit(href)
                if _matches(parsed.hostname or "", ["duckduckgo.com"]):
                    href = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
                if not _public_url(href):
                    continue
                results.append({"url": href, "title": " ".join(link["title"].split()),
                    "search_provider": self.name, "search_publisher": "DuckDuckGo",
                    "search_result_url": url, "url_provenance": "html.result-link.href",
                    "document_publisher_status": "unknown", "company_identity_status": "unresolved"})
            return {"results": results, "executed_queries": [query]}
        except SearchError:
            raise
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise SearchError(f"DuckDuckGo HTTP {code}") from None
        except Exception:
            raise SearchError("DuckDuckGo transport or HTML format failure") from None


class GeminiGoogleSearch:
    """Official REST API; credentials only in the API-key header, no retries.

    max_queries bounds logical searches (up to one Gemini and one Bing call each).
    Google may execute multiple billed internal
    searches per call; their count is recorded, not a hard monetary budget.
    """
    name = "gemini_google_grounding"
    execution_mode = "real"

    def __init__(self, model=None, *, opener=None, max_response_bytes=2 * 1024 * 1024,
                 fallback=True):
        self.model = (model or os.environ.get("SIGNALFORGE_SEARCH_MODEL")
                      or os.environ.get("SIGNALFORGE_MODEL") or "gemini-3.8-flash")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.model):
            raise ValueError("Invalid search model")
        self._opener = opener or urllib.request.build_opener(public_sources._NoRedirect())
        self.max_response_bytes = max_response_bytes
        self.fallback = fallback

    def search(self, query, *, timeout=20):
        started = time.monotonic()
        # Reserve part of each call for public search, including slow Gemini errors.
        try:
            return self._search_gemini(query, timeout=timeout * 0.6 if self.fallback else timeout)
        except SearchError as exc:
            if not self.fallback:
                raise
            remaining = timeout - (time.monotonic() - started)
            failure = str(exc)
            if remaining <= 0:
                return {"results": [], "executed_queries": [], "provider_attempts": [
                    {"provider": self.name, "error": failure}]}
            try:
                reply = BingRSSSearch(max_response_bytes=self.max_response_bytes).search(query, timeout=remaining)
                reply["provider_attempts"] = [{"provider": self.name, "error": failure},
                    *reply.get("provider_attempts", [{"provider": "bing_rss", "status": "completed"}])]
                return reply
            except SearchError as fallback_error:
                return {"results": [], "executed_queries": [], "provider_attempts": [
                    {"provider": self.name, "error": failure},
                    {"provider": "bing_rss", "error": str(fallback_error)}]}

    def _search_gemini(self, query, *, timeout=20):
        key = (os.environ.get("SIGNALFORGE_API_KEY") or os.environ.get("GEMINI_API_KEY")
               or os.environ.get("GOOGLE_API_KEY"))
        if not key:
            raise SearchError("Search credential missing from environment")
        request = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps({"contents": [{"parts": [{"text":
                "Search public sources for this query. Use Google Search. "
                "Find original documents and independent sources: " + query}]}],
                "tools": [{"google_search": {}}]}).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raise SearchError("Search response exceeded byte budget")
            payload = json.loads(raw)
            results, executed, entries = [], [], []
            for candidate in payload.get("candidates", []):
                metadata = candidate.get("groundingMetadata", {})
                executed.extend(metadata.get("webSearchQueries", []))
                if metadata.get("searchEntryPoint"):
                    entries.append(metadata["searchEntryPoint"])
                for index, chunk in enumerate(metadata.get("groundingChunks", [])):
                    web = chunk.get("web", {})
                    if _public_url(web.get("uri")):
                        results.append({"url": web["uri"], "title": web.get("title", ""),
                                        "grounding_chunk_index": index,
                                        "search_provider": self.name,
                                        "url_provenance": "groundingMetadata.groundingChunks.web.uri"})
            # No model prose, citations parsed from text, or inferred URLs.
            return {"results": results, "executed_queries": executed, "search_entry_points": entries}
        except SearchError:
            raise
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise SearchError(f"Search HTTP {code}") from None
        except Exception:
            raise SearchError("Search transport or response format failure") from None


class BingRSSSearch:
    """Public RSS search; item links are candidates, not fetched/verified claims.

    RSS descriptions are deliberately discarded. Search publisher is Bing;
    linked-document publisher, date, identity and independence remain unknown.
    Default fallback probes DuckDuckGo Lite once when RSS has no company-related
    research-document hints or fails; at most two requests per logical search.
    """
    name = "bing_rss"
    execution_mode = "real"

    def __init__(self, *, opener=None, max_response_bytes=2 * 1024 * 1024, fallback=True):
        self._opener = opener or urllib.request.build_opener(public_sources._NoRedirect())
        self.max_response_bytes = max_response_bytes
        self.fallback = fallback

    def search(self, query, *, timeout=20):
        started = time.monotonic()
        reply = {"results": [], "executed_queries": []}
        attempts = []
        try:
            reply = self._search_rss(query, timeout=timeout * 0.4 if self.fallback else timeout)
            quoted = re.match(r'"([^"]+)"', query)
            useful = [hit for hit in reply["results"] if research_document_hint(hit)
                      and (not quoted or company_relevance(hit, quoted[1])[0])]
            attempts.append({"provider": self.name, "status": "completed",
                             "returned_count": len(reply["results"]), "research_document_hints": len(useful)})
            if useful or not self.fallback:
                return reply
        except SearchError as exc:
            if not self.fallback:
                raise
            attempts.append({"provider": self.name, "error": str(exc)})
        remaining = timeout - (time.monotonic() - started)
        if remaining > 0:
            try:
                extra = DuckDuckGoSearch(max_response_bytes=self.max_response_bytes).search(query, timeout=remaining)
                reply["results"].extend(extra["results"])
                reply["executed_queries"].extend(extra["executed_queries"])
                attempts.append({"provider": "duckduckgo_lite", "status": "completed",
                                 "returned_count": len(extra["results"])})
            except SearchError as exc:
                attempts.append({"provider": "duckduckgo_lite", "error": str(exc)})
        reply["provider_attempts"] = attempts
        return reply

    def _search_rss(self, query, *, timeout=20):
        search_url = urllib.parse.urlunsplit(("https", "www.bing.com", "/search",
            urllib.parse.urlencode({"format": "rss", "q": query}), ""))
        request = urllib.request.Request(search_url, headers={
            "User-Agent": public_sources.USER_AGENT, "Accept": "application/rss+xml,application/xml"})
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raise SearchError("Bing RSS response exceeded byte budget")
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise SearchError("Bing RSS XML declarations rejected")
            root = ET.fromstring(raw)
            if root.tag != "rss" or root.find("channel") is None:
                raise SearchError("Bing RSS response is not an RSS feed")
            results = []
            for item in root.findall("./channel/item"):
                url = (item.findtext("link") or "").strip()
                if _public_url(url):
                    results.append({"url": url, "title": item.findtext("title") or "",
                        "search_provider": self.name, "search_publisher": "Bing",
                        "search_result_url": search_url, "url_provenance": "rss.channel.item.link",
                        "document_publisher_status": "unknown", "company_identity_status": "unresolved"})
            return {"results": results, "executed_queries": [query]}
        except SearchError:
            raise
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise SearchError(f"Bing RSS HTTP {code}") from None
        except Exception:
            raise SearchError("Bing RSS transport or XML format failure") from None


class FixtureSearch:
    """Replay a JSON mapping from exact query (or '*') to provider reply."""
    name = "fixture"
    execution_mode = "fixture/replay"

    def __init__(self, responses):
        self.responses = responses

    def search(self, query, *, timeout=20):
        reply = self.responses.get(query, self.responses.get("*"))
        if reply is None or "error" in reply:
            raise SearchError("Fixture search unavailable")
        return reply


def research_document_hint(result):
    text = str(result.get("title", "")) + " " + str(result.get("url", ""))
    return bool(re.search(r"\.pdf(?:[?#]|$)|annual[ _/-]*report|financial[ _/-]*result|"
                          r"commission|regulator|tariff|investor|presentation|filing", text, re.I))


def _site_links(seeds, output, budget, deadline, log):
    """Robots-aware bounded link discovery. Never guess document URL paths."""
    queue = list(dict.fromkeys(seeds))
    hosts = {urllib.parse.urlsplit(u).hostname for u in queue if _public_url(u)}
    seen, results = set(), []
    while queue and len(seen) < budget.max_site_pages and time.monotonic() < deadline:
        parent = queue.pop(0)
        if parent in seen or not _public_url(parent):
            continue
        seen.add(parent)
        log("site_page_requested", url=parent)
        try:
            report = public_sources.retrieve_urls([parent], output / "site_pages",
                timeout=min(budget.request_timeout, max(0.1, deadline-time.monotonic())),
                max_bytes=budget.max_response_bytes, opener=_PublicOpener(deadline), source_relationship="unknown")
            log("site_page_retrieval", url=parent, report=report)
            for source in report["sources"]:
                if source.get("retrieval_status") != "retrieved":
                    continue
                path = Path(source["saved_path"])
                if path.suffix not in {".html", ".htm"}:
                    continue
                parser = _ResultLinks(all_links=True)
                parser.feed(path.read_text(encoding="utf-8", errors="replace"))
                found = []
                for anchor in parser.results:
                    url = urllib.parse.urljoin(source["canonical_url"], anchor["href"])
                    p = urllib.parse.urlsplit(url)
                    if not _public_url(url) or not research_document_hint({"url":url,"title":anchor["title"]}):
                        continue
                    hit = {"url": url, "title": " ".join(anchor["title"].split()),
                           "search_provider": "public_site_links", "url_provenance": "retrieved_html.anchor.href",
                           "parent_url": source["canonical_url"], "parent_sha256": source["source_sha256"],
                           "parent_snapshot_path": str(path), "company_identity_status": "unresolved"}
                    found.append(hit)
                    if len(found) >= 100:
                        break
                results.extend(found)
                log("site_links_discovered", parent_url=source["canonical_url"], results=found)
                # Follow report indexes before other HTML, then order newest first.
                pages = [h for h in found if not urllib.parse.urlsplit(h["url"]).path.lower().endswith(".pdf")
                         and urllib.parse.urlsplit(h["url"]).hostname in hosts]
                pages.sort(key=lambda h:("annual" in (h["title"]+h["url"]).lower(),
                                         h["url"]), reverse=True)
                queue = [h["url"] for h in pages if h["url"] not in seen] + queue
        except Exception:
            log("site_page_failed", url=parent, error="Public site page retrieval/parsing failed")
    return results


def rank_urls(results, *, issuer_domains=(), authority_domains=None, topic=""):
    """Conservative host-based hints; no claim of actual source independence."""
    issuer_domains = tuple(_domain(d) for d in issuer_domains)
    authorities = { _domain(k): v for k, v in (authority_domains or {}).items() }
    allowed = {"exchange_hosted_issuer_copy", "government_regulator", "industry", "competitor", "press_analysis"}
    if any(v not in allowed for v in authorities.values()):
        raise ValueError("Invalid authority classification")
    ranked, seen = [], set()
    for result in results:
        url = result.get("url")
        if not _public_url(url):
            continue
        p = urllib.parse.urlsplit(url)
        normalized = urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))
        if normalized in seen:
            continue
        seen.add(normalized)
        host = p.hostname.lower()
        kind = "unknown"
        if _matches(host, issuer_domains):
            kind = "primary_issuer"
        else:
            kind = next((v for d, v in authorities.items() if _matches(host, [d])), "unknown")
        title = str(result.get("title", ""))
        score = {"primary_issuer": 50, "government_regulator": 45,
                 "exchange_hosted_issuer_copy": 40, "industry": 25}.get(kind, 10)
        score += 5 if re.search(r"annual|report|filing|results", title, re.I) else 0
        score += 30 if p.path.lower().endswith(".pdf") else 0
        score += 15 if research_document_hint(result) else 0
        score -= 20 if p.path in {"", "/"} else 0
        match_text = (title + " " + urllib.parse.unquote(p.path)).casefold()
        score += 6 * sum(w.casefold() in match_text for w in set(_search_terms(topic).split()))
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", match_text)]
        score += max((max(0, min(10, y - 2015)) for y in years), default=0)
        ranked.append({**result, "url": normalized, "source_class": kind, "rank_score": score,
                       "classification_status": "unverified_host_hint", "publisher": None,
                       "publication_date": None, "issuer_submitted": None, "derived_from": [],
                       "independent_group_id": None, "retrieval_status": "not_requested"})
    return sorted(ranked, key=lambda r: (-r["rank_score"], r["url"]))


def company_relevance(result, company, issuer_domains=()):
    """Lexical screening, not identity verification; ignore snippets/query strings."""
    url = result.get("url")
    if not _public_url(url):
        return False, "invalid_or_non_public_result_url"
    p = urllib.parse.urlsplit(url)
    context = (p.hostname + p.path + ' ' + str(result.get('title', ''))).casefold()
    if re.search(r"dictionary|merriam-webster|vocabulary\.com|\bdefinition\b", context):
        return False, "dictionary_or_definition_not_research_source"
    if re.search(r"careers?|recruitment|\blogin\b|\bsign in\b|ntpctender|/tenders?", context):
        return False, "non_research_employment_login_or_tender_portal"
    trusted_domains = tuple(_domain(d) for d in issuer_domains)
    if _matches(p.hostname.lower(), trusted_domains):
        return True, "issuer_domain_match_unverified"
    if any(d + "." in p.hostname.lower() for d in trusted_domains):
        return False, "issuer_domain_embedded_in_untrusted_hostname"
    words = re.findall(r"[a-z0-9]+", company.casefold())
    legal = {"limited", "ltd", "corporation", "corp", "inc", "incorporated", "company",
             "co", "plc", "llc", "india", "indian", "of", "the", "and", "private", "pvt"}
    generic = legal | {"power", "grid", "energy", "electric", "electricity", "national",
                       "holdings", "group", "international", "industries", "services"}
    brand_words = [w for w in words if w not in legal]
    distinctive = {w for w in words if w not in generic and len(w) >= 3}
    text = str(result.get("title", "")) + " " + p.hostname + " " + urllib.parse.unquote(p.path)
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    # RRB NTPC denotes an unrelated railway examination, not the issuer.
    if "ntpc" in words and re.search(r"\b(rrb|railway|railways)\b", text, re.I):
        return False, "ambiguous_company_acronym_railway_context"
    if distinctive.intersection(tokens):
        return True, "distinctive_company_token_match_unverified"
    if len(brand_words) >= 2:
        compact = "".join(brand_words)
        phrase = " ".join(brand_words)
        if compact in tokens or re.search(r"\b" + re.escape(phrase) + r"\b", " ".join(tokens)):
            return True, "company_brand_phrase_match_unverified"
    acronym_words = [w for w in words if w not in {"of", "the", "and"}]
    acronym = "".join(w[0] for w in acronym_words)
    if len(acronym_words) >= 3 and len(acronym) >= 3 and acronym in tokens:
        return True, "company_derived_acronym_match_unverified"
    return False, "no_distinctive_company_token_brand_or_issuer_domain_match"


class _PublicOpener:
    """Validate robots and redirect requests too, before public_sources opens them."""
    def __init__(self, deadline):
        self.deadline = deadline
        self.inner = urllib.request.build_opener(public_sources._NoRedirect())

    def open(self, request, timeout=20):
        url = request.full_url
        if not _public_url(url):
            raise public_sources.RetrievalError("Non-public URL rejected")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise public_sources.RetrievalError("Discovery time budget exhausted")
        p = urllib.parse.urlsplit(url)
        addresses = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise public_sources.RetrievalError("Non-public resolved address rejected")
        return self.inner.open(request, timeout=min(timeout, remaining))


def discover(company, topic, *, provider, budget=None, domains=(), issuer_domains=(),
             authority_domains=None, date_window=None, evidence_gaps=(), output_dir=None,
             retrieve=False, registry_path=None, r1_plan=None, seed_urls=()):
    """Search R1 gaps and contradictions; optionally ingest via public_sources.

    Output directory must be fresh. Retrieval keeps source relationship unknown;
    company registry association and review approval are never manufactured.
    Deadlines are cooperative across operations, not process-level cancellation.
    """
    budget = budget or Budget()
    gaps = [*evidence_gaps, *r1_evidence_gaps(r1_plan or {})]
    queries = build_queries(company, topic, domains, date_window, gaps)
    rank_urls([], issuer_domains=issuer_domains, authority_domains=authority_domains)
    if retrieve and provider.execution_mode != "real":
        raise ValueError("Fixture replay cannot perform network retrieval")
    if retrieve and output_dir is None:
        raise ValueError("Retrieval requires output_dir")
    output = Path(output_dir) if output_dir is not None else None
    site_seeds = [*seed_urls, *("https://"+_domain(d)+"/" for d in issuer_domains)]
    if any(not _public_url(u) for u in site_seeds):
        raise ValueError("Invalid public site seed")
    if output:
        output.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + budget.max_seconds
    search_deadline = deadline - (budget.max_seconds * 0.45 if site_seeds and output and budget.max_site_pages else 0)
    report = {"company": company, "topic": topic, "provider": provider.name,
              "execution_mode": provider.execution_mode, "search_queries": [],
              "search_results": [], "action_log": [], "errors": [],
              "returned_result_count": 0, "relevant_returned_count": 0,
              "relevant_result_count": 0, "rejected_result_count": 0,
              "rejected_results": [], "discovery_status": "no_relevant_candidates",
              "retrieval_status": "not_requested", "budget": vars(budget),
              "company_identity_status": "unresolved", "finding_status": "no_finding",
              "evidence_gaps": gaps, "research_document_count": 0,
              "site_seeds": site_seeds, "site_discovered_count": 0,
              "site_rejected_results": [],
              "finding_reason": "Discovery candidates only; identity and claims have not been verified.",
              "limitations": ["Search results and host classifications are unverified.",
                              "Provider internal searches are not a hard billing budget.",
                              "Independent publication and document lineage require review."],
              "stop_reason": "queries_complete"}

    def persist():
        if output:
            (output / "discovery_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    def log(action, **fields):
        report["action_log"].append({"action": action,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(), **fields})
        persist()

    hits = []
    for query in queries:
        if len(report["search_queries"]) >= budget.max_queries:
            report["stop_reason"] = "query_budget"
            break
        if time.monotonic() >= search_deadline:
            report["stop_reason"] = "time_budget"
            break
        if len(report["search_results"]) >= budget.max_results:
            report["stop_reason"] = "result_budget"
            break
        report["search_queries"].append(query)
        log("search_requested", query=query)
        try:
            reply = provider.search(query, timeout=min(budget.request_timeout, search_deadline - time.monotonic()))
            for attempt in reply.get("provider_attempts", []):
                if attempt.get("error"):
                    report["errors"].append({"query": query, **attempt})
                log("search_provider_attempt", query=query, **attempt)
            found = reply["results"]
            if not isinstance(found, list):
                raise ValueError("Invalid provider results")
            report["returned_result_count"] += len(found)
            relevant = []
            for hit in found:
                accepted, reason = (company_relevance(hit, company, issuer_domains)
                                    if isinstance(hit, dict) else (False, "malformed_result"))
                if accepted:
                    relevant.append({**hit, "query": query, "relevance_reason": reason})
                else:
                    rejection = {"query": query, "result": hit, "rejection_reason": reason}
                    report["rejected_results"].append(rejection)
                    log("search_result_rejected", **rejection)
            report["relevant_returned_count"] += len(relevant)
            report["rejected_result_count"] = len(report["rejected_results"])
            hits.extend(relevant)
            report["search_results"] = rank_urls(hits, issuer_domains=issuer_domains,
                authority_domains=authority_domains, topic=topic)[:budget.max_results]
            report["relevant_result_count"] = len(report["search_results"])
            report["research_document_count"] = sum(research_document_hint(h) for h in report["search_results"])
            report["discovery_status"] = ("unverified_relevant_candidates" if report["search_results"]
                                          else "no_relevant_candidates")
            log("search_completed", query=query, results=found,
                returned_count=len(found), relevant_count=len(relevant), rejected_count=len(found)-len(relevant),
                executed_queries=reply.get("executed_queries", []),
                search_entry_points=reply.get("search_entry_points", []))
            if not found:
                log("search_no_results", query=query)
        except Exception as exc:
            # Provider implementations may accidentally include credentials in errors.
            safe_error = "Search failed; no URLs inferred; next query attempted"
            if type(provider) in {GeminiGoogleSearch, BingRSSSearch, DuckDuckGoSearch} and isinstance(exc, SearchError):
                safe_error = str(exc)
            error = {"query": query, "error": safe_error}
            report["errors"].append(error)
            log("search_failed", **error)
    if site_seeds and output and provider.execution_mode == "real" and budget.max_site_pages:
        links = _site_links(site_seeds, output, budget, deadline, log)
        for hit in links:
            accepted, reason = company_relevance(hit, company, issuer_domains)
            if accepted:
                hits.append({**hit, "relevance_reason": reason})
                report["site_discovered_count"] += 1
            else:
                rejection = {"query": None, "result": hit, "rejection_reason": reason}
                report["site_rejected_results"].append(rejection)
                log("site_link_rejected", **rejection)
        report["search_results"] = rank_urls(hits, issuer_domains=issuer_domains,
            authority_domains=authority_domains, topic=topic)[:budget.max_results]
        report["relevant_result_count"] = len(report["search_results"])
        report["research_document_count"] = sum(research_document_hint(h) for h in report["search_results"])
        report["discovery_status"] = ("unverified_relevant_candidates" if report["search_results"] else "no_relevant_candidates")
        log("site_discovery_completed", accepted_link_count=report["site_discovered_count"])
    if retrieve:
        report["retrieval_status"] = "no_results"
        for hit in report["search_results"][:budget.max_fetches]:
            if time.monotonic() >= deadline:
                report["stop_reason"] = "time_budget"
                break
            log("retrieval_requested", url=hit["url"])
            try:
                retrieval = public_sources.retrieve_urls([hit["url"]], output / "retrieved",
                    registry_path=registry_path, timeout=min(budget.request_timeout, deadline - time.monotonic()),
                    opener=_PublicOpener(deadline), source_relationship="unknown")
                hit["retrieval_status"] = "retrieved" if retrieval["retrieved_count"] else "failed"
                hit["retrieval_report"] = retrieval
                log("retrieval_completed", url=hit["url"], report=retrieval)
            except Exception:
                hit["retrieval_status"] = "failed"
                report["errors"].append({"url": hit["url"], "error": "Retrieval failed"})
                log("retrieval_failed", url=hit["url"])
        statuses = [h["retrieval_status"] for h in report["search_results"]]
        report["retrieval_status"] = ("retrieved" if "retrieved" in statuses else
                                      "failed" if "failed" in statuses else "not_attempted")
    log("discovery_stopped", reason=report["stop_reason"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--issuer-domain", action="append", default=[])
    parser.add_argument("--evidence-gap", action="append", default=[])
    parser.add_argument("--r1-plan", type=Path, help="R1 JSON; use missing evidence/metrics as query intent")
    parser.add_argument("--seed-url", action="append", default=[], help="Operator-supplied public research index; no inferred identity")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fixture", type=Path, help="JSON provider replies; no network")
    parser.add_argument("--model")
    parser.add_argument("--provider", choices=["auto", "gemini", "bing", "duckduckgo"], default="auto")
    parser.add_argument("--retrieve", action="store_true")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--max-queries", type=int, default=6)
    parser.add_argument("--max-results", type=int, default=20)
    parser.add_argument("--max-fetches", type=int, default=5)
    parser.add_argument("--max-seconds", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        if bool(args.date_from) != bool(args.date_to):
            raise ValueError("Both date bounds required")
        budget = Budget(args.max_queries, args.max_results, args.max_fetches, args.max_seconds)
        provider = (FixtureSearch(json.loads(args.fixture.read_text())) if args.fixture else
                    DuckDuckGoSearch(max_response_bytes=budget.max_response_bytes) if args.provider == "duckduckgo" else
                    BingRSSSearch(max_response_bytes=budget.max_response_bytes) if args.provider == "bing" else
                    GeminiGoogleSearch(args.model, max_response_bytes=budget.max_response_bytes,
                                       fallback=args.provider == "auto"))
        report = discover(args.company, args.topic, provider=provider, budget=budget,
            domains=args.domain, issuer_domains=args.issuer_domain, evidence_gaps=args.evidence_gap,
            date_window=(args.date_from, args.date_to) if args.date_from else None,
            output_dir=args.output_dir, retrieve=args.retrieve, registry_path=args.registry,
            r1_plan=json.loads(args.r1_plan.read_text()) if args.r1_plan else None, seed_urls=args.seed_url)
        print(json.dumps({"execution_mode": report["execution_mode"],
                          "result_count": len(report["search_results"]),
                          "returned_result_count": report["returned_result_count"],
                          "relevant_result_count": report["relevant_result_count"],
                          "rejected_result_count": report["rejected_result_count"],
                          "discovery_status": report["discovery_status"],
                          "retrieval_status": report["retrieval_status"],
                          "stop_reason": report["stop_reason"]}))
        return 0 if report["search_results"] and (not args.retrieve or report["retrieval_status"] == "retrieved") else 2
    except Exception:
        print("Discovery failed: check arguments, credentials and fresh output directory.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
