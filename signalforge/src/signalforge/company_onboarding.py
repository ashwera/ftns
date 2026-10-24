"""Zero-setup onboarding for a company that is not in ``company_registry.json``.

Replaces hand-built registry entries and human evidence approval with public,
machine-checkable steps:

1. Acquire a candidate annual-report PDF (drop folder, the company's own site found
   through Wikidata, Gemini-suggested URLs, public search). Every URL is only a
   *candidate*; nothing is trusted because of where it came from.
2. Read the issuer identity from the PDF itself: a valid ISIN (ISO 6166 check digit)
   labelled "ISIN" within the text next to the company's own name.
3. Pin the file by SHA-256 and write a run-local registry entry whose verification
   source is that exact page. The existing ``machine_evidence`` policy then re-opens
   the pinned bytes and re-checks the declaration and each passage.
4. Cross-check the ISIN against Wikidata when available. Agreement is recorded as
   corroboration; disagreement or silence is recorded, never hidden.

This establishes "the document says it is issued by X with ISIN Y", not that the
document is authentic or that its numbers are correct.
"""
from html.parser import HTMLParser
from html import unescape
import contextvars
from functools import wraps
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .source_discovery import _public_url

MAX_PDF_BYTES = 64 * 1024 * 1024
MAX_PAGE_BYTES = 3 * 1024 * 1024
UA = "Mozilla/5.0 (compatible; SignalForgeResearch/0.1)"
ISIN_RE = re.compile(r"(?<![A-Z0-9])(INE[0-9A-Z]{8}[0-9])(?![A-Z0-9])")
CIN_RE = re.compile(r"(?<![A-Z0-9])([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})(?![A-Z0-9])")
LEGAL = r"(?:\s+(?:of\s+India\s+)?(?:Limited|Ltd\.?))?"
IR_PATHS = ("/investors", "/investor-relations", "/investor", "/investors/annual-reports",
            "/investor-relations/annual-reports", "/annual-reports")
DROP_DIR = Path(__file__).resolve().parents[2] / "data" / "demo_drop"
_deadline = contextvars.ContextVar("onboarding_deadline", default=None)


def remaining(timeout):
    deadline = _deadline.get()
    if deadline is None:
        return timeout
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError("Onboarding time budget exhausted")
    return min(timeout, seconds)


def bounded_onboarding(function):
    @wraps(function)
    def wrapper(*args, max_seconds=150, **kwargs):
        token = _deadline.set(time.monotonic() + max_seconds)
        try:
            return function(*args, **kwargs)
        finally:
            _deadline.reset(token)
    return wrapper


