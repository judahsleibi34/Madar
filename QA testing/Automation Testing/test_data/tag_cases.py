from uuid import uuid4


class TagCases:

    @staticmethod
    def valid_tag():
        suffix = uuid4().hex[:8]

        return {
            "english": f"QA Test Tag {suffix}",
            "arabic": f"وسم اختبار {suffix}",
            "slug": f"qa-test-tag-{suffix}",
            "status": "Draft"
        }

    REQUIRED_CASES = [
        {
            "id": "ENGLISH_NAME_EMPTY",
            "english": "",
            "arabic": "وسم اختبار",
            "slug": "qa-empty-english",
            "status": "Draft"
        },
        {
            "id": "SLUG_EMPTY",
            "english": "QA Slug Empty",
            "arabic": "وسم اختبار",
            "slug": "",
            "status": "Draft"
        },
        {
            "id": "STATUS_NOT_SELECTED",
            "english": "QA No Status",
            "arabic": "وسم اختبار",
            "slug": "qa-no-status",
            "status": None
        }
    ]

    MAX_LENGTH = 200
