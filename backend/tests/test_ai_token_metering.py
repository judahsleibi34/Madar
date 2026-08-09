import unittest
from unittest.mock import Mock, patch

from data_analysis.ai import token_metering


class AiTokenMeteringTests(unittest.TestCase):
    def test_integer_normalization_uses_versioned_model_multipliers(self):
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 20,
            "output_tokens": 50,
        }
        multipliers = {
            "version": "test-v1",
            "input_multiplier_micros": 1_000_000,
            "cached_input_multiplier_micros": 250_000,
            "output_multiplier_micros": 2_000_000,
        }
        self.assertEqual(
            token_metering.normalize_standard_tokens(
                input_tokens=usage["input_tokens"],
                cached_input_tokens=usage["cached_input_tokens"],
                output_tokens=usage["output_tokens"],
                multipliers=multipliers,
            ),
            205,
        )

    def test_provider_usage_is_preferred_and_marked_exact(self):
        with token_metering.capture_provider_usage() as captured:
            token_metering.record_provider_usage(
                {
                    "provider": "gemini",
                    "model": "gemini-test",
                    "input_tokens": 11,
                    "output_tokens": 7,
                    "cached_input_tokens": 3,
                    "total_provider_tokens": 21,
                    "usage_source": "provider",
                }
            )
        usage = token_metering.aggregate_usage(
            captured,
            fallback_input="ignored",
            fallback_output="ignored",
            provider="ignored",
            model="ignored",
        )

        self.assertEqual(usage["input_tokens"], 11)
        self.assertEqual(usage["output_tokens"], 7)
        self.assertFalse(usage["estimated"])
        self.assertEqual(usage["usage_source"], "provider")

    def test_server_estimation_does_not_accept_client_counts(self):
        usage = token_metering.aggregate_usage(
            [],
            fallback_input="abc",
            fallback_output="defgh",
            provider="gemini",
            model="gemini-test",
        )
        self.assertTrue(usage["estimated"])
        self.assertEqual(usage["usage_source"], "server_estimate")
        self.assertGreaterEqual(usage["input_tokens"], 1)
        self.assertGreaterEqual(usage["output_tokens"], 1)

    def test_finalization_uses_actual_tokens_from_structured_rpc_result(self):
        response = Mock()
        response.data = [{
            "standard_tokens": 950,
            "covered_standard_tokens": 800,
            "deficit_standard_tokens": 150,
        }]
        rpc = Mock()
        rpc.execute.return_value = response
        client = Mock()
        client.rpc.return_value = rpc
        usage = {
            "provider": "mock",
            "model": "mock",
            "input_tokens": 900,
            "cached_input_tokens": 0,
            "output_tokens": 50,
            "total_provider_tokens": 950,
            "usage_source": "provider",
            "estimated": False,
        }
        with patch.object(token_metering, "service_supabase", client), patch.object(
            token_metering,
            "get_model_multipliers",
            return_value={
                "version": "test",
                "input_multiplier_micros": 1_000_000,
                "cached_input_multiplier_micros": 1_000_000,
                "output_multiplier_micros": 1_000_000,
            },
        ):
            consumed = token_metering.finalize_tokens(
                "request-actual-overrun",
                usage,
                request_status="succeeded",
            )

        self.assertEqual(consumed, 950)
        payload = client.rpc.call_args.args[1]
        self.assertEqual(payload["p_standard_tokens"], 950)
        self.assertNotIn("client_tokens", payload)

    def test_monthly_package_allocation_uses_atomic_server_rpc(self):
        execute = Mock()
        client = Mock()
        client.rpc.return_value.execute = execute
        entitlements = {
            "active_addons": [{"addon_id": "ai_analytics_plus", "state": "active"}],
        }
        with patch.object(
            token_metering,
            "service_supabase",
            client,
        ), patch.object(
            token_metering,
            "get_tenant_entitlements",
            return_value=entitlements,
        ):
            allowance = token_metering.ensure_monthly_allocation(
                7,
                period_key="2026-07",
            )

        self.assertEqual(allowance, 1_500_000)
        self.assertEqual(
            client.rpc.call_args.args[0],
            "ensure_ai_monthly_allocation",
        )
        payload = client.rpc.call_args.args[1]
        self.assertEqual(payload["p_product_id"], "ai_analytics_plus")
        self.assertEqual(payload["p_standard_tokens"], 1_500_000)


if __name__ == "__main__":
    unittest.main()
