import unittest

from tests.test_products_dom import (
    ProductsDomTest
)

from tests.test_product_create import (
    ProductCreateTest
)


if __name__ == "__main__":

    suite = unittest.TestSuite()

    suite.addTests(
        unittest.TestLoader()
        .loadTestsFromTestCase(
            ProductsDomTest
        )
    )

    suite.addTests(
        unittest.TestLoader()
        .loadTestsFromTestCase(
            ProductCreateTest
        )
    )

    unittest.TextTestRunner(
        verbosity=2
    ).run(
        suite
    )
