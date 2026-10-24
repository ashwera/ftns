"""Bounded public URL retrieval with robots checks and ingestion provenance."""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

from .config import Config
from .evidence_ingestion import ingest_paths, load_registry, verify_company, registry_mapping_conflicts

USER_AGENT = "SignalForgeEvidenceBot/0.1 (+local research ingestion; respectful public-source retrieval)"
MAX_BYTES = 15 * 1024 * 1024
MAX_SOURCES = 10

class RetrievalError(RuntimeError):
    pass

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class _HTMLMetadata(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta={}; self.title=[]; self.in_title=False
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag.lower()=="title": self.in_title=True
        if tag.lower()=="meta":
            key=(attrs.get("property") or attrs.get("name") or "").lower()
            if key in {"article:published_time","datepublished","date","dc.date","dc.date.issued"}: self.meta[key]=attrs.get("content")
    def handle_endtag(self, tag):
        if tag.lower()=="title": self.in_title=False
    def handle_data(self, data):
        if self.in_title and data.strip(): self.title.append(data.strip())

def _safe_url(url):
    p=urllib.parse.urlparse(url)
    return p.scheme in {"http","https"} and bool(p.netloc) and not p.username and not p.password

def _robots(url, opener, timeout):
    p=urllib.parse.urlparse(url); robots_url=f"{p.scheme}://{p.netloc}/robots.txt"
    req=urllib.request.Request(robots_url,headers={"User-Agent":USER_AGENT})
    try:
        with opener.open(req,timeout=timeout) as response: lines=response.read(512*1024).decode("utf-8","replace").splitlines()
        rp=urllib.robotparser.RobotFileParser(); rp.set_url(robots_url); rp.parse(lines)
        return rp.can_fetch(USER_AGENT,url),rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*") or 1.0,"robots.txt retrieved"
    except urllib.error.HTTPError as e:
        if 400<=e.code<500: return True,1.0,f"robots.txt returned HTTP {e.code}; treated as unavailable under REP"
        return False,None,f"robots.txt returned HTTP {e.code}; fail closed"
    except Exception as e:
        return False,None,f"robots.txt unavailable ({type(e).__name__}); fail closed"

def _html_metadata(data):
    p=_HTMLMetadata(); p.feed(data.decode("utf-8","replace"))
    pub=None
    raw=next((v for v in p.meta.values() if v),None)
    if raw:
        try: pub=dt.datetime.fromisoformat(raw.replace("Z","+00:00")).date().isoformat()
        except ValueError:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}",raw): pub=raw
    return pub," ".join(p.title).strip() or None

def _source_text(data, extension):
    if extension in {".html",".htm"}:
        from .evidence_ingestion import _html_records
        # Parse from bytes via a temporary byte-preserving decode; this is only an identity gate.
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=extension) as tmp:
            tmp.write(data); tmp.flush()
            return _html_records(tmp.name,Path(tmp.name).name)[0][0].excerpt_or_fact
    if extension==".pdf":
        from .evidence_ingestion import _pdf_records
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=extension) as tmp:
            tmp.write(data); tmp.flush()
            return "\n".join(r.excerpt_or_fact for r in _pdf_records(tmp.name,Path(tmp.name).name))
    return data.decode("utf-8-sig","replace")

def _suffix(content_type,url):
    mime=content_type.split(";",1)[0].strip().lower()
    if mime=="application/pdf": return ".pdf"
    if mime in {"text/html","application/xhtml+xml"}: return ".html"
    if mime.startswith("text/"): return ".txt"
    ext=Path(urllib.parse.urlparse(url).path).suffix.lower()
    return ext if ext in {".pdf",".html",".htm",".txt",".md"} else None

def _append_jsonl(path, records, id_field):
    existing=[]
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip(): existing.append(json.loads(line))
    seen={r.get(id_field) for r in existing}
    merged=existing+[r for r in records if r.get(id_field) not in seen]
    path.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in merged),encoding="utf-8")
    return merged

