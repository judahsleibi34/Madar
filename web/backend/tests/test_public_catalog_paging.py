import re
import threading
import time
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from routes import public_site_routes
from services.ecommerce_cache_service import invalidate_ecommerce_cache

ROW_CAP = 7  # stands in for PostgREST max_rows


class FakeQuery:
    """Small PostgREST stand-in: capped responses, exact counts, ordered
    ranges, and aliased product-link embeds (``alias:table!inner(cols)``)."""

    log: list[tuple[str, str]] = []

    def __init__(self, tables, name):
        self.tables, self.name = tables, name
        self.filters, self.orders, self.embed_orders = [], [], {}
        self.count, self.window, self.embeds = None, None, {}
        self.columns = ""

    def select(self, columns, count=None):
        self.columns, self.count = columns, count
        for alias, table, inner, fields in re.findall(r"(\w+):(\w+)(!inner)?\(([^)]*)\)", columns):
            self.embeds[alias] = (table, bool(inner), fields.split(","))
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, list(values)))
        return self

    def gte(self, field, value):
        self.filters.append(("gte", field, Decimal(str(value))))
        return self

    def lte(self, field, value):
        self.filters.append(("lte", field, Decimal(str(value))))
        return self

    @property
    def not_(self):
        query = self

        class Negated:
            def is_(self, field, _value):
                query.filters.append(("notnull", field, None))
                return query

        return Negated()

    def order(self, field, desc=False, foreign_table=None):
        if foreign_table:
            self.embed_orders[foreign_table] = field
        else:
            self.orders.append((field, desc))
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def limit(self, size):
        self.window = (0, size - 1)
        return self

    def _links(self, alias, row):
        table, _inner, _fields = self.embeds[alias]
        links = [link for link in self.tables[table] if link["product_id"] == row["id"] and link["tenant_id"] == row["tenant_id"]]
        for op, field, value in self.filters:
            if field.startswith(f"{alias}."):
                column = field.split(".", 1)[1]
                links = [link for link in links if (link[column] == value if op == "eq" else link[column] in value)]
        if alias in self.embed_orders:
            links.sort(key=lambda link: link[self.embed_orders[alias]])
        return links

    def _matches(self, row, op, field, value):
        if "." in field:
            return True  # embedded filters apply through _links
        current = row.get(field)
        if op == "eq":
            return current == value
        if op == "in":
            return current in value
        if op == "notnull":
            return current is not None
        if op == "gte":
            return Decimal(str(current)) >= value
        return Decimal(str(current)) <= value

    def execute(self):
        FakeQuery.log.append((self.name, self.columns))
        if self.name not in self.tables:
            raise Exception("{'code': 'PGRST205', 'message': 'Could not find the table'}")
        matched = []
        for row in self.tables[self.name]:
            if not all(self._matches(row, *f) for f in self.filters):
                continue
            embedded = {alias: self._links(alias, row) for alias in self.embeds}
            if any(self.embeds[alias][1] and not embedded[alias] for alias in self.embeds):
                continue
            matched.append({**row, **{
                alias: [{field: link[field] for field in self.embeds[alias][2]} for link in links]
                for alias, links in embedded.items()
            }})
        for field, desc in reversed(self.orders):
            matched.sort(key=lambda row: (row.get(field) is None, row.get(field)), reverse=desc)
        total = len(matched)
        start, end = self.window if self.window else (0, total - 1)
        if self.count and start > 0 and start >= total:
            raise Exception("{'code': 'PGRST103', 'message': 'Requested range not satisfiable'}")
        page = matched[start:end + 1][:ROW_CAP]
        return SimpleNamespace(data=[dict(row) for row in page], count=total if self.count else None)


