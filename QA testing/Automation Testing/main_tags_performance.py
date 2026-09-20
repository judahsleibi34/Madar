import unittest

from tests.test_tags_performance import (
    TagsPerformanceTest
)


if __name__ == "__main__":

    suite = unittest.TestLoader().loadTestsFromTestCase(
        TagsPerformanceTest
    )

    unittest.TextTestRunner(
        verbosity=2
    ).run(
        suite
    )
