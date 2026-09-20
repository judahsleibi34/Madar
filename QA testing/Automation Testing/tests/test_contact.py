from base_test import BaseTest


class ContactPageTest(BaseTest):

    def test_contact_page(self):
        load_time = self.open_page(
            self.variables.CONTACT_URL
        )

        self.check_page(
            "/contact"
        )

        self.check_load_time(
            load_time
        )

        self.print_performance(
            "Contact Page",
            load_time
        )