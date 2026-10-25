"""Optional model access. This module never loads or inspects datasets."""
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
LOCAL_TIMEOUT_SECONDS = 420
XAI_BASE_URL = "https://api.x.ai/v1"
XAI_TIMEOUT_SECONDS = 60
XAI_MAX_OUTPUT_TOKENS = 8192

class LLMError(RuntimeError):
    pass


def configured_secrets(config):
    return tuple(s for s in (getattr(config, "api_key", ""), getattr(config, "xai_api_key", ""), getattr(config, "groq_api_key", "")) if s)


def redact(value, config):
    for secret in configured_secrets(config):
        value = value.replace(secret, "[redacted]")
    return value


def xai_client(config):
    key = getattr(config, "xai_api_key", "").strip()
    if not key:
        raise LLMError("Missing XAI_API_KEY; add XAI_API_KEY to an ignored local .env or export it before starting SignalForge. Other provider credentials are not used for xAI.")
    base = config.base_url or XAI_BASE_URL
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise LLMError("Invalid xAI base URL; configure SIGNALFORGE_BASE_URL=https://api.x.ai/v1 (HTTPS, no embedded credentials).")
    try:
        from openai import OpenAI
    except ImportError:
        raise LLMError("Install the existing OpenAI-compatible SDK from signalforge/requirements.txt.") from None
    return OpenAI(api_key=key, base_url=base, timeout=XAI_TIMEOUT_SECONDS, max_retries=0)


def xai_failure(error):
    status = getattr(error, "status_code", None)
    name = type(error).__name__
    # xAI also returns 400 for malformed API keys. Inspect only for category
    # selection; never include body text or key fragments in the raised error.
    body = str(getattr(error, "body", "")).lower()
    key_error = status == 400 and any(term in body for term in ("api key", "api_key", "authentication", "credential"))
    category = ("authentication" if status in (401, 403) or key_error else "rate_limit" if status == 429 else
                "bad_request" if status == 400 else "model_access" if status == 404 else
                "timeout" if "Timeout" in name else "connection" if "Connection" in name else "provider")
    # Never retain the SDK response body, headers or chained exception.
    return LLMError(f"xAI {category} error" + (f" (HTTP {status})" if isinstance(status, int) else "") + "; request not retried. Check XAI_API_KEY, model access, endpoint and provider status.")


def list_xai_models(config):
    client = xai_client(config)
    try:
        return sorted(m.id for m in client.models.list().data)
    except Exception as error:
        raise xai_failure(error) from None

def model_configured(config):
    """A local Ollama provider needs no cloud credential; cloud providers need a key."""
    if config.provider.strip().lower() == "ollama":
        return True
    if config.provider.strip().lower() == "xai":
        return bool(getattr(config, "xai_api_key", "").strip())
    if config.provider.strip().lower() == "groq":
        return bool(getattr(config, "groq_api_key", "").strip())
    return bool(config.api_key)


def local_model_status(config, timeout=5):
    """(ok, message) for an Ollama provider; (True, '') for cloud providers. No secrets involved."""
    if config.provider.strip().lower() != "ollama":
        return True, ""
    import urllib.request
    base = (config.base_url or OLLAMA_BASE_URL).rstrip("/")
    try:
        with urllib.request.urlopen(base + "/models", timeout=timeout) as response:
            names = {m["id"] for m in json.load(response).get("data", [])}
    except Exception as error:
        return False, f"Local Ollama server unreachable at {base} ({type(error).__name__}). Start it with: ollama serve"
    wanted = {config.model, config.model + ":latest"}
    if not names & wanted:
        return False, f"Ollama model {config.model!r} is not installed (have: {', '.join(sorted(names)) or 'none'}). Run ollama pull / ollama create."
    return True, ""


def generate_json(prompt, payload, config, *, schema=None, audit_path=None):
    provider = config.provider.strip().lower()
    if provider == "groq":
        from .groq_provider import structured_json
        return structured_json(prompt, payload, config, schema=schema, audit_path=audit_path)
    if provider == "xai":
        client = xai_client(config)
        started = time.monotonic()
        try:
            reasoning = {"reasoning":{"effort":"medium"}} if config.model.startswith("grok-4.7") else {}
            response = client.responses.create(model=config.model,
                input=[{"role":"system", "content":prompt}, {"role":"user", "content":json.dumps(payload, ensure_ascii=False)}],
                text={"format": {"type":"json_schema", "name":"signalforge_output", "schema":schema, "strict":True} if schema is not None else {"type":"json_object"}},
                store=False, max_output_tokens=XAI_MAX_OUTPUT_TOKENS, **reasoning)
        except Exception as error:
            raise xai_failure(error) from None
        usage = getattr(response, "usage", None)
        metadata = {"provider":"xai", "model":getattr(response, "model", config.model), "api":"responses",
            "status":getattr(response, "status", None), "elapsed_seconds":round(time.monotonic()-started, 3),
            "usage":usage.model_dump(mode="json") if hasattr(usage, "model_dump") else usage,
            "request_id":getattr(response, "_request_id", None), "max_retries":0, "store":False}
        if audit_path:
            Path(audit_path).write_text(redact(json.dumps(metadata, indent=2), config)+"\n")
        if getattr(response, "status", None) != "completed":
            raise LLMError("xAI incomplete response; no output accepted. Inspect usage/status audit and token limits.")
        content = getattr(response, "output_text", "")
        if not content:
            raise LLMError("Model returned an empty response from xAI (or refusal); no output accepted.")
        try:
            output = json.loads(content)
        except json.JSONDecodeError:
            raise LLMError("Model returned invalid JSON from xAI") from None
        if not isinstance(output, dict):
            raise LLMError("Model returned invalid JSON object from xAI")
        return output
    if provider not in {"openai", "gemini", "ollama"}:
        raise LLMError(f"Unsupported provider {config.provider!r}; currently supported: xai, gemini, openai, ollama")
    if provider != "ollama" and not config.api_key:
        raise LLMError("Missing SIGNALFORGE_API_KEY; configure credentials to run F1 with a model.")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMError("OpenAI-compatible Python SDK is required for model calls. Install it with: python3 -m pip install 'openai>=1.30,<3'") from e
    try:
        local = provider == "ollama"
        # Local inference: placeholder credential, no redundant retries, long single timeout.
        kwargs = {"api_key": "ollama" if local else config.api_key,
                  "timeout": LOCAL_TIMEOUT_SECONDS if local else 60, "max_retries": 0 if local else 2}
        base_url = config.base_url or (GEMINI_OPENAI_BASE_URL if provider == "gemini" else OLLAMA_BASE_URL if local else "")
        if base_url: kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        extra = {"reasoning_effort": "none"} if local else {}  # skip hidden chain-of-thought: speed
        response = client.chat.completions.create(model=config.model, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            **extra)
        content = response.choices[0].message.content
        if not content: raise LLMError("Model returned an empty response")
        text = content.strip()
        if text.startswith("```"):  # some models fence JSON despite response_format
            text = text.split("\n", 1)[1] if "\n" in text else ""
            text = text.rsplit("```", 1)[0]
        try: return json.loads(text)
        except json.JSONDecodeError as e: raise LLMError(f"Model returned invalid JSON: {e}") from e
    except LLMError: raise
    except Exception as e:
        detail = redact(str(e), config)
        raise LLMError(f"Model request failed ({type(e).__name__}): {detail}") from None
