import logging
import sys
from pathlib import Path

from ..psf_dir import PsfDir
from ..psfbin import PsfBinFile


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) < 2:
        path = Path(".")
    else:
        path = Path(sys.argv[1])

    if path.is_dir():
        PsfDir(path)
    elif path.is_file():
        PsfBinFile(path)
    else:
        print(f"File/directory not found: {path}")


if __name__ == "__main__":
    main()
