import csv
import os
import time

from uuid import uuid4

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.tags_page import TagsPage
from test_data.tag_full_matrix import TagFullMatrix


class TagsFullMatrixTest(BaseTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.results = []

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
        suite,
        case_id,
        english,
        arabic,
        slug,
        status,
        expected,
        observed,
        validation,
        save_seconds,
        result
    ):

        self.results.append({
            "suite": suite,
            "case_id": case_id,
            "english": english,
            "arabic": arabic,
            "slug": slug,
            "status": status,
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

        self.tags_page.open_direct()

        self.tags_page.open_add_tag_modal()

        self.tags_page.fill_tag(
            english=case["english"],
            arabic=case["arabic"],
            slug=case["slug"],
            status=case["status"]
        )

        start = time.perf_counter()

        self.tags_page.save()

        save_seconds = round(
            time.perf_counter() - start,
            3
        )

        expected = case["expected"]

        if expected == "ACCEPT":

            try:
                WebDriverWait(
                    self.driver,
                    8
                ).until(
                    EC.invisibility_of_element_located(
                        self.tags_page.MODAL
                    )
                )

                modal_open = False

            except TimeoutException:
                modal_open = (
                    self.tags_page.modal_is_open()
                )

        elif expected == "OBSERVE":

            try:
                WebDriverWait(
                    self.driver,
                    4
                ).until(
                    EC.invisibility_of_element_located(
                        self.tags_page.MODAL
                    )
                )

                modal_open = False

            except TimeoutException:
                modal_open = (
                    self.tags_page.modal_is_open()
                )

        else:
            modal_open = (
                self.tags_page.modal_is_open()
            )

        messages = []

        if modal_open:

            messages = (
                self.tags_page
                .get_validation_messages()
            )

            observed = "REJECTED"

        else:
            observed = "ACCEPTED"

        created = None

        if not modal_open:

            search_value = (
                case["english"].strip()
            )

            if search_value:

                self.tags_page.search_tag(
                    search_value
                )

                created = (
                    self.tags_page
                    .tag_exists(
                        search_value
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
        print("=" * 60)
        print(
            f"{suite}: {case['id']}"
        )
        print("-" * 60)
        print(
            f"English: {repr(case['english'])}"
        )
        print(
            f"Arabic: {repr(case['arabic'])}"
        )
        print(
            f"Slug: {repr(case['slug'])}"
        )
        print(
            f"Status: {case['status']}"
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
            suite=suite,
            case_id=case["id"],
            english=case["english"],
            arabic=case["arabic"],
            slug=case["slug"],
            status=case["status"],
            expected=expected,
            observed=observed,
            validation=" | ".join(messages),
            save_seconds=save_seconds,
            result=result
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

        self.tags_page.open_direct()

        self.tags_page.open_add_tag_modal()

        fields = (
            self.tags_page.get_fields()
        )

        english_required = (
            fields["english"]
            .get_attribute("required")
        )

        arabic_required = (
            fields["arabic"]
            .get_attribute("required")
        )

        slug_required = (
            fields["slug"]
            .get_attribute("required")
        )

        status_required = (
            fields["status"]
            .get_attribute("required")
        )

        english_max = (
            fields["english"]
            .get_attribute("maxlength")
        )

        arabic_max = (
            fields["arabic"]
            .get_attribute("maxlength")
        )

        print()
        print("TAG FORM DOM CONTRACT")
        print("=" * 60)
        print(
            f"English required: "
            f"{english_required}"
        )
        print(
            f"Arabic required: "
            f"{arabic_required}"
        )
        print(
            f"Slug required: "
            f"{slug_required}"
        )
        print(
            f"Status required: "
            f"{status_required}"
        )
        print(
            f"English maxlength: "
            f"{english_max}"
        )
        print(
            f"Arabic maxlength: "
            f"{arabic_max}"
        )

        self.record(
            suite="DOM",
            case_id="DOM_CONTRACT",
            english="",
            arabic="",
            slug="",
            status="",
            expected="OBSERVE",
            observed=(
                f"EN required={english_required}; "
                f"AR required={arabic_required}; "
                f"Slug required={slug_required}; "
                f"Status required={status_required}"
            ),
            validation=(
                f"EN maxlength={english_max}; "
                f"AR maxlength={arabic_max}"
            ),
            save_seconds=0,
            result="OBSERVED"
        )

        self.tags_page.cancel()

    def test_02_all_english_arabic_required_combinations(self):

        cases = (
            TagFullMatrix
            .structural_name_cases()
        )

        print()
        print(
            f"English/Arabic structural "
            f"combinations: {len(cases)}"
        )

        for case in cases:

            with self.subTest(
                case=case["id"]
            ):

                self.submit_case(
                    "NAME_MATRIX",
                    case
                )

    def test_03_language_combinations(self):

        cases = (
            TagFullMatrix
            .language_cases()
        )

        print()
        print(
            f"Language combinations: "
            f"{len(cases)}"
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

        boundary_cases = [
            {
                "id": "ENGLISH_199",
                "english": "A" * 199,
                "arabic": "وسم اختبار",
                "expected_length": 199
            },
            {
                "id": "ENGLISH_200",
                "english": "A" * 200,
                "arabic": "وسم اختبار",
                "expected_length": 200
            },
            {
                "id": "ENGLISH_201",
                "english": "A" * 201,
                "arabic": "وسم اختبار",
                "expected_length": 200
            },
            {
                "id": "ARABIC_199",
                "english": "QA Arabic Length",
                "arabic": "ا" * 199,
                "expected_length": 199
            },
            {
                "id": "ARABIC_200",
                "english": "QA Arabic Length",
                "arabic": "ا" * 200,
                "expected_length": 200
            },
            {
                "id": "ARABIC_201",
                "english": "QA Arabic Length",
                "arabic": "ا" * 201,
                "expected_length": 200
            }
        ]

        for case in boundary_cases:

            with self.subTest(
                case=case["id"]
            ):

                self.tags_page.open_direct()

                self.tags_page.open_add_tag_modal()

                suffix = uuid4().hex[:8]

                self.tags_page.fill_tag(
                    english=case["english"],
                    arabic=case["arabic"],
                    slug=f"qa-length-{suffix}",
                    status="Draft"
                )

                fields = (
                    self.tags_page
                    .get_fields()
                )

                if case["id"].startswith(
                    "ENGLISH"
                ):
                    actual_length = len(
                        fields["english"]
                        .get_attribute("value")
                    )
                else:
                    actual_length = len(
                        fields["arabic"]
                        .get_attribute("value")
                    )

                passed = (
                    actual_length
                    == case["expected_length"]
                )

                print()
                print(
                    f"{case['id']}"
                )
                print(
                    f"Expected length: "
                    f"{case['expected_length']}"
                )
                print(
                    f"Actual length: "
                    f"{actual_length}"
                )
                print(
                    "Result:",
                    "PASS"
                    if passed
                    else "FAIL"
                )

                self.record(
                    suite="LENGTH",
                    case_id=case["id"],
                    english=case["english"],
                    arabic=case["arabic"],
                    slug="",
                    status="Draft",
                    expected=(
                        str(
                            case[
                                "expected_length"
                            ]
                        )
                    ),
                    observed=str(
                        actual_length
                    ),
                    validation="",
                    save_seconds=0,
                    result=(
                        "PASS"
                        if passed
                        else "FAIL"
                    )
                )

                self.assertTrue(
                    passed,
                    (
                        f"{case['id']} "
                        f"expected length "
                        f"{case['expected_length']} "
                        f"but actual was "
                        f"{actual_length}"
                    )
                )

                self.tags_page.cancel()

    def test_05_slug_matrix(self):

        cases = (
            TagFullMatrix
            .slug_cases()
        )

        print()
        print(
            f"Slug scenarios: "
            f"{len(cases)}"
        )

        for case in cases:

            with self.subTest(
                case=case["id"]
            ):

                self.submit_case(
                    "SLUG_MATRIX",
                    case
                )

    def test_06_all_available_statuses(self):

        self.tags_page.open_direct()

        self.tags_page.open_add_tag_modal()

        fields = (
            self.tags_page.get_fields()
        )

        select = Select(
            fields["status"]
        )

        statuses = []

        for option in select.options:

            text = option.text.strip()

            value = option.get_attribute(
                "value"
            )

            if (
                text
                and value
                and "choose" not in text.lower()
            ):
                statuses.append(
                    text
                )

        print()
        print("AVAILABLE STATUSES")
        print("=" * 60)

        for status in statuses:
            print(status)

        self.tags_page.cancel()

        self.assertGreater(
            len(statuses),
            0,
            "No usable Tag statuses found."
        )

        for status in statuses:

            with self.subTest(
                status=status
            ):

                suffix = uuid4().hex[:8]

                case = {
                    "id": (
                        "STATUS_"
                        + status.upper()
                        .replace(" ", "_")
                    ),
                    "english": (
                        f"QA Status "
                        f"{status} {suffix}"
                    ),
                    "arabic": (
                        f"وسم حالة {suffix}"
                    ),
                    "slug": (
                        f"qa-status-"
                        f"{suffix}"
                    ),
                    "status": status,
                    "expected": "ACCEPT"
                }

                self.submit_case(
                    "STATUS_MATRIX",
                    case
                )

    def test_07_full_valid_tag_flow(self):

        suffix = uuid4().hex[:8]

        case = {
            "id": "FULL_VALID_TAG",
            "english": (
                f"QA Full Flow {suffix}"
            ),
            "arabic": (
                f"وسم تدفق كامل {suffix}"
            ),
            "slug": (
                f"qa-full-flow-{suffix}"
            ),
            "status": "Draft",
            "expected": "ACCEPT"
        }

        self.submit_case(
            "END_TO_END",
            case
        )

    @classmethod
    def tearDownClass(cls):

        os.makedirs(
            "reports",
            exist_ok=True
        )

        path = os.path.join(
            "reports",
            "tags_full_matrix.csv"
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
                    "english",
                    "arabic",
                    "slug",
                    "status",
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
        print("=" * 60)
        print(
            f"Full Tags report: {path}"
        )
        print("=" * 60)
