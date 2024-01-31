import itertools
import logging
from pathlib import Path

from pypsf.psfbin import PsfBinFile

from .logfile import PsfAsciiFile, read_asciipsf

logger = logging.getLogger(__name__)


class PsfDir:
    def __init__(self, path: Path) -> None:
        self._path = path.absolute()
        logfile = self._path / "logFile"
        logger.info(f"Reading {logfile = }")
        self.header, self._result = read_asciipsf(logfile)

        logger.info("HEADER:")
        for k, v in self.header.items():
            logger.info(f"    {k:22}: {v}")

        logger.info("")
        logger.info("AVAILABLE DATA FILES:")

        for name, item in self._result.items():
            logger.info(f"{name}:")
            for k, v in itertools.islice(item[1].as_dict().items(), 40):
                logger.info(f"    {k:22}: {v}")

    def get_analysis(self, name: str) -> PsfBinFile | PsfAsciiFile:
        item = self._result[name]
        item_dict = item[1].as_dict()
        type = item_dict["analysisType"]
        filename = item_dict["dataFile"]

        return PsfBinFile(self._path / filename)
