import unittest

from tests.test_categories_performance import (
    CategoriesPerformanceTest
)


if __name__ == "__main__":

    suite = unittest.TestLoader().loadTestsFromTestCase(
        CategoriesPerformanceTest
    )

    unittest.TextTestRunner(
        verbosity=2
    ).run(
        suite
    )
