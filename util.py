import string
from pathlib import Path

import blosc
import numpy as np

from pypsf.memview import batched


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
