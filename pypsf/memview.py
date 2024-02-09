import struct
from typing import Self

from .util import hexprint


class MemoryViewAbs:
    """memoryview class that keeps track of its offset relative to the original bytes object on which it is based.
    Needed because PSF uses absolute file positions for block start/end."""

    def __init__(self, data: bytes | memoryview, _abspos: int = 0) -> None:
        self._mv = memoryview(data)
        self._abspos = _abspos  # offset of self._mv in the original bytes object

    def __getitem__(self, key) -> Self:
        if isinstance(key, slice):
            newpos = self._abspos + key.indices(len(self._mv))[0]
            return self.__class__(self._mv[key], newpos)
        else:
            raise KeyError("Only slices allowed")

    def __len__(self) -> int:
        return len(self._mv)

    def split_at_absolute(self, abs_pos: int) -> tuple[Self, Self]:
        rel_pos = abs_pos - self._abspos
        assert 0 <= rel_pos <= len(self)
        return (self.__class__(self._mv[:rel_pos], self._abspos),
                self.__class__(self._mv[rel_pos:], self._abspos + rel_pos))

    @property
    def data(self) -> memoryview:
        return self._mv

    @property
    def abspos(self) -> int:
        return self._abspos

    def get_int32(self, pos: int) -> int:
        """Read int at position pos (without consuming it)"""
        if pos < 0:
            pos += len(self.data)
        return int.from_bytes(self._mv[pos: pos + 4])

    def _consume(self, n: int) -> None:
        self._mv = self._mv[n:]
        self._abspos += n

    # TODO: in all of these, check that the correct number of bytes were read (and no EOF occurred):

    def read_bytes(self, n, peek=False) -> bytes:
        """Consume and return N bytes"""
        data = bytes(self._mv[:n])
        if not peek:
            self._consume(n)
        return data

    def read_int8(self, peek=False) -> int:
        """Consume 1 byte and return int."""
        value = int.from_bytes(self._mv[:])
        if not peek:
            self._consume(1)
        return value

    def read_int32(self, peek=False) -> int:
        """Consume 4 bytes and return int."""
        value = int.from_bytes(self._mv[:4])
        if not peek:
            self._consume(4)
        return value

    def read_double(self, peek=False) -> float:
        """Consume 8 bytes and return float."""
        value = struct.unpack(">d", self._mv[:8])[0]
        if not peek:
            self._consume(8)
        return value

    def read_cdouble(self) -> float:
        """Consume 16 bytes and return cdouble."""
        raise NotImplementedError()

    def read_string(self) -> str:
        """Consume 4 + length bytes and return string."""
        length = self.read_int32()
        string = bytes(self._mv[:length]).decode()

        pad = ((4 - length) & 3)  # align to 4-byte boundary
        self._consume(length + pad)

        return string

    def hexprint(self, maxlines=5) -> None:
        hexprint(self._mv, maxlines)
