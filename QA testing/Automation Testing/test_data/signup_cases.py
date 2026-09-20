from itertools import combinations
from uuid import uuid4


class SignupCases:

    INVALID_GROUPS = {
        "first_name": [
            (
                "FIRST_NAME_EMPTY",
                {
                    "first_name": ""
                }
            ),
            (
                "FIRST_NAME_SPACES_ONLY",
                {
                    "first_name": "     "
                }
            )
        ],

        "last_name": [
            (
                "LAST_NAME_EMPTY",
                {
                    "last_name": ""
                }
            ),
            (
                "LAST_NAME_SPACES_ONLY",
                {
                    "last_name": "     "
                }
            )
        ],

        "email": [
            (
                "EMAIL_EMPTY",
                {
                    "email": ""
                }
            ),
            (
                "EMAIL_MISSING_AT",
                {
                    "email": "qaexample.com"
                }
            ),
            (
                "EMAIL_MISSING_USERNAME",
                {
                    "email": "@example.com"
                }
            ),
            (
                "EMAIL_MISSING_DOMAIN",
                {
                    "email": "qa@"
                }
            ),
            (
                "EMAIL_MULTIPLE_AT",
                {
                    "email": "qa@@example.com"
                }
            ),
            (
                "EMAIL_CONTAINS_SPACE",
                {
                    "email": "qa test@example.com"
                }
            ),
            (
                "EMAIL_DOUBLE_DOT",
                {
                    "email": "qa@example..com"
                }
            ),
            (
                "EMAIL_TOO_LONG",
                {
                    "email": (
                        ("a" * 245)
                        + "@example.com"
                    )
                }
            )
        ],

        "password": [
            (
                "PASSWORD_EMPTY",
                {
                    "password": "",
                    "confirm_password": ""
                }
            ),
            (
                "PASSWORD_ONE_CHARACTER",
                {
                    "password": "A",
                    "confirm_password": "A"
                }
            ),
            (
                "PASSWORD_SEVEN_CHARACTERS",
                {
                    "password": "Ab1!xyz",
                    "confirm_password": "Ab1!xyz"
                }
            )
        ],

        "confirm_password": [
            (
                "CONFIRM_PASSWORD_EMPTY",
                {
                    "confirm_password": ""
                }
            ),
            (
                "PASSWORD_MISMATCH",
                {
                    "confirm_password": "Different123!"
                }
            )
        ],

        "terms": [
            (
                "TERMS_NOT_ACCEPTED",
                {
                    "terms": False
                }
            )
        ]
    }

    @staticmethod
    def valid_data():
        password = "ValidPass123!"

        return {
            "first_name": "QA",
            "last_name": "Tester",
            "email": (
                f"qa-{uuid4().hex[:12]}"
                "@example.com"
            ),
            "password": password,
            "confirm_password": password,
            "terms": True
        }

    @classmethod
    def single_invalid_cases(cls):
        cases = []

        for field, variants in cls.INVALID_GROUPS.items():

            for case_id, overrides in variants:

                cases.append({
                    "id": case_id,
                    "fields": [field],
                    "overrides": overrides
                })

        return cases

    @classmethod
    def pairwise_invalid_cases(cls):
        cases = []

        fields = list(
            cls.INVALID_GROUPS.keys()
        )

        for field_a, field_b in combinations(
            fields,
            2
        ):

            for case_a, overrides_a in cls.INVALID_GROUPS[
                field_a
            ]:

                for case_b, overrides_b in cls.INVALID_GROUPS[
                    field_b
                ]:

                    overrides = {}

                    overrides.update(
                        overrides_a
                    )

                    overrides.update(
                        overrides_b
                    )

                    cases.append({
                        "id": (
                            f"{case_a}__"
                            f"{case_b}"
                        ),
                        "fields": [
                            field_a,
                            field_b
                        ],
                        "overrides": overrides
                    })

        return cases

    @classmethod
    def high_risk_cases(cls):
        return [
            {
                "id": "ALL_FIELDS_EMPTY",
                "fields": [
                    "first_name",
                    "last_name",
                    "email",
                    "password",
                    "confirm_password",
                    "terms"
                ],
                "overrides": {
                    "first_name": "",
                    "last_name": "",
                    "email": "",
                    "password": "",
                    "confirm_password": "",
                    "terms": False
                }
            },

            {
                "id": (
                    "WHITESPACE_NAMES__"
                    "BAD_EMAIL__"
                    "SHORT_PASSWORD__"
                    "NO_TERMS"
                ),
                "fields": [
                    "first_name",
                    "last_name",
                    "email",
                    "password",
                    "terms"
                ],
                "overrides": {
                    "first_name": "     ",
                    "last_name": "     ",
                    "email": "wrong-email",
                    "password": "1",
                    "confirm_password": "1",
                    "terms": False
                }
            },

            {
                "id": (
                    "INVALID_EMAIL__"
                    "PASSWORD_MISMATCH__"
                    "NO_TERMS"
                ),
                "fields": [
                    "email",
                    "confirm_password",
                    "terms"
                ],
                "overrides": {
                    "email": "qa@@example.com",
                    "confirm_password": "WrongPassword!",
                    "terms": False
                }
            }
        ]

    @classmethod
    def all_invalid_cases(cls):
        return (
            cls.single_invalid_cases()
            + cls.pairwise_invalid_cases()
            + cls.high_risk_cases()
        )
