import logging
from pathlib import Path

import matplotlib
from matplotlib import pyplot as plt

from pypsf import PsfDir, PsfFile

# matplotlib.use('qtagg')


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)-7s] [%(name)-18s %(lineno)4d] %(message)s")

    # fn = Path("examples/frequencySweep")
    fn = Path("examples/simpledc2.dc")
    fn = Path("examples/abc.tran.tran")
    # fn = Path("examples/mc1_dc.montecarlo")
    fn = Path("psf_examples/psf_dcsweep_tran/tran.tran.tran")
    # fn = Path("examples/simpledc2.dc")
    # fn = Path("psf_examples/psf_afs_tran/tran.tran")
    # fn = Path("psf_examples/psf_spectre_ac/ac.ac")
    # fn = Path("private_examples/frequencySweep")
    # fn = Path("private_examples/psfxl_tran_1signal/tran.tran.tran")
    # fn = Path("private_examples/psfxl_large/tran.tran.tran")
    # fn = Path("private_examples/dcswp.dc")
    # psf = PsfFile.load("private_examples/psf_dcsweep_tran/tran.tran.tran")
    fn = Path("private_examples/psf_medusa_dc/allParams.info.allparameters")
    fn = Path("private_examples/dc.dc")

    psf = PsfFile.load(fn)
    print(f"{psf.names=}")
    print(f"{psf.signal_info('M1:ids')}")

    exit()

    psf_dir = PsfDir(fn.parent)
    psf = psf_dir.get_analysis("subckts-info.subckts")
    psf.print_info()
    print()
    exit()

    psf.print_info()
    psf.header
    psf.names
    psf.sweep_info
    wfm = psf.get_signal('vpcb')

    wfm.plot()
    plt.show()


if __name__ == "__main__":
    main()
