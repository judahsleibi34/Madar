import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from data_analysis.ai import settings


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = BACKEND_ROOT.parent


class LegacyGeminiRemovalTests(TestCase):
    def test_gemini_is_not_a_supported_provider(self):
        self.assertNotIn("gemini", settings.SUPPORTED_PROVIDERS)

    def test_gemini_provider_is_rejected(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=False):
            with self.assertRaises(settings.AISettingsError):
                settings.get_default_provider()

    def test_provider_must_be_explicit_when_not_mocking(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                settings.AISettingsError,
                "AI_PROVIDER must be explicitly configured",
            ):
                settings.get_default_provider()

    def test_model_must_be_explicit_when_not_mocking(self):
        environment = {
            "AI_PROVIDER": "openai",
            "AI_MOCK_MODE": "false",
        }

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(
                settings.AISettingsError,
                "AI_FREE_MODEL must be explicitly configured",
            ):
                settings.get_model_for_plan("free")

    def test_mock_mode_remains_available_for_tests(self):
        with patch.dict(
            os.environ,
            {"AI_MOCK_MODE": "true"},
            clear=True,
        ):
            self.assertEqual(
                settings.get_provider_for_plan("free"),
                "mock",
            )
            self.assertEqual(
                settings.get_model_for_plan("free"),
                "mock",
            )

    def test_gemini_api_key_is_not_supported(self):
        with self.assertRaises(settings.AISettingsError):
            settings.get_provider_api_key("gemini")

    def test_runtime_sources_contain_no_gemini_provider_path(self):
        files = [
            BACKEND_ROOT / "data_analysis/ai/planner.py",
            BACKEND_ROOT / "data_analysis/ai/settings.py",
            BACKEND_ROOT / "services/entitlement_service.py",
            BACKEND_ROOT / "services/runtime_config.py",
        ]

        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in files
        ).lower()

        self.assertNotIn("gemini_api_key", combined)
        self.assertNotIn('_call_gemini_json', combined)
        self.assertNotIn('"gemini"', combined)


if __name__ == "__main__":
    import unittest
    unittest.main()
