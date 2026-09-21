import time
from uuid import uuid4

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.products_page import ProductsPage


class ProductDiscountMatrixTest(BaseTest):

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

    def run_discount_case(
        self,
        label,
        discount
    ):
        suffix = uuid4().hex[:8]

        name = (
            f"QA Discount {label} {suffix}"
        )

        self.products_page\
            .open_through_sidebar()

        self.products_page\
            .open_add_product_modal()

        self.products_page.fill_product(
            english_name=name,
            arabic_name="",
            english_description="",
            arabic_description="",
            slug=(
                f"qa-discount-{label.lower()}-"
                f"{suffix}"
            ),
            sku=(
                f"QA-DISC-{suffix}"
            ),
            brand="",
            status="Draft",
            base_price="19.99",
            discount_price=discount,
            store_currency="USD",
            current_stock="10",
            stock_warning="2",
            track_inventory=True,
            allow_sold_out=False
        )

        self.products_page.save()

        closed = (
            self.products_page
            .wait_for_modal_to_close(
                timeout=8
            )
        )

        validation = []

        if not closed:
            validation = (
                self.products_page
                .get_validation_messages()
            )

        print()
        print("=" * 60)
        print(
            f"DISCOUNT CASE: {label}"
        )
        print("-" * 60)
        print(
            "Base Price: 19.99"
        )
        print(
            "Discount:",
            repr(discount)
        )
        print(
            "Observed:",
            (
                "ACCEPTED"
                if closed
                else "REJECTED"
            )
        )
        print(
            "Validation:",
            validation
        )

        if not closed:
            try:
                self.products_page.cancel()
            except Exception:
                pass

        return closed

    def test_discount_matrix(self):

        cases = [
            ("EMPTY", ""),
            ("MIN", "0.01"),
            ("ONE", "1.00"),
            ("LOWER", "14.99"),
            ("NEAR_BASE", "19.98"),
            ("EQUAL", "19.99"),
            ("ABOVE", "20.00")
        ]

        for label, discount in cases:

            with self.subTest(
                case=label
            ):
                self.run_discount_case(
                    label,
                    discount
                )
