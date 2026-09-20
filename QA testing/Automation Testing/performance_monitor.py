import time

from selenium.webdriver.support.ui import WebDriverWait


class PerformanceMonitor:

    def __init__(self, driver, wait_time=20):
        self.driver = driver
        self.wait_time = wait_time

    def load_page(self, url):
        start = time.perf_counter()

        self.driver.get(url)

        WebDriverWait(
            self.driver,
            self.wait_time
        ).until(
            lambda driver:
            driver.execute_script(
                "return document.readyState"
            ) == "complete"
        )

        selenium_time = time.perf_counter() - start

        navigation = self.driver.execute_script(
            """
            const entries =
                performance.getEntriesByType('navigation');

            if (!entries.length) {
                return null;
            }

            return entries[0].toJSON();
            """
        )

        result = {
            "selenium_seconds": round(
                selenium_time,
                3
            ),
            "dns_ms": 0,
            "connection_ms": 0,
            "server_response_ms": 0,
            "dom_loaded_ms": 0,
            "full_load_ms": 0
        }

        if navigation:
            result["dns_ms"] = round(
                navigation["domainLookupEnd"]
                - navigation["domainLookupStart"],
                2
            )

            result["connection_ms"] = round(
                navigation["connectEnd"]
                - navigation["connectStart"],
                2
            )

            result["server_response_ms"] = round(
                navigation["responseStart"]
                - navigation["requestStart"],
                2
            )

            result["dom_loaded_ms"] = round(
                navigation[
                    "domContentLoadedEventEnd"
                ],
                2
            )

            result["full_load_ms"] = round(
                navigation["loadEventEnd"],
                2
            )

        return result

    def measure_action(
        self,
        action,
        condition
    ):
        start = time.perf_counter()

        action()

        WebDriverWait(
            self.driver,
            self.wait_time
        ).until(
            condition
        )

        return round(
            time.perf_counter() - start,
            3
        )

    @staticmethod
    def print_metrics(
        name,
        metrics
    ):
        print()
        print(f"{name} Performance")
        print("--------------------------------")
        print(
            f"Selenium Load: "
            f"{metrics['selenium_seconds']:.3f} sec"
        )
        print(
            f"DNS: "
            f"{metrics['dns_ms']:.2f} ms"
        )
        print(
            f"Connection: "
            f"{metrics['connection_ms']:.2f} ms"
        )
        print(
            f"Server Response: "
            f"{metrics['server_response_ms']:.2f} ms"
        )
        print(
            f"DOM Loaded: "
            f"{metrics['dom_loaded_ms']:.2f} ms"
        )
        print(
            f"Full Load: "
            f"{metrics['full_load_ms']:.2f} ms"
        )
