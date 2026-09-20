from base_test import BaseTest


class PrivacyPolicyPageTest(BaseTest):

    def test_privacy_policy_page(self):
        load_time = self.open_page(
            self.variables.PRIVACY_POLICY_URL
        )

        self.check_page(
            "/privacy-policy"
        )

        self.check_load_time(
            load_time
        )

        self.print_performance(
            "Privacy Policy Page",
            load_time
        )