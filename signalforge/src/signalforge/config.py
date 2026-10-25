from dataclasses import dataclass, field
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def default_provider():
    return os.getenv("SIGNALFORGE_PROVIDER") or ("groq" if os.getenv("GROQ_API_KEY") else "xai" if os.getenv("XAI_API_KEY") else "gemini")

def default_model():
    return os.getenv("SIGNALFORGE_MODEL") or {"groq":"openai/gpt-oss-120b", "xai":"grok-4.7", "ollama":"signalforge-qwen"}.get(default_provider().strip().lower(), "gemini-3.8-flash")

@dataclass(frozen=True)
class Config:
    provider: str = field(default_factory=default_provider)
    model: str = field(default_factory=default_model)
    api_key: str = field(default_factory=lambda: os.getenv("SIGNALFORGE_API_KEY", ""))
    xai_api_key: str = field(default_factory=lambda: os.getenv("XAI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("SIGNALFORGE_BASE_URL", ""))
    csv_path: Path = Path(os.getenv("SIGNALFORGE_CSV_PATH", str(ROOT.parent / "Quote-Equity-NTPC-EQ-15-04-2026-15-10-2026.csv")))
    output_dir: Path = ROOT / "outputs"
    prompt_dir: Path = ROOT / "prompts"
    schema_path: Path = ROOT / "schemas" / "f1_output.schema.json"
    evidence_dir: Path = ROOT / "data" / "processed"
    registry_path: Path = ROOT / "data" / "company_registry.json"
