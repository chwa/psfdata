import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .memview import MemoryViewAbs
from .psf import PsfFile
from .psfbin_sections import (HeaderSection, SectionType, SimpleValueSection, SweepSection, SweepValueSection,
                              TraceSection, TypeSection)
from .psfbin_types import DataType
from .psfxl import DataBuffer, read_xl_signal
from .waveform import Waveform

logger = logging.getLogger(__name__)


@dataclass
class SectionInfo:
    type: SectionType
    offset: int
    size: int


class PsfBinFile(PsfFile):
    def __init__(self, path: Path) -> None:
        logger.info(f"Loading PSF file: {path}")
        self._header: dict[str, Any] = {}
        self.is_sweep: bool = False
        self._value_section = None

        self._path = path

        with open(path, "rb") as f:
            self._data = MemoryViewAbs(f.read())
        logger.info(f"Size is {len(self._data)} bytes.")

        valid_signatures = [
            0x200,   # monte carlo sweep/index?
            0x300,
            0x400,  # normal PSF
            0x500,  # element.info?
        ]
        signature = self._data.read_int32(peek=True)
        assert signature in valid_signatures

        self._toc: dict[SectionType, SectionInfo] = {}
        if self._validate(self._data.data):
            self._read_toc()
            self.is_psfxl_index = False
        else:
            logger.info(f"No TOC found, assuming this is a PSFXL index file.")
            self.is_psfxl_index = True

        self._read_header()
        self._read_defs()
        if not self.is_psfxl_index:
            self._read_traces()

    def __str__(self) -> str:
        cl = self.__class__.__name__

        if self.is_psfxl_index:
            s = f"{cl}:{self._path.name}: PSF-XL index file"
        else:
            s = f"{cl}:{self._path.name}: {len(self.names)} signals"
        if self.is_sweep:
            s += f" (sweep: {self._npoints} points)"
        return s

    @property
    def header(self) -> dict[str, Any]:
        return self._header

    @property
    def sweep_info(self) -> dict[str, Any]:
        if self._sweep_section is None:
            return {}
        sweeps = self._sweep_section.sweeps
        assert len(sweeps) == 1
        data_type = next(iter(sweeps.values()))
        info = data_type.properties.copy()
        info['name'] = data_type.name
        return info

    @property
    def names(self) -> list[str]:
        if SectionType.TRACE in self._toc:
            return [t.name for t in self._trace_section.flattened()]
        else:
            if isinstance(self._value_section, SimpleValueSection):
                return [t.name for t in self._value_section.traces.values()]
            else:
                return list(self._trace_section.traces_by_name.keys())

    def signal_info(self, name: str) -> dict[str, Any]:
        if self.is_sweep:
            for t in self._trace_section.flattened():
                if t.name == name:
                    if t.ref is None:
                        return {}
                    info = t.ref.properties.copy()
                    info['NAME'] = t.ref.name
                    return info
            raise ValueError(f"{name} not Found")
        else:
            if isinstance(self._value_section, SimpleValueSection):
                return self._value_section.traces_by_name[name].ref
            else:
                return self._trace_section.traces_by_name[name]

    def get_signal(self, name: str) -> Waveform | dict:
        if self.is_psfxl_index:
            fn = Path(self._path.parent / (self._path.name+".psfxl"))
            with open(fn, 'rb') as f:
                rdr = DataBuffer(f)
            psfxl_idx = self._trace_section.traces_by_name[name].properties['psfxl_idx']
            assert isinstance(psfxl_idx, tuple)
            assert isinstance(psfxl_idx[1], int)
            wfm = read_xl_signal(rdr, psfxl_idx[1])
            wfm.name = name
            return wfm
        elif self.is_sweep:
            xunits = self.sweep_info.get('units', '-')
            info = self.signal_info(name)
            yunits = info.get('units', '-')
            wfm = Waveform(self._swept_values, xunits, self._trace_values[name], yunits, name)
            return wfm
        else:
            return self._value_section.traces_by_name[name].value

    def get_signals(self, names: Iterable[str]) -> dict[str, Waveform]:
        if self.is_psfxl_index:
            fn = Path(self._path.parent / (self._path.name+".psfxl"))
            with open(fn, 'rb') as f:
                rdr = DataBuffer(f)

            result = {}
            for name in names:
                psfxl_idx = self._trace_section.traces_by_name[name].properties['psfxl_idx']
                assert isinstance(psfxl_idx, tuple)
                assert isinstance(psfxl_idx[1], int)
                wfm = read_xl_signal(rdr, psfxl_idx[1])
                wfm.name = name
                result[name] = wfm

            return result
        else:
            return {}

    @staticmethod
    def _validate(data: memoryview) -> bool:
        return data[-12:-4].tobytes() == b"Clarissa"

    def _read_toc(self):
        logger.info("Read table of contents...")
        # last int32 is the combined size of the sections, excluding the TOC
        datasize = self._data.get_int32(-4)
        # TOC is a number of 8-byte blocks following the last section,
        # and before the 12-byte footer:
        nsections = (self._data.abspos + len(self._data) - 12 - datasize) // 8
        toc_start = (len(self._data) - 12 - 8 * nsections)

        types = []
        offsets = []
        for s in range(nsections):
            types.append(self._data.get_int32(toc_start + 8 * s))
            offsets.append(self._data.get_int32(toc_start + 8*s + 4))
        offsets.append(toc_start)

        logger.info("Sections are:")
        for s in range(nsections):
            t = SectionType(types[s])
            self._toc[t] = SectionInfo(t, offsets[s], offsets[s+1] - offsets[s])

            logger.info(f"    {self._toc[t]}")

    def _read_header(self) -> None:
        if self.is_psfxl_index:
            header_section = HeaderSection(self._data[4:])
        else:
            s = self._toc[SectionType.HEADER]
            header_section = HeaderSection(self._data[s.offset:s.offset+s.size])
        self._rest = header_section._tail
        self._header = header_section.props
        self.is_sweep = self._header["PSF sweeps"] != 0
        self._npoints = self._header["PSF sweep points"]
        self._is_windowed = "PSF window size" in self._header

    def _read_defs(self) -> None:
        """Read type/sweep/trace sections"""

        if self.is_psfxl_index:
            self._type_section = TypeSection(self._rest)
        else:
            s = self._toc[SectionType.TYPE]
            self._type_section = TypeSection(self._data[s.offset:s.offset+s.size])

        self._rest = self._type_section._tail

        self._sweep_section = None
        if self.is_sweep:
            if self.is_psfxl_index:
                self._sweep_section = SweepSection(self._rest, self._type_section.dtypes)
            else:
                s = self._toc[SectionType.SWEEP]
                self._sweep_section = SweepSection(self._data[s.offset:s.offset+s.size], self._type_section.dtypes)
            self._rest = self._sweep_section._tail

        if self.is_psfxl_index:
            self._trace_section = TraceSection(self._rest, self._type_section.dtypes)
        elif SectionType.TRACE in self._toc:
            s = self._toc[SectionType.TRACE]
            self._trace_section = TraceSection(self._data[s.offset:s.offset+s.size], self._type_section.dtypes)

    def _read_traces(self) -> None:
        """Read ValueSection"""
        s = self._toc[SectionType.VALUE]
        data = self._data[s.offset:s.offset+s.size]
        if self.is_sweep:
            assert self._sweep_section is not None
            self._value_section = SweepValueSection(data, self._sweep_section, self._trace_section,
                                                    is_windowed=self._is_windowed)

            if self._value_section.endpos == 0xFFFFFFFF:
                return

            self._swept_values, self._trace_values = self._value_section.get_data(self._npoints)
        else:
            self._value_section = SimpleValueSection(data, self._type_section.dtypes)
