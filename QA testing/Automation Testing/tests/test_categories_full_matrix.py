import csv
import os
import time

from uuid import uuid4

from selenium.common.exceptions import TimeoutException

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.categories_page import CategoriesPage
from test_data.category_full_matrix import (
    CategoryFullMatrix
)


class CategoriesFullMatrixTest(BaseTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.results = []

        cls.login_page = AdminLoginPage(
            cls.driver,
            cls.variables.LOGIN_URL,
            cls.variables.WAIT_TIME
        )

        cls.categories_page = CategoriesPage(
            cls.driver,
            cls.variables.DASHBOARD_URL,
            cls.variables.CATEGORIES_URL,
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
        suite,
        case_id,
        expected,
        observed,
        validation,
        save_seconds,
        result
    ):
        self.results.append({
            "suite": suite,
            "case_id": case_id,
            "expected": expected,
            "observed": observed,
            "validation": validation,
            "save_seconds": save_seconds,
            "result": result
        })

    def submit_case(
        self,
        suite,
        case
    ):
        self.categories_page.open_direct()

        self.categories_page.open_add_category_modal()

        self.categories_page.fill_category(
            english_name=
                case["english_name"],
            arabic_name=
                case["arabic_name"],
            english_description=
                case.get(
                    "english_description",
                    ""
                ),
            arabic_description=
                case.get(
                    "arabic_description",
                    ""
                ),
            slug=case["slug"],
            status=case["status"],
            parent=case.get(
                "parent",
                "Top level"
            ),
            display_position=
                case.get(
                    "display_position",
                    0
                )
        )

        start = time.perf_counter()

        self.categories_page.save()

        save_seconds = round(
            time.perf_counter() - start,
            3
        )

        expected = case["expected"]

        if expected == "ACCEPT":
            try:
                self.categories_page\
                    .wait_for_modal_to_close(
                        timeout=8
                    )

                modal_open = False

            except TimeoutException:
                modal_open = (
                    self.categories_page
                    .modal_is_open()
                )

        elif expected == "OBSERVE":
            try:
                self.categories_page\
                    .wait_for_modal_to_close(
                        timeout=4
                    )

                modal_open = False

            except TimeoutException:
                modal_open = (
                    self.categories_page
                    .modal_is_open()
                )

        else:
            modal_open = (
                self.categories_page
                .modal_is_open()
            )

        messages = []

        if modal_open:
            messages = (
                self.categories_page
                .get_validation_messages()
            )

            observed = "REJECTED"

        else:
            observed = "ACCEPTED"

        created = None

        if not modal_open:

            name = (
                case["english_name"]
                .strip()
            )

            if name:
                self.categories_page\
                    .search_category(
                        name
                    )

                created = (
                    self.categories_page
                    .category_exists(
                        name
                    )
                )

        if expected == "ACCEPT":

            passed = (
                observed == "ACCEPTED"
                and created is True
            )

            result = (
                "PASS"
                if passed
                else "FAIL"
            )

        elif expected == "REJECT":

            passed = (
                observed == "REJECTED"
                and len(messages) > 0
            )

            result = (
                "PASS"
                if passed
                else "FAIL"
            )

        else:
            passed = True
            result = "OBSERVED"

        print()
        print("=" * 65)
        print(
            f"{suite}: {case['id']}"
        )
        print("-" * 65)
        print(
            "English:",
            repr(
                case["english_name"]
            )
        )
        print(
            "Arabic:",
            repr(
                case["arabic_name"]
            )
        )
        print(
            "Slug:",
            repr(
                case["slug"]
            )
        )
        print(
            "Display position:",
            repr(
                case.get(
                    "display_position",
                    0
                )
            )
        )
        print(
            f"Expected: {expected}"
        )
        print(
            f"Observed: {observed}"
        )
        print(
            f"Created / Found: {created}"
        )
        print(
            f"Validation: {messages}"
        )
        print(
            f"Save response: "
            f"{save_seconds:.3f} sec"
        )
        print(
            f"Result: {result}"
        )

        self.record(
            suite,
            case["id"],
            expected,
            observed,
            " | ".join(messages),
            save_seconds,
            result
        )

        if expected != "OBSERVE":
            self.assertTrue(
                passed,
                (
                    f"{case['id']} failed. "
                    f"Expected={expected}, "
                    f"Observed={observed}, "
                    f"Created={created}, "
                    f"Validation={messages}"
                )
            )

    def test_01_dom_contract(self):
        self.categories_page.open_direct()

        self.categories_page\
            .open_add_category_modal()

        fields = (
            self.categories_page
            .get_fields()
        )

        print()
        print("CATEGORY DOM CONTRACT")
        print("=" * 65)

        checks = {
            "English required":
                fields["english_name"]
                .get_attribute("required"),
            "Arabic required":
                fields["arabic_name"]
                .get_attribute("required"),
            "Slug required":
                fields["slug"]
                .get_attribute("required"),
            "Status required":
                fields["status"]
                .get_attribute("required"),
            "Display required":
                fields["display_position"]
                .get_attribute("required"),
            "Display min":
                fields["display_position"]
                .get_attribute("min"),
            "Display step":
                fields["display_position"]
                .get_attribute("step"),
            "English max":
                fields["english_name"]
                .get_attribute("maxlength"),
            "Arabic max":
                fields["arabic_name"]
                .get_attribute("maxlength"),
            "English description max":
                fields["english_description"]
                .get_attribute("maxlength"),
            "Arabic description max":
                fields["arabic_description"]
                .get_attribute("maxlength")
        }

        for key, value in checks.items():
            print(
                f"{key}: {value}"
            )

        self.record(
            "DOM",
            "DOM_CONTRACT",
            "OBSERVE",
            str(checks),
            "",
            0,
            "OBSERVED"
        )

        self.categories_page.cancel()

    def test_02_name_required_optional_matrix(self):
        cases = (
            CategoryFullMatrix
            .name_matrix()
        )

        print()
        print(
            "Category name combinations:",
            len(cases)
        )

        for case in cases:
            with self.subTest(
                case=case["id"]
            ):
                self.submit_case(
                    "NAME_MATRIX",
                    case
                )

    def test_03_language_matrix(self):
        cases = (
            CategoryFullMatrix
            .language_matrix()
        )

        print()
        print(
            "Category language combinations:",
            len(cases)
        )

        for case in cases:
            with self.subTest(
                case=case["id"]
            ):
                self.submit_case(
                    "LANGUAGE_MATRIX",
                    case
                )

    def test_04_name_length_boundaries(self):
        cases = [
            (
                "ENGLISH_199",
                "english_name",
                "A" * 199,
                199
            ),
            (
                "ENGLISH_200",
                "english_name",
                "A" * 200,
                200
            ),
            (
                "ENGLISH_201",
                "english_name",
                "A" * 201,
                200
            ),
            (
                "ARABIC_199",
                "arabic_name",
                "\u0627" * 199,
                199
            ),
            (
                "ARABIC_200",
                "arabic_name",
                "\u0627" * 200,
                200
            ),
            (
                "ARABIC_201",
                "arabic_name",
                "\u0627" * 201,
                200
            )
        ]

        for (
            case_id,
            field_name,
            value,
            expected_length
        ) in cases:

            with self.subTest(
                case=case_id
            ):
                self.categories_page\
                    .open_direct()

                self.categories_page\
                    .open_add_category_modal()

                suffix = uuid4().hex[:8]

                english = (
                    value
                    if field_name
                    == "english_name"
                    else f"QA Length {suffix}"
                )

                arabic = (
                    value
                    if field_name
                    == "arabic_name"
                    else "\u0641\u0626\u0629"
                )

                self.categories_page\
                    .fill_category(
                        english_name=english,
                        arabic_name=arabic,
                        slug=(
                            f"qa-length-"
                            f"{suffix}"
                        ),
                        status="Draft",
                        parent="Top level",
                        display_position=0
                    )

                fields = (
                    self.categories_page
                    .get_fields()
                )

                actual = len(
                    fields[field_name]
                    .get_attribute("value")
                )

                passed = (
                    actual
                    == expected_length
                )

                print()
                print(case_id)
                print(
                    f"Expected: "
                    f"{expected_length}"
                )
                print(
                    f"Actual: {actual}"
                )
                print(
                    "Result:",
                    "PASS"
                    if passed
                    else "FAIL"
                )

                self.record(
                    "NAME_LENGTH",
                    case_id,
                    str(expected_length),
                    str(actual),
                    "",
                    0,
                    (
                        "PASS"
                        if passed
                        else "FAIL"
                    )
                )

                self.assertTrue(
                    passed
                )

                self.categories_page.cancel()

    def test_05_description_length_boundaries(self):
        cases = [
            (
                "EN_DESCRIPTION_9999",
                "english_description",
                "A" * 9999,
                9999
            ),
            (
                "EN_DESCRIPTION_10000",
                "english_description",
                "A" * 10000,
                10000
            ),
            (
                "EN_DESCRIPTION_10001",
                "english_description",
                "A" * 10001,
                10000
            ),
            (
                "AR_DESCRIPTION_9999",
                "arabic_description",
                "\u0627" * 9999,
                9999
            ),
            (
                "AR_DESCRIPTION_10000",
                "arabic_description",
                "\u0627" * 10000,
                10000
            ),
            (
                "AR_DESCRIPTION_10001",
                "arabic_description",
                "\u0627" * 10001,
                10000
            )
        ]

        for (
            case_id,
            field_name,
            value,
            expected_length
        ) in cases:

            with self.subTest(
                case=case_id
            ):
                self.categories_page\
                    .open_direct()

                self.categories_page\
                    .open_add_category_modal()

                suffix = uuid4().hex[:8]

                kwargs = {
                    "english_name":
                        f"QA Description {suffix}",
                    "arabic_name":
                        "\u0641\u0626\u0629",
                    "english_description": "",
                    "arabic_description": "",
                    "slug":
                        f"qa-desc-{suffix}",
                    "status": "Draft",
                    "parent": "Top level",
                    "display_position": 0
                }

                kwargs[field_name] = value

                self.categories_page\
                    .fill_category(
                        **kwargs
                    )

                fields = (
                    self.categories_page
                    .get_fields()
                )

                actual = len(
                    fields[field_name]
                    .get_attribute("value")
                )

                passed = (
                    actual
                    == expected_length
                )

                print()
                print(case_id)
                print(
                    f"Expected: "
                    f"{expected_length}"
                )
                print(
                    f"Actual: {actual}"
                )
                print(
                    "Result:",
                    "PASS"
                    if passed
                    else "FAIL"
                )

                self.record(
                    "DESCRIPTION_LENGTH",
                    case_id,
                    str(expected_length),
                    str(actual),
                    "",
                    0,
                    (
                        "PASS"
                        if passed
                        else "FAIL"
                    )
                )

                self.assertTrue(
                    passed
                )

                self.categories_page.cancel()

    def test_06_slug_matrix(self):
        for case in (
            CategoryFullMatrix
            .slug_matrix()
        ):
            with self.subTest(
                case=case["id"]
            ):
                self.submit_case(
                    "SLUG_MATRIX",
                    case
                )

    def test_07_display_position_matrix(self):
        suffix = uuid4().hex[:8]

        for index, item in enumerate(
            CategoryFullMatrix
            .display_position_matrix(),
            start=1
        ):
            with self.subTest(
                case=item["id"]
            ):
                case = {
                    "id": item["id"],
                    "english_name":
                        (
                            f"QA Position "
                            f"{suffix} {index}"
                        ),
                    "arabic_name":
                        "\u0641\u0626\u0629 "
                        "\u0627\u062e\u062a\u0628\u0627\u0631",
                    "english_description": "",
                    "arabic_description": "",
                    "slug":
                        (
                            f"qa-position-"
                            f"{suffix}-{index}"
                        ),
                    "status": "Draft",
                    "parent": "Top level",
                    "display_position":
                        item["value"],
                    "expected":
                        item["expected"]
                }

                self.submit_case(
                    "DISPLAY_POSITION",
                    case
                )

    def test_08_all_statuses(self):
        self.categories_page.open_direct()

        self.categories_page\
            .open_add_category_modal()

        statuses = (
            self.categories_page
            .get_available_statuses()
        )

        print()
        print("AVAILABLE CATEGORY STATUSES")
        print("=" * 65)

        for status in statuses:
            print(status)

        self.categories_page.cancel()

        self.assertGreater(
            len(statuses),
            0
        )

        for status in statuses:

            with self.subTest(
                status=status
            ):
                suffix = uuid4().hex[:8]

                case = {
                    "id":
                        (
                            "STATUS_"
                            + status.upper()
                            .replace(" ", "_")
                        ),
                    "english_name":
                        (
                            f"QA Category "
                            f"{status} {suffix}"
                        ),
                    "arabic_name":
                        "\u0641\u0626\u0629 "
                        "\u0627\u062e\u062a\u0628\u0627\u0631",
                    "english_description": "",
                    "arabic_description": "",
                    "slug":
                        f"qa-status-{suffix}",
                    "status": status,
                    "parent": "Top level",
                    "display_position": 0,
                    "expected": "ACCEPT"
                }

                self.submit_case(
                    "STATUS_MATRIX",
                    case
                )

    def test_09_parent_child_flow(self):
        suffix = uuid4().hex[:8]

        parent_name = (
            f"QA Parent {suffix}"
        )

        parent_case = {
            "id": "CREATE_PARENT",
            "english_name":
                parent_name,
            "arabic_name":
                "\u0641\u0626\u0629 "
                "\u0631\u0626\u064a\u0633\u064a\u0629",
            "english_description":
                "QA parent category.",
            "arabic_description": "",
            "slug":
                f"qa-parent-{suffix}",
            "status": "Draft",
            "parent": "Top level",
            "display_position": 0,
            "expected": "ACCEPT"
        }

        self.submit_case(
            "HIERARCHY",
            parent_case
        )

        child_case = {
            "id": "CREATE_CHILD",
            "english_name":
                f"QA Child {suffix}",
            "arabic_name":
                "\u0641\u0626\u0629 "
                "\u0641\u0631\u0639\u064a\u0629",
            "english_description":
                "QA child category.",
            "arabic_description": "",
            "slug":
                f"qa-child-{suffix}",
            "status": "Draft",
            "parent": parent_name,
            "display_position": 1,
            "expected": "ACCEPT"
        }

        self.submit_case(
            "HIERARCHY",
            child_case
        )

    @classmethod
    def tearDownClass(cls):
        os.makedirs(
            "reports",
            exist_ok=True
        )

        path = os.path.join(
            "reports",
            "categories_full_matrix.csv"
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
                    "suite",
                    "case_id",
                    "expected",
                    "observed",
                    "validation",
                    "save_seconds",
                    "result"
                ]
            )

            writer.writeheader()

            writer.writerows(
                cls.results
            )

        print()
        print("=" * 65)
        print(
            f"Categories report: {path}"
        )
        print("=" * 65)
