"""Reproducible machine-evidence -> real F1 -> real R1 command.

Example (from repo root, after configuring the ignored .env or environment):
PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.live_research \
    --original-pdf report.pdf --company COMPANY --expected-sha256 HASH \
    --run-dir signalforge/data/runs/FRESH_RUN

Use --evidence-dir instead of --original-pdf to replay an existing bounded store;
the production runners still recheck eligibility against original source bytes.
Raw responses, schema requests, validation repairs and arithmetic corrections are
saved automatically by the production runners. No runtime adapters are used.
"""
import argparse
from dataclasses import replace
import datetime as dt
import json
from pathlib import Path

from .f1_research_angle_selector import MAX_F1_EVIDENCE_RECORD_BYTES, MAX_F1_EVIDENCE_RECORDS, run as run_f1
from .r1_research_investigator import run as run_r1
from .machine_evidence import create_machine_evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--original-pdf")
    inputs.add_argument("--evidence-dir")
    parser.add_argument("--company", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--pages", nargs="+", type=int)
    parser.add_argument("--max-records", type=int, default=16)
    args = parser.parse_args(argv)
    # Reuse the app's literal allowlisted dotenv loader; never source a shell file.
    from .research_session import local_config
    config = local_config()
    folder = Path(args.run_dir).resolve()
    if folder.exists():
        print("Run directory already exists; choose a fresh directory.")
        return 2
    folder.mkdir(parents=True, exist_ok=False)
    manifest = {"run_id": folder.name, "provider": config.provider, "model": config.model,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "stages": {},
        "runner": "signalforge.live_research", "max_generation_attempts_per_stage": 2,
        "limitations": ["Machine passage matching is not human review or claim verification.",
                         "R1 is a plan, not executed research; source independence is assessed separately."]}

    def save():
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    stage = "machine_evidence"
    try:
        if args.evidence_dir:
            if args.pages or args.expected_sha256:
                raise ValueError("PDF options require --original-pdf")
            records = []
            with (Path(args.evidence_dir) / "evidence.jsonl").open(encoding="utf-8") as stream:
                while True:
                    line = stream.readline(MAX_F1_EVIDENCE_RECORD_BYTES + 1)
                    if not line: break
                    if len(line.encode("utf-8")) > MAX_F1_EVIDENCE_RECORD_BYTES:
                        raise ValueError("Evidence record exceeds byte bound")
                    if not line.strip(): continue
                    records.append(json.loads(line))
                    if len(records) > MAX_F1_EVIDENCE_RECORDS:
                        raise ValueError("Evidence replay exceeds 40 records")
        else:
            records = create_machine_evidence(args.original_pdf, args.company, config,
                expected_sha256=args.expected_sha256, pages=args.pages, max_records=args.max_records)
        evidence = folder / "evidence"
        evidence.mkdir()
        (evidence / "evidence.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        config = replace(config, evidence_dir=evidence, output_dir=folder)
        manifest["evidence_ids"] = [r["evidence_id"] for r in records]
        manifest["stages"][stage] = {"status": "prepared", "count": len(records)}
        save()
        stage = "f1"
        manifest["stages"][stage] = {"status": "running"}; save()
        result = run_f1(args.company, config.csv_path, folder / "f1.json", config)
        manifest["stages"][stage] = {"status": "validated", "execution": "real",
            "ranking_reliable": result["ranking_reliable"],
            "recommended_candidate_id": result["recommended_candidate_id"]}; save()
        if not result["ranking_reliable"] or not result["recommended_candidate_id"]:
            manifest["stages"]["r1"] = {"status": "blocked", "reason": "No reliable F1 recommendation"}
            return 0
        stage = "r1"
        manifest["stages"][stage] = {"status": "running"}; save()
        plan = run_r1(folder / "f1.json", folder / "r1.json", config)
        manifest["stages"][stage] = {"status": "validated", "execution": "real",
                                     "retrieval_performed": plan["retrieval_performed"]}
        print(f"Validated live F1/R1 saved to {folder}; claims remain unverified.")
        return 0
    except Exception as error:
        manifest["stages"][stage] = {"status": "failed", "error_type": type(error).__name__}
        print(f"Live research stopped at {stage} ({type(error).__name__}); see run audit artifacts.")
        return 2
    finally:
        manifest["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat(); save()


if __name__ == "__main__":
    raise SystemExit(main())
