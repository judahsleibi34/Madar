import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


class TagsPage:

    ONLINE_STORE_BUTTON = (
        By.XPATH,
        "//button[@title='Online Store']"
    )

    TAGS_LINK = (
        By.CSS_SELECTOR,
        "a[href='/ecommerce/tags']"
    )

    PAGE_TITLE = (
        By.XPATH,
        "//h1[normalize-space()='Tags']"
    )

    ADD_TAG_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(.), 'Add tag')]"
    )

    MODAL = (
        By.CSS_SELECTOR,
        "section[role='dialog']"
    )

    SEARCH = (
        By.XPATH,
        "//input[contains(@placeholder, 'Search')]"
    )

    def __init__(
        self,
        driver,
        dashboard_url,
        tags_url,
        wait_time=20,
        action_wait=1
    ):
        self.driver = driver
        self.dashboard_url = dashboard_url
        self.tags_url = tags_url
        self.wait = WebDriverWait(
            driver,
            wait_time
        )
        self.action_wait = action_wait

    def open_dashboard(self):
        self.driver.get(
            self.dashboard_url
        )

        self.wait.until(
            lambda driver:
            "/dashboard" in driver.current_url
        )

    def open_through_sidebar(self):
        self.open_dashboard()

        self.wait.until(
            EC.element_to_be_clickable(
                self.ONLINE_STORE_BUTTON
            )
        ).click()

        self.wait.until(
            EC.element_to_be_clickable(
                self.TAGS_LINK
            )
        ).click()

        self.wait.until(
            lambda driver:
            "/ecommerce/tags"
            in driver.current_url
        )

    def open_direct(self):
        self.driver.get(
            self.tags_url
        )

        self.wait.until(
            lambda driver:
            "/ecommerce/tags"
            in driver.current_url
        )

    def open_add_tag_modal(self):
        self.wait.until(
            EC.element_to_be_clickable(
                self.ADD_TAG_BUTTON
            )
        ).click()

        self.wait.until(
            EC.visibility_of_element_located(
                self.MODAL
            )
        )

    def get_modal(self):
        return self.wait.until(
            EC.visibility_of_element_located(
                self.MODAL
            )
        )

    def get_fields(self):
        modal = self.get_modal()

        inputs = [
            element
            for element in modal.find_elements(
                By.CSS_SELECTOR,
                "input"
            )
            if element.is_displayed()
        ]

        selects = [
            element
            for element in modal.find_elements(
                By.CSS_SELECTOR,
                "select"
            )
            if element.is_displayed()
        ]

        print()
        print("TAG MODAL FIELD DEBUG")
        print("---------------------")
        print(
            f"Visible inputs found: {len(inputs)}"
        )
        print(
            f"Visible selects found: {len(selects)}"
        )

        for index, element in enumerate(
            inputs,
            start=1
        ):
            print(
                f"Input {index}: "
                f"name={element.get_attribute('name')} "
                f"type={element.get_attribute('type')} "
                f"placeholder={element.get_attribute('placeholder')} "
                f"maxlength={element.get_attribute('maxlength')}"
            )

        if len(inputs) < 3:
            raise AssertionError(
                f"Expected at least 3 visible inputs "
                f"inside tag modal, found {len(inputs)}"
            )

        if len(selects) < 1:
            raise AssertionError(
                "Status select was not found "
                "inside tag modal"
            )

        return {
            "english": inputs[0],
            "arabic": inputs[1],
            "slug": inputs[2],
            "status": selects[0]
        }

    def clear_and_type(
        self,
        element,
        value
    ):
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            element
        )

        element.click()

        element.send_keys(
            Keys.CONTROL,
            "a"
        )

        element.send_keys(
            Keys.BACKSPACE
        )

        if value is not None and value != "":
            element.send_keys(
                value
            )

    def fill_tag(
        self,
        english="",
        arabic="",
        slug="",
        status=None
    ):
        fields = self.get_fields()

        print()
        print("FILLING TAG")
        print("---------------------")
        print(
            f"English: {repr(english)}"
        )
        print(
            f"Arabic: {repr(arabic)}"
        )
        print(
            f"Slug: {repr(slug)}"
        )
        print(
            f"Status: {repr(status)}"
        )

        self.clear_and_type(
            fields["english"],
            english
        )

        self.clear_and_type(
            fields["arabic"],
            arabic
        )

        self.clear_and_type(
            fields["slug"],
            slug
        )

        if status is not None:
            Select(
                fields["status"]
            ).select_by_visible_text(
                status
            )

        time.sleep(
            self.action_wait
        )

        print()
        print("VALUES AFTER FILL")
        print("---------------------")
        print(
            "English:",
            fields["english"].get_attribute(
                "value"
            )
        )
        print(
            "Arabic:",
            fields["arabic"].get_attribute(
                "value"
            )
        )
        print(
            "Slug:",
            fields["slug"].get_attribute(
                "value"
            )
        )
        print(
            "Status:",
            Select(
                fields["status"]
            ).first_selected_option.text
        )

    def save(self):
        modal = self.get_modal()

        button = self.wait.until(
            lambda driver:
            next(
                (
                    element
                    for element
                    in modal.find_elements(
                        By.CSS_SELECTOR,
                        "button[type='submit']"
                    )
                    if element.is_displayed()
                    and element.is_enabled()
                ),
                False
            )
        )

        button.click()

        time.sleep(
            self.action_wait
        )

    def cancel(self):
        modal = self.get_modal()

        buttons = modal.find_elements(
            By.TAG_NAME,
            "button"
        )

        for button in buttons:
            if (
                button.is_displayed()
                and button.text.strip().lower()
                == "cancel"
            ):
                button.click()
                break

        self.wait.until(
            EC.invisibility_of_element_located(
                self.MODAL
            )
        )

    def modal_is_open(self):
        elements = self.driver.find_elements(
            *self.MODAL
        )

        return any(
            element.is_displayed()
            for element in elements
        )

    def get_validation_messages(self):
        messages = []

        modal = self.get_modal()

        fields = modal.find_elements(
            By.CSS_SELECTOR,
            "input, select, textarea"
        )

        for field in fields:
            try:
                message = self.driver.execute_script(
                    "return arguments[0].validationMessage;",
                    field
                )

                if message:
                    message = message.strip()

                    if message not in messages:
                        messages.append(
                            message
                        )

            except Exception:
                pass

        error_elements = modal.find_elements(
            By.CSS_SELECTOR,
            "[role='alert'], "
            "[class*='error'], "
            "[class*='invalid'], "
            "[class*='danger'], "
            "[class*='destructive']"
        )

        for element in error_elements:
            try:
                text = element.text.strip()

                if (
                    text
                    and text not in messages
                ):
                    messages.append(
                        text
                    )

            except Exception:
                pass

        return messages

    def get_english_value(self):
        return self.get_fields()[
            "english"
        ].get_attribute(
            "value"
        )

    def get_arabic_value(self):
        return self.get_fields()[
            "arabic"
        ].get_attribute(
            "value"
        )

    def get_slug_value(self):
        return self.get_fields()[
            "slug"
        ].get_attribute(
            "value"
        )

    def search_tag(
        self,
        value
    ):
        search = self.wait.until(
            EC.visibility_of_element_located(
                self.SEARCH
            )
        )

        self.clear_and_type(
            search,
            value
        )

        time.sleep(
            self.action_wait
        )

    def tag_exists(
        self,
        tag_name
    ):
        elements = self.driver.find_elements(
            By.XPATH,
            f"//*[normalize-space()="
            f"'{tag_name}']"
        )

        return any(
            element.is_displayed()
            for element in elements
        )

    def wait_for_modal_to_close(self):
        self.wait.until(
            EC.invisibility_of_element_located(
                self.MODAL
            )
        )
