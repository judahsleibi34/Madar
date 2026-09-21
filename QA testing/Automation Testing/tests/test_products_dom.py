import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.products_page import ProductsPage


class ProductsDomTest(BaseTest):

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


    def test_product_dom_contract(self):

        self.products_page.open_through_sidebar()

        self.products_page\
            .open_add_product_modal()

        self.products_page\
            .debug_fields()

        fields = (
            self.products_page
            .get_fields()
        )

        print()
        print(
            "PRODUCT CONTRACT"
        )
        print(
            "--------------------------"
        )

        print(
            "English Name required:",
            fields["english_name"]
            .get_attribute("required")
        )

        print(
            "English Name maxlength:",
            fields["english_name"]
            .get_attribute("maxlength")
        )

        print(
            "Arabic Name required:",
            fields["arabic_name"]
            .get_attribute("required")
        )

        print(
            "Arabic Name maxlength:",
            fields["arabic_name"]
            .get_attribute("maxlength")
        )

        print(
            "English Description maxlength:",
            fields["english_description"]
            .get_attribute("maxlength")
        )

        print(
            "Arabic Description maxlength:",
            fields["arabic_description"]
            .get_attribute("maxlength")
        )

        print(
            "Slug required:",
            fields["slug"]
            .get_attribute("required")
        )

        print(
            "SKU required:",
            fields["sku"]
            .get_attribute("required")
        )

        print(
            "Brand required:",
            fields["brand"]
            .get_attribute("required")
        )

        print(
            "Base Price required:",
            fields["base_price"]
            .get_attribute("required")
        )

        print(
            "Base Price min:",
            fields["base_price"]
            .get_attribute("min")
        )

        print(
            "Base Price step:",
            fields["base_price"]
            .get_attribute("step")
        )

        print(
            "Discount Price required:",
            fields["discount_price"]
            .get_attribute("required")
        )

        print(
            "Currency required:",
            fields["store_currency"]
            .get_attribute("required")
        )

        print(
            "Current Stock min:",
            fields["current_stock"]
            .get_attribute("min")
        )

        print(
            "Warning Stock min:",
            fields["stock_warning"]
            .get_attribute("min")
        )

        print(
            "Statuses:",
            self.products_page
            .get_statuses()
        )

        self.assertEqual(
            fields["english_name"]
            .get_attribute("maxlength"),
            "200"
        )

        self.assertEqual(
            fields["arabic_name"]
            .get_attribute("maxlength"),
            "200"
        )

        self.assertEqual(
            fields["english_name"]
            .get_attribute("required"),
            "true"
        )

        self.assertIn(
            "Draft",
            self.products_page
            .get_statuses()
        )

        self.products_page.cancel()
