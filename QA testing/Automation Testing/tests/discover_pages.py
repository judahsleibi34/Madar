import time

from urllib.parse import urljoin, urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from driver_loader import DriverLoader
from variables import Variables


driver = DriverLoader.get_driver()
variables = Variables()

driver.get(variables.URL)

WebDriverWait(driver, 20).until(
    lambda d: d.execute_script(
        "return document.readyState"
    ) == "complete"
)

time.sleep(5)

elements = driver.find_elements(
    By.CSS_SELECTOR,
    "a[href], [role='link']"
)

pages = set()

base_domain = urlparse(
    variables.URL
).netloc.replace("www.", "")

print()
print("Found elements:", len(elements))
print()

for element in elements:
    href = element.get_attribute("href")

    if not href:
        continue

    url = urljoin(
        variables.URL,
        href
    )

    parsed = urlparse(url)

    domain = parsed.netloc.replace("www.", "")

    if domain != base_domain:
        continue

    if parsed.scheme not in ("http", "https"):
        continue

    clean_url = (
        f"{parsed.scheme}://"
        f"{parsed.netloc}"
        f"{parsed.path}"
    )

    pages.add(clean_url)


print("Madar Pages")
print("--------------------------------")

for page in sorted(pages):
    print(page)