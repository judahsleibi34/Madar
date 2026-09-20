import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


class CategoriesPage:

    ONLINE_STORE_BUTTON = (
        By.XPATH,
        "//button[@title='Online Store']"
    )

    CATEGORIES_LINK = (
        By.CSS_SELECTOR,
        "a[href='/ecommerce/categories']"
    )

    PAGE_TITLE = (
        By.XPATH,
        "//h1[normalize-space()='Categories']"
    )

    ADD_CATEGORY_BUTTON = (
        By.XPATH,
        "//button[contains(normalize-space(.), 'Add category')]"
    )

    MODAL = (
        By.CSS_SELECTOR,
        "section[role='dialog']"
    )

    SEARCH = (
        By.XPATH,
        "//input[contains(@placeholder, 'Search Categories')]"
    )

    def __init__(
        self,
        driver,
        dashboard_url,
        categories_url,
        wait_time=20,
        action_wait=1
    ):
        self.driver = driver
        self.dashboard_url = dashboard_url
        self.categories_url = categories_url
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
            "/dashboard"
            in driver.current_url
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
                self.CATEGORIES_LINK
            )
        ).click()

        self.wait.until(
            lambda driver:
            "/ecommerce/categories"
            in driver.current_url
        )

        self.wait.until(
            EC.visibility_of_element_located(
                self.PAGE_TITLE
            )
        )

    def open_direct(self):
        self.driver.get(
            self.categories_url
        )

        self.wait.until(
            lambda driver:
            "/ecommerce/categories"
            in driver.current_url
        )

        self.wait.until(
            EC.element_to_be_clickable(
                self.ADD_CATEGORY_BUTTON
            )
        )

    def open_add_category_modal(self):
        self.wait.until(
            EC.element_to_be_clickable(
                self.ADD_CATEGORY_BUTTON
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

        textareas = [
            element
            for element in modal.find_elements(
                By.CSS_SELECTOR,
                "textarea"
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
        print("CATEGORY MODAL FIELD DEBUG")
        print("--------------------------")
        print(
            f"Visible inputs found: "
            f"{len(inputs)}"
        )
        print(
            f"Visible textareas found: "
            f"{len(textareas)}"
        )
        print(
            f"Visible selects found: "
            f"{len(selects)}"
        )

        for index, element in enumerate(
            inputs,
            start=1
        ):
            print(
                f"Input {index}: "
                f"type={element.get_attribute('type')} "
                f"name={element.get_attribute('name')} "
                f"required={element.get_attribute('required')} "
                f"maxlength={element.get_attribute('maxlength')} "
                f"min={element.get_attribute('min')} "
                f"step={element.get_attribute('step')}"
            )

        for index, element in enumerate(
            textareas,
            start=1
        ):
            print(
                f"Textarea {index}: "
                f"name={element.get_attribute('name')} "
                f"required={element.get_attribute('required')} "
                f"maxlength={element.get_attribute('maxlength')}"
            )

        for index, element in enumerate(
            selects,
            start=1
        ):
            print(
                f"Select {index}: "
                f"name={element.get_attribute('name')} "
                f"required={element.get_attribute('required')}"
            )

        if len(inputs) < 4:
            raise AssertionError(
                f"Expected at least 4 visible inputs "
                f"inside category modal, "
                f"found {len(inputs)}"
            )

        if len(textareas) < 2:
            raise AssertionError(
                f"Expected 2 visible description "
                f"textareas inside category modal, "
                f"found {len(textareas)}"
            )

        if len(selects) < 2:
            raise AssertionError(
                f"Expected Status and Parent Category "
                f"selects, found {len(selects)}"
            )

        return {
            "english_name": inputs[0],
            "arabic_name": inputs[1],
            "english_description": textareas[0],
            "arabic_description": textareas[1],
            "slug": inputs[2],
            "status": selects[0],
            "parent": selects[1],
            "display_position": inputs[3]
        }

    def clear_and_type(
        self,
        element,
        value
    ):
        if value is None:
            value = ""

        value = str(value)

        maxlength = element.get_attribute(
            "maxlength"
        )

        if (
            maxlength
            and maxlength.isdigit()
        ):
            value = value[
                :int(maxlength)
            ]

        if len(value) > 500:

            self.driver.execute_script(
                """
                const element = arguments[0];
                const value = arguments[1];

                let prototype;

                if (
                    element.tagName.toLowerCase()
                    === 'textarea'
                ) {
                    prototype =
                        HTMLTextAreaElement.prototype;
                } else {
                    prototype =
                        HTMLInputElement.prototype;
                }

                const descriptor =
                    Object.getOwnPropertyDescriptor(
                        prototype,
                        'value'
                    );

                descriptor.set.call(
                    element,
                    value
                );

                element.dispatchEvent(
                    new InputEvent(
                        'input',
                        {
                            bubbles: true,
                            inputType:
                                'insertText',
                            data: null
                        }
                    )
                );

                element.dispatchEvent(
                    new Event(
                        'change',
                        {
                            bubbles: true
                        }
                    )
                );
                """,
                element,
                value
            )

            return

        element.click()

        element.send_keys(
            Keys.CONTROL,
            "a"
        )

        element.send_keys(
            Keys.BACKSPACE
        )

        if value != "":
            element.send_keys(
                value
            )

    def fill_category(
        self,
        english_name="",
        arabic_name="",
        english_description="",
        arabic_description="",
        slug="",
        status=None,
        parent=None,
        display_position=None
    ):
        #
        # React may re-render elements after large
        # textarea updates, so fill stable fields first.
        #
        fields = self.get_fields()

        self.clear_and_type(
            fields["english_name"],
            english_name
        )

        fields = self.get_fields()

        self.clear_and_type(
            fields["arabic_name"],
            arabic_name
        )

        fields = self.get_fields()

        self.clear_and_type(
            fields["slug"],
            slug
        )

        fields = self.get_fields()

        self.clear_and_type(
            fields["display_position"],
            display_position
        )

        fields = self.get_fields()

        if status is not None:
            Select(
                fields["status"]
            ).select_by_visible_text(
                status
            )

        fields = self.get_fields()

        if parent is not None:
            Select(
                fields["parent"]
            ).select_by_visible_text(
                parent
            )

        #
        # Descriptions are filled LAST because
        # 10,000-character updates can trigger
        # a React re-render.
        #
        fields = self.get_fields()

        self.clear_and_type(
            fields["english_description"],
            english_description
        )

        #
        # Reacquire elements after React update.
        #
        fields = self.get_fields()

        self.clear_and_type(
            fields["arabic_description"],
            arabic_description
        )

        #
        # Reacquire once more before reading values.
        #
        fields = self.get_fields()

        print()
        print("VALUES AFTER FILL")
        print("--------------------------")
        print(
            "English Name:",
            fields["english_name"]
            .get_attribute("value")
        )
        print(
            "Arabic Name:",
            fields["arabic_name"]
            .get_attribute("value")
        )
        print(
            "Slug:",
            fields["slug"]
            .get_attribute("value")
        )
        print(
            "Status:",
            Select(
                fields["status"]
            ).first_selected_option.text
        )
        print(
            "Parent:",
            Select(
                fields["parent"]
            ).first_selected_option.text
        )
        print(
            "Display Position:",
            fields["display_position"]
            .get_attribute("value")
        )
        print(
            "English Description Length:",
            len(
                fields["english_description"]
                .get_attribute("value")
            )
        )
        print(
            "Arabic Description Length:",
            len(
                fields["arabic_description"]
                .get_attribute("value")
            )
        )

    def save(self):
        modal = self.get_modal()

        button = modal.find_element(
            By.XPATH,
            ".//button["
            "@type='submit' "
            "and normalize-space()='Save'"
            "]"
        )

        button.click()

        time.sleep(
            self.action_wait
        )

    def cancel(self):
        modal = self.get_modal()

        button = modal.find_element(
            By.XPATH,
            ".//button[normalize-space()='Cancel']"
        )

        button.click()

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

    def wait_for_modal_to_close(
        self,
        timeout=8
    ):
        WebDriverWait(
            self.driver,
            timeout
        ).until(
            EC.invisibility_of_element_located(
                self.MODAL
            )
        )

    def get_validation_messages(self):
        messages = []

        if self.modal_is_open():
            modal = self.get_modal()

            fields = modal.find_elements(
                By.CSS_SELECTOR,
                "input, textarea, select"
            )

            for field in fields:
                try:
                    message = (
                        self.driver.execute_script(
                            "return arguments[0]"
                            ".validationMessage;",
                            field
                        )
                    )

                    if message:
                        message = message.strip()

                        if (
                            message
                            and message not in messages
                        ):
                            messages.append(
                                message
                            )

                except Exception:
                    pass

        error_elements = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[role='alert'], "
            "[aria-live='assertive'], "
            "[class*='error'], "
            "[class*='invalid'], "
            "[class*='destructive'], "
            "[class*='text-red'], "
            "[data-sonner-toast]"
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

    def search_category(
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

    def category_exists(
        self,
        category_name
    ):
        elements = self.driver.find_elements(
            By.XPATH,
            "//*[normalize-space()="
            f"'{category_name}']"
        )

        return any(
            element.is_displayed()
            for element in elements
        )

    def get_available_statuses(self):
        fields = self.get_fields()

        select = Select(
            fields["status"]
        )

        statuses = []

        for option in select.options:
            text = option.text.strip()
            value = option.get_attribute(
                "value"
            )

            if (
                text
                and value
                and "choose" not in text.lower()
            ):
                statuses.append(
                    text
                )

        return statuses

    def get_parent_options(self):
        fields = self.get_fields()

        return [
            option.text.strip()
            for option
            in Select(
                fields["parent"]
            ).options
            if option.text.strip()
        ]
