from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Config:
    provider: str = os.getenv("SIGNALFORGE_PROVIDER", "gemini")
    model: str = os.getenv("SIGNALFORGE_MODEL", "gemini-3.8-flash")
    api_key: str = os.getenv("SIGNALFORGE_API_KEY", "")
    base_url: str = os.getenv("SIGNALFORGE_BASE_URL", "")
    csv_path: Path = Path(os.getenv("SIGNALFORGE_CSV_PATH", str(ROOT.parent / "Quote-Equity-NTPC-EQ-15-04-2026-15-10-2026.csv")))
    output_dir: Path = ROOT / "outputs"
    prompt_dir: Path = ROOT / "prompts"
    schema_path: Path = ROOT / "schemas" / "f1_output.schema.json"
    evidence_dir: Path = ROOT / "data" / "processed"
    registry_path: Path = ROOT / "data" / "company_registry.json"
