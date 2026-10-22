import unittest
from unittest.mock import patch

from greeting import greet


class GreetingTests(unittest.TestCase):
    def test_names_trim_only_surrounding_whitespace(self):
        for name, expected in (("Ada", "Ada"), ("  Ada  ", "Ada"),
                               ("\tAda Lovelace\n", "Ada Lovelace"),
                               (" A  B ", "A  B"), ("你好🌍", "你好🌍"),
                               (" e\u0301 ", "e\u0301"),
                               ("\u2003你好\u3000", "你好")):
            with self.subTest(name=name):
                self.assertEqual(greet(name), f"Hello, {expected}!")

    def test_empty_or_whitespace_name_uses_world(self):
        for name in ("", " ", "\t\n\r", "\u2003\u3000"):
            with self.subTest(name=name):
                self.assertEqual(greet(name), "Hello, world!")

    def test_prefix_is_obtained_on_each_call(self):
        with patch("greeting.greeting_prefix", side_effect=["Hi", "Welcome"]) as prefix:
            self.assertEqual(greet(" Ada "), "Hi, Ada!")
            self.assertEqual(greet("\t"), "Welcome, world!")
        self.assertEqual(prefix.call_count, 2)
        prefix.assert_called_with()


if __name__ == "__main__":
    unittest.main()
