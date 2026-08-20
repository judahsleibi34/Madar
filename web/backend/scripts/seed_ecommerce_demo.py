"""Idempotently seed a tenant with a translated ecommerce demo catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import service_supabase


def translated(en_name: str, en_description: str, ar_name: str, ar_description: str):
    return {
        "en": {"name": en_name, "description": en_description},
        "ar": {"name": ar_name, "description": ar_description},
    }


TAGS = [
    {
        "slug": "demo-new-arrival",
        "translations": translated("New Arrival", "Recently added to the collection.", "وصل حديثاً", "أضيف حديثاً إلى المجموعة."),
    },
    {
        "slug": "demo-handmade",
        "translations": translated("Handmade", "Made with care by independent makers.", "صناعة يدوية", "مصنوع بعناية على يد حرفيين مستقلين."),
    },
    {
        "slug": "demo-gift-ready",
        "translations": translated("Gift Ready", "A thoughtful choice for gifting.", "جاهز للإهداء", "خيار مميز ومناسب للهدايا."),
    },
    {
        "slug": "demo-sustainable",
        "translations": translated("Sustainable", "Designed with responsible materials.", "مستدام", "مصمم باستخدام مواد مسؤولة."),
    },
    {
        "slug": "demo-sale",
        "translations": translated("Sale", "Special demo pricing.", "تخفيض", "سعر تجريبي خاص."),
    },
]


ROOT_CATEGORIES = [
    {
        "key": "home",
        "slug": "demo-home-living",
        "sort_order": 10,
        "translations": translated("Home & Living", "Objects that make everyday spaces feel considered.", "المنزل والمعيشة", "قطع تضيف لمسة مميزة إلى المساحات اليومية."),
    },
    {
        "key": "accessories",
        "slug": "demo-accessories",
        "sort_order": 20,
        "translations": translated("Accessories", "Wearable details and practical companions.", "الإكسسوارات", "تفاصيل أنيقة وعملية للاستخدام اليومي."),
    },
    {
        "key": "art",
        "slug": "demo-art-collectibles",
        "sort_order": 30,
        "translations": translated("Art & Collectibles", "Small editions and pieces with a story.", "الفن والمقتنيات", "إصدارات محدودة وقطع تحمل قصة."),
    },
    {
        "key": "experiences",
        "slug": "demo-experiences",
        "sort_order": 40,
        "translations": translated("Experiences", "Workshops, services, and digital gifts.", "التجارب", "ورش وخدمات وهدايا رقمية."),
    },
]


CHILD_CATEGORIES = [
    {
        "key": "tableware",
        "parent": "home",
        "slug": "demo-tableware",
        "sort_order": 11,
        "translations": translated("Tableware", "Useful pieces for shared meals.", "أدوات المائدة", "قطع عملية للوجبات المشتركة."),
    },
    {
        "key": "decor",
        "parent": "home",
        "slug": "demo-home-decor",
        "sort_order": 12,
        "translations": translated("Home Decor", "Warm details for shelves, tables, and walls.", "ديكور المنزل", "تفاصيل دافئة للرفوف والطاولات والجدران."),
    },
    {
        "key": "bags",
        "parent": "accessories",
        "slug": "demo-bags",
        "sort_order": 21,
        "translations": translated("Bags", "Everyday carry pieces built to last.", "الحقائب", "حقائب يومية مصممة لتدوم."),
    },
    {
        "key": "jewelry",
        "parent": "accessories",
        "slug": "demo-jewelry",
        "sort_order": 22,
        "translations": translated("Jewelry", "Simple pieces with a handcrafted finish.", "المجوهرات", "قطع بسيطة بلمسة حرفية."),
    },
    {
        "key": "wall_art",
        "parent": "art",
        "slug": "demo-wall-art",
        "sort_order": 31,
        "translations": translated("Wall Art", "Prints and originals for personal spaces.", "فن الجدران", "مطبوعات وأعمال أصلية للمساحات الخاصة."),
    },
]


PRODUCTS = [
    {
        "slug": "demo-hand-thrown-vase",
        "sku": "DEMO-VASE-001",
        "category": "decor",
        "tags": ["demo-new-arrival", "demo-handmade"],
        "translations": translated("Hand-thrown Sand Vase", "A softly textured ceramic vase shaped and glazed by hand. Natural variations make every piece unique.", "مزهرية رملية مصنوعة يدوياً", "مزهرية خزفية بملمس ناعم، شُكّلت وطُليت يدوياً، لذلك تتميز كل قطعة بتفاصيل فريدة."),
        "brand": "Madar Atelier",
        "price": 68,
        "compare_at_price": None,
        "cost_price": 27,
        "inventory_quantity": 8,
        "weight": 1.4,
        "images": ["https://images.unsplash.com/photo-1610701596007-11502861dcfa?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-olive-wood-serving-board",
        "sku": "DEMO-BOARD-002",
        "category": "tableware",
        "tags": ["demo-handmade", "demo-sustainable", "demo-gift-ready"],
        "translations": translated("Olive Wood Serving Board", "A food-safe serving board with a live edge and a warm natural grain.", "لوح تقديم من خشب الزيتون", "لوح تقديم آمن للطعام بحافة طبيعية ونقشة خشبية دافئة."),
        "brand": "Local Grain",
        "price": 42,
        "compare_at_price": 52,
        "cost_price": 18,
        "inventory_quantity": 14,
        "weight": 0.85,
        "images": ["https://images.unsplash.com/photo-1556911220-bff31c812dba?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-ceramic-coffee-set",
        "sku": "DEMO-COFFEE-003",
        "category": "tableware",
        "tags": ["demo-new-arrival", "demo-handmade", "demo-gift-ready"],
        "translations": translated("Ceramic Coffee Set", "Four hand-finished cups with a matching serving pot for slow coffee moments.", "طقم قهوة خزفي", "أربعة فناجين بلمسة يدوية مع إبريق تقديم متناسق للحظات القهوة الهادئة."),
        "brand": "Madar Atelier",
        "price": 86,
        "compare_at_price": None,
        "cost_price": 35,
        "inventory_quantity": 5,
        "weight": 1.8,
        "images": ["https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-woven-storage-basket",
        "sku": "DEMO-BASKET-004",
        "category": "decor",
        "tags": ["demo-sustainable", "demo-handmade"],
        "translations": translated("Woven Storage Basket", "A sturdy natural-fiber basket for blankets, toys, or market-day essentials.", "سلة تخزين منسوجة", "سلة متينة من الألياف الطبيعية للبطانيات أو الألعاب أو احتياجات السوق."),
        "brand": "Field & Fiber",
        "price": 54,
        "compare_at_price": None,
        "cost_price": 22,
        "inventory_quantity": 9,
        "weight": 0.7,
        "images": ["https://images.unsplash.com/photo-1594226801341-41427b4e5c22?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-amber-table-lamp",
        "sku": "DEMO-LAMP-005",
        "category": "decor",
        "tags": ["demo-sale", "demo-new-arrival"],
        "translations": translated("Amber Table Lamp", "A compact ambient lamp that casts a warm pool of light across a desk or bedside table.", "مصباح طاولة كهرماني", "مصباح صغير يمنح ضوءاً دافئاً للمكتب أو الطاولة الجانبية."),
        "brand": "North Light",
        "price": 74,
        "compare_at_price": 95,
        "cost_price": 31,
        "inventory_quantity": 3,
        "weight": 1.1,
        "images": ["https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-everyday-leather-tote",
        "sku": "DEMO-TOTE-006",
        "category": "bags",
        "tags": ["demo-handmade", "demo-gift-ready"],
        "translations": translated("Everyday Leather Tote", "A structured full-grain leather tote with room for a laptop and daily essentials.", "حقيبة جلدية يومية", "حقيبة متينة من الجلد الطبيعي تتسع للحاسوب والاحتياجات اليومية."),
        "brand": "Workshop No. 7",
        "price": 128,
        "compare_at_price": None,
        "cost_price": 58,
        "inventory_quantity": 6,
        "weight": 0.95,
        "images": ["https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-mother-of-pearl-pendant",
        "sku": "DEMO-PENDANT-007",
        "category": "jewelry",
        "tags": ["demo-handmade", "demo-gift-ready", "demo-new-arrival"],
        "translations": translated("Mother-of-Pearl Pendant", "A luminous hand-cut pendant on a fine adjustable chain.", "قلادة من عرق اللؤلؤ", "قلادة لامعة مقطوعة يدوياً مع سلسلة ناعمة قابلة للتعديل."),
        "brand": "Bethlehem Studio",
        "price": 59,
        "compare_at_price": None,
        "cost_price": 21,
        "inventory_quantity": 11,
        "weight": 0.04,
        "weight_unit": "kg",
        "images": ["https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-botanical-wall-print",
        "sku": "DEMO-PRINT-008",
        "category": "wall_art",
        "tags": ["demo-sustainable", "demo-gift-ready"],
        "translations": translated("Botanical Wall Print", "An archival art print on responsibly sourced textured paper. Frame not included.", "مطبوع جداري نباتي", "مطبوع فني على ورق مستدام ذي ملمس مميز. الإطار غير مشمول."),
        "brand": "Paper Garden",
        "price": 36,
        "compare_at_price": 44,
        "cost_price": 9,
        "inventory_quantity": 25,
        "weight": 0.2,
        "images": ["https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-citrus-soy-candle",
        "sku": "DEMO-CANDLE-009",
        "category": "decor",
        "tags": ["demo-sustainable", "demo-gift-ready", "demo-sale"],
        "translations": translated("Citrus & Cedar Soy Candle", "A clean-burning soy candle with bright citrus, cedar, and a quiet spice finish.", "شمعة الصويا بالحمضيات والأرز", "شمعة صويا نظيفة الاحتراق برائحة الحمضيات والأرز ولمسة خفيفة من التوابل."),
        "brand": "Quiet Flame",
        "price": 24,
        "compare_at_price": 30,
        "cost_price": 8,
        "inventory_quantity": 0,
        "weight": 0.42,
        "images": ["https://images.unsplash.com/photo-1603006905003-be475563bc59?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-ceramics-workshop",
        "sku": "DEMO-WORKSHOP-010",
        "category": "experiences",
        "tags": ["demo-new-arrival", "demo-gift-ready"],
        "translations": translated("Beginner Ceramics Workshop", "A two-hour guided studio experience. Materials, firing, and refreshments are included.", "ورشة خزف للمبتدئين", "تجربة استوديو موجهة لمدة ساعتين تشمل المواد والحرق والضيافة."),
        "brand": "Madar Experiences",
        "price": 45,
        "compare_at_price": None,
        "cost_price": 14,
        "inventory_quantity": 12,
        "product_type": "service",
        "track_inventory": True,
        "requires_shipping": False,
        "weight": None,
        "images": ["https://images.unsplash.com/photo-1452860606245-08befc0ff44b?w=1200&auto=format&fit=crop"],
    },
    {
        "slug": "demo-digital-gift-card",
        "sku": "DEMO-GIFT-011",
        "category": "experiences",
        "tags": ["demo-gift-ready"],
        "translations": translated("Digital Gift Card", "A digital gift card delivered by email and redeemable across the demo collection.", "بطاقة هدية رقمية", "بطاقة هدية رقمية تُرسل عبر البريد الإلكتروني ويمكن استخدامها لشراء منتجات المجموعة التجريبية."),
        "brand": "Madar Store",
        "price": 50,
        "compare_at_price": None,
        "cost_price": 0,
        "inventory_quantity": 0,
        "product_type": "digital",
        "track_inventory": False,
        "requires_shipping": False,
        "weight": None,
        "images": [],
    },
    {
        "slug": "demo-limited-studio-scarf",
        "sku": "DEMO-SCARF-012",
        "category": "accessories",
        "tags": ["demo-handmade", "demo-new-arrival"],
        "translations": translated("Limited Studio Scarf", "A lightweight woven scarf prepared as a draft product for dashboard testing.", "وشاح استوديو محدود", "وشاح خفيف منسوج ومحفوظ كمسودة لاختبار لوحة التحكم."),
        "brand": "Field & Fiber",
        "price": 48,
        "compare_at_price": None,
        "cost_price": 17,
        "inventory_quantity": 7,
        "status": "draft",
        "weight": 0.18,
        "images": ["https://images.unsplash.com/photo-1520903920243-00d872a2d1c9?w=1200&auto=format&fit=crop"],
    },
]


def rows(result) -> list[dict[str, Any]]:
    return getattr(result, "data", None) or []


def resolve_target(email: str) -> tuple[int, int]:
    users = rows(
        service_supabase.table("users")
        .select("id")
        .eq("email", email.strip().lower())
        .limit(1)
        .execute()
    )
    if len(users) != 1:
        raise RuntimeError("Expected exactly one user for the supplied email")
    memberships = rows(
        service_supabase.table("tenant_memberships")
        .select("tenant_id,status")
        .eq("user_id", users[0]["id"])
        .eq("status", "active")
        .execute()
    )
    if len(memberships) != 1:
        raise RuntimeError("Expected exactly one active tenant membership")
    return int(memberships[0]["tenant_id"]), int(users[0]["id"])


def upsert(table: str, payload: dict[str, Any], conflict: str) -> dict[str, Any]:
    saved = rows(
        service_supabase.table(table)
        .upsert(payload, on_conflict=conflict)
        .execute()
    )
    if not saved:
        raise RuntimeError(f"Could not seed {table}")
    return saved[0]


def seed(email: str) -> dict[str, int]:
    tenant_id, user_id = resolve_target(email)
    tag_ids: dict[str, str] = {}
    for item in TAGS:
        saved = upsert(
            "ecommerce_tags",
            {
                **item,
                "tenant_id": tenant_id,
                "created_by": user_id,
                "status": "active",
            },
            "tenant_id,slug",
        )
        tag_ids[item["slug"]] = str(saved["id"])

    category_ids: dict[str, str] = {}
    for item in ROOT_CATEGORIES:
        saved = upsert(
            "ecommerce_categories",
            {
                "tenant_id": tenant_id,
                "created_by": user_id,
                "slug": item["slug"],
                "translations": item["translations"],
                "status": "active",
                "sort_order": item["sort_order"],
                "parent_id": None,
            },
            "tenant_id,slug",
        )
        category_ids[item["key"]] = str(saved["id"])
    for item in CHILD_CATEGORIES:
        saved = upsert(
            "ecommerce_categories",
            {
                "tenant_id": tenant_id,
                "created_by": user_id,
                "slug": item["slug"],
                "translations": item["translations"],
                "status": "active",
                "sort_order": item["sort_order"],
                "parent_id": category_ids[item["parent"]],
            },
            "tenant_id,slug",
        )
        category_ids[item["key"]] = str(saved["id"])

    product_count = 0
    link_count = 0
    for item in PRODUCTS:
        category_key = item["category"]
        product_tags = item["tags"]
        payload = {
            "tenant_id": tenant_id,
            "created_by": user_id,
            "category_id": category_ids[category_key],
            "slug": item["slug"],
            "sku": item["sku"],
            "barcode": None,
            "translations": item["translations"],
            "status": item.get("status", "active"),
            "product_type": item.get("product_type", "physical"),
            "brand": item["brand"],
            "price": item["price"],
            "compare_at_price": item["compare_at_price"],
            "cost_price": item["cost_price"],
            "currency": "USD",
            "track_inventory": item.get("track_inventory", True),
            "inventory_quantity": item["inventory_quantity"],
            "low_stock_threshold": 3,
            "allow_backorder": False,
            "images": item["images"],
            "weight": item.get("weight"),
            "weight_unit": item.get("weight_unit", "kg"),
            "requires_shipping": item.get("requires_shipping", True),
            "taxable": True,
            "seo_title": item["translations"]["en"]["name"],
            "seo_description": item["translations"]["en"]["description"][:500],
        }
        saved = upsert(
            "ecommerce_products",
            payload,
            "tenant_id,slug",
        )
        product_id = str(saved["id"])
        product_count += 1
        for tag_slug in product_tags:
            upsert(
                "ecommerce_product_tags",
                {
                    "tenant_id": tenant_id,
                    "product_id": product_id,
                    "tag_id": tag_ids[tag_slug],
                },
                "product_id,tag_id",
            )
            link_count += 1
    return {
        "tags": len(tag_ids),
        "categories": len(category_ids),
        "products": product_count,
        "product_tag_links": link_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Owner/member email used only to resolve one tenant")
    args = parser.parse_args()
    summary = seed(args.email)
    print("Demo ecommerce catalog seeded successfully:", summary)


if __name__ == "__main__":
    main()
