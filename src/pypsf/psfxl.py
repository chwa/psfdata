import re
import struct
from io import BufferedReader

import blosc  # type: ignore
import numpy as np

"""
PSF-XL compressed binary format
===============================

The tran.tran.tran file is more or less a regular PSF binary file, although it is missing value section and TOC.
Each entry in the trace section has a special nameless property identified by the type 0x24, followed by
4xint32, 4xdouble, which stand for
(idx, file_offset, point_start, npoints, tstart, tend, vmin, vmax)

The 'file_offset' values are used to find the actual waveform data in the *.psfxl file.
They point to markers which look like this:

"\03:1:ffffffffffffffff:201:151:a2:199c.d63:151\0"

(colon-separated string of hex characters, beginning and ending with a null character)

2) [0, 1, 2...] is the signal index (nth element of the group) ?
3) [fffff..] position of the previous chunk (-1 for first chunk)
4) [201] is the number of transient points (in this chunk)
5) is the size of the following binary chunk.
   For signals of type 0x22 (x+y), the combined (compressed) size of x and y vectors
6) Chunk type:
   - 0xa2 = blosc compressed data chunk
   - 0xa0 = single (literal) value or uncompressed values
   - 0x20 = what what? single value PLUS x data ?
   - 0x22 x+y (first) signal

Rest: file offsets for reading the x and y chunks:
   a0 is followed by xoffset[?].xlen (the y value is the 8-byte value at the next 8-byte boundary)
   a2 is followed by xoffset[?].xlen:ylen (the y chunk starts at the next 8-byte boundary)
   22 is followed by xlen:ylen (x chunk starts at the next 8-byte boundary, the y chunk 'xlen' bytes after that)

following the header, at the next 8byte boundary is the start of a blosc chunk starting with either

02 01 01 08  or
02 01 11 08

followed by 3x int32(LE) for nbytes, blocksize, cbytes

(https://www.blosc.org/c-blosc2/format/chunk_format.html)


"""

xl_marker = re.compile(
    "3:(?P<idx>[0-9a-f]+):"
    "(?P<previous>[0-9a-f]+):"
    "(?P<npoints>[0-9a-f]+):"
    "(?P<csize>[0-9a-f]+):"
    "(?P<type>[0-9a-f]+):"
    "(?:(?P<xoffset>[0-9a-f]+)\\.)?"
    "(?P<xlen>[0-9a-f]+)"
    "(?::(?P<ylen>[0-9a-f]+))?"
)


def hex2signed(h: str) -> int:
    assert len(h) <= 16
    h = h.rjust(16, '0')
    return int.from_bytes(bytes.fromhex(h), signed=True)


class DataBuffer:
    def __init__(self, f: BufferedReader):
        self._data = f.read()
        self._pos = 0

    def seek(self, pos: int):
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def read(self, nbytes: int) -> bytes:
        d = self._data[self._pos: self._pos+nbytes]
        self._pos += nbytes
        return d


def read_xl_chunk(f: DataBuffer, offset: int):
    f.seek(offset + 1)
    desc_str = ""
    while (c := f.read(1)) != b'\0':
        desc_str += c.decode()
    desc_str = desc_str.rstrip('\n')

    m = xl_marker.match(desc_str)
    if m is None:
        raise ValueError(f"Invalid chunk marker: {desc_str}")
    chunk_props: dict[str, int] = {k: hex2signed(v) for k, v in m.groupdict().items() if v is not None}

    # value start is at next word boundary
    value_start = 8*((f.tell()+7) // 8)

    # READ X VECTOR
    if 'xoffset' in chunk_props:
        x_start = offset - chunk_props['xoffset']
    else:
        x_start = value_start

    # print(f"X starts at {x_start}")
    f.seek(x_start)
    x_bytes = f.read(chunk_props['xlen'])
    x_uncomp = blosc.decompress(x_bytes, as_bytearray=True)
    x_value = np.frombuffer(x_uncomp, dtype='float')
    # print(f"x = {x_value} ({len(x_value)})")

    # READ Y VECTOR (or single value)
    f.seek(value_start)
    if chunk_props['type'] == 0xa0:
        if chunk_props['csize'] == 8:
            y_value, = struct.unpack('d', f.read(8))
        else:
            y_bytes = f.read(chunk_props['csize'])
            y_value = np.frombuffer(y_bytes, dtype='float')
            # print(f">>> special y data: {y_value}")
            # print(f">>> for x values: {x_value}")
    else:
        y_start = value_start
        if chunk_props['type'] in [0x22]:
            y_start += chunk_props['xlen']
        # print(f"Y starts at {y_start}")
        f.seek(y_start)
        if chunk_props['type'] in [0x22, 0xa2]:
            y_bytes = f.read(chunk_props['ylen'])
        else:
            y_bytes = f.read(chunk_props['xlen'])
        try:
            y_uncomp = blosc.decompress(y_bytes, as_bytearray=True)
        except:
            print(f"{hex(len(y_bytes))}")
            # l = 8*(len(y_bytes) // 8)
            # l = chunk_props['npoints']
            # l = 124
            print(np.frombuffer(y_bytes[:64], dtype='float'))
            # hexprint(bytearray(y_bytes))
            # print(l)
            raise
        y_value = np.frombuffer(y_uncomp, dtype='float')

    # print(f"y = {y_value} ({len(y_value)})")
    nextpos = chunk_props['previous']

    return x_value, y_value, nextpos


def read_xl_signal(f: DataBuffer, offset: int):
    nextpos = offset
    xs = []
    ys = []
    i = 0

    while nextpos != -1:
        x, y, nextpos = read_xl_chunk(f, nextpos)
        xs.append(x)
        ys.append(y)
        i += 1
        # if i > 1000:
        # break
    print(f"read {i} chunks")
    x = np.concatenate(list(reversed(xs)))
    y = np.concatenate(list(reversed(ys)))
    from pypsf import Waveform
    wfm = Waveform(x, 's', y, 'V')
    return wfm
