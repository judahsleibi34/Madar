import unittest

from tests.test_products_performance import (
    ProductsPerformanceTest
)


if __name__ == "__main__":

    suite = (
        unittest.TestLoader()
        .loadTestsFromTestCase(
            ProductsPerformanceTest
        )
    )

    unittest.TextTestRunner(
        verbosity=2
    ).run(
        suite
    )
