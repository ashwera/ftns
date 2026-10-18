import dataclasses
import sys
import types
import unittest
from unittest.mock import patch

from signalforge.config import Config
from signalforge.llm_client import GEMINI_OPENAI_BASE_URL, LLMError, generate_json


class LlmClientTests(unittest.TestCase):
    def _fake_sdk(self, response_content='{"ok":true}', error=None):
        calls = {}

        class Completions:
            def create(self, **kwargs):
                calls["request"] = kwargs
                if error:
                    raise RuntimeError(error)
                message = types.SimpleNamespace(content=response_content)
                choice = types.SimpleNamespace(message=message)
                return types.SimpleNamespace(choices=[choice])

        class OpenAI:
            def __init__(self, **kwargs):
                calls["client"] = kwargs
                self.chat = types.SimpleNamespace(completions=Completions())

        return types.SimpleNamespace(OpenAI=OpenAI), calls

    def test_gemini_key_routes_to_official_compat_endpoint_and_parses_json(self):
        sdk, calls = self._fake_sdk()
        cfg = dataclasses.replace(Config(), provider="gemini", model="gemini-3.8-flash", api_key="fixture-secret", base_url="")
        with patch.dict(sys.modules, {"openai": sdk}):
            result = generate_json("system prompt", {"value": "fixture"}, cfg)
        self.assertEqual({"ok": True}, result)
        self.assertEqual("fixture-secret", calls["client"]["api_key"])
        self.assertEqual(GEMINI_OPENAI_BASE_URL, calls["client"]["base_url"])
        self.assertEqual(60, calls["client"]["timeout"])
        self.assertEqual(2, calls["client"]["max_retries"])
        self.assertEqual("gemini-3.8-flash", calls["request"]["model"])
        self.assertEqual({"type": "json_object"}, calls["request"]["response_format"])
        self.assertEqual('{"value": "fixture"}', calls["request"]["messages"][1]["content"])

    def test_explicit_base_url_is_respected_for_gemini_compatible_deployment(self):
        sdk, calls = self._fake_sdk()
        cfg = dataclasses.replace(Config(), provider="gemini", api_key="fixture-secret", base_url="https://gemini.example.test/v1/openai/")
        with patch.dict(sys.modules, {"openai": sdk}):
            generate_json("prompt", {}, cfg)
        self.assertEqual("https://gemini.example.test/v1/openai/", calls["client"]["base_url"])

    def test_openai_provider_does_not_inherit_gemini_endpoint(self):
        sdk, calls = self._fake_sdk()
        cfg = dataclasses.replace(Config(), provider=" OpenAI ", model="gpt-4o-mini", api_key="fixture-secret", base_url="")
        with patch.dict(sys.modules, {"openai": sdk}):
            generate_json("prompt", {}, cfg)
        self.assertNotIn("base_url", calls["client"])
        self.assertEqual("gpt-4o-mini", calls["request"]["model"])

    def test_api_key_is_redacted_from_model_errors(self):
        secret = "fixture-secret-value"
        sdk, _ = self._fake_sdk(error=f"request failed with {secret}")
        cfg = dataclasses.replace(Config(), provider="gemini", api_key=secret, base_url="")
        with patch.dict(sys.modules, {"openai": sdk}):
            with self.assertRaises(LLMError) as caught:
                generate_json("prompt", {}, cfg)
        self.assertNotIn(secret, str(caught.exception))
        self.assertIn("[redacted]", str(caught.exception))

    def test_empty_and_non_json_responses_fail_closed(self):
        cfg = dataclasses.replace(Config(), provider="gemini", api_key="fixture-secret", base_url="")
        for content, expected in (("", "empty response"), ("not-json", "invalid JSON")):
            sdk, _ = self._fake_sdk(response_content=content)
            with self.subTest(content=content), patch.dict(sys.modules, {"openai": sdk}):
                with self.assertRaisesRegex(LLMError, expected):
                    generate_json("prompt", {}, cfg)

    def test_missing_key_and_unsupported_provider_fail_before_sdk_import(self):
        cfg = dataclasses.replace(Config(), provider="gemini", api_key="")
        with patch.dict(sys.modules, {"openai": None}):
            with self.assertRaisesRegex(LLMError, "Missing SIGNALFORGE_API_KEY"):
                generate_json("prompt", {}, cfg)
            with self.assertRaisesRegex(LLMError, "Unsupported provider"):
                generate_json("prompt", {}, dataclasses.replace(cfg, provider="unsupported", api_key="present"))


if __name__ == "__main__":
    unittest.main()
