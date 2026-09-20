from base_test import BaseTest


class PricingPageTest(BaseTest):

    def test_pricing_page(self):
        load_time = self.open_page(
            self.variables.PRICING_URL
        )

        self.check_page(
            "/pricing"
        )

        self.check_load_time(
            load_time
        )

        self.print_performance(
            "Pricing Page",
            load_time
        )