import csv
import os
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from performance_monitor import PerformanceMonitor


class TagsPerformanceTest(BaseTest):

    ONLINE_STORE = (
        By.XPATH,
        "//button["
        "@title='Online Store' "
        "or contains(normalize-space(.), 'Online Store')"
        "]"
    )

    TAGS_LINK = (
        By.XPATH,
        "//a[contains(@href, '/ecommerce/tags')]"
    )

    ADD_TAG = (
        By.XPATH,
        "//button[contains(normalize-space(.), 'Add tag')]"
    )

    TAG_MODAL = (
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

        cls.performance = PerformanceMonitor(
            cls.driver,
            cls.variables.WAIT_TIME
        )

    def record(
        self,
        name,
        metric_type,
        seconds,
        details=""
    ):
        self.results.append({
            "name": name,
            "type": metric_type,
            "seconds": seconds,
            "details": details
        })

    def ensure_logged_in(self):

        self.driver.get(
            self.variables.DASHBOARD_URL
        )

        time.sleep(1)

        if "/login" in self.driver.current_url:

            self.login_page.login(
                self.variables.LOGIN_EMAIL,
                self.variables.LOGIN_PASSWORD
            )

            self.login_page.wait_for_dashboard()

    def test_01_login_page_load(self):

        metrics = self.performance.load_page(
            self.variables.LOGIN_URL
        )

        self.performance.print_metrics(
            "Login Page",
            metrics
        )

        self.record(
            "Login Page",
            "document_load",
            metrics["selenium_seconds"],
            (
                f"TTFB="
                f"{metrics['server_response_ms']}ms; "
                f"DOM="
                f"{metrics['dom_loaded_ms']}ms; "
                f"Full="
                f"{metrics['full_load_ms']}ms"
            )
        )

    def test_02_login_to_dashboard(self):

        self.login_page.open()

        start = time.perf_counter()

        self.login_page.login(
            self.variables.LOGIN_EMAIL,
            self.variables.LOGIN_PASSWORD
        )

        self.login_page.wait_for_dashboard()

        duration = round(
            time.perf_counter() - start,
            3
        )

        print()
        print("Login -> Dashboard")
        print("--------------------------------")
        print(
            f"User Flow Time: {duration:.3f} sec"
        )

        self.record(
            "Login -> Dashboard",
            "user_flow",
            duration
        )

    def test_03_dashboard_page_load(self):

        self.ensure_logged_in()

        metrics = self.performance.load_page(
            self.variables.DASHBOARD_URL
        )

        self.performance.print_metrics(
            "Dashboard Page",
            metrics
        )

        self.record(
            "Dashboard Page",
            "document_load",
            metrics["selenium_seconds"],
            (
                f"TTFB="
                f"{metrics['server_response_ms']}ms; "
                f"DOM="
                f"{metrics['dom_loaded_ms']}ms; "
                f"Full="
                f"{metrics['full_load_ms']}ms"
            )
        )

    def test_04_tags_document_load(self):

        self.ensure_logged_in()

        metrics = self.performance.load_page(
            self.variables.TAGS_URL
        )

        self.performance.print_metrics(
            "Tags Page Document",
            metrics
        )

        self.record(
            "Tags Page",
            "document_load",
            metrics["selenium_seconds"],
            (
                f"TTFB="
                f"{metrics['server_response_ms']}ms; "
                f"DOM="
                f"{metrics['dom_loaded_ms']}ms; "
                f"Full="
                f"{metrics['full_load_ms']}ms"
            )
        )

    def test_05_tags_ui_ready(self):

        self.ensure_logged_in()

        start = time.perf_counter()

        self.driver.get(
            self.variables.TAGS_URL
        )

        self.wait.until(
            EC.element_to_be_clickable(
                self.ADD_TAG
            )
        )

        duration = round(
            time.perf_counter() - start,
            3
        )

        print()
        print("Tags Page UI Ready")
        print("--------------------------------")
        print(
            f"Document -> Usable UI: "
            f"{duration:.3f} sec"
        )

        self.record(
            "Tags Page UI Ready",
            "ui_ready",
            duration,
            "Measured until Add tag button became clickable"
        )

    def test_06_dashboard_to_tags_flow(self):

        self.ensure_logged_in()

        self.driver.get(
            self.variables.DASHBOARD_URL
        )

        online_store = self.wait.until(
            EC.element_to_be_clickable(
                self.ONLINE_STORE
            )
        )

        print()
        print("Dashboard -> Tags")
        print("--------------------------------")

        start = time.perf_counter()

        try:
            online_store.click()

            tags_link = self.wait.until(
                EC.element_to_be_clickable(
                    self.TAGS_LINK
                )
            )

            tags_link.click()

            self.wait.until(
                EC.url_contains(
                    "/ecommerce/tags"
                )
            )

            self.wait.until(
                EC.element_to_be_clickable(
                    self.ADD_TAG
                )
            )

        except TimeoutException:

            duration = round(
                time.perf_counter() - start,
                3
            )

            print(
                f"Timeout after: "
                f"{duration:.3f} sec"
            )

            print(
                f"Current URL: "
                f"{self.driver.current_url}"
            )

            print(
                "Online Store elements:",
                len(
                    self.driver.find_elements(
                        *self.ONLINE_STORE
                    )
                )
            )

            print(
                "Tags links:",
                len(
                    self.driver.find_elements(
                        *self.TAGS_LINK
                    )
                )
            )

            self.record(
                "Dashboard -> Tags",
                "user_flow_error",
                duration,
                (
                    "Navigation timed out. "
                    f"URL={self.driver.current_url}"
                )
            )

            raise

        duration = round(
            time.perf_counter() - start,
            3
        )

        print(
            f"Navigation + UI Ready: "
            f"{duration:.3f} sec"
        )

        self.record(
            "Dashboard -> Tags",
            "user_flow",
            duration,
            (
                "Online Store click -> "
                "Tags Add button clickable"
            )
        )

    def test_07_add_tag_modal_open(self):

        self.ensure_logged_in()

        self.driver.get(
            self.variables.TAGS_URL
        )

        add_button = self.wait.until(
            EC.element_to_be_clickable(
                self.ADD_TAG
            )
        )

        #
        # Timer starts ONLY after Tags UI
        # is already ready.
        #
        start = time.perf_counter()

        add_button.click()

        self.wait.until(
            EC.visibility_of_element_located(
                self.TAG_MODAL
            )
        )

        duration = round(
            time.perf_counter() - start,
            3
        )

        print()
        print("Add Tag Modal")
        print("--------------------------------")
        print(
            f"Click -> Modal Visible: "
            f"{duration:.3f} sec"
        )

        self.record(
            "Add Tag Modal",
            "interaction",
            duration,
            "Add tag click -> dialog visible"
        )

    @classmethod
    def tearDownClass(cls):

        os.makedirs(
            "reports",
            exist_ok=True
        )

        path = os.path.join(
            "reports",
            "tags_performance.csv"
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
                    "name",
                    "type",
                    "seconds",
                    "details"
                ]
            )

            writer.writeheader()

            writer.writerows(
                cls.results
            )

        print()
        print(
            f"Performance report: {path}"
        )
