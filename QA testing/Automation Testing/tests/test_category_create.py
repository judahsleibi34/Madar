from uuid import uuid4

from base_test import BaseTest
from pages.admin_login_page import AdminLoginPage
from pages.categories_page import CategoriesPage


class CategoryCreateTest(BaseTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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

    def test_create_valid_category(self):

        suffix = uuid4().hex[:8]

        english_name = (
            f"QA Category {suffix}"
        )

        arabic_name = (
            "\u0641\u0626\u0629 "
            f"\u0627\u062e\u062a\u0628\u0627\u0631 {suffix}"
        )

        slug = (
            f"qa-category-{suffix}"
        )

        self.categories_page.open_direct()

        self.categories_page.open_add_category_modal()

        self.categories_page.fill_category(
            english_name=english_name,
            arabic_name=arabic_name,
            english_description=
                "QA English category description",
            arabic_description=
                "\u0648\u0635\u0641 "
                "\u0641\u0626\u0629 "
                "\u0627\u062e\u062a\u0628\u0627\u0631",
            slug=slug,
            status="Draft",
            parent="Top level",
            display_position=0
        )

        print()
        print("CREATING VALID CATEGORY")
        print("--------------------------")
        print(
            f"English: {english_name}"
        )
        print(
            f"Arabic: {arabic_name}"
        )
        print(
            f"Slug: {slug}"
        )
        print(
            "Status: Draft"
        )
        print(
            "Parent: Top level"
        )
        print(
            "Display Position: 0"
        )

        self.categories_page.save()

        self.categories_page.wait_for_modal_to_close(
            timeout=10
        )

        self.categories_page.search_category(
            english_name
        )

        exists = (
            self.categories_page
            .category_exists(
                english_name
            )
        )

        print()
        print(
            f"Category found: {exists}"
        )

        self.assertTrue(
            exists,
            (
                "Category was submitted "
                "but could not be found: "
                f"{english_name}"
            )
        )
