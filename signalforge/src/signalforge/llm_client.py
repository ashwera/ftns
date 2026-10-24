"""Optional model access. This module never loads or inspects datasets."""
import json

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
LOCAL_TIMEOUT_SECONDS = 420

class LLMError(RuntimeError):
    pass

def model_configured(config):
    """A local Ollama provider needs no cloud credential; cloud providers need a key."""
    if config.provider.strip().lower() == "ollama":
        return True
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


def generate_json(prompt, payload, config):
    provider = config.provider.strip().lower()
    if provider not in {"openai", "gemini", "ollama"}:
        raise LLMError(f"Unsupported provider {config.provider!r}; currently supported: gemini, openai, ollama")
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
        detail = str(e).replace(config.api_key, "[redacted]") if config.api_key else str(e)
        raise LLMError(f"Model request failed ({type(e).__name__}): {detail}") from None
