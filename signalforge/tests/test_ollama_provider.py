"""Ollama provider wiring; no network and no real model calls."""
import dataclasses
import sys
import types
import unittest
from unittest.mock import patch

from signalforge.config import Config
from signalforge import llm_client


def cfg(**kw):
    return dataclasses.replace(Config(), provider="ollama", model="m", api_key="", base_url="", **kw)


class FakeOpenAI:
    created = {}

    def __init__(self, **kwargs):
        FakeOpenAI.created = kwargs
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        FakeOpenAI.request = kwargs
        message = types.SimpleNamespace(content='```json\n{"ok": true}\n```')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


class OllamaTests(unittest.TestCase):
    def test_ready_without_key_but_cloud_requires_one(self):
        self.assertTrue(llm_client.model_configured(cfg()))
        self.assertFalse(llm_client.model_configured(dataclasses.replace(cfg(), provider="gemini")))

    def test_local_call_uses_placeholder_credential_local_url_no_retries(self):
        with patch.dict(sys.modules, {"openai": types.SimpleNamespace(OpenAI=FakeOpenAI)}):
            self.assertEqual({"ok": True}, llm_client.generate_json("p", {"a": 1}, cfg()))
        self.assertEqual("ollama", FakeOpenAI.created["api_key"])
        self.assertEqual(llm_client.OLLAMA_BASE_URL, FakeOpenAI.created["base_url"])
        self.assertEqual(0, FakeOpenAI.created["max_retries"])
        self.assertEqual("m", FakeOpenAI.request["model"])

    def test_gemini_behaviour_unchanged(self):
        gem = dataclasses.replace(cfg(), provider="gemini", api_key="K")
        with patch.dict(sys.modules, {"openai": types.SimpleNamespace(OpenAI=FakeOpenAI)}):
            llm_client.generate_json("p", {}, gem)
        self.assertEqual("K", FakeOpenAI.created["api_key"])
        self.assertEqual(0, FakeOpenAI.created["max_retries"])
        self.assertEqual(llm_client.GEMINI_OPENAI_BASE_URL, FakeOpenAI.created["base_url"])
        with self.assertRaises(llm_client.LLMError):
            llm_client.generate_json("p", {}, dataclasses.replace(gem, api_key=""))

    def test_unreachable_server_is_an_explicit_failure(self):
        bad = dataclasses.replace(cfg(), base_url="http://127.0.0.1:9/v1")
        ok, message = llm_client.local_model_status(bad, timeout=1)
        self.assertFalse(ok)
        self.assertIn("unreachable", message)

    def test_cloud_provider_skips_local_check(self):
        self.assertEqual((True, ""), llm_client.local_model_status(dataclasses.replace(cfg(), provider="gemini")))


if __name__ == "__main__":
    unittest.main()
