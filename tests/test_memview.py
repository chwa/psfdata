import pytest

from pypsf.memview import MemoryViewAbs

LENGTH = 2000


@pytest.fixture
def mv():
    b = bytes([x % 256 for x in range(LENGTH)])
    return MemoryViewAbs(b)


def test_from_bytes(mv: MemoryViewAbs):
    assert len(mv) == LENGTH


def test_slice(mv: MemoryViewAbs):
    start = LENGTH // 4
    stop = LENGTH // 3
    mv_sliced = mv[start:stop]
    assert len(mv_sliced) == stop-start
    assert mv_sliced.abspos == mv.abspos + start
    assert mv_sliced.data == mv.data[start:stop]


def test_split_at(mv: MemoryViewAbs):
    mv1, mv2 = mv.split_at_absolute(LENGTH//2)

    assert len(mv1) == LENGTH//2
    assert len(mv1) + len(mv2) == LENGTH
    assert mv1.abspos == mv.abspos
    assert mv2.abspos == mv.abspos + LENGTH//2


def test_getint(mv: MemoryViewAbs):
    assert mv.get_int32(pos=1) == 16909060


def test_read_string():
    b = b"\0\0\0\x12Yes, i'm a string."
    mv = MemoryViewAbs(b)
    assert len(mv) == 22
    assert mv.read_string() == "Yes, i'm a string."


def test_read_bad_string_length():
    b = b"\0\0\0\x33Yes, i'm a string."
    mv = MemoryViewAbs(b)
    with pytest.raises(ValueError):
        mv.read_string()


def test_read_bad_string_data():
    b = b"\0\0\0\x12Yes, \xFF'm a string."
    mv = MemoryViewAbs(b)
    with pytest.raises(UnicodeDecodeError):
        mv.read_string()


def test_hexprint(mv: MemoryViewAbs):
    mv.hexprint(maxlines=7)
