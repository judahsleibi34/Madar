import unittest

from tests.test_categories_full_matrix import (
    CategoriesFullMatrixTest
)


if __name__ == "__main__":

    suite = unittest.TestLoader().loadTestsFromTestCase(
        CategoriesFullMatrixTest
    )

    unittest.TextTestRunner(
        verbosity=2
    ).run(
        suite
    )
