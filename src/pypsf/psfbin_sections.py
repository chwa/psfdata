from __future__ import annotations

import logging
from abc import ABC
from collections import defaultdict
from itertools import islice
from typing import Any, Generator

import numpy as np

from .memview import MemoryViewAbs
from .psfbin_defs import SectionType
from .psfbin_types import DataType, read_datatypes, read_properties

logger = logging.getLogger(__name__)


class Index:
    """TypeSection has an index at the end - not strictly necessary"""

    def __init__(self, data: MemoryViewAbs):
        type = data.read_int32()
        assert type == 0x13

        size = data.read_int32()
        endpos = data.abspos + size

        self.table = {}

        while data.abspos < endpos:
            id = data.read_int32()
            pos = data.read_int32()
            self.table[id] = pos

    def __str__(self) -> str:
        return f"Index: {self.table}"


class Section(ABC):
    def __init__(self, data: MemoryViewAbs) -> None:
        t = data.read_int32()

        self.endpos = data.read_int32()

        classname = self.__class__.__name__
        logger.info("")
        logger.info(f"{classname} starting at {hex(data.abspos)}, ending at {hex(self.endpos)}  ({t=:#x}):")
        assert t == 21
        self._data, self._tail = data.split_at_absolute(self.endpos)


class HeaderSection(Section):
    def __init__(self, data: MemoryViewAbs) -> None:
        super().__init__(data)

        self.props = read_properties(self._data)
        for k, v in self.props.items():
            logger.info(f"    {k}: {v}")


class TypeSection(Section):
    def __init__(self, data: MemoryViewAbs) -> None:
        super().__init__(data)

        section_type = self._data.read_int32()
        assert section_type == 22

        indexpos = self._data.read_int32()  # start of the section index

        self._data, indexdata = self._data.split_at_absolute(indexpos)

        self.dtypes = read_datatypes(self._data)
        for v in self.dtypes.values():
            logger.info(f"    {v}")
            for c in v.children[:10]:
                logger.info(f"        {c}")
            if len(v.children) > 10:
                logger.info(f"        ...")

        self.index = Index(indexdata)


class SweepSection(Section):
    def __init__(self, data: MemoryViewAbs, typedefs: dict[int, Any]) -> None:
        super().__init__(data)

        # # discard anything past endpos (TBC):
        # self._data = self._data[:self._data.abspos + endpos]

        self.sweeps = read_datatypes(self._data, typedefs=typedefs)
        for v in self.sweeps.values():
            logger.info(f"    {v}")


class TraceIndex:
    def __init__(self, data: MemoryViewAbs):
        self.type = data.read_int32()
        assert self.type == 0x13

        self.size = data.read_int32()
        endpos = data.abspos + self.size

        self.table = defaultdict(list)

        while data.abspos < endpos:
            id = data.read_bytes(4).rstrip(b'\x00').decode()
            offset = data.read_int32()
            extra1 = data.read_int32()
            extra2 = data.read_int32()
            if id:  # most entries are empty (?)
                self.table[id].append(offset)

    def __str__(self) -> str:
        return f"Index: {dict(self.table)}"


class TraceSection(Section):
    """identical to TypeSection, except datatypes are references and index is a TraceIndex..."""

    def __init__(self, data: MemoryViewAbs, typedefs: dict[int, Any]) -> None:
        super().__init__(data)

        section_type = self._data.read_int32()
        assert section_type == 22

        indexpos = self._data.read_int32()  # start of the section index

        self._data, indexdata = self._data.split_at_absolute(indexpos)

        # read datatypes or groupdefs...
        self.traces = read_datatypes(self._data, typedefs=typedefs)

        self.traces_by_name: dict[str, DataType] = {}
        for v in self.traces.values():
            grp_str = f'(Group, n={len(v.children)})'if v.is_group else ''
            logger.info(f"    Element {v.name!r} (0x{v.id:02x}) {grp_str}")
            if v.is_group:
                sub_dict = {}
                for i, c in enumerate(v.children):
                    sub_dict[c.name] = c
                    # just flatten it for now...
                    self.traces_by_name[c.name] = c
                    if i < 10:
                        logger.info(f"    - {c}")
                if len(v.children) > 10:
                    logger.info(f"    - ...")
            else:
                self.traces_by_name[v.name] = v

        self.index = TraceIndex(indexdata)

    def flattened(self) -> Generator[DataType, None, None]:
        for dt in self.traces.values():
            if dt.is_group:
                yield from dt.children
            else:
                yield dt


