from selenium import webdriver
from selenium.common.exceptions import WebDriverException


class DriverLoader:
    _driver = None

    @classmethod
    def create_driver(cls):
        options = webdriver.ChromeOptions()

        options.add_argument("--start-maximized")

        options.add_experimental_option(
            "detach",
            True
        )

        #
        # Disable Chrome password-manager popups
        # and compromised-password warnings.
        #
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.password_manager_leak_detection": False,
            "profile.default_content_setting_values.notifications": 2
        }

        options.add_experimental_option(
            "prefs",
            prefs
        )

        options.add_argument(
            "--disable-features=PasswordLeakDetection"
        )

        cls._driver = webdriver.Chrome(
            options=options
        )

        cls._driver.set_page_load_timeout(
            30
        )

        return cls._driver

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            return cls.create_driver()

        try:
            handles = cls._driver.window_handles

            if not handles:
                return cls.create_driver()

            return cls._driver

        except WebDriverException:
            return cls.create_driver()

    @classmethod
    def recreate_driver(cls):
        cls._driver = None

        return cls.create_driver()
