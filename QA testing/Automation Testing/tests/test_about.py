from base_test import BaseTest


class AboutPageTest(BaseTest):

    def test_about_page(self):
        load_time = self.open_page(
            self.variables.ABOUT_URL
        )

        self.check_page(
            "/about"
        )

        self.check_load_time(
            load_time
        )

        self.print_performance(
            "About Page",
            load_time
        )