import unittest
from alpha import greet
class AlphaTests(unittest.TestCase):
    def test_named(self): self.assertEqual(greet("Ada"), "Hello, Ada!")
    def test_blank(self): self.assertEqual(greet(""), "Hello, world!")
    def test_surrounding_whitespace(self):
        self.assertEqual(greet(" \tAda\n"), "Hello, Ada!")
    def test_whitespace_only(self):
        for name in [" ", "\t\n", "\u3000"]:
            with self.subTest(name=name):
                self.assertEqual(greet(name), "Hello, world!")
    def test_internal_whitespace(self):
        self.assertEqual(greet("  Ada  Lovelace  "), "Hello, Ada  Lovelace!")
