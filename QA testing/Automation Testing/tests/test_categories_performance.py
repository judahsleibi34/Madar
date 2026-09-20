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
from pages.categories_page import CategoriesPage
from performance_monitor import PerformanceMonitor


class CategoriesPerformanceTest(BaseTest):

    RUNS = 5

    ONLINE_STORE = (
        By.XPATH,
        "//button["
        "@title='Online Store' "
        "or contains(normalize-space(.), 'Online Store')"
        "]"
    )

    CATEGORIES_LINK = (
        By.CSS_SELECTOR,
        "a[href='/ecommerce/categories']"
    )

    ADD_CATEGORY = (
        By.XPATH,
        "//button[contains(normalize-space(.), 'Add category')]"
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

        cls.categories_page = CategoriesPage(
            cls.driver,
            cls.variables.DASHBOARD_URL,
            cls.variables.CATEGORIES_URL,
            cls.variables.WAIT_TIME,
            cls.variables.ACTION_WAIT
        )

        cls.performance = PerformanceMonitor(
            cls.driver,
            cls.variables.WAIT_TIME
        )

        cls.login()

    @classmethod
    def login(cls):
        cls.login_page.open()

        cls.login_page.login(
            cls.variables.LOGIN_EMAIL,
            cls.variables.LOGIN_PASSWORD
        )

        cls.login_page.wait_for_dashboard()

    def ensure_logged_in(self):
        self.driver.get(
            self.variables.DASHBOARD_URL
        )

        time.sleep(0.5)

        if "/login" in self.driver.current_url:
            self.login()

    def record(
        self,
        test_name,
        run_number,
        seconds,
        metric_type,
        details=""
    ):
        self.results.append({
            "test": test_name,
            "run": run_number,
            "seconds": seconds,
            "type": metric_type,
            "details": details
        })

    def print_summary(
        self,
        title,
        values
    ):
        average = statistics.mean(values)
        median = statistics.median(values)

        ordered = sorted(values)

        p95_index = max(
            0,
            int(
                0.95 * len(ordered)
            ) - 1
        )

        p95 = ordered[p95_index]

        print()
        print("=" * 60)
        print(title)
        print("=" * 60)
        print(
            f"Runs:    {len(values)}"
        )
        print(
            f"Average: {average:.3f} sec"
        )
        print(
            f"Median:  {median:.3f} sec"
        )
        print(
            f"Min:     {min(values):.3f} sec"
        )
        print(
            f"Max:     {max(values):.3f} sec"
        )
        print(
            f"P95:     {p95:.3f} sec"
        )

    def test_01_categories_document_load(self):

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            self.ensure_logged_in()

            metrics = (
                self.performance.load_page(
                    self.variables.CATEGORIES_URL
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
                f"Categories document "
                f"run {run}"
            )
            print(
                "-----------------------------"
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
                "Categories Document Load",
                run,
                seconds,
                "document_load",
                (
                    f"TTFB="
                    f"{metrics['server_response_ms']}ms; "
                    f"DOM="
                    f"{metrics['dom_loaded_ms']}ms; "
                    f"Full="
                    f"{metrics['full_load_ms']}ms"
                )
            )

        self.print_summary(
            "CATEGORIES DOCUMENT LOAD",
            values
        )

    def test_02_categories_ui_ready(self):

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            self.ensure_logged_in()

            start = time.perf_counter()

            self.driver.get(
                self.variables.CATEGORIES_URL
            )

            self.wait.until(
                EC.element_to_be_clickable(
                    self.ADD_CATEGORY
                )
            )

            duration = round(
                time.perf_counter() - start,
                3
            )

            values.append(
                duration
            )

            print()
            print(
                f"Categories UI ready "
                f"run {run}: "
                f"{duration:.3f} sec"
            )

            self.record(
                "Categories UI Ready",
                run,
                duration,
                "ui_ready",
                (
                    "Navigation start -> "
                    "Add category clickable"
                )
            )

        self.print_summary(
            "CATEGORIES UI READY",
            values
        )

    def test_03_dashboard_to_categories(self):

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            self.ensure_logged_in()

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

            categories = self.wait.until(
                EC.element_to_be_clickable(
                    self.CATEGORIES_LINK
                )
            )

            categories.click()

            self.wait.until(
                EC.url_contains(
                    "/ecommerce/categories"
                )
            )

            self.wait.until(
                EC.element_to_be_clickable(
                    self.ADD_CATEGORY
                )
            )

            duration = round(
                time.perf_counter() - start,
                3
            )

            values.append(
                duration
            )

            print()
            print(
                f"Dashboard -> Categories "
                f"run {run}: "
                f"{duration:.3f} sec"
            )

            self.record(
                "Dashboard -> Categories",
                run,
                duration,
                "user_flow",
                (
                    "Online Store click -> "
                    "Categories usable"
                )
            )

        self.print_summary(
            "DASHBOARD -> CATEGORIES",
            values
        )

    def test_04_add_category_modal(self):

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            self.categories_page.open_direct()

            button = self.wait.until(
                EC.element_to_be_clickable(
                    self.ADD_CATEGORY
                )
            )

            start = time.perf_counter()

            button.click()

            self.wait.until(
                EC.visibility_of_element_located(
                    self.MODAL
                )
            )

            duration = round(
                time.perf_counter() - start,
                3
            )

            values.append(
                duration
            )

            print()
            print(
                f"Add Category modal "
                f"run {run}: "
                f"{duration:.3f} sec"
            )

            self.record(
                "Add Category Modal",
                run,
                duration,
                "interaction",
                (
                    "Add category click -> "
                    "modal visible"
                )
            )

            self.categories_page.cancel()

        self.print_summary(
            "ADD CATEGORY MODAL",
            values
        )

    def test_05_save_category_response(self):

        values = []

        for run in range(
            1,
            4
        ):
            suffix = uuid4().hex[:8]

            english_name = (
                f"QA Perf Category "
                f"{suffix}"
            )

            slug = (
                f"qa-perf-category-"
                f"{suffix}"
            )

            self.categories_page.open_direct()

            self.categories_page\
                .open_add_category_modal()

            self.categories_page.fill_category(
                english_name=english_name,
                arabic_name=(
                    "\u0641\u0626\u0629 "
                    "\u0627\u062e\u062a\u0628\u0627\u0631"
                ),
                english_description=(
                    "Performance test category."
                ),
                arabic_description="",
                slug=slug,
                status="Draft",
                parent="Top level",
                display_position=0
            )

            start = time.perf_counter()

            self.categories_page.save()

            self.categories_page\
                .wait_for_modal_to_close(
                    timeout=10
                )

            duration = round(
                time.perf_counter() - start,
                3
            )

            values.append(
                duration
            )

            print()
            print(
                f"Save Category "
                f"run {run}: "
                f"{duration:.3f} sec"
            )

            self.record(
                "Save Category",
                run,
                duration,
                "save_response",
                (
                    "Save click -> "
                    "modal closed"
                )
            )

        self.print_summary(
            "SAVE CATEGORY RESPONSE",
            values
        )

    def test_06_search_category_response(self):

        suffix = uuid4().hex[:8]

        english_name = (
            f"QA Search Perf {suffix}"
        )

        self.categories_page.open_direct()

        self.categories_page\
            .open_add_category_modal()

        self.categories_page.fill_category(
            english_name=english_name,
            arabic_name="",
            english_description="",
            arabic_description="",
            slug=(
                f"qa-search-perf-{suffix}"
            ),
            status="Draft",
            parent="Top level",
            display_position=0
        )

        self.categories_page.save()

        self.categories_page\
            .wait_for_modal_to_close(
                timeout=10
            )

        values = []

        for run in range(
            1,
            self.RUNS + 1
        ):
            self.categories_page.open_direct()

            start = time.perf_counter()

            self.categories_page\
                .search_category(
                    english_name
                )

            found = (
                self.categories_page
                .category_exists(
                    english_name
                )
            )

            duration = round(
                time.perf_counter() - start,
                3
            )

            values.append(
                duration
            )

            print()
            print(
                f"Search Category "
                f"run {run}: "
                f"{duration:.3f} sec "
                f"Found={found}"
            )

            self.record(
                "Search Category",
                run,
                duration,
                "search_response",
                (
                    f"Found={found}"
                )
            )

            self.assertTrue(
                found,
                (
                    "Category was not found "
                    "during search performance test."
                )
            )

        self.print_summary(
            "SEARCH CATEGORY RESPONSE",
            values
        )

    @classmethod
    def tearDownClass(cls):

        os.makedirs(
            "reports",
            exist_ok=True
        )

        path = os.path.join(
            "reports",
            "categories_performance.csv"
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
            f"Categories performance "
            f"report: {path}"
        )
