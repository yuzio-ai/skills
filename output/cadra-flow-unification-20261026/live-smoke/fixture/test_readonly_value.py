import unittest
from readonly_value import last_value
class ReadonlyTests(unittest.TestCase):
    def test_last(self):
        self.assertIsNone(last_value([]))
        self.assertEqual(last_value([1, 3]), 3)
