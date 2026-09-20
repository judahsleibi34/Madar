import csv
import os
import time

from base_test import BaseTest
from pages.login_page import LoginPage
from test_data.login_cases import LoginCases


class LoginValidationTest(BaseTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.results = []

        cls.login_page = LoginPage(
            cls.driver,
            cls.variables.LOGIN_URL,
            cls.variables.WAIT_TIME,
            cls.variables.ACTION_WAIT
        )

    def test_invalid_login_matrix(self):
        cases = LoginCases.all_invalid_cases()

        print()
        print(
            f"Login negative cases: {len(cases)}"
        )
        print(
            "--------------------------------"
        )

        for case in cases:

            with self.subTest(
                case=case["id"]
            ):

                self.login_page.open()

                start_time = time.perf_counter()

                self.login_page.login(
                    case["email"],
                    case["password"]
                )

                duration = (
                    time.perf_counter()
                    - start_time
                )

                messages = (
                    self.login_page
                    .get_validation_messages()
                )

                still_on_login = (
                    self.login_page
                    .is_on_login_page()
                )

                passed = still_on_login

                self.results.append({
                    "case_id": case["id"],
                    "email": case["email"],
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

                print()
                print(
                    f"Case: {case['id']}"
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
                    still_on_login,
                    (
                        "Invalid credentials "
                        "left /login: "
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
            "login_invalid_results.csv"
        )

        fields = [
            "case_id",
            "email",
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
            f"Login report: {path}"
        )
