import unittest
from alpha import greet
class AlphaTests(unittest.TestCase):
    def test_named(self): self.assertEqual(greet("Ada"), "Hello, Ada!")
    def test_blank(self): self.assertEqual(greet(""), "Hello, world!")
