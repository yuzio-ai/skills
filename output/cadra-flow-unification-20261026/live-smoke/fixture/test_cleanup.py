import unittest
from cleanup import greeting
class CleanupTests(unittest.TestCase):
    def test_greeting(self):
        self.assertEqual(greeting("cat"), "hello cat")
