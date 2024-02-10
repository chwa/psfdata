import logging
import sys
from pathlib import Path

from pypsf import PsfDir

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="[%(levelname)-7s] [%(name)-18s %(lineno)4d] %(message)s")

    psf_dir = PsfDir(Path(sys.argv[1]))

    analysis = psf_dir.get_analysis('tran-tran')
    print(analysis)
