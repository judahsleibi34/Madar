import json
import time
from uuid import uuid4

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.products_page import ProductsPage


class ProductSaveDiagnosticTest(BaseTest):

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

        print()
        print("AUTHENTICATED")
        print("--------------------------")
        print(
            "URL:",
            cls.driver.current_url
        )

    def dump_failed_network_calls(self):

        requests = {}
        responses = []

        logs = self.driver.get_log(
            "performance"
        )

        for entry in logs:

            try:
                message = json.loads(
                    entry["message"]
                )["message"]

            except Exception:
                continue

            method = message.get(
                "method"
            )

            params = message.get(
                "params",
                {}
            )

            if method == "Network.requestWillBeSent":

                request = params.get(
                    "request",
                    {}
                )

                requests[
                    params.get("requestId")
                ] = {
                    "method":
                        request.get("method"),

                    "url":
                        request.get("url"),

                    "postData":
                        request.get("postData")
                }

            elif method == "Network.responseReceived":

                response = params.get(
                    "response",
                    {}
                )

                responses.append({
                    "requestId":
                        params.get("requestId"),

                    "status":
                        response.get("status"),

                    "url":
                        response.get("url")
                })

        print()
        print("=" * 70)
        print("FAILED NETWORK RESPONSES")
        print("=" * 70)

        found_failure = False

        for response in responses:

            status = response.get(
                "status"
            )

            if status is None:
                continue

            if status < 400:
                continue

            found_failure = True

            request_id = response[
                "requestId"
            ]

            request = requests.get(
                request_id,
                {}
            )

            print()
            print(
                "Status:",
                status
            )

            print(
                "Method:",
                request.get("method")
            )

            print(
                "URL:",
                response.get("url")
            )

            post_data = request.get(
                "postData"
            )

            if post_data:
                print()
                print(
                    "Request body:"
                )
                print(
                    post_data[:5000]
                )

            try:
                body = (
                    self.driver
                    .execute_cdp_cmd(
                        "Network.getResponseBody",
                        {
                            "requestId":
                                request_id
                        }
                    )
                )

                print()
                print(
                    "Response body:"
                )

                print(
                    body.get(
                        "body",
                        ""
                    )[:5000]
                )

            except Exception as error:

                print()
                print(
                    "Could not read response body:",
                    error
                )

        if not found_failure:
            print(
                "No HTTP 4xx/5xx response "
                "was captured."
            )

        print()
        print("=" * 70)

    def test_product_save_diagnostic(self):

        suffix = uuid4().hex[:8]

        english_name = (
            f"QA Diagnostic Product "
            f"{suffix}"
        )

        slug = (
            f"qa-diagnostic-{suffix}"
        )

        sku = (
            f"QA-DIAG-{suffix}"
        )

        self.products_page\
            .open_through_sidebar()

        self.products_page\
            .open_add_product_modal()

        #
        # Enable network domain and clear
        # any previous performance records.
        #
        self.driver.execute_cdp_cmd(
            "Network.enable",
            {}
        )

        self.driver.get_log(
            "performance"
        )

        #
        # Use the simplest possible product
        # before adding optional fields.
        #
        self.products_page.fill_product(
            english_name=english_name,
            arabic_name="",
            english_description="",
            arabic_description="",
            slug=slug,
            sku=sku,
            brand="",
            status="Draft",
            base_price="10.00",
            discount_price="",
            store_currency="USD",
            current_stock="10",
            stock_warning="5",
            track_inventory=True,
            allow_sold_out=False
        )

        print()
        print("TRYING SIMPLE PRODUCT")
        print("--------------------------")
        print(
            "Name:",
            english_name
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

        time.sleep(2)

        if self.products_page.modal_is_open():

            print()
            print(
                "UI Validation:",
                self.products_page
                .get_validation_messages()
            )

            self.dump_failed_network_calls()

        else:

            print()
            print(
                "Product saved successfully."
            )
