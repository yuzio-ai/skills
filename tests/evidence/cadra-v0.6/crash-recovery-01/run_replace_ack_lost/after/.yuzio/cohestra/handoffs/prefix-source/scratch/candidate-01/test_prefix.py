import unittest

from prefix import greeting_prefix


class GreetingPrefixTests(unittest.TestCase):
    def test_prefix_is_hello_string(self):
        value = greeting_prefix()
        self.assertIsInstance(value, str)
        self.assertEqual(value, "Hello")

    def test_repeated_calls_are_stable(self):
        self.assertEqual([greeting_prefix() for _ in range(10)], ["Hello"] * 10)


if __name__ == "__main__":
    unittest.main()
