import time

from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class SignupPage:

    def __init__(
        self,
        driver,
        url,
        wait_time=20,
        action_wait=1
    ):
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

    def get_fields(self):
        form = self.get_form()

        text_inputs = [
            element
            for element in form.find_elements(
                By.CSS_SELECTOR,
                "input[type='text'], input:not([type])"
            )
            if element.is_displayed()
        ]

        email_inputs = [
            element
            for element in form.find_elements(
                By.CSS_SELECTOR,
                "input[type='email']"
            )
            if element.is_displayed()
        ]

        password_inputs = [
            element
            for element in form.find_elements(
                By.CSS_SELECTOR,
                "input[type='password']"
            )
            if element.is_displayed()
        ]

        checkboxes = [
            element
            for element in form.find_elements(
                By.CSS_SELECTOR,
                "input[type='checkbox']"
            )
            if element.is_displayed()
        ]

        if len(text_inputs) < 2:
            raise AssertionError(
                "First name and last name inputs were not found"
            )

        if not email_inputs:
            raise AssertionError(
                "Email input was not found"
            )

        if len(password_inputs) < 2:
            raise AssertionError(
                "Password and confirm password inputs were not found"
            )

        return {
            "first_name": text_inputs[0],
            "last_name": text_inputs[1],
            "email": email_inputs[0],
            "password": password_inputs[0],
            "confirm_password": password_inputs[1],
            "terms": checkboxes[0] if checkboxes else None
        }

    def set_value(self, element, value):
        element.click()
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.BACKSPACE)

        if value is not None:
            element.send_keys(value)

    def fill(self, data):
        fields = self.get_fields()

        self.set_value(
            fields["first_name"],
            data["first_name"]
        )

        self.set_value(
            fields["last_name"],
            data["last_name"]
        )

        self.set_value(
            fields["email"],
            data["email"]
        )

        self.set_value(
            fields["password"],
            data["password"]
        )

        self.set_value(
            fields["confirm_password"],
            data["confirm_password"]
        )

        checkbox = fields["terms"]

        if checkbox is not None:
            desired_state = data["terms"]

            if checkbox.is_selected() != desired_state:
                try:
                    checkbox.click()
                except Exception:
                    self.driver.execute_script(
                        "arguments[0].click();",
                        checkbox
                    )

    def submit(self):
        form = self.get_form()

        button = form.find_element(
            By.CSS_SELECTOR,
            "button[type='submit'], input[type='submit']"
        )

        if button.is_enabled():
            button.click()

        time.sleep(self.action_wait)

    def get_current_values(self):
        fields = self.get_fields()

        return {
            "first_name": fields[
                "first_name"
            ].get_attribute("value"),
            "last_name": fields[
                "last_name"
            ].get_attribute("value"),
            "email": fields[
                "email"
            ].get_attribute("value"),
            "password": fields[
                "password"
            ].get_attribute("value"),
            "confirm_password": fields[
                "confirm_password"
            ].get_attribute("value"),
            "terms": (
                fields["terms"].is_selected()
                if fields["terms"] is not None
                else False
            )
        }

    def get_validation_messages(self):
        messages = []

        form = self.get_form()

        inputs = form.find_elements(
            By.CSS_SELECTOR,
            "input"
        )

        for element in inputs:
            try:
                message = self.driver.execute_script(
                    "return arguments[0].validationMessage;",
                    element
                )

                if message:
                    message = message.strip()

                    if message not in messages:
                        messages.append(message)

            except Exception:
                pass

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

    def is_on_signup_page(self):
        path = urlparse(
            self.driver.current_url
        ).path.rstrip("/")

        return path == "/signup"