def retrieve_urls(urls, output_dir, registry_path=None, timeout=20, max_bytes=MAX_BYTES, opener=None, robots_checker=None, sleep_fn=time.sleep, source_relationship="unknown", company=None, source_organization=None, normalize_evidence=True):
    if not urls: raise ValueError("At least one URL is required")
    if len(urls)>MAX_SOURCES: raise ValueError(f"Maximum {MAX_SOURCES} URLs per run")
    if source_relationship not in {"original_disclosure","republication","independent_source","unknown"}: raise ValueError("Invalid source relationship classification")
    verified_identity=None
    if company:
        verified_identity=verify_company(company,load_registry(registry_path))
        if verified_identity[2]!="verified": raise RetrievalError(f"Company {company!r} is unresolved or conflicting in the registry; company-scoped retrieval is disabled.")
    opener=opener or urllib.request.build_opener(_NoRedirect())
    robots_checker=robots_checker or (lambda u:_robots(u,opener,timeout))
    output=Path(output_dir); source_dir=output/"sources"; source_dir.mkdir(parents=True,exist_ok=True)
    manifest=[]; local_paths=[]; metadata={}; last_host={}
    for url in urls:
        item={"requested_url":url,"retrieval_status":"failed","retrieved_at":dt.datetime.now(dt.timezone.utc).isoformat(),"warnings":[]}
        try:
            if not _safe_url(url): raise RetrievalError("Only public HTTP(S) URLs without embedded credentials are accepted.")
            final_url=url; redirect_chain=[]
            for _ in range(6):
                if not _safe_url(final_url): raise RetrievalError("Redirect target is not a public HTTP(S) URL")
                allowed,delay,robots_note=robots_checker(final_url); item.setdefault("robots_checks",[]).append({"url":final_url,"status":robots_note})
                if not allowed: raise RetrievalError("robots.txt disallows retrieval or could not be verified.")
                host=urllib.parse.urlparse(final_url).netloc
                wait=max(1.0,delay or 1.0)-(time.monotonic()-last_host.get(host,0))
                if wait>0: sleep_fn(wait)
                request=urllib.request.Request(final_url,headers={"User-Agent":USER_AGENT,"Accept":"text/html,application/pdf,text/plain;q=0.9"})
                try:
                    with opener.open(request,timeout=timeout) as response:
                        data=response.read(max_bytes+1); final_url=response.geturl(); ctype=response.headers.get("Content-Type",""); status=getattr(response,"status",200)
                    last_host[host]=time.monotonic(); break
                except urllib.error.HTTPError as redirect:
                    location=redirect.headers.get("Location")
                    if redirect.code not in {301,302,303,307,308} or not location: raise
                    redirect_chain.append({"status":redirect.code,"from":final_url,"to":urllib.parse.urljoin(final_url,location)})
                    final_url=urllib.parse.urljoin(final_url,location)
            else: raise RetrievalError("Redirect limit exceeded")
            if len(data)>max_bytes: raise RetrievalError(f"Response exceeded {max_bytes} byte limit")
            if not _safe_url(final_url): raise RetrievalError("Redirect target is not a public HTTP(S) URL")
            ext=_suffix(ctype,final_url)
            if ext not in {".pdf",".html",".htm",".txt",".md"}: raise RetrievalError(f"Unsupported Content-Type {ctype!r}")
            digest=hashlib.sha256(data).hexdigest(); source_tag=hashlib.sha256(url.encode()).hexdigest()[:8]; target=source_dir/(digest[:12]+"_"+source_tag+ext)
            if not target.exists(): target.write_bytes(data)
            pub,title=(None,None)
            if ext in {".html",".htm"}: pub,title=_html_metadata(data)
            company_verified=bool(verified_identity)
            if verified_identity:
                try: body=_source_text(data,ext).casefold()
                except Exception: body=""
                canonical=verified_identity[0].casefold(); identifier=str(verified_identity[1] or "").casefold()
                if canonical not in body and (not identifier or identifier not in body):
                    company_verified=False
            retrieved=dt.datetime.now(dt.timezone.utc).isoformat()
            item.update({"retrieval_status":"retrieved","http_status":status,"canonical_url":final_url,"redirect_chain":redirect_chain,"source_sha256":digest,"content_type":ctype,"saved_path":str(target),"document_title":title,"publication_date":pub,"source_relationship":source_relationship,"retrieved_at":retrieved,"company_association_status":"verified" if company_verified else "unresolved" if company else "not_requested"})
            if company and not company_verified: item["warnings"].append("Downloaded content did not contain the verified canonical company name or identifier; company association withheld.")
            if not pub: item["warnings"].append("Publication date not established from recognized page metadata; retrieval time is not substituted.")
            local_paths.append(target)
            metadata[str(target)]={"source_url":final_url,"retrieved_at":retrieved,"publication_date":pub,"source_relationship":source_relationship,"source_organization":source_organization}
            if company_verified:
                metadata[str(target)].update({"company_name":verified_identity[0],"verified_identifier":verified_identity[1],"company_identity_status":"verified"})
        except (urllib.error.URLError,TimeoutError,RetrievalError,OSError,ValueError) as e:
            item["error"]=f"{type(e).__name__}: {e}"
        manifest.append(item)
    if local_paths and normalize_evidence:
        run_dir=output/"retrieval_runs"/dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        records,ingest_report=ingest_paths(local_paths,run_dir,registry_path,root=output,source_metadata=metadata)
        # Merge by stable IDs, retaining prior records and original files.
        for name,id_field in (("evidence.jsonl","evidence_id"),("source_records.jsonl","source_record_id")):
            new=[json.loads(line) for line in (run_dir/name).read_text(encoding="utf-8").splitlines() if line.strip()]
            _append_jsonl(output/name,new,id_field)
        (output/"ingestion_report.json").write_text(json.dumps(ingest_report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    else: records=[]; ingest_report={"duplicate_documents":[],"conflicts":[],"manual_review_evidence_ids":[]}
    report={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"requested_count":len(urls),"retrieved_count":sum(x["retrieval_status"]=="retrieved" for x in manifest),"failed_count":sum(x["retrieval_status"]!="retrieved" for x in manifest),"sources":manifest,"normalized_evidence_record_count":len(records),"duplicate_documents":ingest_report.get("duplicate_documents",[]),"conflicts":ingest_report.get("conflicts",[]),"manual_review_count":len(ingest_report.get("manual_review_evidence_ids",[]))}
    report["normalization_status"] = "performed" if normalize_evidence else "deferred_to_identity_and_machine_evidence_intake"
    (output/"retrieval_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return report

def verify_identity_from_document(alias,canonical_name,ticker,isin,url,registry_path,output_dir,timeout=20,opener=None,robots_checker=None):
    report=retrieve_urls([url],output_dir,registry_path,timeout,opener=opener,robots_checker=robots_checker,sleep_fn=lambda _:None,source_relationship="original_disclosure")
    if report["retrieved_count"]!=1: return {"verification_status":"unresolved","reason":"Authoritative identity source could not be retrieved.","retrieval_report":report}
    source=report["sources"][0]; path=Path(source["saved_path"])
    if path.suffix.lower() in {".html",".htm"}:
        from .evidence_ingestion import _html_records
        text=_html_records(path,path.name)[0][0].excerpt_or_fact
    elif path.suffix.lower()==".pdf":
        from .evidence_ingestion import _pdf_records
        text="\n".join(r.excerpt_or_fact for r in _pdf_records(path,path.name))
    else: text=path.read_text(encoding="utf-8-sig",errors="replace")
    norm=lambda s:re.sub(r"[^a-z0-9]","",s.casefold())
    if not all(norm(v) in norm(text) for v in (canonical_name,ticker,isin)):
        return {"verification_status":"unresolved","reason":"Retrieved source text did not explicitly contain canonical name, ticker, and ISIN.","retrieval_report":report}
    registry=load_registry(registry_path); conflicts=[]
    conflicts=registry_mapping_conflicts(registry,alias,canonical_name,isin)
    if conflicts: return {"verification_status":"unresolved","reason":"Conflicting verified registry mapping exists; no entry was overwritten.","conflicts":conflicts,"retrieval_report":report}
    excerpt=next((line.strip() for line in text.splitlines() if all(norm(v) in norm(line) for v in (canonical_name,ticker,isin)))," ".join(text.split())[:500])
    entry={"canonical_name":canonical_name,"verified_identifier":isin,"identifiers":[ticker,isin],"aliases":sorted(set([alias,ticker]),key=str.casefold),"verification_source":url,"verification_source_type":"exchange_filing","verification_status":"verified","verification_retrieval_date":source["retrieved_at"][:10],"verification_publication_date":source.get("publication_date"),"verification_excerpt":excerpt,"note":"Identity values matched in the retrieved public exchange disclosure. This does not establish company identity for rows lacking identifiers."}
    registry["companies"]=[e for e in registry.get("companies",[]) if alias.casefold() not in [str(x).casefold() for x in [e.get("canonical_name"),*e.get("aliases",[]),*e.get("identifiers",[])] if x]]
    registry["companies"].append(entry)
    Path(registry_path).write_text(json.dumps(registry,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return {"verification_status":"verified","company":entry,"retrieval_report":report}

def main(argv=None):
    cfg=Config(); p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url",action="append",default=[],help="Public HTTP(S) source URL; repeat up to ten sources")
    p.add_argument("--output-dir",default=str(cfg.evidence_dir)); p.add_argument("--registry",default=str(cfg.registry_path))
    p.add_argument("--source-relationship",choices=["original_disclosure","republication","independent_source","unknown"],default="unknown")
    p.add_argument("--company",help="Associate retrieval only with a company verified in the registry")
    p.add_argument("--source-organization",help="Source organization, only when known from the document or domain")
    p.add_argument("--verify-alias"); p.add_argument("--canonical-name"); p.add_argument("--ticker"); p.add_argument("--isin"); p.add_argument("--identity-url")
    a=p.parse_args(argv)
    try:
        if a.verify_alias:
            if not all((a.canonical_name,a.ticker,a.isin,a.identity_url)): p.error("verification requires --canonical-name, --ticker, --isin, and --identity-url")
            result=verify_identity_from_document(a.verify_alias,a.canonical_name,a.ticker,a.isin,a.identity_url,a.registry,a.output_dir)
            print(json.dumps(result,indent=2,ensure_ascii=False)); return 0 if result["verification_status"]=="verified" else 2
        if not a.url: p.error("provide at least one --url")
        result=retrieve_urls(a.url,a.output_dir,a.registry,source_relationship=a.source_relationship,company=a.company,source_organization=a.source_organization)
        print(json.dumps(result,indent=2,ensure_ascii=False)); return 0 if result["retrieved_count"] else 2
    except (OSError,ValueError,RuntimeError,RetrievalError) as e:
        print(f"Public source retrieval error: {e}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
