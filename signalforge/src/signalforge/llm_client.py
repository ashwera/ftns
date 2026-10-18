"""Optional model access. This module never loads or inspects datasets."""
import json

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

class LLMError(RuntimeError):
    pass

def generate_json(prompt, payload, config):
    if not config.api_key:
        raise LLMError("Missing SIGNALFORGE_API_KEY; configure credentials to run F1 with a model.")
    provider = config.provider.strip().lower()
    if provider not in {"openai", "gemini"}:
        raise LLMError(f"Unsupported provider {config.provider!r}; currently supported: gemini, openai")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMError("OpenAI-compatible Python SDK is required for model calls. Install it with: python3 -m pip install 'openai>=1.30,<3'") from e
    try:
        kwargs = {"api_key": config.api_key, "timeout": 60, "max_retries": 2}
        base_url = config.base_url or (GEMINI_OPENAI_BASE_URL if provider == "gemini" else "")
        if base_url: kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        response = client.chat.completions.create(model=config.model, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
        content = response.choices[0].message.content
        if not content: raise LLMError("Model returned an empty response")
        try: return json.loads(content)
        except json.JSONDecodeError as e: raise LLMError(f"Model returned invalid JSON: {e}") from e
    except LLMError: raise
    except Exception as e:
        detail = str(e).replace(config.api_key, "[redacted]")
        raise LLMError(f"Model request failed ({type(e).__name__}): {detail}") from None