def isin_valid(isin):
    """ISO 6166: letters expand to two digits, then Luhn over the digit string."""
    if not re.fullmatch(r"[A-Z]{2}[0-9A-Z]{9}[0-9]", isin or ""):
        return False
    digits = "".join(str(int(c, 36)) for c in isin)
    total = 0
    for index, char in enumerate(reversed(digits)):
        n = int(char)
        if index % 2:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def core_name(company):
    core = re.sub(r"\b(limited|ltd\.?|corporation of india|of india)\b", "", company, flags=re.I)
    return re.sub(r"\s+", " ", core).strip(" ,.-")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def read_identity(pdf_bytes, company, max_pages=1000):
    """Find (name, isin, page, snippet) where the PDF declares the issuer and ISIN."""
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(pdf_bytes))
    if reader.is_encrypted or not 1 <= len(reader.pages) <= max_pages:
        raise ValueError("Encrypted or oversized PDF is ineligible")
    core = core_name(company)
    if len(core) < 3:
        raise ValueError("Company name too short to match")
    name_re = re.compile(r"(?<!\w)" + re.escape(core).replace(r"\ ", r"\s+") + LEGAL + r"(?!\w)", re.I)
    found = []
    for number, page in enumerate(reader.pages, 1):
        remaining(1)
        text = page.extract_text() or ""
        for match in CIN_RE.finditer(text):
            snippet = text[max(0, match.start() - 1200):match.end() + 300]
            named = name_re.search(snippet)
            if named and re.search(r"\bCIN\b|Corporate\s+Identi(?:ty|fication)\s+Number", text[max(0,match.start()-120):match.start()], re.I):
                found.append({"canonical_name": re.sub(r"\s+", " ", named.group(0)).strip(),
                    "isin": None, "identifier": match.group(1), "identifier_type": "CIN", "page": number, "snippet": snippet})
        for match in ISIN_RE.finditer(text):
            isin = match.group(1)
            # Equity securities carry type code 01; debentures/NCDs of the same issuer do not.
            if not isin_valid(isin) or isin[7:9] != "01":
                continue
            if not re.search(r"ISIN", text[max(0, match.start() - 450):match.end() + 20], re.I):
                continue
            snippet = text[max(0, match.start() - 1200):match.end() + 300]
            named = name_re.search(snippet)
            if named:
                found.append({"canonical_name": re.sub(r"\s+", " ", named.group(0)).strip(), "isin": isin, "identifier": isin, "identifier_type": "ISIN",
                              "page": number, "snippet": snippet})
        if found and number >= found[0]["page"] + 40:
            break
    if found:
        found = [i for i in found if i.get("isin")] or found
        counts = {}
        for item in found:
            counts[item["identifier"]] = counts.get(item["identifier"], 0) + 1
        best = max(counts, key=lambda k: (counts[k], -min(i["page"] for i in found if i["identifier"] == k)))
        return next(i for i in found if i["identifier"] == best)
    raise ValueError("No labelled ISIN or CIN declaration next to the company name found in the PDF")


def download_pdf(url, dest_dir, timeout=60):
    """Bounded public download; accepts only a real PDF. Returns (path, sha256)."""
    if not _public_url(url):
        raise ValueError("Non-public URL refused")
    import time
    from . import public_sources
    from .source_discovery import _PublicOpener
    timeout = remaining(timeout)
    retrieved = public_sources.retrieve_urls([url], dest_dir, timeout=timeout, max_bytes=MAX_PDF_BYTES,
        opener=_PublicOpener(time.monotonic() + timeout), source_relationship="unknown", normalize_evidence=False)
    source = next((s for s in retrieved["sources"] if s.get("retrieval_status") == "retrieved"), None)
    if source is None:
        raise ValueError("Public PDF retrieval failed; inspect onboarding_pdfs/retrieval_report.json")
    path = Path(source["saved_path"])
    data = path.read_bytes()
    if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("Not a bounded PDF")
    digest = _sha(data)
    return path, digest


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self._href, self._text = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href, self._text = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None


def _fetch_text(url, timeout=25, final_url_out=None):
    if not _public_url(url):
        return ""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=remaining(timeout)) as response:
            if not _public_url(response.geturl()):
                return ""
            if final_url_out is not None:
                final_url_out.append(response.geturl())
            return response.read(MAX_PAGE_BYTES).decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, ValueError):
        return ""


def page_links(url):
    parser = _Links()
    final = []
    content = _fetch_text(url, final_url_out=final)
    document_url = final[0] if final else url
    try:
        parser.feed(content)
    except Exception:
        pass
    out = []
    for href, text in parser.links:
        absolute = urllib.parse.urljoin(document_url, href.strip())
        if _public_url(absolute):
            out.append((absolute, text))
    # Some issuer sites embed the report table as HTML strings in a script.
    # Extract only literal PDF hrefs as untrusted navigation leads; execute no JS.
    seen = {u for u, _ in out}
    for href in re.findall(r'''href\s*=\s*["']([^"']+\.pdf(?:\?[^"']*)?)["']''', content, re.I)[:500]:
        absolute = urllib.parse.urljoin(document_url, unescape(href))
        if _public_url(absolute) and absolute not in seen:
            out.append((absolute, ""))
            seen.add(absolute)
    return out


