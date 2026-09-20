from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class AdminLoginPage:

    EMAIL = (
        By.CSS_SELECTOR,
        "input[type='email']"
    )

    PASSWORD = (
        By.CSS_SELECTOR,
        "input[type='password']"
    )

    LOGIN_BUTTON = (
        By.CSS_SELECTOR,
        "button[type='submit']"
    )

    def __init__(
        self,
        driver,
        login_url,
        wait_time=20
    ):
        self.driver = driver
        self.login_url = login_url
        self.wait = WebDriverWait(
            driver,
            wait_time
        )

    def open(self):
        self.driver.get(
            self.login_url
        )

        self.wait.until(
            EC.visibility_of_element_located(
                self.EMAIL
            )
        )

    def clear_and_type(
        self,
        element,
        value
    ):
        element.click()
        element.send_keys(
            Keys.CONTROL,
            "a"
        )
        element.send_keys(
            Keys.BACKSPACE
        )
        element.send_keys(
            value
        )

    def login(
        self,
        email,
        password
    ):
        email_input = self.wait.until(
            EC.visibility_of_element_located(
                self.EMAIL
            )
        )

        password_input = self.wait.until(
            EC.visibility_of_element_located(
                self.PASSWORD
            )
        )

        self.clear_and_type(
            email_input,
            email
        )

        self.clear_and_type(
            password_input,
            password
        )

        self.wait.until(
            EC.element_to_be_clickable(
                self.LOGIN_BUTTON
            )
        ).click()

    def wait_for_dashboard(self):
        self.wait.until(
            lambda driver:
            "/dashboard"
            in driver.current_url
        )

        return self.driver.current_url
