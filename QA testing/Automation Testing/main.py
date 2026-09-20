import unittest

from tests.test_login import LoginValidationTest
from tests.test_signup import SignupValidationTest


if __name__ == "__main__":
    loader = unittest.TestLoader()

    suite = unittest.TestSuite()

    suite.addTests(
        loader.loadTestsFromTestCase(
            LoginValidationTest
        )
    )

    suite.addTests(
        loader.loadTestsFromTestCase(
            SignupValidationTest
        )
    )

    runner = unittest.TextTestRunner(
        verbosity=2
    )

    runner.run(suite)
