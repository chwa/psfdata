from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import islice
from typing import Any, Generator

import numpy as np

from pypsf.waveform import Waveform

from .memview import MemoryViewAbs
from .psfbin_types import (Group, SignalDef, TypeDef, get_complex_dtype, read_properties, read_signaldef, read_typedef,
                           read_value_entry)

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
        typedata, indexdata = self._data.split_at_absolute(indexpos)

        self.typedefs: dict[int, TypeDef] = {}
        self.read_typedefs(typedata)

        for v in self.typedefs.values():
            logger.info(f"    {v}")
            if v.struct_members is not None:
                for c in v.struct_members[:10]:
                    logger.info(f"        {c}")
                if len(v.struct_members) > 10:
                    logger.info(f"        ...")

        self.index = Index(indexdata)

    def read_typedefs(self, data: MemoryViewAbs) -> None:
        while len(data):
            next = data.read_int32(peek=True)
            match next:
                case 0x03:
                    return  # TODO... does this mean anything?
                case 0x10 | 0x11:
                    element = read_typedef(data)
                    self.typedefs[element.id] = element
                case _:
                    raise ValueError(f"Unknown DataType starting with: {next=}")


class SweepSection(Section):
    def __init__(self, data: MemoryViewAbs, typedefs: dict[int, Any]) -> None:
        super().__init__(data)

        # # discard anything past endpos (TBC):
        # self._data = self._data[:self._data.abspos + endpos]

        self.sweep_def: SignalDef = read_signaldef(self._data, typedefs)
        # TODO: check if more than one sweep ?

        logger.info(f"    {self.sweep_def}")


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

    def __init__(self, data: MemoryViewAbs, typedefs: dict[int, TypeDef]) -> None:
        super().__init__(data)

        section_type = self._data.read_int32()
        assert section_type == 22

        indexpos = self._data.read_int32()  # start of the section index
        tracedata, indexdata = self._data.split_at_absolute(indexpos)

        self.traces: dict[int, SignalDef | Group] = {}
        self.traces_by_name: dict[str, SignalDef] = {}
        while len(tracedata):
            next = tracedata.read_int32(peek=True)
            match next:
                case 0x03:
                    break  # TODO... does this mean anything?
                case 0x10 | 0x11:
                    signaldef = read_signaldef(tracedata, typedefs=typedefs)
                    self.traces[signaldef.id] = signaldef

                    # TODO: do we really want to flatten groups
                    if isinstance(signaldef, Group):
                        for c in signaldef.children:
                            self.traces_by_name[c.name] = c
                    else:
                        self.traces_by_name[signaldef.name] = signaldef
                case _:
                    raise ValueError(f"Unknown DataType starting with: {next=}")

        self.index = TraceIndex(indexdata)

        for k, v in self.traces_by_name.items():
            logger.info(f"    {str(v)[:100]}")
            if isinstance(v, Group):
                for c in v.children:
                    logger.info(f"        {str(c)[:96]}")

    def flattened(self) -> Generator[SignalDef, None, None]:
        for dt in self.traces.values():
            if isinstance(dt, Group):
                yield from dt.children
            else:
                yield dt


class ValueSection(Section):
    def __init__(self, data: MemoryViewAbs) -> None:
        super().__init__(data)

        self._names: list[str] = []

    @property
    def sweep_info(self) -> dict[str, Any] | None:
        return None

    @property
    def names(self) -> list[str]:
        return self._names

    @abstractmethod
    def get_signal(self, name: str) -> Waveform | dict:
        raise NotImplementedError()


class SimpleValueSection(ValueSection):
    def __init__(self, data: MemoryViewAbs, typedefs: dict[int, TypeDef]) -> None:
        super().__init__(data)

        section_type = self._data.read_int32()
        assert section_type == 22

        indexpos = self._data.read_int32()  # start of the section index

        valuedata, indexdata = self._data.split_at_absolute(indexpos)

        self.values: dict[str, int | float | dict] = {}

        while len(valuedata):
            next = valuedata.read_int32(peek=True)
            match next:
                case 0x03:
                    break  # TODO... does this mean anything?
                case 0x10 | 0x11:
                    id, name, value, properties = read_value_entry(valuedata, typedefs)
                    self.values[name] = value
                case _:
                    raise ValueError(f"Unknown DataType starting with: {next=}")

        for k, v in islice(self.values.items(), 10):
            logger.info(f"    {k} = {str(v)[:60]}")
        if len(self.values) > 10:
            logger.info(f"    ...")

    def get_signal(self, name: str) -> int | float | dict:
        return self.values[name]


class SweepValueSection(ValueSection):
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
            self.complex_dtype = get_complex_dtype(self.dt_pos, sweep_section.sweep_def, trace_section.traces)

    def get_signal(self, name: str) -> Waveform:
        if self._sweep_signal is None or self._signals is None:
            self._sweep_signal, self._signals = self.get_data(npoints=99999999)  # TODO
        return Waveform(self._sweep_signal, "x", self._signals[name], "y")  # TODO

    def get_data(self, npoints: int):
        # this is for sweep data only
        swept_values = np.zeros(npoints)
        trace_values = {}
        for trace in self._trace_section.flattened():
            assert isinstance(trace, SignalDef)
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

                dtype = self._sweep_section.sweep_def.dtype
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
            dtype = self.complex_dtype
            array = np.frombuffer(
                self._data.data, count=len(self._data) // dtype.itemsize, dtype=dtype)

            swept_name = self._sweep_section.sweep_def.name
            trace_names = list(self._trace_section.traces_by_name.keys())
            swept_values = array[swept_name]
            trace_values = {n: array[n] for n in trace_names}  # TODO complicated...

        return swept_values, trace_values
