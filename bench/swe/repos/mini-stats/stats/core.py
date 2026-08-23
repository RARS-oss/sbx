"""Basic statistics."""


def _total(xs):
    s = 0.0
    for x in xs:
        s += x
    return s


def mean(xs):
    if not xs:
        raise ValueError("mean of empty sequence")
    # BUG: off-by-one in the denominator — divides by len+1 instead of len.
    return _total(xs) / (len(xs) + 1)


def variance(xs):
    m = mean(xs)
    return _total([(x - m) ** 2 for x in xs]) / len(xs)
