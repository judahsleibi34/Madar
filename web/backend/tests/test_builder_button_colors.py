import copy
import unittest

from fastapi import HTTPException

from routes import builder_routes


def button_schema(**button_updates):
    button = {
        "id": "button-1",
        "type": "button",
        "content": "Continue",
        "styles": {
            "color": "var(--theme-text-inverse)",
            "backgroundColor": "var(--theme-primary)",
        },
        "action": {"type": "none"},
    }
    button.update(button_updates)
    return {
        "schema_version": 1,
        "pages": [{
            "id": "home",
            "name": "Home",
            "slug": "/",
            "sections": [{
                "id": "section-1",
                "rows": [{"id": "row-1", "columns": [{"id": "column-1", "elements": [button]}]}],
                "freeElements": [],
            }],
        }],
        "forms": [],
    }


class BuilderButtonColorValidationTests(unittest.TestCase):
    def test_draft_and_publish_preserve_and_normalize_explicit_colors(self):
        schema = button_schema(
            backgroundColor="#1a2b3c",
            textColor="#FFFFFF",
            hoverBackgroundColor="#334455",
            hoverTextColor="#abcdef",
            borderColor="#000000",
        )
        draft = builder_routes.assert_json_object(copy.deepcopy(schema))
        published, _ = builder_routes.validate_publish_schema(copy.deepcopy(draft))
        for candidate in (draft, published):
            button = candidate["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"][0]
            self.assertEqual(button["backgroundColor"], "#1A2B3C")
            self.assertEqual(button["textColor"], "#FFFFFF")
            self.assertEqual(button["hoverBackgroundColor"], "#334455")
            self.assertEqual(button["hoverTextColor"], "#ABCDEF")
            self.assertEqual(button["borderColor"], "#000000")

    def test_empty_colors_are_cleared_without_rewriting_legacy_defaults(self):
        draft = builder_routes.assert_json_object(button_schema(backgroundColor="  "))
        button = draft["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"][0]
        self.assertNotIn("backgroundColor", {key: value for key, value in button.items() if key != "styles"})
        self.assertEqual(button["styles"]["backgroundColor"], "var(--theme-primary)")

    def test_rejects_malformed_and_css_injection_values(self):
        invalid_values = (
            "#123",
            "red",
            "#123456; color: red",
            "url(https://example.com/x)",
            "expression(alert(1))",
            "javascript:alert(1)",
            "<script>alert(1)</script>",
            "var(--theme-primary)",
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(HTTPException) as raised:
                builder_routes.assert_json_object(button_schema(backgroundColor=value))
            self.assertEqual(raised.exception.status_code, 400)

    def test_rejects_arbitrary_or_nested_color_style_objects(self):
        for update in (
            {"style": {"backgroundColor": "#112233"}},
            {"buttonColors": {"backgroundColor": "#112233"}},
            {"styles": {"hoverBackgroundColor": "#112233"}},
        ):
            with self.subTest(update=update), self.assertRaises(HTTPException) as raised:
                builder_routes.assert_json_object(button_schema(**update))
            self.assertEqual(raised.exception.status_code, 400)

    def test_existing_button_without_explicit_colors_remains_valid(self):
        original = button_schema()
        validated, _ = builder_routes.validate_publish_schema(copy.deepcopy(original))
        button = validated["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"][0]
        self.assertFalse(any(field in button for field in builder_routes.BUTTON_COLOR_FIELDS))
        self.assertEqual(button["styles"], original["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"][0]["styles"])


if __name__ == "__main__":
    unittest.main()