def catalog_tables(product_count, tenant_id=9):
    categories = [
        {"id": "c-root", "slug": "apparel", "parent_id": None, "status": "active", "sort_order": 0, "created_at": "1", "tenant_id": tenant_id, "translations": {}},
        {"id": "c-child", "slug": "kids", "parent_id": "c-root", "status": "active", "sort_order": 1, "created_at": "2", "tenant_id": tenant_id, "translations": {}},
    ]
    tags = [
        {"id": "t-new", "slug": "new", "status": "active", "created_at": "1", "tenant_id": tenant_id, "translations": {}},
        {"id": "t-sale", "slug": "sale", "status": "active", "created_at": "2", "tenant_id": tenant_id, "translations": {}},
    ]
    products, product_tags, product_categories = [], [], []
    for index in range(product_count):
        product_id = f"p-{index:03d}"
        products.append({
            "id": product_id, "tenant_id": tenant_id, "status": "active", "slug": f"item-{index}", "sku": f"S{index}",
            "category_id": None, "brand_id": None, "translations": {"en": {"name": f"Item {index}"}},
            "price": index % 5 * 10, "compare_at_price": None, "currency": "USD", "created_at": f"2026-01-01T00:{index:03d}",
        })
        if index % 2 == 0:
            product_tags.append({"tenant_id": tenant_id, "product_id": product_id, "tag_id": "t-new"})
        if index % 4 == 0:
            product_tags.append({"tenant_id": tenant_id, "product_id": product_id, "tag_id": "t-sale"})
        if index % 3 == 0:
            product_categories.append({"tenant_id": tenant_id, "product_id": product_id, "category_id": "c-child", "sort_order": 0})
    return {
        "ecommerce_categories": categories,
        "ecommerce_tags": tags,
        "ecommerce_brands": [],
        "ecommerce_products": products,
        "ecommerce_product_tags": product_tags,
        "ecommerce_product_categories": product_categories,
    }


