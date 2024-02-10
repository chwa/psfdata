import itertools
import logging
import typing
from pathlib import Path

from pypsf.psfascii import PsfAsciiFile

from . import PsfFile

logger = logging.getLogger(__name__)


class PsfDir:
    def __init__(self, path: Path) -> None:
        self._path = path.absolute()
        logfile_path = self._path / "logFile"
        if not logfile_path.is_file():
            raise FileNotFoundError(f"{logfile_path}")
        logger.info(f"Reading {logfile_path}")
        self._logfile = typing.cast(PsfAsciiFile, PsfFile.load(logfile_path))

        logger.info("HEADER:")
        for k, v in self._logfile.header.items():
            logger.info(f"    {k:22}: {v}")

        logger.info("")
        logger.info("AVAILABLE DATA FILES:")

        for name, item in self._logfile._values.items():
            logger.info(f"{name}:")
            for k, v in itertools.islice(item.items(), 40):
                logger.info(f"    {k:22}: {v}")

    def get_analysis(self, name: str) -> PsfFile:
        item = self._logfile._values[name]
        filename = item["dataFile"]

        return PsfFile.load(self._path / filename)
