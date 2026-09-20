import unittest

from tests.test_tags_full_matrix import (
    TagsFullMatrixTest
)


if __name__ == "__main__":

    suite = unittest.TestLoader().loadTestsFromTestCase(
        TagsFullMatrixTest
    )

    unittest.TextTestRunner(
        verbosity=2
    ).run(
        suite
    )
