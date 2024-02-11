import logging
import typing
from pathlib import Path
from sys import getsizeof

import matplotlib
from matplotlib import pyplot as plt

from pypsf import PsfDir, PsfFile
from pypsf.psfbin import PsfBinFile

matplotlib.use('qtagg')


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)-7s] [%(name)-18s %(lineno)4d] %(message)s")

    # fn = Path("examples/frequencySweep")
    fn = Path("private_examples/dc.dc")
    # fn = Path("examples/abc.tran.tran")
    # fn = Path("examples/mc1_dc.montecarlo")
    fn = Path("private_examples/psf_dcsweep_tran/tran.tran.tran")
    # fn = Path("examples/simpledc2.dc")
    # fn = Path("psf_examples/psf_afs_tran/tran.tran")
    # fn = Path("private_examples/psf_spectre_ac/ac.ac")
    # fn = Path("private_examples/frequencySweep")
    # fn = Path("private_examples/psf_dcsweep_tran/dc.dc")
    fn = Path("private_examples/psfxl_tran_1signal/tran.tran.tran")
    # fn = Path("private_examples/psfxl_large/tran.tran.tran")
    # fn = Path("private_examples/dcswp.dc")
    # fn = Path("private_examples/psf_medusa_dc/allParams.info.allparameters")
    # fn = Path("private_examples/dc.dc")
    # fn = Path("private_examples/psf_4G/tran.tran.tran")
    # psf = typing.cast(PsfBinFile, PsfFile.load(fn))

    psf = PsfFile.load(fn)

    print(psf.sweep_info)
    for name in psf.names:
        wfm = psf.get_signal(name)
        print(wfm)
        wfm.plot()

    plt.show()

    # psf_dir = PsfDir(fn.parent)
    # psf = psf_dir.get_analysis("subckts-info.subckts")
    # psf.print_info()
    # print()
    # exit()

    # psf.print_info()
    # psf.header
    # psf.names
    # psf.sweep_info
    # wfm = psf.get_signal('vpcb')

    # wfm.plot()
    # plt.show()


if __name__ == "__main__":
    main()