class PublicCatalogPagingTests(unittest.TestCase):
    def setUp(self):
        invalidate_ecommerce_cache(9)
        FakeQuery.log = []
        self.catalog = catalog_tables(23)
        client = SimpleNamespace(table=lambda name: FakeQuery(self.catalog, name))
        for patcher in (
            patch.object(public_site_routes, "service_supabase", client),
            patch.object(public_site_routes, "_attach_public_variant_options"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(invalidate_ecommerce_cache, 9)

    def product_reads(self, columns):
        return [read for name, read in FakeQuery.log if name == "ecommerce_products" and read == columns]

    def test_read_all_rows_reads_past_the_response_row_cap(self):
        for parallel in (False, True):
            rows = public_site_routes._read_all_rows(
                lambda count: FakeQuery(self.catalog, "ecommerce_products").select("id", count=count).order("id"),
                parallel_batches=parallel,
            )
            assert [row["id"] for row in rows] == [f"p-{index:03d}" for index in range(23)]

    def test_catalog_pages_reach_every_product_beyond_the_row_cap(self):
        first = public_site_routes._catalog_payload(tenant_id=9, locale="en", limit=5)
        assert first["pagination"] == {"page": 1, "limit": 5, "total": 23, "pages": 5}
        seen = [
            item["id"]
            for page in range(1, 6)
            for item in public_site_routes._catalog_payload(tenant_id=9, locale="en", page=page, limit=5)["products"]
        ]
        assert seen == [f"p-{index:03d}" for index in reversed(range(23))]

    def test_ordering_breaks_timestamp_and_price_ties_by_product_id(self):
        # Effective public order, ending with the unique product id so paging
        # never repeats or skips a product:
        #   latest     = created_at desc, id asc
        #   price_low  = price asc,  created_at desc, id asc
        #   price_high = price desc, created_at desc, id asc
        for row in self.catalog["ecommerce_products"][:6]:
            row["created_at"] = "2026-01-01T00:000"
        latest = [
            item["id"]
            for page in range(1, 6)
            for item in public_site_routes._catalog_payload(tenant_id=9, locale="en", page=page, limit=5)["products"]
        ]
        assert latest[-6:] == ["p-000", "p-001", "p-002", "p-003", "p-004", "p-005"]
        assert len(set(latest)) == 23
        cheapest = public_site_routes._catalog_payload(tenant_id=9, locale="en", sort="price_low", limit=48)["products"]
        assert [item["id"] for item in cheapest[:5]] == ["p-020", "p-015", "p-010", "p-000", "p-005"]
        dearest = public_site_routes._catalog_payload(tenant_id=9, locale="en", sort="price_high", limit=48)["products"]
        assert [item["id"] for item in dearest[:3]] == ["p-019", "p-014", "p-009"]

    def test_tag_and_category_filters_count_the_whole_catalog(self):
        tagged = public_site_routes._catalog_payload(tenant_id=9, locale="en", tag="new", limit=48)
        assert tagged["pagination"]["total"] == 12
        by_parent_category = public_site_routes._catalog_payload(tenant_id=9, locale="en", category="apparel", limit=48)
        assert by_parent_category["pagination"]["total"] == 8
        assert {item["category_ids"][0] for item in by_parent_category["products"]} == {"c-child"}

    def test_filtered_products_still_report_all_of_their_links(self):
        on_sale = public_site_routes._catalog_payload(tenant_id=9, locale="en", tag="sale", limit=48)["products"]
        assert on_sale and all(sorted(item["tag_ids"]) == ["t-new", "t-sale"] for item in on_sale)
        kids = public_site_routes._catalog_payload(tenant_id=9, locale="en", category="kids", tag="new", limit=48)["products"]
        assert kids and all(item["category_ids"] == ["c-child"] and "t-new" in item["tag_ids"] for item in kids)

    def test_unknown_taxonomy_slug_matches_nothing(self):
        for filters in ({"tag": "missing"}, {"category": "missing"}, {"brand": "missing"}):
            payload = public_site_routes._catalog_payload(tenant_id=9, locale="en", **filters)
            assert payload["products"] == []
            assert payload["pagination"]["total"] == 0
            assert payload["price_bounds"] == {"min": None, "max": None, "currency": ""}

    def test_page_past_the_end_is_empty_with_the_real_total(self):
        payload = public_site_routes._catalog_payload(tenant_id=9, locale="en", page=40, limit=12)
        assert payload["products"] == []
        assert payload["pagination"]["total"] == 23

    def test_price_bounds_ignore_the_price_filter_and_sort_is_stable(self):
        payload = public_site_routes._catalog_payload(
            tenant_id=9, locale="en", sort="price_low", min_price=Decimal("20"), max_price=Decimal("30"), limit=48,
        )
        assert payload["price_bounds"] == {"min": "0", "max": "40", "currency": "USD"}
        prices = [Decimal(item["price"]) for item in payload["products"]]
        assert prices == sorted(prices) and set(prices) == {Decimal("20"), Decimal("30")}

    def test_bounds_reuse_the_first_row_and_unfiltered_bounds_are_cached(self):
        first = public_site_routes._catalog_payload(tenant_id=9, locale="en")
        # cheapest + dearest; the newest product is the latest page's first row
        assert len(self.product_reads("price")) == 2 and self.product_reads("currency") == []
        FakeQuery.log = []
        second = public_site_routes._catalog_payload(tenant_id=9, locale="en", page=2)
        assert self.product_reads("price") == [] and self.product_reads("currency") == []
        assert second["price_bounds"] == first["price_bounds"] == {"min": "0", "max": "40", "currency": "USD"}

    def test_product_detail_finds_a_product_beyond_the_row_cap(self):
        detail = public_site_routes._catalog_product_payload(tenant_id=9, product_slug="item-0", locale="en")
        assert detail["product"]["id"] == "p-000"
        assert sorted(detail["product"]["tag_ids"]) == ["t-new", "t-sale"]
        assert detail["product"]["category_ids"] == ["c-child"]

    def test_tenants_never_read_each_others_catalog(self):
        other = catalog_tables(5, tenant_id=10)
        for table, rows in other.items():
            self.catalog[table].extend({**row, "id": f"{row['id']}-t10"} if "id" in row else row for row in rows)
        payload = public_site_routes._catalog_payload(tenant_id=9, locale="en", limit=48)
        assert payload["pagination"]["total"] == 23
        assert all(not item["id"].endswith("-t10") for item in payload["products"])
        assert {item["id"] for item in payload["categories"]} == {"c-root", "c-child"}

    def test_parallel_reads_never_exceed_the_per_request_fan_out(self):
        active, peak, lock = [0], [0], threading.Lock()

        def read(value):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.02)
            with lock:
                active[0] -= 1
            return value

        results = public_site_routes._run_parallel_reads({index: (lambda index=index: read(index)) for index in range(9)})
        assert results == {index: index for index in range(9)}
        assert peak[0] <= public_site_routes.PUBLIC_CATALOG_FAN_OUT == 4


if __name__ == "__main__":
    unittest.main()
