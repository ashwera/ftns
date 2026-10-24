"""Read-only availability and optional minimal JSON probe, without printing credentials."""
import argparse
from dataclasses import replace
import json
import time

from .llm_client import credentials, generate_json, local_model_status, routes, trace_requests
from .research_session import local_config


def check(config, probe=False):
    result = {"provider": config.provider, "model": config.model}
    if config.provider != "ollama" and not credentials(config):
        return {**result, "status": "missing_credential", "variable": "GROQ_API_KEY" if config.provider == "groq" else "SIGNALFORGE_API_KEY"}
    try:
        from openai import OpenAI
        from .llm_client import GEMINI_OPENAI_BASE_URL, GROQ_BASE_URL, OLLAMA_BASE_URL
        base = config.base_url or {"groq": GROQ_BASE_URL, "gemini": GEMINI_OPENAI_BASE_URL, "ollama": OLLAMA_BASE_URL}.get(config.provider)
        client = OpenAI(api_key=credentials(config) or "ollama", base_url=base, timeout=10, max_retries=0)
        names = {m.id.removeprefix("models/") for m in client.models.list()}
        result.update(status="available" if config.model in names else "model_not_listed", model_count=len(names),
                      selected_model_listed=config.model in names)
        if probe:
            calls = []
            with trace_requests(calls, "health"):
                reply = generate_json('Return only JSON: {"ok": true}', {}, replace(config, fallback_providers="", request_timeout=30))
            result.update(json_probe=reply == {"ok": True}, calls=calls)
    except Exception as error:
        # Error class/status suffice; SDK messages can contain request details.
        result.update(status="unavailable", error_type=type(error).__name__, http_status=getattr(error, "status_code", None))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="Send one minimal inference request per configured provider")
    parser.add_argument("--all", action="store_true", help="Check Gemini, Groq and Ollama, even if not in fallback order")
    args = parser.parse_args()
    config = local_config()
    if args.all:
        config = replace(config, fallback_providers="gemini,groq,ollama")
    print(json.dumps({"providers": [check(c, args.probe) for c in routes(config)]}, indent=2))


if __name__ == "__main__":
    main()
