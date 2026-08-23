import unittest
from stats import mean


class TestMean(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(mean([1, 2, 3]), 2.0)

    def test_single(self):
        self.assertEqual(mean([5]), 5.0)


if __name__ == "__main__":
    unittest.main()
