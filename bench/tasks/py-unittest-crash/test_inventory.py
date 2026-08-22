import unittest

from inventory import Inventory


class TestInventory(unittest.TestCase):
    def test_add(self):
        inv = Inventory()
        inv.add("apple", 2)
        inv.add("apple", 3)
        self.assertEqual(inv.total(), 5)
        self.assertEqual(inv.names(), ["apple"])

    def test_remove_missing_is_noop(self):
        inv = Inventory()
        inv.add("pear", 1)
        inv.remove("ghost")
        inv.remove("ghost", 3)
        self.assertEqual(inv.total(), 1)

    def test_remove_all(self):
        inv = Inventory()
        inv.add("apple", 2)
        inv.add("pear", 1)
        inv.remove("apple")
        self.assertEqual(inv.names(), ["pear"])
        self.assertEqual(inv.total(), 1)

    def test_remove_some(self):
        inv = Inventory()
        inv.add("apple", 5)
        inv.remove("apple", 2)
        self.assertEqual(inv.total(), 3)

    def test_remove_exact_deletes_entry(self):
        inv = Inventory()
        inv.add("apple", 2)
        inv.remove("apple", 2)
        self.assertEqual(inv.names(), [])
        self.assertEqual(inv.total(), 0)

    def test_remove_more_than_have_deletes_entry(self):
        inv = Inventory()
        inv.add("apple", 2)
        inv.remove("apple", 5)
        self.assertEqual(inv.names(), [])
        self.assertEqual(inv.total(), 0)

    def test_add_invalid(self):
        inv = Inventory()
        with self.assertRaises(ValueError):
            inv.add("x", 0)


if __name__ == "__main__":
    unittest.main()
