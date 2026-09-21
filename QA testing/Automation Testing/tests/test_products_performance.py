import csv
import os
import statistics
import time

from uuid import uuid4

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.products_page import ProductsPage
from performance_monitor import PerformanceMonitor


class ProductsPerformanceTest(BaseTest):

    RUNS = 5

    ONLINE_STORE = (
        By.XPATH,
        "//button["
        "@title='Online Store' "
        "or contains(normalize-space(.), 'Online Store')"
        "]"
    )

    PRODUCTS_LINK = (
        By.CSS_SELECTOR,
        "a[href='/ecommerce/products']"
    )

    ADD_PRODUCT = (
        By.XPATH,
        "//button[contains("
        "normalize-space(.), "
        "'Add product'"
        ")]"
    )

    MODAL = (
        By.CSS_SELECTOR,
        "section[role='dialog']"
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.results = []

        cls.wait = WebDriverWait(
            cls.driver,
            cls.variables.WAIT_TIME
        )

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

        cls.performance = PerformanceMonitor(
            cls.driver,
            cls.variables.WAIT_TIME
        )

        cls.ensure_authenticated()

    @classmethod
    def ensure_authenticated(cls):

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

        cls.wait.until(
            EC.presence_of_element_located(
                cls.ONLINE_STORE
            )
        )

    def record(
        self,
        name,
        run,
        seconds,
        metric_type,
        details=""
    ):
        self.results.append({
            "test": name,
            "run": run,
            "seconds": seconds,
            "type": metric_type,
            "details": details
        })

    def summary(
        self,
        title,
        values
    ):
        ordered = sorted(values)

        p95_index = max(
            0,
            int(
                0.95 * len(ordered)
            ) - 1
        )

        print()
        print("=" * 60)
        print(title)
        print("=" * 60)
        print(
            f"Runs:    {len(values)}"
        )
        print(
            f"Average: "
            f"{statistics.mean(values):.3f} sec"
        )
        print(
            f"Median:  "
            f"{statistics.median(values):.3f} sec"
        )
        print(
            f"Min:     {min(values):.3f} sec"
        )
        print(
            f"Max:     {max(values):.3f} sec"
        )
        print(
            f"P95:     "
            f"{ordered[p95_index]:.3f} sec"
        )

    def test_01_products_document_load(self):

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            metrics = (
                self.performance.load_page(
                    self.variables.PRODUCTS_URL
                )
            )

            seconds = (
                metrics["selenium_seconds"]
            )

            values.append(
                seconds
            )

            print()
            print(
                f"Products document "
                f"run {run}"
            )
            print(
                f"Selenium Load: "
                f"{seconds:.3f} sec"
            )
            print(
                f"Server Response: "
                f"{metrics['server_response_ms']:.2f} ms"
            )
            print(
                f"DOM Loaded: "
                f"{metrics['dom_loaded_ms']:.2f} ms"
            )
            print(
                f"Full Load: "
                f"{metrics['full_load_ms']:.2f} ms"
            )

            self.record(
                "Products Document Load",
                run,
                seconds,
                "document_load"
            )

        self.summary(
            "PRODUCTS DOCUMENT LOAD",
            values
        )

    def test_02_products_ui_ready(self):

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            start = time.perf_counter()

            self.driver.get(
                self.variables.PRODUCTS_URL
            )

            self.wait.until(
                EC.element_to_be_clickable(
                    self.ADD_PRODUCT
                )
            )

            duration = (
                time.perf_counter()
                - start
            )

            values.append(
                duration
            )

            print(
                f"Products UI ready "
                f"run {run}: "
                f"{duration:.3f} sec"
            )

            self.record(
                "Products UI Ready",
                run,
                duration,
                "ui_ready"
            )

        self.summary(
            "PRODUCTS UI READY",
            values
        )

    def test_03_dashboard_to_products(self):

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            self.driver.get(
                self.variables.DASHBOARD_URL
            )

            online_store = self.wait.until(
                EC.element_to_be_clickable(
                    self.ONLINE_STORE
                )
            )

            start = time.perf_counter()

            online_store.click()

            products = self.wait.until(
                EC.element_to_be_clickable(
                    self.PRODUCTS_LINK
                )
            )

            products.click()

            self.wait.until(
                EC.element_to_be_clickable(
                    self.ADD_PRODUCT
                )
            )

            duration = (
                time.perf_counter()
                - start
            )

            values.append(
                duration
            )

            print(
                f"Dashboard -> Products "
                f"run {run}: "
                f"{duration:.3f} sec"
            )

            self.record(
                "Dashboard -> Products",
                run,
                duration,
                "user_flow"
            )

        self.summary(
            "DASHBOARD -> PRODUCTS",
            values
        )

    def test_04_add_product_modal(self):

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            self.products_page.open_direct()

            button = self.wait.until(
                EC.element_to_be_clickable(
                    self.ADD_PRODUCT
                )
            )

            start = time.perf_counter()

            button.click()

            self.wait.until(
                EC.visibility_of_element_located(
                    self.MODAL
                )
            )

            duration = (
                time.perf_counter()
                - start
            )

            values.append(
                duration
            )

            print(
                f"Add Product modal "
                f"run {run}: "
                f"{duration:.3f} sec"
            )

            self.record(
                "Add Product Modal",
                run,
                duration,
                "interaction"
            )

            self.products_page.cancel()

        self.summary(
            "ADD PRODUCT MODAL",
            values
        )

    def test_05_save_product_response(self):

        values = []

        for run in range(
            1,
            4
        ):
            suffix = uuid4().hex[:8]

            name = (
                f"QA Perf Product "
                f"{suffix}"
            )

            self.products_page.open_direct()

            self.products_page\
                .open_add_product_modal()

            self.products_page.fill_product(
                english_name=name,
                arabic_name="",
                english_description="",
                arabic_description="",
                slug=(
                    f"qa-perf-product-"
                    f"{suffix}"
                ),
                sku=(
                    f"QA-PERF-{suffix}"
                ),
                brand="",
                status="Draft",
                base_price="10.00",
                discount_price="",
                store_currency="USD",
                current_stock="10",
                stock_warning="2",
                track_inventory=True,
                allow_sold_out=False
            )

            start = time.perf_counter()

            self.products_page.save()

            closed = (
                self.products_page
                .wait_for_modal_to_close(
                    timeout=12
                )
            )

            duration = (
                time.perf_counter()
                - start
            )

            print(
                f"Save Product run {run}: "
                f"{duration:.3f} sec "
                f"Closed={closed}"
            )

            self.assertTrue(
                closed,
                "Performance product "
                "could not be saved."
            )

            values.append(
                duration
            )

            self.record(
                "Save Product",
                run,
                duration,
                "save_response"
            )

        self.summary(
            "SAVE PRODUCT RESPONSE",
            values
        )

    @classmethod
    def tearDownClass(cls):

        os.makedirs(
            "reports",
            exist_ok=True
        )

        path = (
            "reports/"
            "products_performance.csv"
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
                    "test",
                    "run",
                    "seconds",
                    "type",
                    "details"
                ]
            )

            writer.writeheader()
            writer.writerows(
                cls.results
            )

        print()
        print(
            "Products performance report:",
            path
        )
