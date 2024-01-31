from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pypsf.waveform import Waveform


class PsfFile(ABC):
    """Base class for ASCII and binary PSF files (and other file formats?)"""
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
    def get_signal(self, name: str) -> Waveform:
        ...

    @abstractmethod
    def get_signals(self, names: list[str]) -> dict[str, Waveform]:
        ...
