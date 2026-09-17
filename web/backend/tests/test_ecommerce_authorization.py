from tests.entitlement_test_support import installed_business_fixture
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Request, Response

from routes import ecommerce_routes


class TenantQuery:
    def __init__(self, table, rows):
        self.table_name = table
        self.rows = rows
        self.filters = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        matching = list(self.rows.get(self.table_name, []))
        for field, value in self.filters:
            matching = [row for row in matching if str(row.get(field)) == str(value)]
        return SimpleNamespace(data=matching)


class TenantSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def table(self, name):
        query = TenantQuery(name, self.rows)
        self.queries.append(query)
        return query


def request():
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/ecommerce/catalog",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
        "scheme": "http",
    })


def context(tenant_id=7, role="member"):
    return SimpleNamespace(tenant_id=tenant_id, user_id=12, role=role)


class EcommerceAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(installed_business_fixture(7))

    def test_every_private_ecommerce_route_uses_the_authorization_gate(self):
        private_routes = [
            route
            for route in ecommerce_routes.router.routes
            if route.path.startswith("/ecommerce")
        ]
        self.assertTrue(private_routes)
        for route in private_routes:
            self.assertIn(
                "_require_ecommerce_access",
                route.endpoint.__code__.co_names,
                route.path,
            )

    def test_ecommerce_access_disables_platform_account_impersonation(self):
        with patch.object(
            ecommerce_routes,
            "require_active_tenant_member",
            return_value=context(),
        ) as authorize:
            resolved = ecommerce_routes._require_ecommerce_access(request(), Response())

        self.assertEqual(resolved.tenant_id, 7)
        authorize.assert_called_once()
        self.assertEqual(
            authorize.call_args.kwargs,
            {"allow_admin_account_access": False},
        )

    def test_ecommerce_access_rejects_an_unknown_membership_role(self):
        with patch.object(
            ecommerce_routes,
            "require_active_tenant_member",
            return_value=context(role="customer"),
        ):
            with self.assertRaises(HTTPException) as captured:
                ecommerce_routes._require_ecommerce_access(request(), Response())

        self.assertEqual(captured.exception.status_code, 403)

    def test_catalog_read_returns_only_the_authenticated_tenant_rows(self):
        database = TenantSupabase({
            "ecommerce_tags": [
                {"id": "tag-7", "tenant_id": 7},
                {"id": "tag-8", "tenant_id": 8},
            ],
            "ecommerce_categories": [
                {"id": "category-7", "tenant_id": 7},
                {"id": "category-8", "tenant_id": 8},
            ],
            "ecommerce_products": [
                {"id": "product-7", "tenant_id": 7},
                {"id": "product-8", "tenant_id": 8},
            ],
            "ecommerce_product_tags": [
                {"tenant_id": 7, "product_id": "product-7", "tag_id": "tag-7"},
                {"tenant_id": 8, "product_id": "product-8", "tag_id": "tag-8"},
            ],
        })

        with patch.object(ecommerce_routes, "service_supabase", database):
            catalog = ecommerce_routes._catalog_for_tenant(7)

        self.assertEqual([row["id"] for row in catalog["tags"]], ["tag-7"])
        self.assertEqual(
            [row["id"] for row in catalog["categories"]],
            ["category-7"],
        )
        self.assertEqual(
            [row["id"] for row in catalog["products"]],
            ["product-7"],
        )
        self.assertEqual(catalog["products"][0]["tag_ids"], ["tag-7"])
        self.assertTrue(
            all(("tenant_id", 7) in query.filters for query in database.queries)
        )

    def test_cross_tenant_record_lookup_is_hidden_as_not_found(self):
        database = TenantSupabase({
            "ecommerce_products": [
                {
                    "id": "00000000-0000-0000-0000-000000000008",
                    "tenant_id": 8,
                }
            ],
        })

        with patch.object(ecommerce_routes, "service_supabase", database):
            with self.assertRaises(HTTPException) as captured:
                ecommerce_routes._tenant_row(
                    "ecommerce_products",
                    "00000000-0000-0000-0000-000000000008",
                    7,
                )

        self.assertEqual(captured.exception.status_code, 404)
        self.assertNotIn("tenant", str(captured.exception.detail).lower())


if __name__ == "__main__":
    unittest.main()
