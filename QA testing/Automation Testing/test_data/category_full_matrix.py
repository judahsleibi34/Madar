from uuid import uuid4


class CategoryFullMatrix:

    @staticmethod
    def suffix():
        return uuid4().hex[:8]

    @staticmethod
    def arabic_category():
        return (
            "\u0641\u0626\u0629 "
            "\u0627\u062e\u062a\u0628\u0627\u0631"
        )

    @staticmethod
    def arabic_description():
        return (
            "\u0648\u0635\u0641 "
            "\u0627\u062e\u062a\u0628\u0627\u0631 "
            "\u0644\u0644\u0641\u0626\u0629"
        )

    @staticmethod
    def name_matrix():
        suffix = CategoryFullMatrix.suffix()

        cases = []

        english_states = {
            "VALID": None,
            "EMPTY": "",
            "WHITESPACE": "   "
        }

        arabic_states = {
            "VALID": None,
            "EMPTY": "",
            "WHITESPACE": "   "
        }

        counter = 1

        for en_state, en_value in english_states.items():

            for ar_state, ar_value in arabic_states.items():

                english = (
                    f"QA Category {suffix} {counter}"
                    if en_state == "VALID"
                    else en_value
                )

                arabic = (
                    (
                        f"{CategoryFullMatrix.arabic_category()} "
                        f"{suffix} {counter}"
                    )
                    if ar_state == "VALID"
                    else ar_value
                )

                expected = (
                    "ACCEPT"
                    if en_state == "VALID"
                    else "REJECT"
                )

                cases.append({
                    "id": (
                        f"NAME_{counter:02d}_"
                        f"EN_{en_state}__"
                        f"AR_{ar_state}"
                    ),
                    "english_name": english,
                    "arabic_name": arabic,
                    "english_description": "",
                    "arabic_description": "",
                    "slug": (
                        f"qa-category-name-"
                        f"{suffix}-{counter}"
                    ),
                    "status": "Draft",
                    "parent": "Top level",
                    "display_position": 0,
                    "expected": expected
                })

                counter += 1

        return cases

    @staticmethod
    def language_matrix():
        suffix = CategoryFullMatrix.suffix()

        arabic = (
            CategoryFullMatrix.arabic_category()
        )

        return [
            {
                "id": "LANG_VALID_ENGLISH_ARABIC",
                "english_name":
                    f"QA Clothing {suffix}",
                "arabic_name":
                    f"{arabic} {suffix}",
                "english_description":
                    "English category description.",
                "arabic_description":
                    CategoryFullMatrix
                    .arabic_description(),
                "slug":
                    f"qa-cat-lang-valid-{suffix}",
                "status": "Draft",
                "parent": "Top level",
                "display_position": 0,
                "expected": "ACCEPT"
            },
            {
                "id": "LANG_ARABIC_NAME_EMPTY",
                "english_name":
                    f"QA Arabic Empty {suffix}",
                "arabic_name": "",
                "english_description": "",
                "arabic_description": "",
                "slug":
                    f"qa-cat-ar-empty-{suffix}",
                "status": "Draft",
                "parent": "Top level",
                "display_position": 0,
                "expected": "ACCEPT"
            },
            {
                "id": "LANG_ARABIC_NAME_WHITESPACE",
                "english_name":
                    f"QA Arabic Space {suffix}",
                "arabic_name": "   ",
                "english_description": "",
                "arabic_description": "",
                "slug":
                    f"qa-cat-ar-space-{suffix}",
                "status": "Draft",
                "parent": "Top level",
                "display_position": 0,
                "expected": "ACCEPT"
            },
            {
                "id":
                    "LANG_ARABIC_ONLY_IN_ENGLISH_NAME",
                "english_name":
                    f"{arabic} {suffix}",
                "arabic_name":
                    f"{arabic} {suffix}",
                "english_description": "",
                "arabic_description": "",
                "slug":
                    f"qa-cat-ar-in-en-{suffix}",
                "status": "Draft",
                "parent": "Top level",
                "display_position": 0,
                "expected": "REJECT"
            },
            {
                "id":
                    "LANG_ENGLISH_ONLY_IN_ARABIC_NAME",
                "english_name":
                    f"QA Clothing {suffix}",
                "arabic_name":
                    f"English Translation {suffix}",
                "english_description": "",
                "arabic_description": "",
                "slug":
                    f"qa-cat-en-in-ar-{suffix}",
                "status": "Draft",
                "parent": "Top level",
                "display_position": 0,
                "expected": "REJECT"
            },
            {
                "id":
                    "LANG_ARABIC_ONLY_IN_ENGLISH_DESCRIPTION",
                "english_name":
                    f"QA Description {suffix}",
                "arabic_name":
                    f"{arabic} {suffix}",
                "english_description":
                    CategoryFullMatrix
                    .arabic_description(),
                "arabic_description":
                    CategoryFullMatrix
                    .arabic_description(),
                "slug":
                    f"qa-cat-ar-desc-en-{suffix}",
                "status": "Draft",
                "parent": "Top level",
                "display_position": 0,
                "expected": "REJECT"
            },
            {
                "id":
                    "LANG_ENGLISH_ONLY_IN_ARABIC_DESCRIPTION",
                "english_name":
                    f"QA Description AR {suffix}",
                "arabic_name":
                    f"{arabic} {suffix}",
                "english_description":
                    "Correct English description.",
                "arabic_description":
                    "English text in Arabic description.",
                "slug":
                    f"qa-cat-en-desc-ar-{suffix}",
                "status": "Draft",
                "parent": "Top level",
                "display_position": 0,
                "expected": "REJECT"
            },
            {
                "id": "LANG_NUMBERS_ALLOWED",
                "english_name":
                    f"QA Category 2026 {suffix}",
                "arabic_name":
                    f"{arabic} 2026 {suffix}",
                "english_description":
                    "Category 2026 description.",
                "arabic_description":
                    (
                        CategoryFullMatrix
                        .arabic_description()
                        + " 2026"
                    ),
                "slug":
                    f"qa-cat-number-{suffix}",
                "status": "Draft",
                "parent": "Top level",
                "display_position": 0,
                "expected": "ACCEPT"
            }
        ]

    @staticmethod
    def slug_matrix():
        suffix = CategoryFullMatrix.suffix()

        base = {
            "arabic_name":
                CategoryFullMatrix
                .arabic_category(),
            "english_description": "",
            "arabic_description": "",
            "status": "Draft",
            "parent": "Top level",
            "display_position": 0
        }

        return [
            {
                **base,
                "id": "SLUG_EMPTY",
                "english_name":
                    f"QA Empty Slug {suffix}",
                "slug": "",
                "expected": "REJECT"
            },
            {
                **base,
                "id": "SLUG_WHITESPACE",
                "english_name":
                    f"QA Space Slug {suffix}",
                "slug": "   ",
                "expected": "REJECT"
            },
            {
                **base,
                "id": "SLUG_VALID",
                "english_name":
                    f"QA Valid Slug {suffix}",
                "slug":
                    f"qa-valid-category-{suffix}",
                "expected": "ACCEPT"
            },
            {
                **base,
                "id": "SLUG_WITH_SPACES",
                "english_name":
                    f"QA Slug Spaces {suffix}",
                "slug":
                    f"qa category {suffix}",
                "expected": "OBSERVE"
            },
            {
                **base,
                "id": "SLUG_UNDERSCORE",
                "english_name":
                    f"QA Slug Underscore {suffix}",
                "slug":
                    f"qa_category_{suffix}",
                "expected": "OBSERVE"
            },
            {
                **base,
                "id": "SLUG_SPECIAL_CHARACTERS",
                "english_name":
                    f"QA Slug Special {suffix}",
                "slug":
                    f"qa@category!{suffix}",
                "expected": "OBSERVE"
            }
        ]

    @staticmethod
    def display_position_matrix():
        suffix = CategoryFullMatrix.suffix()

        return [
            {
                "id": "POSITION_ZERO",
                "value": 0,
                "expected": "ACCEPT"
            },
            {
                "id": "POSITION_ONE",
                "value": 1,
                "expected": "ACCEPT"
            },
            {
                "id": "POSITION_LARGE",
                "value": 999,
                "expected": "ACCEPT"
            },
            {
                "id": "POSITION_EMPTY",
                "value": None,
                "expected": "REJECT"
            },
            {
                "id": "POSITION_NEGATIVE",
                "value": -1,
                "expected": "REJECT"
            },
            {
                "id": "POSITION_DECIMAL",
                "value": "1.5",
                "expected": "REJECT"
            }
        ]
