import time
from uuid import uuid4

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.products_page import ProductsPage


class ProductOptionalMatrixTest(BaseTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.login_page = AdminLoginPage(
            cls.driver,
            cls.variables.LOGIN_URL,
            cls.variables.WAIT_TIME
        )

        cls.products_page = ProductsPage(
            cls.driver,
            cls.variables.DASHBOARD_URL,
            cls.variables.PRODUCTS_URL,
            cls.variables.WAIT_TIME,
            cls.variables.ACTION_WAIT
        )

        cls.driver.get(
            cls.variables.DASHBOARD_URL
        )

        time.sleep(2)

        if "/login" in cls.driver.current_url:

            print()
            print("LOGIN REQUIRED")
            print("--------------------------")

            cls.login_page.open()

            cls.login_page.login(
                cls.variables.LOGIN_EMAIL,
                cls.variables.LOGIN_PASSWORD
            )

            cls.login_page.wait_for_dashboard()

        WebDriverWait(
            cls.driver,
            cls.variables.WAIT_TIME
        ).until(
            lambda driver:
                len(
                    driver.find_elements(
                        By.XPATH,
                        "//button["
                        "@title='Online Store' "
                        "or contains("
                        "normalize-space(.), "
                        "'Online Store'"
                        ")"
                        "]"
                    )
                ) > 0
        )

        print()
        print("AUTHENTICATED")
        print("--------------------------")
        print(
            "URL:",
            cls.driver.current_url
        )

    def submit_case(
        self,
        case_name,
        arabic_name="",
        english_description="",
        arabic_description="",
        brand="",
        discount_price=""
    ):

        suffix = uuid4().hex[:8]

        english_name = (
            f"QA Product {case_name} "
            f"{suffix}"
        )

        slug = (
            f"qa-{case_name.lower()}-"
            f"{suffix}"
        ).replace(
            "_",
            "-"
        )

        sku = (
            f"QA-{case_name[:8]}-"
            f"{suffix}"
        )

        self.products_page\
            .open_through_sidebar()

        self.products_page\
            .open_add_product_modal()

        self.products_page.fill_product(
            english_name=english_name,
            arabic_name=arabic_name,
            english_description=(
                english_description
            ),
            arabic_description=(
                arabic_description
            ),
            slug=slug,
            sku=sku,
            brand=brand,
            status="Draft",
            base_price="19.99",
            discount_price=(
                discount_price
            ),
            store_currency="USD",
            current_stock="10",
            stock_warning="2",
            track_inventory=True,
            allow_sold_out=False
        )

        print()
        print("=" * 65)
        print(
            "OPTIONAL FIELD CASE:",
            case_name
        )
        print("-" * 65)

        self.products_page.save()

        closed = (
            self.products_page
            .wait_for_modal_to_close(
                timeout=8
            )
        )

        if closed:

            observed = "ACCEPTED"
            validation = []

        else:

            observed = "REJECTED"

            validation = (
                self.products_page
                .get_validation_messages()
            )

        print(
            "Observed:",
            observed
        )

        print(
            "Validation:",
            validation
        )

        print(
            "Arabic Name:",
            repr(arabic_name)
        )

        print(
            "English Description:",
            repr(
                english_description
            )
        )

        print(
            "Arabic Description:",
            repr(
                arabic_description
            )
        )

        print(
            "Brand:",
            repr(brand)
        )

        print(
            "Discount:",
            repr(
                discount_price
            )
        )

        if not closed:
            try:
                self.products_page.cancel()
            except Exception:
                pass

        return {
            "case":
                case_name,

            "accepted":
                closed,

            "validation":
                validation
        }

    def test_optional_fields_matrix(self):

        arabic_name = (
            "\u0645\u0646\u062a\u062c "
            "\u0627\u062e\u062a\u0628\u0627\u0631"
        )

        arabic_description = (
            "\u0648\u0635\u0641 "
            "\u0645\u0646\u062a\u062c "
            "\u0627\u062e\u062a\u0628\u0627\u0631"
        )

        cases = [
            {
                "case_name":
                    "BASELINE"
            },
            {
                "case_name":
                    "ARABIC_NAME",
                "arabic_name":
                    arabic_name
            },
            {
                "case_name":
                    "EN_DESCRIPTION",
                "english_description":
                    "QA automation product."
            },
            {
                "case_name":
                    "AR_DESCRIPTION",
                "arabic_description":
                    arabic_description
            },
            {
                "case_name":
                    "BRAND",
                "brand":
                    "QA Brand"
            },
            {
                "case_name":
                    "DISCOUNT",
                "discount_price":
                    "14.99"
            },
            {
                "case_name":
                    "ALL_OPTIONAL",
                "arabic_name":
                    arabic_name,
                "english_description":
                    "QA automation product.",
                "arabic_description":
                    arabic_description,
                "brand":
                    "QA Brand",
                "discount_price":
                    "14.99"
            }
        ]

        results = []

        for case in cases:

            with self.subTest(
                case=case["case_name"]
            ):

                result = self.submit_case(
                    **case
                )

                results.append(
                    result
                )

        print()
        print("=" * 65)
        print(
            "OPTIONAL FIELD MATRIX SUMMARY"
        )
        print("=" * 65)

        for result in results:

            print(
                f"{result['case']}: "
                f"{'ACCEPTED' if result['accepted'] else 'REJECTED'} "
                f"{result['validation']}"
            )
