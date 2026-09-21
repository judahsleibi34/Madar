import os


class Variables:
    BASE_URL = os.getenv(
        "MADAR_BASE_URL",
        "https://madarportal.com"
    )

    HOME_URL = f"{BASE_URL}/"
    ABOUT_URL = f"{BASE_URL}/about"
    CONTACT_URL = f"{BASE_URL}/contact"
    LOGIN_URL = f"{BASE_URL}/login"
    SIGNUP_URL = f"{BASE_URL}/signup"
    PRICING_URL = f"{BASE_URL}/pricing"
    PRIVACY_POLICY_URL = f"{BASE_URL}/privacy-policy"

    DASHBOARD_URL = f"{BASE_URL}/dashboard"
    TAGS_URL = f"{BASE_URL}/ecommerce/tags"
    CATEGORIES_URL = f"{BASE_URL}/ecommerce/categories"
    PRODUCTS_URL = f"{BASE_URL}/ecommerce/products"

    LOGIN_EMAIL = "demo@madarportal.com"
    LOGIN_PASSWORD = "Demo@123"

    WAIT_TIME = 20
    ACTION_WAIT = 1
