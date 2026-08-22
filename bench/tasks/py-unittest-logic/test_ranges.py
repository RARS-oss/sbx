import unittest

from ranges import covered, merge


class TestMerge(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(merge([]), [])

    def test_single(self):
        self.assertEqual(merge([(2, 5)]), [(2, 5)])

    def test_disjoint_sorted(self):
        self.assertEqual(merge([(1, 2), (5, 6)]), [(1, 2), (5, 6)])

    def test_overlap(self):
        self.assertEqual(merge([(1, 4), (3, 6)]), [(1, 6)])

    def test_touching_are_merged(self):
        self.assertEqual(merge([(1, 3), (4, 6)]), [(1, 6)])

    def test_shared_boundary(self):
        self.assertEqual(merge([(1, 3), (3, 6)]), [(1, 6)])

    def test_unsorted_input(self):
        self.assertEqual(merge([(5, 6), (1, 2), (2, 4)]), [(1, 6)])

    def test_contained(self):
        self.assertEqual(merge([(1, 10), (3, 4)]), [(1, 10)])

    def test_gap_of_one_is_not_touching(self):
        self.assertEqual(merge([(1, 3), (5, 6)]), [(1, 3), (5, 6)])


class TestCovered(unittest.TestCase):
    def test_single_point(self):
        self.assertEqual(covered([(7, 7)]), 1)

    def test_inclusive_count(self):
        self.assertEqual(covered([(1, 3)]), 3)

    def test_merged_count(self):
        self.assertEqual(covered([(1, 3), (4, 6), (10, 10)]), 7)


if __name__ == "__main__":
    unittest.main()
