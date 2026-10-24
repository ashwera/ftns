"""Offline fixtures only: no paid searches or public retrieval."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from signalforge import source_discovery as sd


def grounded(url="https://issuer.example/report.pdf"):
    return {"candidates": [{"content": {"parts": [{"text":
        "Invented claim https://fake.example/not-grounded"}]},
        "groundingMetadata": {"webSearchQueries": ["actual provider query"],
            "groundingChunks": [{"web": {"uri": url, "title": "Annual report"}}],
            "searchEntryPoint": {"renderedContent": "fixture widget"}}}]}


class Response:
    def __init__(self, payload):
        self.data = json.dumps(payload).encode()
    def read(self, size):
        return self.data[:size]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class Opener:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        return Response(self.payload)


class DiscoveryTests(unittest.TestCase):
    def test_duckduckgo_lite_links_only_and_challenge_handling(self):
        class HTMLResponse(Response):
            status = 200
            def __init__(self, data):
                self.data = data
        class HTMLOpener:
            def __init__(self, data): self.data = data
            def open(self, request, timeout): return HTMLResponse(self.data)
        html = b'''<a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fissuer.example%2Freport.pdf">PDF <b>Issuer</b> report</a>
          <td class="result-snippet">UNVERIFIED 9999 MW</td>
          <a href="https://advert.example/">Advert</a>
          <a class="result-link" href="https://issuer.example/annual">Annual report</a>
          <a class="result-link" href="//duckduckgo.com/l/?uddg=http%3A%2F%2F127.0.0.1">private</a>'''
        r = sd.DuckDuckGoSearch(opener=HTMLOpener(html)).search("query", timeout=2)
        self.assertEqual([h["url"] for h in r["results"]],
                         ["https://issuer.example/report.pdf", "https://issuer.example/annual"])
        self.assertEqual(r["results"][0]["title"], "PDF Issuer report")
        self.assertNotIn("9999", json.dumps(r))
        for data in [b'<form id="challenge-form">', b'captcha', html]:
            provider = sd.DuckDuckGoSearch(opener=HTMLOpener(data),
                                          max_response_bytes=2 if data == html else 100)
            with self.assertRaises(sd.SearchError): provider.search("q")

    def test_weak_rss_uses_bounded_lite_fallback_with_provenance(self):
        rss = {"results": [{"url": "https://dictionary.example/power", "title": "Power definition"}],
               "executed_queries": ["q"]}
        lite = {"results": [{"url": "https://issuer.example/annual.pdf", "title": "annual report"}],
                "executed_queries": ["q"]}
        with patch.object(sd.BingRSSSearch, "_search_rss", return_value=rss), \
                patch.object(sd.DuckDuckGoSearch, "search", return_value=lite) as fallback:
            r = sd.BingRSSSearch().search('"Issuer" annual report', timeout=4)
        self.assertEqual(len(r["results"]), 2)
        self.assertLessEqual(fallback.call_args.kwargs["timeout"], 4)
        self.assertEqual(r["provider_attempts"][-1]["provider"], "duckduckgo_lite")

    def test_r1_gaps_are_early_search_intent_and_queries_are_concise(self):
        plan = {"research_questions": [{"missing": ["commissioned transmission assets"],
                 "metrics": ["capex"], "periods": ["2024-25"]}],
                "evidence_ledger": [{"status": "planned_lookup", "claim_supported": "cancelled projects"}]}
        gaps = sd.r1_evidence_gaps(plan)
        queries = sd.build_queries("Meridian Energy Limited", "How does the company compare capex and assets?",
                                   evidence_gaps=gaps)
        self.assertIn("commissioned transmission assets", queries[0])
        self.assertIn("capex 2024-25", queries[1])
        self.assertIn('"Meridian Energy" annual report filetype:pdf', queries[2])
        report = sd.discover("Meridian Energy Limited", "capex", provider=sd.FixtureSearch({}),
                             r1_plan=plan, budget=sd.Budget(max_queries=0))
        self.assertEqual(report["evidence_gaps"], gaps)

    def test_followup_gap_precedes_annual_and_preserves_named_projects(self):
        topic = "investigate performance generation economics cost overruns " * 12 + "North Karanpura 2024-25"
        queries = sd.build_queries("NTPC Limited", topic, ["ntpc.co.in"], evidence_gaps=[topic])
        self.assertIn("North Karanpura", queries[0])
        self.assertIn("2024-25", queries[0])
        self.assertNotIn("annual report", queries[0])
        report = sd.discover("NTPC Limited", topic, provider=sd.FixtureSearch({}),
                             budget=sd.Budget(max_queries=2), evidence_gaps=[topic])
        self.assertIn("North Karanpura", report["search_queries"][0])

    def test_site_link_discovery_preserves_parent_hash_and_bounds_pages(self):
        provider = sd.FixtureSearch({"*": {"results": []}})
        provider.execution_mode = "real"
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp)/"index.html"
            page.write_text('<a href="/reports/annual.pdf">Meridian annual report</a>'
                            '<a href="/annual-reports">annual reports</a>'
                            '<a href="http://127.0.0.1/private.pdf">private PDF</a>')
            retrieval = {"retrieved_count": 1, "sources": [{"retrieval_status": "retrieved",
                "canonical_url": "https://meridian.example/", "source_sha256": "abc123", "saved_path": str(page)}]}
            with patch.object(sd.public_sources, "retrieve_urls", return_value=retrieval) as fetch:
                report = sd.discover("Meridian Limited", "report", provider=provider,
                    budget=sd.Budget(max_queries=0,max_site_pages=1), issuer_domains=["meridian.example"],
                    output_dir=Path(tmp)/"run")
            self.assertEqual(fetch.call_count, 1)
        hit = report["search_results"][0]
        self.assertEqual(hit["url"], "https://meridian.example/reports/annual.pdf")
        self.assertEqual(hit["parent_sha256"], "abc123")
        self.assertEqual(hit["url_provenance"], "retrieved_html.anchor.href")
        self.assertEqual(report["company_identity_status"], "unresolved")

    def test_company_relevance_generic_words_compact_brand_and_acronym(self):
        company = "Power Grid Corporation of India Limited"
        for hit in ({"url": "https://app.powerbi.com/home", "title": "Power BI"},
                    {"url": "https://en.wikipedia.org/wiki/Power_(TV_series)", "title": "Power TV series"},
                    {"url": "https://power.delhi.gov.in/", "title": "Power India corporation"},
                    {"url": "https://unrelated.example/?q=powergrid", "title": "Electricity grid"},
                    {"url": "https://powergrid.in.evil.example/", "title": "Login"}):
            self.assertFalse(sd.company_relevance(hit, company, ["powergrid.in"])[0], hit)
        for hit in ({"url": "https://www.powergrid.in/report"},
                    {"url": "https://news.example/powergrid-results"},
                    {"url": "https://news.example/report", "title": "Power Grid annual report"},
                    {"url": "https://exchange.example/pgcil/results"}):
            self.assertTrue(sd.company_relevance(hit, company, ["powergrid.in"])[0], hit)
        self.assertFalse(sd.company_relevance({"url": "https://unrelated.example/power"}, "NTPC Limited")[0])
        self.assertFalse(sd.company_relevance({"url": "https://jobs.example/rrb-ntpc-vacancy"}, "NTPC Limited")[0])
        self.assertTrue(sd.company_relevance({"url": "https://news.example/ntpc-results"}, "NTPC Limited")[0])

    def test_rejected_results_are_logged_and_never_retrieved(self):
        provider = sd.FixtureSearch({"*": {"results": [
            {"url": "https://app.powerbi.com/home", "title": "Power"},
            {"url": "https://en.wikipedia.org/wiki/Power_(TV_series)"},
            {"url": "https://powergrid.in/report"}]}})
        provider.execution_mode = "real"  # fixtures with all retrieval mocked
        with tempfile.TemporaryDirectory() as tmp, patch.object(sd.public_sources, "retrieve_urls",
                return_value={"retrieved_count": 1, "sources": []}) as fetch:
            report = sd.discover("Power Grid Corporation of India Limited", "report", provider=provider,
                budget=sd.Budget(max_queries=1), retrieve=True, output_dir=Path(tmp)/"run")
        self.assertEqual(report["returned_result_count"], 3)
        self.assertEqual(report["relevant_result_count"], 1)
        self.assertEqual(report["rejected_result_count"], 2)
        self.assertEqual(fetch.call_args.args[0], ["https://powergrid.in/report"])
        self.assertEqual(fetch.call_count, 1)
        self.assertTrue(all(r["rejection_reason"] for r in report["rejected_results"]))
        self.assertEqual(report["finding_status"], "no_finding")

    def test_unrelated_ntpc_rss_cannot_trigger_retrieval(self):
        provider = sd.FixtureSearch({"*": {"results": [
            {"url": "https://jobs.example/rrb-ntpc", "title": "RRB NTPC"},
            {"url": "https://app.powerbi.com/", "title": "Power BI"}]}})
        provider.execution_mode = "real"
        with tempfile.TemporaryDirectory() as tmp, patch.object(sd.public_sources, "retrieve_urls") as fetch:
            report = sd.discover("NTPC Limited", "capacity", provider=provider,
                budget=sd.Budget(max_queries=1), retrieve=True, output_dir=Path(tmp)/"run")
        fetch.assert_not_called()
        self.assertEqual(report["discovery_status"], "no_relevant_candidates")
        self.assertEqual(report["returned_result_count"], 2)
        self.assertEqual(report["relevant_result_count"], 0)

    def test_bing_xml_fixture_and_provenance(self):
        xml = b'''<rss version="2.0"><channel><title>Bing</title><item>
        <title>Issuer report</title><link>https://issuer.example/report?a=1&amp;b=2</link>
        <description>UNVERIFIED capacity is 9999 MW</description>
        <pubDate>Search feed date is not publication date</pubDate></item>
        <item><link>http://127.0.0.1/private</link></item></channel></rss>'''
        class XMLResponse(Response):
            def __init__(self, payload):
                self.data = payload
        class XMLopener(Opener):
            def open(self, request, timeout):
                self.requests.append(request)
                return XMLResponse(self.payload)
        opener = XMLopener(xml)
        result = sd.BingRSSSearch(opener=opener, fallback=False).search("Example & capacity", timeout=2)
        self.assertEqual(len(result["results"]), 1)
        hit = result["results"][0]
        self.assertEqual(hit["url"], "https://issuer.example/report?a=1&b=2")
        self.assertEqual(hit["search_publisher"], "Bing")
        self.assertEqual(hit["company_identity_status"], "unresolved")
        self.assertNotIn("9999", json.dumps(result))
        self.assertNotIn("pubDate", json.dumps(result))
        self.assertIn("format=rss", opener.requests[0].full_url)
        self.assertIn("q=Example+%26+capacity", opener.requests[0].full_url)
        for payload in (b"<html>blocked</html>", b"<!DOCTYPE rss><rss/>", b"<rss>"):
            with self.assertRaises(sd.SearchError):
                sd.BingRSSSearch(opener=XMLopener(payload), fallback=False).search("q")
        with self.assertRaises(sd.SearchError):
            sd.BingRSSSearch(opener=XMLopener(xml), max_response_bytes=2, fallback=False).search("q")

    def test_default_rate_limit_fallback_and_audit(self):
        class RateLimited:
            def open(self, request, timeout):
                raise sd.urllib.error.HTTPError(request.full_url, 429, "secret body", {}, None)
        fallback = {"results": [{"url": "https://issuer.example/report", "search_provider": "bing_rss"}],
                    "executed_queries": ["q"]}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "SECRET"}, clear=True), \
                patch.object(sd.BingRSSSearch, "search", return_value=fallback) as bing:
            report = sd.discover("Example", "capacity", provider=sd.GeminiGoogleSearch(opener=RateLimited()),
                                 budget=sd.Budget(max_queries=1))
        self.assertEqual(report["errors"][0]["error"], "Search HTTP 429")
        self.assertEqual(report["search_results"][0]["search_provider"], "bing_rss")
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertLessEqual(bing.call_args.kwargs["timeout"], 20)

    def test_both_providers_fail_safely(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(sd.BingRSSSearch, "search",
                side_effect=sd.SearchError("Bing RSS HTTP 503")):
            report = sd.discover("Example", "capacity", provider=sd.GeminiGoogleSearch(),
                                 budget=sd.Budget(max_queries=1))
        self.assertEqual(len(report["errors"]), 2)
        self.assertEqual(report["search_results"], [])

    def test_rest_grounding_only_and_environment_model(self):
        opener = Opener(grounded())
        with patch.dict(os.environ, {"SIGNALFORGE_API_KEY": "secret-test",
                                     "SIGNALFORGE_MODEL": "gemini-2.5-flash"}, clear=True):
            provider = sd.GeminiGoogleSearch(opener=opener)
            reply = provider.search("Example Power capacity", timeout=3)
        self.assertEqual(reply["results"][0]["url"], "https://issuer.example/report.pdf")
        self.assertNotIn("Invented", json.dumps(reply))
        request = opener.requests[0]
        self.assertIn("gemini-2.5-flash:generateContent", request.full_url)
        self.assertNotIn("secret-test", request.full_url)
        self.assertEqual(json.loads(request.data)["tools"], [{"google_search": {}}])
        self.assertEqual(reply["executed_queries"], ["actual provider query"])

    def test_no_metadata_does_not_use_model_text(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret"}, clear=True):
            reply = sd.GeminiGoogleSearch(opener=Opener({"candidates": [
                {"content": {"parts": [{"text": "https://fake.example"}]}}]})).search("q")
        self.assertEqual(reply["results"], [])

    def test_errors_never_include_remote_exception(self):
        class Broken:
            def open(self, *args, **kwargs):
                raise RuntimeError("SECRET credential remote body")
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "SECRET"}, clear=True):
            with self.assertRaises(sd.SearchError) as ctx:
                sd.GeminiGoogleSearch(opener=Broken(), fallback=False).search("q")
        self.assertNotIn("SECRET", str(ctx.exception))
        self.assertTrue(ctx.exception.__suppress_context__)

    def test_missing_key_and_byte_budget(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(sd.SearchError):
                sd.GeminiGoogleSearch(fallback=False).search("q")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret"}, clear=True):
            with self.assertRaises(sd.SearchError):
                sd.GeminiGoogleSearch(opener=Opener(grounded()), max_response_bytes=2, fallback=False).search("q")

    def test_timeout_is_bounded_and_failure_persisted(self):
        class TimedOut:
            def open(inner, request, timeout):
                self.assertGreater(timeout, 0)
                self.assertLessEqual(timeout, 2)
                raise TimeoutError("secret transport detail")
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,
                {"GEMINI_API_KEY": "secret"}, clear=True):
            out = Path(tmp)/"run"
            sd.discover("Example", "capacity", provider=sd.GeminiGoogleSearch(opener=TimedOut(), fallback=False),
                budget=sd.Budget(max_queries=1, max_seconds=2), output_dir=out)
            report = json.loads((out/"discovery_report.json").read_text())
        self.assertEqual(len(report["errors"]), 1)
        self.assertNotIn("secret", json.dumps(report))
        self.assertEqual(report["action_log"][1]["action"], "search_failed")

    def test_deadline_stops_followup_search(self):
        with patch.object(sd.time, "monotonic", side_effect=[0, 3]):
            report = sd.discover("Example", "capacity", provider=sd.FixtureSearch({}),
                                 budget=sd.Budget(max_seconds=2))
        self.assertEqual(report["stop_reason"], "time_budget")
        self.assertEqual(report["search_queries"], [])

    def test_generic_queries_dates_gaps(self):
        for company in ("Example Power", "Another Energy"):
            queries = sd.build_queries(company, "capacity", ["issuer.example"],
                ("2025-01-01", "2025-12-31"), ["commissioning evidence"])
            self.assertTrue(all(company in q for q in queries))
            self.assertIn("after:2024-12-31 before:2026-01-01", queries[0])
            self.assertTrue(any("contradiction" in q for q in queries))
            self.assertTrue(any("commissioning" in q for q in queries))

    def test_rank_deduplicate_and_never_infer_independence(self):
        hits = [{"url": "https://issuer.example/report#one"},
                {"url": "https://issuer.example/report#two"},
                {"url": "https://exchange.example/copy"},
                {"url": "http://127.0.0.1/private"}]
        ranked = sd.rank_urls(hits, issuer_domains=["issuer.example"],
            authority_domains={"exchange.example": "exchange_hosted_issuer_copy"})
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["source_class"], "primary_issuer")
        self.assertTrue(all(r["independent_group_id"] is None for r in ranked))

    def test_fixture_log_result_and_query_budgets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fresh"
            report = sd.discover("Example", "capacity", provider=sd.FixtureSearch({"*": {
                "results": [{"url": "https://issuer.example/report"}]}}),
                budget=sd.Budget(max_queries=1), output_dir=out)
            self.assertEqual(report["execution_mode"], "fixture/replay")
            self.assertEqual(report["stop_reason"], "query_budget")
            self.assertEqual(json.loads((out / "discovery_report.json").read_text()), report)
            with self.assertRaises(FileExistsError):
                sd.discover("Example", "capacity", provider=sd.FixtureSearch({}), output_dir=out)
        report = sd.discover("Example", "capacity", provider=sd.FixtureSearch({"*": {
            "results": [{"url": "https://one.example"}, {"url": "https://two.example"}]}}),
            budget=sd.Budget(max_results=1))
        self.assertEqual(len(report["search_results"]), 1)
        self.assertEqual(len(report["search_queries"]), 1)

    def test_failure_fallback_and_zero_budget(self):
        report = sd.discover("Example", "capacity", provider=sd.FixtureSearch({}),
                             budget=sd.Budget(max_queries=2))
        self.assertEqual(len(report["errors"]), 2)
        self.assertEqual(report["search_results"], [])
        report = sd.discover("Example", "capacity", provider=sd.FixtureSearch({}),
                             budget=sd.Budget(max_queries=0))
        self.assertEqual(report["search_queries"], [])
        for kwargs in ({"max_queries": -1}, {"max_fetches": 11}, {"max_seconds": float("nan")}):
            with self.assertRaises(ValueError):
                sd.Budget(**kwargs)

    def test_retrieval_delegates_without_approving_or_associating(self):
        provider = sd.FixtureSearch({"*": {"results": [{"url": "https://issuer.example"}]}})
        provider.execution_mode = "real"  # synthetic provider; mocked retrieval below
        with tempfile.TemporaryDirectory() as tmp, patch.object(sd.public_sources, "retrieve_urls",
                return_value={"retrieved_count": 1, "sources": []}) as fetch:
            result = sd.discover("Example", "capacity", provider=provider,
                budget=sd.Budget(max_queries=1, max_fetches=1), output_dir=Path(tmp)/"out", retrieve=True)
        self.assertEqual(result["retrieval_status"], "retrieved")
        self.assertEqual(fetch.call_args.kwargs["source_relationship"], "unknown")
        self.assertNotIn("company", fetch.call_args.kwargs)
        self.assertIsInstance(fetch.call_args.kwargs["opener"], sd._PublicOpener)

    def test_fixture_cannot_fetch_and_dns_guard(self):
        with self.assertRaises(ValueError):
            sd.discover("Example", "capacity", provider=sd.FixtureSearch({}), retrieve=True)
        opener = sd._PublicOpener(float("inf"))
        with patch.object(sd.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 443))]):
            with self.assertRaises(sd.public_sources.RetrievalError):
                opener.open(sd.urllib.request.Request("https://issuer.example/report"))
        for url in ("file:///etc/passwd", "http://localhost/a", "http://[::1]/a", "https://u:p@host.example"):
            self.assertFalse(sd._public_url(url))

    def test_cli_fixture_and_safe_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)/"fixture.json"
            fixture.write_text(json.dumps({"*": {"results": [{"url": "https://issuer.example/report"}]}}))
            args = ["--company", "Example", "--topic", "capacity", "--fixture", str(fixture),
                    "--output-dir", str(Path(tmp)/"out")]
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(sd.main(args), 0)
                self.assertEqual(sd.main(args), 2)
            self.assertIn("fixture/replay", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