def score_pdf_link(url, text="", company=None):
    """Prefer the latest annual / integrated report; reject obvious non-reports."""
    blob = urllib.parse.unquote(url + " " + text).lower()
    if ".pdf" not in blob:
        return 0
    if re.search(r"policy|code-of|terms|notice|presentation|factsheet|newsletter|circular|esg-data", blob):
        return 0
    score = 0
    if re.search(r"annual[-_ ]?report|integrated[-_ ]?(annual[-_ ]?)?report|(?:^|[^a-z])(?:i?ar)[-_ ]?20", blob):
        score += 5
    if re.search(r"2024[-_ /]?25|2025[-_ /]?26|fy[-_ ]?25|fy[-_ ]?26|2025", blob):
        score += 4
    elif re.search(r"2023[-_ /]?24|fy[-_ ]?24", blob):
        score += 2
    if re.search(r"standalone|consolidated.*financial|abridged|summary", blob):
        score -= 2
    if company and score:
        words = re.findall(r"[a-z0-9]+", company.lower())
        core = [w for w in words if w not in {"limited", "ltd", "of", "the"}]
        compact = "".join(core)
        acronym = "".join(w[0] for w in words if w not in {"of", "the"})
        filename = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]).lower()
        if compact and len(compact) >= 4 and compact in re.sub(r"[^a-z0-9]", "", filename):
            score += 8
        elif len(acronym) >= 3 and re.search(r"(?:^|[^a-z])" + re.escape(acronym) + r"(?:[^a-z]|$)", filename):
            score += 8
    years = [int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", blob)]
    return score + (max(years) - 2000) / 100 if score and years else score


def wikidata_identity(company, timeout=20):
    """Public cross-check: (isin, website). Failures return (None, None)."""
    def get(url):
        request = urllib.request.Request(url, headers={"User-Agent": "SignalForgeDemo/0.1 (research)"})
        with urllib.request.urlopen(request, timeout=remaining(timeout)) as response:
            return json.load(response)
    try:
        found = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&limit=5&search="
                    + urllib.parse.quote(core_name(company)))
        best = None
        for entity in found.get("search", []):
            claims = get(f"https://www.wikidata.org/wiki/Special:EntityData/{entity['id']}.json")["entities"][entity["id"]]["claims"]
            isins = [c["mainsnak"]["datavalue"]["value"] for c in claims.get("P946", []) if "datavalue" in c["mainsnak"]]
            sites = [c["mainsnak"]["datavalue"]["value"] for c in claims.get("P856", []) if "datavalue" in c["mainsnak"]]
            indian = [i for i in isins if i.startswith("INE")]
            if indian or sites:
                best = (indian[0] if indian else None, sites[0] if sites else None)
                if indian:
                    break
        return best or (None, None)
    except Exception:
        return None, None


def gemini_url_suggestions(company, config, timeout=60):
    """Unverified URL hints via the selected inference route; never web evidence.

    Historical function name retained for compatibility. Actual URLs must be
    downloaded and checked; model memory is not proof of existence or identity.
    """
    try:
        from dataclasses import replace
        from .llm_client import generate_json
        reply = generate_json('Return JSON {"urls": [up to three official company homepage or annual-report index URLs]}. '
            'These are unverified navigation hints, not search results. Do not provide guessed document filenames or financial facts.',
            {"company": company}, replace(config, request_timeout=min(30, remaining(timeout))))
        urls = reply.get("urls", [])
        return [u for u in urls if isinstance(u, str) and _public_url(u)][:5]
    except Exception:
        return []


def bing_pdf_candidates(company):
    try:
        from .source_discovery import BingRSSSearch
        reply = BingRSSSearch().search(f'"{company}" annual report 2024-25 filetype:pdf', timeout=25)
        return [r["url"] for r in reply.get("results", []) if ".pdf" in r["url"].lower()]
    except Exception:
        return []


