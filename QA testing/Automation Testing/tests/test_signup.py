import csv
import os
import time

from selenium.common.exceptions import (
    NoSuchWindowException,
    InvalidSessionIdException,
    WebDriverException
)

from base_test import BaseTest
from pages.signup_page import SignupPage
from test_data.signup_cases import SignupCases


class SignupValidationTest(BaseTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.results = []

    def create_signup_page(self):
        driver = self.get_live_driver()

        return SignupPage(
            driver,
            self.variables.SIGNUP_URL,
            self.variables.WAIT_TIME,
            self.variables.ACTION_WAIT
        )

    def open_signup_page(self):
        try:
            page = self.create_signup_page()
            page.open()
            return page

        except (
            NoSuchWindowException,
            InvalidSessionIdException,
            WebDriverException
        ):
            print()
            print(
                "Browser session lost. "
                "Starting new Chrome..."
            )

            self.recreate_driver()

            page = SignupPage(
                self.driver,
                self.variables.SIGNUP_URL,
                self.variables.WAIT_TIME,
                self.variables.ACTION_WAIT
            )

            page.open()

            return page

    def test_00_valid_baseline_fields(self):
        page = self.open_signup_page()

        data = SignupCases.valid_data()

        page.fill(data)

        values = page.get_current_values()

        print()
        print("Valid baseline")
        print("--------------------------------")
        print(
            f"First name: {values['first_name']}"
        )
        print(
            f"Last name: {values['last_name']}"
        )
        print(
            f"Email: {values['email']}"
        )
        print(
            f"Terms checked: {values['terms']}"
        )

        self.assertEqual(
            values["first_name"],
            data["first_name"]
        )

        self.assertEqual(
            values["last_name"],
            data["last_name"]
        )

        self.assertEqual(
            values["email"],
            data["email"]
        )

        self.assertEqual(
            values["password"],
            data["password"]
        )

        self.assertEqual(
            values["confirm_password"],
            data["confirm_password"]
        )

        self.assertTrue(
            values["terms"]
        )

    def test_invalid_signup_matrix(self):
        cases = SignupCases.all_invalid_cases()

        print()
        print(
            f"Signup negative cases: {len(cases)}"
        )
        print("--------------------------------")

        for number, case in enumerate(
            cases,
            start=1
        ):

            with self.subTest(
                case=case["id"]
            ):

                print()
                print(
                    f"[{number}/{len(cases)}] "
                    f"{case['id']}"
                )

                data = SignupCases.valid_data()

                data.update(
                    case["overrides"]
                )

                signup_page = (
                    self.open_signup_page()
                )

                signup_page.fill(
                    data
                )

                start_time = (
                    time.perf_counter()
                )

                signup_page.submit()

                duration = (
                    time.perf_counter()
                    - start_time
                )

                messages = (
                    signup_page
                    .get_validation_messages()
                )

                still_on_signup = (
                    signup_page
                    .is_on_signup_page()
                )

                passed = (
                    still_on_signup
                    and len(messages) > 0
                )

                self.results.append({
                    "case_id": case["id"],
                    "invalid_fields": ",".join(
                        case["fields"]
                    ),
                    "first_name": data[
                        "first_name"
                    ],
                    "last_name": data[
                        "last_name"
                    ],
                    "email": data["email"],
                    "terms": data["terms"],
                    "url": self.driver.current_url,
                    "validation_messages": " | ".join(
                        messages
                    ),
                    "duration_seconds": round(
                        duration,
                        3
                    ),
                    "result": (
                        "PASS"
                        if passed
                        else "FAIL"
                    )
                })

                print(
                    f"Invalid fields: "
                    f"{case['fields']}"
                )

                print(
                    f"URL: "
                    f"{self.driver.current_url}"
                )

                print(
                    f"Validation: {messages}"
                )

                print(
                    "Result:",
                    "PASS"
                    if passed
                    else "FAIL"
                )

                self.assertTrue(
                    still_on_signup,
                    (
                        "Invalid signup left "
                        "/signup: "
                        f"{case['id']} -> "
                        f"{self.driver.current_url}"
                    )
                )

                self.assertGreater(
                    len(messages),
                    0,
                    (
                        "No validation detected "
                        "for invalid case: "
                        f"{case['id']}"
                    )
                )

    @classmethod
    def tearDownClass(cls):
        os.makedirs(
            "reports",
            exist_ok=True
        )

        path = os.path.join(
            "reports",
            "signup_invalid_results.csv"
        )

        fields = [
            "case_id",
            "invalid_fields",
            "first_name",
            "last_name",
            "email",
            "terms",
            "url",
            "validation_messages",
            "duration_seconds",
            "result"
        ]

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fields
            )

            writer.writeheader()

            writer.writerows(
                cls.results
            )

        print()
        print(
            f"Signup report: {path}"
        )
