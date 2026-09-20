class LoginCases:

    @staticmethod
    def all_invalid_cases():
        return [
            {
                "id": "EMPTY_EMAIL_AND_PASSWORD",
                "email": "",
                "password": ""
            },
            {
                "id": "EMPTY_EMAIL",
                "email": "",
                "password": "WrongPassword123!"
            },
            {
                "id": "EMPTY_PASSWORD",
                "email": "qa.invalid@example.com",
                "password": ""
            },
            {
                "id": "EMAIL_MISSING_AT",
                "email": "qaexample.com",
                "password": "WrongPassword123!"
            },
            {
                "id": "EMAIL_MISSING_USERNAME",
                "email": "@example.com",
                "password": "WrongPassword123!"
            },
            {
                "id": "EMAIL_MISSING_DOMAIN",
                "email": "qa@",
                "password": "WrongPassword123!"
            },
            {
                "id": "EMAIL_MULTIPLE_AT",
                "email": "qa@@example.com",
                "password": "WrongPassword123!"
            },
            {
                "id": "EMAIL_CONTAINS_SPACE",
                "email": "qa test@example.com",
                "password": "WrongPassword123!"
            },
            {
                "id": "WRONG_CREDENTIALS",
                "email": "qa.invalid@example.com",
                "password": "WrongPassword123!"
            },
            {
                "id": "VERY_LONG_EMAIL",
                "email": (
                    ("a" * 245)
                    + "@example.com"
                ),
                "password": "WrongPassword123!"
            },
            {
                "id": "VERY_LONG_PASSWORD",
                "email": "qa.invalid@example.com",
                "password": "A" * 1000
            }
        ]