def candidate_pdf_urls(company, config, log):
    """Yield (url, origin) most-promising first. Pure candidates; nothing trusted."""
    seeds, seen = [], set()
    isin, site = wikidata_identity(company)
    log("wikidata", isin=isin, website=site)
    from .llm_client import trace_requests
    calls = []
    with trace_requests(calls, "onboarding_url_hints"):
        hints = gemini_url_suggestions(company, config)
    log("model_url_hints", urls=hints, model_calls=calls, status="unverified_navigation_candidates_only")
    for url in hints:
        seeds.append((url, "model_navigation_hint"))
    if site:
        base = site if site.startswith("http") else "https://" + site
        seeds.append((base, "wikidata_website"))
        parts = urllib.parse.urlsplit(base)
        root = f"{parts.scheme}://{parts.netloc}"
        seeds += [(root + path, "wikidata_website_ir_path") for path in IR_PATHS]
    ranked = []
    for url, origin in seeds:
        remaining(1)
        if url.lower().split("?")[0].endswith(".pdf"):
            ranked.append((score_pdf_link(url, company=company) + 1, url, origin))
            continue
        for link, text in page_links(url):
            s = score_pdf_link(link, text, company)
            if s > 0:
                ranked.append((s, link, origin))
            elif re.search(r"annual[-\s]?report|integrated[-\s]?report", (link + " " + text).lower()) and not link.lower().endswith(".pdf") and (link, origin) not in seen:
                seen.add((link, origin))
                for inner, inner_text in page_links(link)[:400]:
                    s2 = score_pdf_link(inner, inner_text, company)
                    if s2 > 0:
                        ranked.append((s2, inner, origin + "+annual_report_page"))
    for url in bing_pdf_candidates(company):
        ranked.append((score_pdf_link(url, company=company), url, "bing_rss"))
    done = set()
    for s, url, origin in sorted(ranked, key=lambda r: -r[0]):
        remaining(1)
        if url not in done:
            done.add(url)
            yield url, origin


def drop_folder_pdfs():
    return sorted(DROP_DIR.glob("*.pdf")) if DROP_DIR.is_dir() else []


