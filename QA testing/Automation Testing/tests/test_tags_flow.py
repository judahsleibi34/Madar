import csv
import os

from uuid import uuid4

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.tags_page import TagsPage
from test_data.tag_cases import TagCases


class TagsFlowTest(BaseTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.results = []

        if (
            cls.variables.LOGIN_EMAIL
            == "PUT_YOUR_EMAIL_HERE"
            or cls.variables.LOGIN_PASSWORD
            == "PUT_YOUR_PASSWORD_HERE"
        ):
            raise AssertionError(
                "Set LOGIN_EMAIL and LOGIN_PASSWORD "
                "inside variables.py first."
            )

        cls.login_page = AdminLoginPage(
            cls.driver,
            cls.variables.LOGIN_URL,
            cls.variables.WAIT_TIME
        )

        cls.tags_page = TagsPage(
            cls.driver,
            cls.variables.DASHBOARD_URL,
            cls.variables.TAGS_URL,
            cls.variables.WAIT_TIME,
            cls.variables.ACTION_WAIT
        )

        cls.login_page.open()

        cls.login_page.login(
            cls.variables.LOGIN_EMAIL,
            cls.variables.LOGIN_PASSWORD
        )

        cls.login_page.wait_for_dashboard()

    def record(
        self,
        case,
        result,
        details=""
    ):
        self.results.append({
            "case": case,
            "result": result,
            "details": details,
            "url": self.driver.current_url
        })

    def test_01_tags_navigation_flow(self):

        self.tags_page.open_through_sidebar()

        passed = (
            "/ecommerce/tags"
            in self.driver.current_url
        )

        print()
        print("TAGS NAVIGATION")
        print("---------------------")
        print(
            f"URL: {self.driver.current_url}"
        )
        print(
            "Result:",
            "PASS"
            if passed
            else "FAIL"
        )

        self.record(
            "TAGS_NAVIGATION",
            "PASS"
            if passed
            else "FAIL",
            self.driver.current_url
        )

        self.assertTrue(
            passed,
            "Tags page was not opened "
            "through Online Store sidebar."
        )

    def test_02_required_fields(self):

        for case in TagCases.REQUIRED_CASES:

            with self.subTest(
                case=case["id"]
            ):

                self.tags_page.open_direct()

                self.tags_page.open_add_tag_modal()

                self.tags_page.fill_tag(
                    english=case["english"],
                    arabic=case["arabic"],
                    slug=case["slug"],
                    status=case["status"]
                )

                self.tags_page.save()

                messages = (
                    self.tags_page
                    .get_validation_messages()
                )

                modal_open = (
                    self.tags_page
                    .modal_is_open()
                )

                passed = (
                    modal_open
                    and len(messages) > 0
                )

                print()
                print(
                    f"Case: {case['id']}"
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

                self.record(
                    case["id"],
                    "PASS"
                    if passed
                    else "FAIL",
                    " | ".join(messages)
                )

                self.assertTrue(
                    modal_open,
                    (
                        "Invalid tag data "
                        "closed the modal: "
                        f"{case['id']}"
                    )
                )

                self.assertGreater(
                    len(messages),
                    0,
                    (
                        "No validation detected: "
                        f"{case['id']}"
                    )
                )

    def test_03_arabic_name_optional(self):

        suffix = uuid4().hex[:8]

        english = (
            f"QA Arabic Optional {suffix}"
        )

        slug = (
            f"qa-arabic-optional-{suffix}"
        )

        self.tags_page.open_direct()

        self.tags_page.open_add_tag_modal()

        self.tags_page.fill_tag(
            english=english,
            arabic="",
            slug=slug,
            status="Draft"
        )

        print()
        print("ARABIC NAME EMPTY")
        print("---------------------")
        print(
            f"English: {english}"
        )
        print(
            "Arabic: EMPTY"
        )
        print(
            f"Slug: {slug}"
        )

        self.tags_page.save()

        try:
            self.tags_page.wait_for_modal_to_close()

            modal_closed = True

        except Exception:
            modal_closed = False

        if modal_closed:

            print(
                "Modal closed: True"
            )

            self.tags_page.search_tag(
                english
            )

            exists = (
                self.tags_page
                .tag_exists(
                    english
                )
            )

            print(
                f"Tag found: {exists}"
            )

            print(
                "Result:",
                "PASS"
                if exists
                else "FAIL"
            )

            self.record(
                "ARABIC_NAME_EMPTY",
                "PASS"
                if exists
                else "FAIL",
                (
                    "Arabic empty accepted. "
                    f"Tag={english}"
                )
            )

            self.assertTrue(
                exists,
                (
                    "Tag modal closed after "
                    "Arabic was left empty, "
                    "but the created tag "
                    "was not found."
                )
            )

        else:

            messages = (
                self.tags_page
                .get_validation_messages()
            )

            print(
                "Modal closed: False"
            )

            print(
                f"Validation: {messages}"
            )

            print(
                "Result: FAIL"
            )

            self.record(
                "ARABIC_NAME_EMPTY",
                "FAIL",
                " | ".join(messages)
            )

            self.fail(
                (
                    "Arabic field appears "
                    "optional in the DOM, "
                    "but the form did not save. "
                    f"Validation: {messages}"
                )
            )

    def test_04_name_max_length(self):

        self.tags_page.open_direct()

        self.tags_page.open_add_tag_modal()

        long_value = (
            "A" * 250
        )

        self.tags_page.fill_tag(
            english=long_value,
            arabic=long_value,
            slug="qa-max-length",
            status="Draft"
        )

        english_value = (
            self.tags_page
            .get_english_value()
        )

        arabic_value = (
            self.tags_page
            .get_arabic_value()
        )

        english_length = len(
            english_value
        )

        arabic_length = len(
            arabic_value
        )

        print()
        print("TAG MAX LENGTH")
        print("---------------------")

        print(
            f"English length: "
            f"{english_length}"
        )

        print(
            f"Arabic length: "
            f"{arabic_length}"
        )

        passed = (
            english_length
            <= TagCases.MAX_LENGTH
            and
            arabic_length
            <= TagCases.MAX_LENGTH
        )

        print(
            "Result:",
            "PASS"
            if passed
            else "FAIL"
        )

        self.record(
            "TAG_NAME_MAX_LENGTH",
            "PASS"
            if passed
            else "FAIL",
            (
                f"English={english_length}, "
                f"Arabic={arabic_length}"
            )
        )

        self.assertLessEqual(
            english_length,
            TagCases.MAX_LENGTH
        )

        self.assertLessEqual(
            arabic_length,
            TagCases.MAX_LENGTH
        )

        self.tags_page.cancel()

    def test_05_create_valid_tag(self):

        data = (
            TagCases.valid_tag()
        )

        self.tags_page.open_direct()

        self.tags_page.open_add_tag_modal()

        self.tags_page.fill_tag(
            english=data["english"],
            arabic=data["arabic"],
            slug=data["slug"],
            status=data["status"]
        )

        print()
        print("CREATE VALID TAG")
        print("---------------------")

        print(
            f"English: "
            f"{data['english']}"
        )

        print(
            f"Arabic: "
            f"{data['arabic']}"
        )

        print(
            f"Slug: "
            f"{data['slug']}"
        )

        print(
            f"Status: "
            f"{data['status']}"
        )

        self.tags_page.save()

        self.tags_page.wait_for_modal_to_close()

        self.tags_page.search_tag(
            data["english"]
        )

        exists = (
            self.tags_page
            .tag_exists(
                data["english"]
            )
        )

        print(
            f"Tag found: {exists}"
        )

        print(
            "Result:",
            "PASS"
            if exists
            else "FAIL"
        )

        self.record(
            "CREATE_VALID_TAG",
            "PASS"
            if exists
            else "FAIL",
            data["english"]
        )

        self.assertTrue(
            exists,
            (
                "Created tag was not "
                "found after saving: "
                f"{data['english']}"
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
            "tags_flow_results.csv"
        )

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "case",
                    "result",
                    "details",
                    "url"
                ]
            )

            writer.writeheader()

            writer.writerows(
                cls.results
            )

        print()
        print(
            f"Tags report: {path}"
        )
