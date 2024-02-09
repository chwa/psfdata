import string
from itertools import islice


def batched(iterable, n):
    """Like itertools.batched in Python 3.12"""
    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch


def hexprint(data: bytearray, maxlines=5) -> None:
    print("-".join(f"{b:02x}" for b in range(16)))

    def prnt(code):
        s = chr(code)
        if s in string.printable and s not in string.whitespace:
            return s
        else:
            return "."

    for line, word in enumerate(batched(data, 16)):
        if line == maxlines:
            break
        s = " ".join(f"{b:02x}" for b in word) + "   "
        s += " ".join(prnt(b) for b in word) + " "

        print(s)