@bounded_onboarding
def onboard(company, run_dir, config, *, pdf_path=None, pdf_url=None, max_downloads=5, log=None):
    """Return ``(registry_path, source_pdf_path, sha256, report)`` or raise ValueError.

    The registry is written inside ``run_dir`` only; the committed registry is never edited.
    """
    run_dir = Path(run_dir)
    log = log or (lambda *a, **k: None)
    report = {"company": company, "attempts": [], "policy": "issuer_self_declaration_in_original_pdf_v1"}
    sources = []
    discovered = {}
    discovery_path = run_dir / "discovery" / "discovery_report.json"
    if discovery_path.is_file():
        discovery = json.loads(discovery_path.read_text())
        if discovery.get("company") == company:
            for hit in discovery.get("search_results", []) + discovery.get("fallback_candidates", []):
                for source in hit.get("retrieval_report", {}).get("sources", []):
                    path = Path(source.get("saved_path", ""))
                    if source.get("retrieval_status") == "retrieved" and path.suffix.lower() == ".pdf":
                        discovered[str(path)] = source
                        sources.append(("live_discovery_snapshot", path))
    prior_path = run_dir / "onboarding_pdfs/retrieval_report.json"
    if prior_path.is_file():
        prior = json.loads(prior_path.read_text())
        for source in prior.get("sources", []):
            path = Path(source.get("saved_path", "")).resolve()
            if source.get("retrieval_status") == "retrieved" and path.suffix.lower() == ".pdf" and path.is_relative_to(run_dir.resolve()):
                discovered[str(path)] = source
                sources.append(("live_discovery_snapshot", path))
    if pdf_path:
        sources.append(("operator_pdf", Path(pdf_path)))
    for path in drop_folder_pdfs():
        sources.append(("drop_folder", path))
    if pdf_url:
        sources.append(("operator_url", pdf_url))
    result = None
    seen_digests = set()
    downloads = 0

    def attempt(origin, path_or_url):
        nonlocal downloads
        entry = {"origin": origin, "source": str(path_or_url)}
        report["attempts"].append(entry)
        try:
            if isinstance(path_or_url, Path):
                path = path_or_url
                data = path.read_bytes()
                if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF-"):
                    raise ValueError("Not a bounded PDF")
                digest = _sha(data)
                if origin == "live_discovery_snapshot" and digest != discovered[str(path)].get("source_sha256"):
                    raise ValueError("Discovery snapshot hash changed")
            else:
                downloads += 1
                path, digest = download_pdf(path_or_url, run_dir / "onboarding_pdfs")
                data = path.read_bytes()
            if digest in seen_digests:
                raise ValueError("Duplicate original already checked")
            seen_digests.add(digest)
            identity = read_identity(data, company)
            entry.update(status="identity_found", sha256=digest, page=identity["page"], isin=identity["isin"],
                         identifier=identity.get("identifier") or identity["isin"], identifier_type=identity.get("identifier_type", "ISIN"))
            return path, digest, identity
        except Exception as error:
            entry.update(status="rejected", reason=f"{type(error).__name__}: {str(error)[:160]}")
            return None

    for origin, source in sources:
        result = attempt(origin, source)
        if result:
            break
    if not result:
        for url, origin in candidate_pdf_urls(company, config, log):
            if downloads >= max_downloads:
                break
            result = attempt(origin, url)
            if result:
                break
    if not result:
        (run_dir / "onboarding_report.json").write_text(json.dumps(report, indent=2) + "\n")
        raise ValueError("No annual-report PDF declaring this company's ISIN could be obtained. "
                         "Drop the PDF in signalforge/data/demo_drop/ or pass --original-pdf.")
    path, digest, identity = result
    wd_isin, _ = wikidata_identity(company)
    cross = ("not_comparable_CIN_only" if not identity.get("isin") else "agrees" if wd_isin == identity["isin"] else "disagrees" if wd_isin else "unavailable")
    chosen = next(a for a in report["attempts"] if a.get("status") == "identity_found")
    selected_url = (discovered.get(str(path), {}).get("canonical_url") or discovered.get(str(path), {}).get("requested_url")
                    or (chosen["source"] if chosen["source"].startswith("http") else None))
    report.update(selected_path=str(path), selected_url=selected_url,
                  selected_origin=chosen["origin"], selected_sha256=digest, wikidata_isin_cross_check=cross, identity=
                  {k: identity.get(k) for k in ("canonical_name", "isin", "identifier", "identifier_type", "page")})
    if cross == "disagrees":
        report["identity_status"] = "conflicting"
        (run_dir / "onboarding_report.json").write_text(json.dumps(report, indent=2) + "\n")
        raise ValueError("PDF issuer ISIN conflicts with the external identity lookup; investigation stopped.")
    entry = {
        "canonical_name": identity["canonical_name"], "verified_identifier": identity.get("identifier") or identity["isin"],
        "identifiers": [identity.get("identifier") or identity["isin"]], "aliases": sorted({company, core_name(company)}),
        "verification_source": f"pdf-sha256:{digest}#page={identity['page']}",
        "verification_source_type": "issuer_annual_report_self_declaration",
        "verification_status": "verified", "verification_excerpt": identity["snippet"][-500:],
        "note": f"Machine-read from the original PDF; Wikidata ISIN cross-check {cross}. "
                "Not an exchange registry entry and not human reviewed.",
    }
    registry = run_dir / "run_registry.json"
    registry.write_text(json.dumps({"version": 1, "companies": [entry]}, indent=2) + "\n")
    (run_dir / "onboarding_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return registry, path, digest, report
