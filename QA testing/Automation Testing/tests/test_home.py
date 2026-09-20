from base_test import BaseTest


class HomePageTest(BaseTest):

    def test_home_page(self):
        load_time = self.open_page(
            self.variables.HOME_URL
        )

        self.check_page(
            "madarportal.com"
        )

        self.check_load_time(
            load_time
        )

        self.print_performance(
            "Home Page",
            load_time
        )