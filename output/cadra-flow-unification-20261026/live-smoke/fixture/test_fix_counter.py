import unittest
from fix_counter import count_up_to
class CounterTests(unittest.TestCase):
    def test_limits(self):
        for n in (0, 1, 3):
            with self.subTest(n=n): self.assertEqual(count_up_to(n), n)
