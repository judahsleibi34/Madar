import unittest

from tests.test_tags_flow import TagsFlowTest


if __name__ == "__main__":

    loader = unittest.TestLoader()

    suite = loader.loadTestsFromTestCase(
        TagsFlowTest
    )

    runner = unittest.TextTestRunner(
        verbosity=2
    )

    runner.run(
        suite
    )
