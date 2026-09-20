import unittest

from driver_loader import DriverLoader
from variables import Variables


class BaseTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.variables = Variables()
        cls.driver = DriverLoader.get_driver()

    def get_live_driver(self):
        self.driver = DriverLoader.get_driver()
        return self.driver

    def recreate_driver(self):
        self.driver = DriverLoader.recreate_driver()
        return self.driver
