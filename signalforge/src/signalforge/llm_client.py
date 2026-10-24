"""Optional model access. This module never loads or inspects datasets."""
import json
import re
import contextlib
import contextvars
from dataclasses import replace
import time

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
LOCAL_TIMEOUT_SECONDS = 120
_trace = contextvars.ContextVar("model_request_trace", default=None)


@contextlib.contextmanager
def trace_requests(events, stage, schema=None):
    token = _trace.set((events, stage, schema))
    try:
        yield
    finally:
        _trace.reset(token)


def credentials(config):
    return config.groq_api_key if config.provider.strip().lower() == "groq" else config.api_key


def redact(text, config):
    for key in (config.api_key, config.groq_api_key):
        if key:
            text = text.replace(key, "[redacted]")
    return text


def routes(config):
    """Explicit provider order; a single short provider-directed quota retry is allowed."""
    primary = config.provider.strip().lower()
    seen = set()
    for provider in [primary, *config.fallback_providers.split(",")]:
        provider = provider.strip().lower()
        if not provider or provider in seen:
            continue
        if provider not in {"gemini", "groq", "ollama", "openai"}:
            raise LLMError(f"Unsupported provider {provider!r}")
        seen.add(provider)
        if provider == primary:
            yield config
        else:
            if provider == "openai":
                raise LLMError("OpenAI fallback requires its own explicit configuration")
            yield replace(config, provider=provider, base_url="", model=getattr(config, provider + "_model"))

class LLMError(RuntimeError):
    pass

def model_configured(config):
    """A local Ollama provider needs no cloud credential; cloud providers need a key."""
    return any(c.provider.strip().lower() == "ollama" or bool(credentials(c)) for c in routes(config))


def local_model_status(config, timeout=5):
    """(ok, message) for an Ollama provider; (True, '') for cloud providers. No secrets involved."""
    if config.provider.strip().lower() != "ollama":
        return True, ""
    if config.fallback_providers:
        return True, ""  # Availability is checked by bounded inference; allow cloud fallback.
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


def generate_json(prompt, payload, config):
    failures = []
    for route_index, selected in enumerate(routes(config)):
        for attempt in (1, 2):
            event = {"provider": selected.provider, "model": selected.model, "request_attempt": attempt,
                     "fallback_reason": failures[-1] if failures and route_index else None}
            context = _trace.get()
            if context:
                event["stage"] = context[1]
                context[0].append(event)
            started = time.monotonic()
            delay = 0
            try:
                result = _generate_once(prompt, payload, selected, event)
            except LLMError as error:
                event.update(outcome="failed", error_type=type(error).__name__)
                if not getattr(error, "failover_allowed", False):
                    raise
                failures.append(redact(str(error), config))
                suggested = getattr(error, "retry_after_seconds", 0)
                if attempt == 1 and 0 < suggested <= config.quota_wait_seconds:
                    delay = suggested + 0.25
                    event["quota_wait_seconds"] = delay
            else:
                event["outcome"] = "responded"
                return result
            finally:
                event["latency_seconds"] = round(time.monotonic() - started, 3)
            if not delay:
                break
            time.sleep(delay)  # One provider-directed short quota reset only.
    raise LLMError("All configured providers unavailable: " + "; ".join(failures)) from None


def _unavailable(message):
    error = LLMError(message)
    error.failover_allowed = True
    return error


def _generate_once(prompt, payload, config, event):
    provider = config.provider.strip().lower()
    key = credentials(config)
    if provider != "ollama" and not key:
        env_name = "GROQ_API_KEY" if provider == "groq" else "SIGNALFORGE_API_KEY"
        raise _unavailable(f"Missing {env_name} for {provider}")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMError("OpenAI-compatible Python SDK is required for model calls. Install it with: python3 -m pip install 'openai>=1.30,<3'") from e
    try:
        local = provider == "ollama"
        # Local inference: placeholder credential and one bounded request timeout.
        kwargs = {"api_key": "ollama" if local else key,
                  "timeout": min(config.request_timeout, LOCAL_TIMEOUT_SECONDS) if local else config.request_timeout, "max_retries": 0}
        base_url = config.base_url or {"gemini": GEMINI_OPENAI_BASE_URL, "groq": GROQ_BASE_URL, "ollama": OLLAMA_BASE_URL}.get(provider, "")
        if base_url: kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        extra = {"reasoning_effort": "none"} if local else {}  # skip hidden chain-of-thought: speed
        response_format = {"type": "json_object"}
        if provider == "groq" and config.model.startswith("openai/gpt-oss-"):
            context = _trace.get()
            extra.update(reasoning_effort="low", max_completion_tokens=2500)
            if context and context[2]:
                response_format = {"type": "json_schema", "json_schema": {
                    "name": context[1].replace("-", "_"), "strict": False, "schema": context[2]}}
        response = client.chat.completions.create(model=config.model, response_format=response_format,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            **extra)
        content = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        if usage:
            event["usage"] = {k: getattr(usage, k, None) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
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
        status = getattr(e, "status_code", None)
        body = getattr(e, "body", None)
        provider_error = body.get("error", body) if isinstance(body, dict) else {}
        if status == 400 and provider_error.get("code") == "json_validate_failed":
            raise LLMError("Model returned invalid JSON: provider could not validate its generated content") from None
        retryable = status in {401, 403, 408, 429, 500, 502, 503, 504} or type(e).__name__ in {"APIConnectionError", "APITimeoutError", "TimeoutError", "ConnectionError"}
        # Groq uses HTTP 413 for a request exceeding its account token quota.
        # Do not retry it on Groq; an explicitly configured Gemini route may
        # accept the same audited input under its larger input allowance.
        if provider == "groq" and status == 413 and "gemini" in {p.strip() for p in config.fallback_providers.split(",")}:
            retryable = True
        event["http_status"] = status
        error = LLMError(f"Model request failed ({type(e).__name__}): {detail}")
        error.failover_allowed = retryable
        if provider == "groq" and status == 429:
            headers = getattr(e, "headers", {}) or {}
            retry_after = headers.get("retry-after", "")
            match = re.search(r"try again in ([0-9.]+)s", provider_error.get("message", ""), re.I)
            try:
                error.retry_after_seconds = float(retry_after or (match.group(1) if match else 0))
            except (ValueError, TypeError):
                pass
        raise error from None
