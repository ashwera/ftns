"""Per-run, opt-in cloud-to-local recovery; evidence validation stays upstream."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
import os

_runtime = ContextVar("signalforge_model_runtime", default=None)


@contextmanager
def model_runtime(config, record):
    state = {"config": config, "record": record, "fallback": os.getenv("SIGNALFORGE_OLLAMA_FALLBACK", ""), 'fallback_used':False}
    token = _runtime.set(state)
    try:
        yield
    finally:
        _runtime.reset(token)


def effective_config(config):
    state = _runtime.get()
    if not state:
        return config
    selected = state['config']
    return replace(config, provider=selected.provider, model=selected.model, base_url=selected.base_url)


def using_fallback():
    state = _runtime.get()
    return bool(state and state['fallback_used'])


def invoke(config, call):
    from .llm_client import LLMError, local_model_status, OLLAMA_BASE_URL
    state = _runtime.get()
    selected = effective_config(config)
    try:
        result = call(selected)
    except LLMError as error:
        recoverable = str(error).startswith(("Groq rate_limit error", "Groq timeout error", "Groq provider error",
            "Model returned invalid JSON from Groq structured generation; provider schema validation failed."))
        if not state or not state["fallback"] or selected.provider != "groq" or not recoverable:
            raise
        state["record"]("provider_error", selected, str(error))
        local = replace(selected, provider="ollama", model=state["fallback"], base_url=OLLAMA_BASE_URL)
        ready, reason = local_model_status(local)
        if not ready:
            state["record"]("fallback_unavailable", local, reason)
            raise error from None
        state["config"] = local
        state['fallback_used'] = True
        state["record"]("fallback_selected", local, "Authorized local recovery; no cloud retry. Schema, exact-passage and adjudication checks remain required.")
        selected = local
        result = call(selected)
    if state:
        state["record"]("generated", selected, "Model response received; validation outcome is recorded separately.")
    return result