class SimpleValueSection(Section):
    def __init__(self, data: MemoryViewAbs, typedefs: dict[int, Any]) -> None:
        super().__init__(data)

        section_type = self._data.read_int32()
        assert section_type == 22

        indexpos = self._data.read_int32()  # start of the section index

        self._data, indexdata = self._data.split_at_absolute(indexpos)

        # read datatypes or groupdefs...
        self.traces = read_datatypes(self._data, typedefs=typedefs, with_value=True)

        self.traces_by_name: dict[str, DataType] = {}
        for v in list(self.traces.values()):
            self.traces_by_name[v.name] = v

        for k, v in islice(self.traces_by_name.items(), 10):
            logger.info(f"    {k} = {str(v.value)[:60]}")

        if len(self.traces_by_name) > 10:
            logger.info(f"    ...")

        # self.index = TraceIndex(indexdata) TODO...


class SweepValueSection(Section):
    def __init__(self, data: MemoryViewAbs, sweep_section: SweepSection, trace_section: TraceSection,
                 is_windowed=False, windowsize=4096) -> None:
        super().__init__(data)

        self._sweep_section = sweep_section
        self._trace_section = trace_section

        if self.endpos == 0xFFFFFFFF:
            logger.error("Empty ValueSection (PSFXL file?)")
            return

        self.is_windowed = is_windowed
        self.windowsize = windowsize

        self.dtype_dict: dict[str, list] = {"names": [], "formats": [], "offsets": []}
        self.dt_pos = 0

        if self.is_windowed:
            logger.warn("Windowed format, removing zero pad...")
            type = self._data.read_int32()
            assert type == 0x14
            zeropad_size = self._data.read_int32()
            logger.warn(f"...removed  {zeropad_size} bytes.")
            for i in range(zeropad_size):
                assert self._data.data[i] == 0
            self._data = self._data[zeropad_size:]
        else:
            logger.info("Non-windowed format, creating dtype dictionary")
            self._create_dtype_dict()

    def _add_single_dtype(self, dt: DataType, is_sweep: bool = False):
        dtype_dict, next_offset = dt.get_dtype_dict(self.dt_pos)

        for name, lst in self.dtype_dict.items():
            lst.extend(dtype_dict[name])

        self.dt_pos = next_offset

    def _create_dtype_dict(self):
        dt_sweep = next(iter(self._sweep_section.sweeps.values()))
        self._add_single_dtype(dt_sweep, is_sweep=True)

        for c in self._trace_section.traces.values():
            self._add_single_dtype(c)

    def get_data(self, npoints: int):
        # this is for sweep data only
        swept_values = np.zeros(npoints)
        trace_values = {}
        for trace in self._trace_section.flattened():
            assert isinstance(trace, DataType)
            trace_values[trace.name] = np.zeros(npoints)

        if self.is_windowed:
            points_read = 0
            while points_read < npoints:
                chunkt = self._data.read_int32()
                if chunkt == 0x14:
                    # chunk type  0x14 is filler (0xdead)
                    l = self._data.read_int32()
                    self._data = self._data[l:]
                    continue

                d = self._data.read_int32()
                npoints_win = d >> 16  # for example 511 for windowsize=4096 and double type
                npoints_valid = d & 0xFFFF  # i supect that is what the 2nd int16 means...

                dtype = next(iter(self._sweep_section.sweeps.values())).dtype
                dtype = dtype.newbyteorder('>')  # big endian

                data = np.frombuffer(self._data._mv, count=npoints_valid, dtype=dtype)

                swept_values[points_read:points_read+npoints_valid] = data
                self._data = self._data[npoints_win * dtype.itemsize:]

                for trace in self._trace_section.flattened():
                    self._data = self._data[8:]  # what's this extra padding? (ff ff ff ff 7f ff ff ff or similar)

                    dtype = trace.dtype
                    dtype = dtype.newbyteorder('>')  # big endian

                    data = np.frombuffer(self._data._mv, count=npoints_valid, dtype=dtype)
                    trace_values[trace.name][points_read:points_read+npoints_valid] = data
                    self._data = self._data[npoints_win * dtype.itemsize:]

                points_read += npoints_win
        else:
            dtype = np.dtype(self.dtype_dict)  # type: ignore
            array = np.frombuffer(
                self._data.data, count=len(self._data) // dtype.itemsize, dtype=dtype)

            swept_name = self.dtype_dict["names"][0]
            trace_names = self.dtype_dict["names"][1:]
            swept_values = array[swept_name]
            trace_values = {n: array[n] for n in trace_names}

        return swept_values, trace_values


_mapping = {
    SectionType.HEADER: HeaderSection,
    SectionType.TYPE: TypeSection,
    SectionType.SWEEP: SweepSection,
    SectionType.TRACE: TraceSection,
    SectionType.VALUE: SweepValueSection,
}


def new_section(type: SectionType, data: MemoryViewAbs) -> Section:
    return _mapping[type](data)
