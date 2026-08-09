"""Explicit commercial-entitlement state for route isolation tests.

These helpers patch the entitlement service's lookup boundary, not the route
gate. Requests therefore still execute ``require_entitlement`` and fail closed
for tenants that a test has not deliberately configured.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException

from services import entitlement_service
from services.api_errors import error_detail
from services.commercial_catalog import get_product


class EntitlementTestState:
    def __init__(self):
        self._states: dict[str, dict] = {}

    @staticmethod
    def _key(tenant_id) -> str:
        return str(tenant_id)

    def activate_plan(self, tenant_id, plan_id: str):
        product = get_product(plan_id)
        if not product or product.get("type") != "base_plan":
            raise ValueError(f"Unknown test plan: {plan_id}")
        self._states[self._key(tenant_id)] = {
            "tenant_id": tenant_id,
            "source": "canonical_test_fixture",
            "plan_id": plan_id,
            "subscription": {"plan_id": plan_id, "state": "active"},
            "subscriptions": [{"plan_id": plan_id, "state": "active"}],
            "active_addons": [],
            "capabilities": list(product.get("capabilities") or []),
            "allowances": dict(product.get("allowances") or {}),
            "legacy_features": [],
            "review_required": False,
        }
        return self

    def allow_capability(self, tenant_id, capability: str):
        key = self._key(tenant_id)
        current = self._states.setdefault(
            key,
            {
                "tenant_id": tenant_id,
                "source": "canonical_test_fixture",
                "plan_id": None,
                "subscription": {"state": "active"},
                "subscriptions": [{"state": "active"}],
                "active_addons": [],
                "capabilities": [],
                "allowances": {},
                "legacy_features": [],
                "review_required": False,
            },
        )
        current["capabilities"] = sorted(
            set(current.get("capabilities") or []) | {capability}
        )
        return self

    def deny_capability(self, tenant_id, capability: str):
        key = self._key(tenant_id)
        if key not in self._states:
            self.allow_capability(tenant_id, capability)
        self._states[key]["capabilities"] = [
            item
            for item in self._states[key].get("capabilities") or []
            if item != capability
        ]
        return self

    def lookup(self, tenant_id):
        state = self._states.get(self._key(tenant_id))
        if state is None:
            raise HTTPException(
                status_code=503,
                detail=error_detail(
                    "entitlement_dependency_unavailable",
                    "Subscription access could not be verified.",
                ),
            )
        return state

    @contextmanager
    def installed(self):
        with patch.object(
            entitlement_service,
            "get_tenant_entitlements",
            side_effect=self.lookup,
        ):
            yield self
