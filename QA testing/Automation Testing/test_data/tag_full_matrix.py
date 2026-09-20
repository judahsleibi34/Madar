from uuid import uuid4


class TagFullMatrix:

    @staticmethod
    def suffix():
        return uuid4().hex[:8]

    @staticmethod
    def structural_name_cases():
        """
        Full English/Arabic state matrix.

        English:
        - valid
        - empty
        - whitespace

        Arabic:
        - valid
        - empty
        - whitespace

        3 x 3 = 9 combinations.

        Current known contract:
        - English is required.
        - Arabic appears optional.
        """

        suffix = TagFullMatrix.suffix()

        english_states = {
            "VALID": f"QA English {suffix}",
            "EMPTY": "",
            "WHITESPACE": "   "
        }

        arabic_states = {
            "VALID": f"وسم اختبار {suffix}",
            "EMPTY": "",
            "WHITESPACE": "   "
        }

        cases = []

        counter = 1

        for english_state, english_value in english_states.items():

            for arabic_state, arabic_value in arabic_states.items():

                should_save = (
                    english_state == "VALID"
                )

                cases.append({
                    "id": (
                        f"NAME_{counter:02d}_"
                        f"EN_{english_state}__"
                        f"AR_{arabic_state}"
                    ),
                    "english": english_value,
                    "arabic": arabic_value,
                    "slug": (
                        f"qa-name-matrix-"
                        f"{suffix}-{counter}"
                    ),
                    "status": "Draft",
                    "expected": (
                        "ACCEPT"
                        if should_save
                        else "REJECT"
                    )
                })

                counter += 1

        return cases

    @staticmethod
    def language_cases():
        """
        Business rules:

        - English Name is primary and required.
        - Arabic Name is optional and used for translation.
        - Arabic-only content is invalid in English Name.
        - English-only content is invalid in Arabic Name when provided.
        """

        suffix = TagFullMatrix.suffix()

        arabic_fashion = "\u0623\u0632\u064a\u0627\u0621 \u0627\u062e\u062a\u0628\u0627\u0631"
        arabic_name = "\u0627\u0633\u0645 \u0639\u0631\u0628\u064a"
        arabic_translation = "\u062a\u0631\u062c\u0645\u0629 \u0639\u0631\u0628\u064a\u0629"

        return [
            {
                "id": "LANG_VALID_ENGLISH_AND_ARABIC",
                "english": f"QA Fashion {suffix}",
                "arabic": f"{arabic_fashion} {suffix}",
                "slug": f"qa-lang-valid-{suffix}",
                "status": "Draft",
                "expected": "ACCEPT"
            },
            {
                "id": "LANG_VALID_ENGLISH_ARABIC_EMPTY",
                "english": f"QA Fashion {suffix}",
                "arabic": "",
                "slug": f"qa-lang-ar-empty-{suffix}",
                "status": "Draft",
                "expected": "ACCEPT"
            },
            {
                "id": "LANG_VALID_ENGLISH_ARABIC_WHITESPACE",
                "english": f"QA Fashion {suffix}",
                "arabic": "   ",
                "slug": f"qa-lang-ar-space-{suffix}",
                "status": "Draft",
                "expected": "ACCEPT"
            },
            {
                "id": "LANG_ARABIC_ONLY_IN_ENGLISH_FIELD",
                "english": f"{arabic_fashion} {suffix}",
                "arabic": f"{arabic_translation} {suffix}",
                "slug": f"qa-lang-ar-in-en-{suffix}",
                "status": "Draft",
                "expected": "REJECT"
            },
            {
                "id": "LANG_ENGLISH_ONLY_IN_ARABIC_FIELD",
                "english": f"QA Fashion {suffix}",
                "arabic": f"English Translation {suffix}",
                "slug": f"qa-lang-en-in-ar-{suffix}",
                "status": "Draft",
                "expected": "REJECT"
            },
            {
                "id": "LANG_FIELDS_SWAPPED",
                "english": f"{arabic_name} {suffix}",
                "arabic": f"English Name {suffix}",
                "slug": f"qa-lang-swapped-{suffix}",
                "status": "Draft",
                "expected": "REJECT"
            },
            {
                "id": "LANG_ENGLISH_WITH_NUMBERS",
                "english": f"QA Fashion 2026 {suffix}",
                "arabic": f"{arabic_fashion} {suffix}",
                "slug": f"qa-lang-en-num-{suffix}",
                "status": "Draft",
                "expected": "ACCEPT"
            },
            {
                "id": "LANG_ARABIC_WITH_NUMBERS",
                "english": f"QA Fashion {suffix}",
                "arabic": f"{arabic_fashion} 2026 {suffix}",
                "slug": f"qa-lang-ar-num-{suffix}",
                "status": "Draft",
                "expected": "ACCEPT"
            }
        ]

    @staticmethod
    def slug_cases():

        suffix = TagFullMatrix.suffix()

        return [
            {
                "id": "SLUG_EMPTY",
                "english": f"QA Empty Slug {suffix}",
                "arabic": f"وسم اختبار {suffix}",
                "slug": "",
                "status": "Draft",
                "expected": "REJECT"
            },
            {
                "id": "SLUG_WHITESPACE_ONLY",
                "english": f"QA Space Slug {suffix}",
                "arabic": f"وسم اختبار {suffix}",
                "slug": "   ",
                "status": "Draft",
                "expected": "REJECT"
            },
            {
                "id": "SLUG_VALID_HYPHEN",
                "english": f"QA Valid Slug {suffix}",
                "arabic": f"وسم اختبار {suffix}",
                "slug": f"qa-valid-slug-{suffix}",
                "status": "Draft",
                "expected": "ACCEPT"
            },
            {
                "id": "SLUG_WITH_SPACES",
                "english": f"QA Space Inside Slug {suffix}",
                "arabic": f"وسم اختبار {suffix}",
                "slug": f"qa slug {suffix}",
                "status": "Draft",
                "expected": "OBSERVE"
            },
            {
                "id": "SLUG_ARABIC",
                "english": f"QA Arabic Slug {suffix}",
                "arabic": f"وسم اختبار {suffix}",
                "slug": f"وسم-{suffix}",
                "status": "Draft",
                "expected": "OBSERVE"
            },
            {
                "id": "SLUG_UNDERSCORE",
                "english": f"QA Underscore {suffix}",
                "arabic": f"وسم اختبار {suffix}",
                "slug": f"qa_slug_{suffix}",
                "status": "Draft",
                "expected": "OBSERVE"
            },
            {
                "id": "SLUG_SPECIAL_CHARACTERS",
                "english": f"QA Special Slug {suffix}",
                "arabic": f"وسم اختبار {suffix}",
                "slug": f"qa@tag!{suffix}",
                "status": "Draft",
                "expected": "OBSERVE"
            }
        ]
