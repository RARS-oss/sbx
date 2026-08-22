"""Merge inclusive integer ranges."""


def merge(ranges):
    """Return the minimal sorted list of non-overlapping inclusive ranges covering `ranges`.

    Touching ranges are merged: (1, 3) + (4, 6) -> (1, 6).
    """
    if not ranges:
        return []
    rs = sorted((int(lo), int(hi)) for lo, hi in ranges)
    out = [rs[0]]
    for lo, hi in rs[1:]:
        cur_lo, cur_hi = out[-1]
        if lo <= cur_hi + 1:
            out[-1] = (cur_lo, max(cur_hi, hi))
        else:
            out.append((lo, hi))
    return out


def covered(ranges):
    """Number of integers covered by the merged ranges."""
    return sum(hi - lo + 1 for lo, hi in merge(ranges))
