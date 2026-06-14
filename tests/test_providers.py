import os
import unittest
from unittest.mock import patch

from stupidex import providers


class ProviderTests(unittest.TestCase):
    def test_catalog_has_two_models_per_provider(self):
        self.assertEqual(len(providers.MODELS), 10)
        for provider in ("openai", "anthropic", "gemini", "deepseek", "openrouter"):
            self.assertEqual(
                sum(model["provider"] == provider for model in providers.MODELS), 2
            )

    def test_selected_provider_uses_its_environment_key(self):
        captured = {}

        def completion(**kwargs):
            captured.update(kwargs)
            return []

        user = {
            "provider": "openai",
            "api_key_enc": "stored",
            "base_url": "https://custom-openai.example/v1",
        }
        with (
            patch.object(providers.litellm, "completion", side_effect=completion),
            patch.object(providers, "decrypt", return_value="stored-openai-key"),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "anthropic-env-key"}),
        ):
            list(
                providers.stream_chat(
                    user,
                    [{"role": "user", "content": "hello"}],
                    model="anthropic/claude-opus-4-8",
                )
            )

        self.assertEqual(captured["api_key"], "anthropic-env-key")
        self.assertNotIn("api_base", captured)

    def test_configured_provider_keeps_byok_and_base_url(self):
        captured = {}

        def completion(**kwargs):
            captured.update(kwargs)
            return []

        user = {
            "provider": "openai",
            "api_key_enc": "stored",
            "base_url": "https://custom-openai.example/v1",
        }
        with (
            patch.object(providers.litellm, "completion", side_effect=completion),
            patch.object(providers, "decrypt", return_value="stored-openai-key"),
        ):
            list(
                providers.stream_chat(
                    user,
                    [{"role": "user", "content": "hello"}],
                    model="gpt-5.4",
                )
            )

        self.assertEqual(captured["api_key"], "stored-openai-key")
        self.assertEqual(captured["api_base"], "https://custom-openai.example/v1")

    def test_unknown_model_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Modelo não suportado"):
            list(providers.stream_chat({}, [], model="unknown/model"))

    def test_custom_endpoint_keeps_custom_model_support(self):
        captured = {}

        def completion(**kwargs):
            captured.update(kwargs)
            return []

        user = {
            "provider": "openai",
            "model": "company/custom-model",
            "api_key_enc": "stored",
            "base_url": "https://models.example/v1",
        }
        with (
            patch.object(providers.litellm, "completion", side_effect=completion),
            patch.object(providers, "decrypt", return_value="custom-key"),
        ):
            list(providers.stream_chat(user, [], model="company/custom-model"))

        self.assertEqual(captured["model"], "company/custom-model")
        self.assertEqual(captured["api_base"], "https://models.example/v1")


if __name__ == "__main__":
    unittest.main()
