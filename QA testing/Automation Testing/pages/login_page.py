import time

from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class LoginPage:

    def __init__(self, driver, url, wait_time=20, action_wait=1):
        self.driver = driver
        self.url = url
        self.wait = WebDriverWait(driver, wait_time)
        self.action_wait = action_wait

    def open(self):
        self.driver.get(self.url)

        self.wait.until(
            lambda driver: driver.execute_script(
                "return document.readyState"
            ) == "complete"
        )

    def get_form(self):
        return self.wait.until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "form")
            )
        )

    def set_value(self, element, value):
        element.click()
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.BACKSPACE)

        if value is not None:
            element.send_keys(value)

    def fill(self, email, password):
        form = self.get_form()

        email_input = form.find_element(
            By.CSS_SELECTOR,
            "input[type='email']"
        )

        password_input = form.find_element(
            By.CSS_SELECTOR,
            "input[type='password']"
        )

        self.set_value(
            email_input,
            email
        )

        self.set_value(
            password_input,
            password
        )

    def submit(self):
        form = self.get_form()

        button = form.find_element(
            By.CSS_SELECTOR,
            "button[type='submit'], "
            "input[type='submit']"
        )

        if button.is_enabled():
            button.click()

        time.sleep(self.action_wait)

    def login(self, email, password):
        self.fill(
            email,
            password
        )

        self.submit()

    def get_validation_messages(self):
        messages = []

        form = self.get_form()

        inputs = form.find_elements(
            By.CSS_SELECTOR,
            "input"
        )

        for element in inputs:
            message = self.driver.execute_script(
                "return arguments[0].validationMessage;",
                element
            )

            if message:
                message = message.strip()

                if message not in messages:
                    messages.append(message)

        error_elements = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[role='alert'], "
            "[aria-live='assertive'], "
            "[aria-live='polite'], "
            "[class*='error'], "
            "[class*='invalid'], "
            "[class*='destructive'], "
            "[class*='text-red'], "
            "[data-sonner-toast]"
        )

        for element in error_elements:
            try:
                text = element.text.strip()

                if text and text not in messages:
                    messages.append(text)

            except Exception:
                pass

        return messages

    def is_on_login_page(self):
        path = urlparse(
            self.driver.current_url
        ).path.rstrip("/")

        return path == "/login"
