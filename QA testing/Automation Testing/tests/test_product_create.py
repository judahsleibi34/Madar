import time
from uuid import uuid4

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.products_page import ProductsPage


class ProductCreateTest(BaseTest):

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

        #
        # AUTHENTICATE FIRST
        #
        cls.driver.get(
            cls.variables.DASHBOARD_URL
        )

        #
        # Madar can briefly show /dashboard before
        # client-side authentication redirects to /login.
        # Give that redirect time to finish.
        #
        time.sleep(2)

        print()
        print("AUTH CHECK")
        print("--------------------------")
        print(
            "URL after auth redirect check:",
            cls.driver.current_url
        )

        needs_login = (
            "/login" in cls.driver.current_url
        )

        if not needs_login:
            #
            # URL alone is not enough.
            # Confirm authenticated navigation exists.
            #
            try:
                WebDriverWait(
                    cls.driver,
                    3
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

            except Exception:
                needs_login = True

        if needs_login:

            print()
            print("LOGIN REQUIRED")
            print("--------------------------")

            cls.login_page.open()

            cls.login_page.login(
                cls.variables.LOGIN_EMAIL,
                cls.variables.LOGIN_PASSWORD
            )

            #
            # Wait for the authenticated admin shell,
            # not only the dashboard URL.
            #
            WebDriverWait(
                cls.driver,
                cls.variables.WAIT_TIME
            ).until(
                lambda driver:
                    "/login" not in driver.current_url
            )

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
        print("AUTHENTICATED ADMIN SESSION")
        print("--------------------------")
        print(
            "Current URL:",
            cls.driver.current_url
        )


    def test_create_valid_product(self):

        suffix = uuid4().hex[:8]

        english_name = (
            f"QA Product {suffix}"
        )

        arabic_name = (
            "\u0645\u0646\u062a\u062c "
            "\u0627\u062e\u062a\u0628\u0627\u0631 "
            f"{suffix}"
        )

        slug = (
            f"qa-product-{suffix}"
        )

        sku = (
            f"QA-SKU-{suffix}"
        )

        self.products_page.open_through_sidebar()

        self.products_page\
            .open_add_product_modal()

        self.products_page.fill_product(
            english_name=english_name,
            arabic_name=arabic_name,
            english_description=(
                "QA automation product."
            ),
            arabic_description=(
                "\u0648\u0635\u0641 "
                "\u0645\u0646\u062a\u062c "
                "\u0627\u062e\u062a\u0628\u0627\u0631"
            ),
            slug=slug,
            sku=sku,
            brand="QA Brand",
            status="Draft",
            base_price="19.99",
            discount_price="14.99",
            store_currency="USD",
            current_stock="10",
            stock_warning="2",
            track_inventory=True,
            allow_sold_out=False
        )

        print()
        print(
            "CREATING VALID PRODUCT"
        )
        print(
            "--------------------------"
        )

        print(
            "English:",
            english_name
        )

        print(
            "Arabic:",
            arabic_name
        )

        print(
            "Slug:",
            slug
        )

        print(
            "SKU:",
            sku
        )

        self.products_page.save()

        closed = (
            self.products_page
            .wait_for_modal_to_close(
                timeout=12
            )
        )

        if not closed:

            validation = (
                self.products_page
                .get_validation_messages()
            )

            print(
                "Validation:",
                validation
            )

            self.fail(
                "Product modal did not close. "
                f"Validation={validation}"
            )

        self.products_page.open_through_sidebar()

        self.products_page\
            .search_product(
                english_name
            )

        found = (
            self.products_page
            .product_exists(
                english_name
            )
        )

        print()
        print(
            "Product found:",
            found
        )

        self.assertTrue(
            found,
            (
                "Product was saved but "
                "could not be found in "
                "the Products list."
            )
        )
