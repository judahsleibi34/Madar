import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException
)


class ProductsPage:

    ONLINE_STORE_BUTTON = (
        By.XPATH,
        "//button["
        "@title='Online Store' "
        "or contains(normalize-space(.), 'Online Store')"
        "]"
    )

    PRODUCTS_LINK = (
        By.CSS_SELECTOR,
        "a[href='/ecommerce/products']"
    )

    ADD_PRODUCT_BUTTON = (
        By.XPATH,
        "//button[contains("
        "normalize-space(.), "
        "'Add product'"
        ")]"
    )

    MODAL = (
        By.CSS_SELECTOR,
        "section[role='dialog']"
    )

    SEARCH = (
        By.XPATH,
        "//input[@placeholder='Search Products']"
    )

    def __init__(
        self,
        driver,
        dashboard_url,
        products_url,
        wait_time=20,
        action_wait=1
    ):
        self.driver = driver
        self.dashboard_url = dashboard_url
        self.products_url = products_url
        self.wait_time = wait_time
        self.action_wait = action_wait

        self.wait = WebDriverWait(
            driver,
            wait_time
        )

    def open_dashboard(self):
        self.driver.get(
            self.dashboard_url
        )

    def open_direct(self):
        self.driver.get(
            self.products_url
        )

        self.wait.until(
            EC.element_to_be_clickable(
                self.ADD_PRODUCT_BUTTON
            )
        )

    def open_through_sidebar(self):
        self.open_dashboard()

        online_store = self.wait.until(
            EC.element_to_be_clickable(
                self.ONLINE_STORE_BUTTON
            )
        )

        online_store.click()

        products = self.wait.until(
            EC.element_to_be_clickable(
                self.PRODUCTS_LINK
            )
        )

        products.click()

        self.wait.until(
            EC.url_contains(
                "/ecommerce/products"
            )
        )

        self.wait.until(
            EC.element_to_be_clickable(
                self.ADD_PRODUCT_BUTTON
            )
        )

    def open_add_product_modal(self):
        button = self.wait.until(
            EC.element_to_be_clickable(
                self.ADD_PRODUCT_BUTTON
            )
        )

        button.click()

        return self.wait.until(
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

    def scroll_to(self, element):
        self.driver.execute_script(
            """
            arguments[0].scrollIntoView({
                behavior: 'instant',
                block: 'center'
            });
            """,
            element
        )

    def _control_by_label(
        self,
        modal,
        label_text,
        tag_name="input"
    ):
        wanted = (
            label_text
            .strip()
            .lower()
        )

        labels = modal.find_elements(
            By.TAG_NAME,
            "label"
        )

        for label in labels:

            text = (
                label.text
                .strip()
            )

            if not text:
                continue

            first_line = (
                text.splitlines()[0]
                .strip()
                .lower()
            )

            if (
                first_line == wanted
                or first_line.startswith(
                    wanted
                )
            ):
                controls = label.find_elements(
                    By.TAG_NAME,
                    tag_name
                )

                visible = [
                    element
                    for element in controls
                    if element.is_displayed()
                ]

                if visible:
                    return visible[0]

        raise NoSuchElementException(
            f"Could not locate "
            f"{tag_name} for label: "
            f"{label_text}"
        )

    def _checkbox_by_label(
        self,
        modal,
        label_text
    ):
        wanted = (
            label_text
            .strip()
            .lower()
        )

        labels = modal.find_elements(
            By.TAG_NAME,
            "label"
        )

        for label in labels:

            text = (
                label.text
                .strip()
                .lower()
            )

            if wanted in text:

                checkboxes = (
                    label.find_elements(
                        By.CSS_SELECTOR,
                        "input[type='checkbox']"
                    )
                )

                if checkboxes:
                    return checkboxes[0]

        raise NoSuchElementException(
            "Could not locate checkbox: "
            + label_text
        )

    def get_fields(self):

        modal = self.get_modal()

        english_name = modal.find_element(
            By.CSS_SELECTOR,
            "input[aria-label='Name (English)']"
        )

        arabic_name = modal.find_element(
            By.CSS_SELECTOR,
            "input[aria-label='Name (Arabic)']"
        )

        english_description = (
            modal.find_element(
                By.CSS_SELECTOR,
                "textarea[aria-label="
                "'Description (English)']"
            )
        )

        arabic_description = (
            modal.find_element(
                By.CSS_SELECTOR,
                "textarea[aria-label="
                "'Description (Arabic)']"
            )
        )

        fields = {
            "english_name":
                english_name,

            "arabic_name":
                arabic_name,

            "english_description":
                english_description,

            "arabic_description":
                arabic_description,

            "slug":
                self._control_by_label(
                    modal,
                    "Slug"
                ),

            "sku":
                self._control_by_label(
                    modal,
                    "Product SKU"
                ),

            "brand":
                self._control_by_label(
                    modal,
                    "Brand"
                ),

            "status":
                self._control_by_label(
                    modal,
                    "Status",
                    "select"
                ),

            "base_price":
                self._control_by_label(
                    modal,
                    "Base price"
                ),

            "discount_price":
                self._control_by_label(
                    modal,
                    "Discount price"
                ),

            "store_currency":
                self._control_by_label(
                    modal,
                    "Store currency"
                ),

            "current_stock":
                self._control_by_label(
                    modal,
                    "Current stock"
                ),

            "stock_warning":
                self._control_by_label(
                    modal,
                    "Warn me when stock reaches"
                ),

            "track_inventory":
                self._checkbox_by_label(
                    modal,
                    "Track Inventory"
                ),

            "allow_sold_out":
                self._checkbox_by_label(
                    modal,
                    "Let customers order "
                    "when sold out"
                )
        }

        return fields

    def debug_fields(self):

        modal = self.get_modal()

        inputs = [
            element
            for element in modal.find_elements(
                By.TAG_NAME,
                "input"
            )
            if element.is_displayed()
        ]

        textareas = [
            element
            for element in modal.find_elements(
                By.TAG_NAME,
                "textarea"
            )
            if element.is_displayed()
        ]

        selects = [
            element
            for element in modal.find_elements(
                By.TAG_NAME,
                "select"
            )
            if element.is_displayed()
        ]

        print()
        print(
            "PRODUCT MODAL FIELD DEBUG"
        )
        print(
            "--------------------------"
        )

        print(
            "Visible inputs found:",
            len(inputs)
        )

        print(
            "Visible textareas found:",
            len(textareas)
        )

        print(
            "Visible selects found:",
            len(selects)
        )

        for index, element in enumerate(
            inputs,
            start=1
        ):
            print(
                f"Input {index}: "
                f"type="
                f"{element.get_attribute('type')} "
                f"aria-label="
                f"{element.get_attribute('aria-label')} "
                f"required="
                f"{element.get_attribute('required')} "
                f"maxlength="
                f"{element.get_attribute('maxlength')} "
                f"min="
                f"{element.get_attribute('min')} "
                f"max="
                f"{element.get_attribute('max')} "
                f"step="
                f"{element.get_attribute('step')} "
                f"value="
                f"{element.get_attribute('value')}"
            )

        for index, element in enumerate(
            textareas,
            start=1
        ):
            print(
                f"Textarea {index}: "
                f"aria-label="
                f"{element.get_attribute('aria-label')} "
                f"required="
                f"{element.get_attribute('required')} "
                f"maxlength="
                f"{element.get_attribute('maxlength')}"
            )

        for index, element in enumerate(
            selects,
            start=1
        ):
            print(
                f"Select {index}: "
                f"required="
                f"{element.get_attribute('required')} "
                f"value="
                f"{element.get_attribute('value')}"
            )

            print(
                "  Options:",
                [
                    option.text
                    for option
                    in Select(element).options
                ]
            )

    def clear_and_type(
        self,
        element,
        value
    ):

        if value is None:
            value = ""

        value = str(value)

        maxlength = (
            element.get_attribute(
                "maxlength"
            )
        )

        if (
            maxlength
            and maxlength.isdigit()
        ):
            value = value[
                :int(maxlength)
            ]

        self.scroll_to(
            element
        )

        if len(value) > 500:

            self.driver.execute_script(
                """
                const element = arguments[0];
                const value = arguments[1];

                let prototype;

                if (
                    element.tagName
                    .toLowerCase()
                    === 'textarea'
                ) {
                    prototype =
                        HTMLTextAreaElement
                        .prototype;
                } else {
                    prototype =
                        HTMLInputElement
                        .prototype;
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
                                'insertText'
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

    def set_checkbox(
        self,
        element,
        wanted
    ):
        self.scroll_to(
            element
        )

        if (
            element.is_selected()
            != bool(wanted)
        ):
            self.driver.execute_script(
                "arguments[0].click();",
                element
            )

    def fill_product(
        self,
        english_name="",
        arabic_name="",
        english_description="",
        arabic_description="",
        slug="",
        sku="",
        brand="",
        status="Draft",
        base_price="0",
        discount_price="",
        store_currency="USD",
        current_stock="0",
        stock_warning="5",
        track_inventory=True,
        allow_sold_out=False
    ):

        values = {
            "english_name":
                english_name,

            "arabic_name":
                arabic_name,

            "english_description":
                english_description,

            "arabic_description":
                arabic_description,

            "slug":
                slug,

            "sku":
                sku,

            "brand":
                brand,

            "base_price":
                base_price,

            "discount_price":
                discount_price,

            "store_currency":
                store_currency,

            "current_stock":
                current_stock,

            "stock_warning":
                stock_warning
        }

        for key, value in values.items():

            fields = self.get_fields()

            self.clear_and_type(
                fields[key],
                value
            )

        fields = self.get_fields()

        if status is not None:

            self.scroll_to(
                fields["status"]
            )

            Select(
                fields["status"]
            ).select_by_visible_text(
                status
            )

        fields = self.get_fields()

        self.set_checkbox(
            fields["track_inventory"],
            track_inventory
        )

        fields = self.get_fields()

        self.set_checkbox(
            fields["allow_sold_out"],
            allow_sold_out
        )

        fields = self.get_fields()

        print()
        print(
            "PRODUCT VALUES AFTER FILL"
        )
        print(
            "--------------------------"
        )

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
            "SKU:",
            fields["sku"]
            .get_attribute("value")
        )

        print(
            "Brand:",
            fields["brand"]
            .get_attribute("value")
        )

        print(
            "Status:",
            Select(
                fields["status"]
            ).first_selected_option.text
        )

        print(
            "Base Price:",
            fields["base_price"]
            .get_attribute("value")
        )

        print(
            "Discount Price:",
            fields["discount_price"]
            .get_attribute("value")
        )

        print(
            "Currency:",
            fields["store_currency"]
            .get_attribute("value")
        )

        print(
            "Current Stock:",
            fields["current_stock"]
            .get_attribute("value")
        )

        print(
            "Stock Warning:",
            fields["stock_warning"]
            .get_attribute("value")
        )

        print(
            "Track Inventory:",
            fields["track_inventory"]
            .is_selected()
        )

        print(
            "Allow Sold Out:",
            fields["allow_sold_out"]
            .is_selected()
        )

    def get_statuses(self):

        fields = self.get_fields()

        return [
            option.text
            for option in Select(
                fields["status"]
            ).options
        ]

    def save(self):

        modal = self.get_modal()

        button = modal.find_element(
            By.XPATH,
            ".//button[contains("
            "normalize-space(.), "
            "'Save product'"
            ")]"
        )

        self.scroll_to(
            button
        )

        button.click()

        time.sleep(
            self.action_wait
        )

    def cancel(self):

        modal = self.get_modal()

        button = modal.find_element(
            By.XPATH,
            ".//button["
            "normalize-space(.)='Cancel'"
            "]"
        )

        self.scroll_to(
            button
        )

        button.click()

        time.sleep(
            0.3
        )

    def modal_is_open(self):

        try:
            modal = self.driver.find_element(
                *self.MODAL
            )

            return modal.is_displayed()

        except Exception:
            return False

    def wait_for_modal_to_close(
        self,
        timeout=10
    ):

        try:
            WebDriverWait(
                self.driver,
                timeout
            ).until(
                EC.invisibility_of_element_located(
                    self.MODAL
                )
            )

            return True

        except TimeoutException:
            return False

    def get_validation_messages(self):

        messages = []

        if not self.modal_is_open():
            return messages

        modal = self.get_modal()

        controls = modal.find_elements(
            By.CSS_SELECTOR,
            "input, textarea, select"
        )

        for element in controls:

            if not element.is_displayed():
                continue

            message = self.driver.execute_script(
                """
                return arguments[0]
                    .validationMessage || '';
                """,
                element
            )

            message = (
                message or ""
            ).strip()

            if (
                message
                and message not in messages
            ):
                messages.append(
                    message
                )

        candidates = self.driver.find_elements(
            By.CSS_SELECTOR,
            "[role='alert'], "
            "[class*='toast'], "
            "[class*='error']"
        )

        for element in candidates:

            try:
                if not element.is_displayed():
                    continue

                text = (
                    element.text
                    .strip()
                )

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

    def search_product(
        self,
        product_name
    ):

        search = self.wait.until(
            EC.visibility_of_element_located(
                self.SEARCH
            )
        )

        search.click()

        search.send_keys(
            Keys.CONTROL,
            "a"
        )

        search.send_keys(
            Keys.BACKSPACE
        )

        search.send_keys(
            product_name
        )

        time.sleep(
            self.action_wait
        )

    def product_exists(
        self,
        product_name
    ):

        matches = self.driver.find_elements(
            By.XPATH,
            "//*[normalize-space(.)="
            + self._xpath_literal(
                product_name
            )
            + "]"
        )

        return any(
            element.is_displayed()
            for element in matches
        )

    def _xpath_literal(
        self,
        value
    ):
        if "'" not in value:
            return (
                "'"
                + value
                + "'"
            )

        if '"' not in value:
            return (
                '"'
                + value
                + '"'
            )

        parts = value.split("'")

        return (
            "concat("
            + ", \"'\", ".join(
                "'" + part + "'"
                for part in parts
            )
            + ")"
        )
