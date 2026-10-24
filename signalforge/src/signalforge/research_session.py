"""Isolated local research runs. No shell commands or caller-selected paths."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
import uuid

from .config import Config, ROOT


def now():
    return datetime.now(timezone.utc).isoformat()


def local_config():
    """Read literal allowlisted dotenv assignments; never evaluate or log secrets."""
    allowed = {"SIGNALFORGE_API_KEY", "SIGNALFORGE_MODEL", "SIGNALFORGE_PROVIDER",
               "SIGNALFORGE_BASE_URL", "SIGNALFORGE_SEARCH_MODEL", "GEMINI_API_KEY", "GOOGLE_API_KEY"}
    for path in (ROOT.parent / ".env", ROOT / ".env", Path(__file__).with_name(".env")):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and key in allowed:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                os.environ.setdefault(key, value)
    # Config defaults are evaluated at import time: override explicitly after dotenv.
    return replace(Config(), **{field: os.environ.get(env, getattr(Config(), field))
        for field, env in (("api_key", "SIGNALFORGE_API_KEY"), ("model", "SIGNALFORGE_MODEL"),
                           ("provider", "SIGNALFORGE_PROVIDER"), ("base_url", "SIGNALFORGE_BASE_URL"))})


class ResearchSessions:
    def __init__(self, root=None, config=None, executor=None):
        self.root = Path(root or ROOT / "data" / "research_runs")
        self.config = config or local_config()
        self.executor = executor or execute
        self.lock = threading.Lock()
        self.active = None

    def list_runs(self):
        runs = []
        for path in sorted(self.root.glob("research_*/manifest.json"), reverse=True)[:30]:
            try:
                value = self.get(path.parent.name)
                runs.append({k: value.get(k) for k in ("run_id", "company", "prompt", "created_at", "status", "stage")})
            except (KeyError, ValueError, OSError):
                continue
        return {"runs": runs}

    def get(self, run_id):
        if not re.fullmatch(r"research_\d{8}T\d{6}_[a-f0-9]{12}", run_id):
            raise KeyError(run_id)
        try:
            result = json.loads((self.root / run_id / "manifest.json").read_text())
        except FileNotFoundError:
            raise KeyError(run_id) from None
        if result["status"] == "running" and result["stage"] == "discovery":
            try:
                discovery = json.loads((self.root / run_id / "discovery" / "discovery_report.json").read_text())
                actions = discovery.get("action_log", [])
                result["discovery_actions"] = actions
                if any(a["action"].startswith("retrieval_") for a in actions):
                    result["stage"] = "retrieval"
            except (FileNotFoundError, json.JSONDecodeError):
                pass  # Discovery can be between incremental report writes.
        return result

    def start(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"company", "prompt"}:
            raise ValueError("Expected company and prompt only")
        for key, limit in (("company", 200), ("prompt", 4000)):
            if not isinstance(payload[key], str) or not payload[key].strip() or len(payload[key]) > limit:
                raise ValueError(f"Invalid {key} (maximum {limit} characters)")
        with self.lock:
            if self.active:
                raise RuntimeError("A research run is already active")
            run_id = datetime.now(timezone.utc).strftime("research_%Y%m%dT%H%M%S_") + uuid.uuid4().hex[:12]
            folder = self.root / run_id
            folder.mkdir(parents=True)
            manifest = {"run_id": run_id, **{k: v.strip() for k, v in payload.items()},
                        "created_at": now(), "updated_at": now(), "status": "queued",
                        "stage": "queued", "events": [], "artifacts": [],
                        "finding": None, "model": {"provider": self.config.provider, "model": self.config.model},
                        "source_manifest_path": "discovery/discovery_report.json",
                        "budget": {"max_queries": 3, "max_results": 10, "max_fetches": 3, "max_seconds": 90, "request_timeout": 40},
                        "stages": [{"name": name, "execution": "not_executed"} for name in ("discovery", "retrieval", "machine_evidence", "f1", "r1", "investigation", "adjudication")],
                        "limitations": ["Source retrieval and machine passage matching do not verify financial claims.",
                                         "Discovery time budget is cooperative; downstream model requests use their existing client timeouts."]}
            self._save(folder, manifest)
            self.active = run_id
            threading.Thread(target=self._work, args=(folder, manifest), daemon=True).start()
            return dict(manifest)

    def _save(self, folder, manifest):
        temporary = folder / "manifest.tmp"
        temporary.write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.replace(folder / "manifest.json")

    def _work(self, folder, manifest):
        def update(stage, message, status="running", **fields):
            previous = manifest["stage"]
            for item in manifest["stages"]:
                if item["name"] == previous and previous != stage and item["execution"] == "running":
                    item["execution"] = "real"
                if item["name"] == stage:
                    item.update(execution="running" if status == "running" else status, detail=message)
            manifest.update(stage=stage, status=status, updated_at=now(), **fields)
            if status in {"blocked", "failed", "completed"}:
                manifest["finished_at"] = now()
            event = {"at": now(), "stage": stage, "message": message}
            manifest["events"].append(event)
            with (folder / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(event) + "\n")
            self._save(folder, manifest)
        try:
            self.executor(folder, manifest, self.config, update)
        except Exception as error:
            # Exceptions from providers can contain credentials or request bodies:
            # record only the type and code locations, never message text.
            import traceback
            manifest["error"] = {"type": type(error).__name__, "frames": [
                f"{Path(f.filename).name}:{f.lineno} in {f.name}" for f in traceback.extract_tb(error.__traceback__)[-4:]]}
            update(manifest["stage"], "Execution failed; inspect local prerequisites and retry. No finding generated.", "failed")
            finish_evidence_gap(folder, manifest, update,
                f"{manifest['stage']} could not complete ({type(error).__name__}); saved model and retrieval audits retain the failure. No financial finding was accepted.",
                failed_stage=manifest["stage"])
        finally:
            with self.lock:
                self.active = None


def execute(folder, manifest, config, update):
    from . import source_discovery
    Budget, discover = source_discovery.Budget, source_discovery.discover
    update("discovery", "Discovering public sources (3 queries, 10 results, 3 retrievals, 90 seconds).")
    provider = source_discovery.BingRSSSearch()
    update("discovery", f"Searching with {provider.name}; source candidates are unverified.", search_provider=provider.name)
    report = discover(manifest["company"], manifest["prompt"], provider=provider,
        budget=Budget(max_queries=3, max_results=10, max_fetches=3, max_seconds=90, request_timeout=40),
        output_dir=folder / "discovery", retrieve=True, registry_path=config.registry_path)
    update("retrieval", "Bounded discovery and retrieval finished.",
           artifacts=["discovery/discovery_report.json"],
           source_count=len(report["search_results"]), retrieval_status=report["retrieval_status"])
    update("machine_evidence", "Checking retrieved PDFs against canonical issuer declarations and exact passages.")
    from .evidence_ingestion import load_registry, verify_company
    if verify_company(manifest["company"], load_registry(config.registry_path))[2] != "verified":
        update("machine_evidence", "Company not in the registry: onboarding from its own annual report (public PDF, ISIN self-declaration, hash-pinned).")
        try:
            from .company_onboarding import onboard
            registry, pdf, digest, onboarding = onboard(manifest["company"], folder, config,
                log=lambda action, **fields: None)
            config = replace(config, registry_path=registry)
            manifest["onboarding"] = {"identity": onboarding["identity"], "sha256": digest,
                "wikidata_isin_cross_check": onboarding["wikidata_isin_cross_check"]}
            update("machine_evidence", f"Identity read from the original PDF: {onboarding['identity']['canonical_name']} "
                   f"(ISIN {onboarding['identity']['isin']}, page {onboarding['identity']['page']}); Wikidata cross-check {onboarding['wikidata_isin_cross_check']}.",
                   artifacts=manifest.get("artifacts", []) + ["onboarding_report.json", "run_registry.json"])
            records = onboarded_records(pdf, digest, manifest["company"], config, manifest["prompt"])
        except Exception as error:
            update("machine_evidence", f"Issuer onboarding could not establish eligible original evidence ({type(error).__name__}).", "blocked",
                   artifacts=manifest.get("artifacts", []) + (["onboarding_report.json"] if (folder / "onboarding_report.json").exists() else []))
            finish_evidence_gap(folder, manifest, update, "Issuer identity could not be resolved from a retrieved or supplied original PDF. Research stopped before F1; no company-specific financial conclusion is justified.")
            return
    else:
        records = machine_records(folder, manifest["company"], config, manifest["prompt"])
    if not records:
        update("machine_evidence", "Search did not retrieve an eligible PDF. Rechecking available pinned official-source snapshots; cached inputs will be labelled.")
        records = cached_machine_records(folder, manifest["company"], config, manifest["prompt"])
    if not records:
        update("machine_evidence", "No retrieved or pinned cached original passed source/issuer checks. See machine_evidence_report.json for the exact failures.", "blocked", artifacts=manifest.get("artifacts", []) + ["machine_evidence_report.json"])
        finish_evidence_gap(folder, manifest, update, "No original passed company identity and evidence eligibility checks. Discovery candidates remain unverified leads; F1, R1 and model investigation did not run.")
        return
    evidence = folder / "eligible_evidence"
    evidence.mkdir()
    (evidence / "evidence.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    config = replace(config, evidence_dir=evidence, output_dir=folder)
    from .llm_client import model_configured, local_model_status
    if not model_configured(config):
        update("f1", "F1 model credential unavailable; eligible evidence retained.", "blocked")
        return
    ready, why = local_model_status(config)
    if not ready:
        update("f1", why, "blocked", artifacts=manifest.get("artifacts", []))
        return
    from .f1_research_angle_selector import run as f1
    from .r1_research_investigator import run as r1
    update("f1", "Running F1 on policy-eligible evidence.")
    result = f1(manifest["company"], config.csv_path, folder / "f1.json", config, research_question=manifest["prompt"])
    fallback_path = folder / "f1_fallback.json"
    if fallback_path.is_file():
        fallback_record = json.loads(fallback_path.read_text(encoding="utf-8"))
        manifest["f1_ranking_provenance"] = fallback_record
        if fallback_record.get("used"):
            update("f1", "F1 model ranking was unreliable; deterministic evidence-grounded planning fallback used. This is a research plan, not a verified financial finding.",
                   artifacts=manifest.get("artifacts", []) + ["f1.json", "f1_fallback.json", "f1_model_output.json", "eligible_evidence/evidence.jsonl"])
        elif fallback_record.get("blocked"):
            manifest["artifacts"] = manifest.get("artifacts", []) + ["f1_fallback.json"]
            update("f1", "F1 model ranking was unusable and fallback stopped because eligible company-specific evidence did not match any contest angle.", artifacts=manifest["artifacts"])
        else:
            manifest["artifacts"] = manifest.get("artifacts", []) + ["f1_fallback.json"]
            update("f1", "F1 used its model-generated ranking; no financial finding is implied.", artifacts=manifest["artifacts"])
    for retry in ((2,) if config.provider.strip().lower() == "ollama" else (2, 3)):  # local inference is slow
        # The model's own reliability flag varies between identical runs; re-ask, never override it.
        if result.get("ranking_reliable"):
            break
        update("f1", f"F1 judged its ranking unreliable; re-running (attempt {retry}).")
        result = f1(manifest["company"], config.csv_path, folder / "f1.json", config, research_question=manifest["prompt"])
    if not result.get("ranking_reliable"):
        update("f1", "F1 returned no reliable recommendation. R1 not run.", "blocked", artifacts=manifest["artifacts"] + ["f1.json", "eligible_evidence/evidence.jsonl"])
        return
    update("r1", "Preparing R1 research plan; a plan is not a verified finding.")
    plan = r1(folder / "f1.json", folder / "r1.json", config)
    from .investigation import run_investigation
    investigation = run_investigation(folder, manifest["company"], manifest["prompt"], plan, config, update)
    update("complete", f"Investigation finished: {investigation['status']} / {investigation['evidence_strength']}. Inspect the claim checks and limitations.", "completed",
           investigation=investigation,
           artifacts=manifest["artifacts"] + ["eligible_evidence/evidence.jsonl", "f1.json", "r1.json", "investigation.json", "investigation_review.json", "investigation_report.md"])


def finish_evidence_gap(folder, manifest, update, reason, failed_stage=None):
    from .investigation import evidence_gap_report
    result = evidence_gap_report(folder, manifest["company"], manifest["prompt"], reason, failed_stage=failed_stage)
    update("complete", "Evidence-gap report saved. No verified financial finding; inspect execution stages and limitations.", "completed",
        investigation=result, artifacts=list(dict.fromkeys(manifest.get("artifacts", []) + ["investigation.json", "investigation_report.md"])))


def onboarded_records(pdf, digest, company, config, research_question=None):
    from .machine_evidence import create_machine_evidence
    return create_machine_evidence(pdf, company, config, expected_sha256=digest, max_records=16,
                                   research_question=research_question)


def machine_records(folder, company, config, research_question=None):
    from .evidence_ingestion import load_registry, verify_company
    from .machine_evidence import create_machine_evidence
    registry = load_registry(config.registry_path)
    name, identifier, status = verify_company(company, registry)
    if status != "verified":
        return []
    records = []
    report = json.loads((folder / "discovery" / "discovery_report.json").read_text())
    pinned = {}
    for hit in report.get("search_results", []):
        for source in hit.get("retrieval_report", {}).get("sources", []):
            if source.get("retrieval_status") == "retrieved":
                pinned[str(Path(source["saved_path"]).resolve())] = source
    # Only fresh snapshots under this run; never accept a request-supplied path.
    for path in sorted((folder / "discovery" / "retrieved" / "sources").glob("*.pdf"))[:3]:
        try:
            source = pinned.get(str(path.resolve()))
            if not source:
                continue
            batch = create_machine_evidence(path, company, config, expected_sha256=source["source_sha256"], max_records=16, research_question=research_question)
            records.extend(batch)
        except Exception:
            continue
    return records[:24]


def cached_machine_records(folder, company, config, research_question=None):
    """Use only company-matching, hash-pinned originals in operator catalogs.

    This is explicit cached evidence intake, never a claimed live download or
    human approval. Re-run the same original-PDF policy on the pinned bytes.
    """
    from .evidence_ingestion import load_registry, verify_company
    from .machine_evidence import create_machine_evidence
    from .source_catalog import load
    name, identifier, status = verify_company(company, load_registry(config.registry_path))
    report = {"intake_mode": "cached_original_rechecked", "company": name or company, "attempts": []}
    records = []
    if status == "verified":
        for catalog_path in sorted((ROOT / "data/pipeline_inputs").glob("*catalog.json")):
            try:
                catalog = load(catalog_path)
                if str(catalog.get("company", "")).casefold() != name.casefold():
                    continue
                for source in catalog["sources"]:
                    if source.get("source_class") != "official_filing" or not source.get("local_path") or not re.fullmatch(r"[a-f0-9]{64}", source.get("sha256") or ""):
                        continue
                    path = (catalog_path.parent / source["local_path"]).resolve()
                    attempt = {"source_id": source["source_id"], "catalog": str(catalog_path), "url": source.get("url"), "source_sha256": source["sha256"], "intake_mode": "cached_original_rechecked"}
                    report["attempts"].append(attempt)
                    try:
                        records = create_machine_evidence(path, company, config, expected_sha256=source["sha256"], max_records=16, research_question=research_question)
                        attempt.update(status="eligible", record_count=len(records))
                    except Exception as error:
                        attempt.update(status="rejected", error_type=type(error).__name__)
                    if records:
                        break
            except (ValueError, OSError, TypeError, KeyError):
                continue
            if records:
                break
    else:
        report["reason"] = "Company identity is not registry verified"
    report["eligible_record_count"] = len(records)
    (folder / "machine_evidence_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return records
