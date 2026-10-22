import unittest
from beta import square
class BetaTests(unittest.TestCase):
    def test_values(self):
        for value in [-3, 0, 4]: self.assertEqual(square(value), value * value)
