import unittest
from review_total import sum_values
class TotalTests(unittest.TestCase):
    def test_total(self):
        for values in ([], [2], [2, 3]):
            with self.subTest(values=values): self.assertEqual(sum_values(values), sum(values))
