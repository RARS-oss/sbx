"""A tiny in-memory inventory."""


class Inventory:
    def __init__(self):
        self.items = {}

    def add(self, name, qty=1):
        if qty <= 0:
            raise ValueError("qty must be positive")
        self.items[name] = self.items.get(name, 0) + qty

    def remove(self, name, qty=None):
        """Remove qty units (or the whole item when qty is None). Missing items are ignored."""
        if qty is None:
            del self.items[name]
            return
        self.items[name] -= qty
        if self.items[name] < 0:
            del self.items[name]

    def total(self):
        return sum(self.items.values())

    def names(self):
        return sorted(self.items)
