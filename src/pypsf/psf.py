from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .waveform import Waveform


class PsfFile(ABC):
    """Base class for ASCII and binary PSF files (and other file formats?)"""

    @staticmethod
    def load(path: Path | str) -> PsfFile:
        """
        Load a PSF (binary/ASCII) file from the given file path.
        """
        path = Path(path)
        with open(path, 'rb') as f:
            header_bytes = f.read(6)

        if header_bytes == str.encode('HEADER'):
            from pypsf.psfascii import PsfAsciiFile
            return PsfAsciiFile(path)
        else:
            from pypsf.psfbin import PsfBinFile
            return PsfBinFile(path)

    @property
    @abstractmethod
    def header(self) -> dict[str, Any]:
        ...

    @property
    @abstractmethod
    def sweep_info(self) -> dict[str, Any] | None:
        ...

    @property
    @abstractmethod
    def names(self) -> list[str]:
        ...

    @abstractmethod
    def signal_info(self, name: str) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_signal(self, name: str) -> Waveform | dict | int | float:
        ...

    def print_info(self) -> None:
        print("HEADER")
        for k, v in self.header.items():
            print(f"    {k+':':<24} {str(v)[:80]}")

        print("VALUES")
        for n in self.names:
            print(f"    {n}")
