import logging
from itertools import islice
from pathlib import Path

import matplotlib
from matplotlib import pyplot as plt

from psfdata import PsfFile

matplotlib.use('qtagg')


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)-7s] [%(name)-18s %(lineno)4d] %(message)s")

    fn = Path("private_examples/dc.dc")
    fn = Path("private_examples/dcswp.dc")
    fn = Path("private_examples/psf_dcsweep_tran/tran.tran.tran")
    fn = Path("private_examples/psf_afs_tran/tran.tran")
    fn = Path("private_examples/psf_spectre_ac/ac.ac")
    fn = Path("private_examples/psf_dcsweep_tran/dc.dc")
    fn = Path("private_examples/psfxl_tran_1signal/tran.tran.tran")
    fn = Path("private_examples/psfxl_large/tran.tran.tran")
    fn = Path("private_examples/psf_medusa_dc/allParams.info.allparameters")
    fn = Path("private_examples/psf_4G/tran.tran.tran")

    psf = PsfFile.load(fn)

    print('\n\n')
    print(type(psf))
    print("\n")

    psf.print_info()
    print("\nheader:")
    print(psf.header)
    print("\nsweep_info:")
    print(psf.sweep_info)
    print("\nnames:")
    print(psf.names)
    print("\nsignal_info:")
    print(psf.signal_info(psf.names[0]))

    print()
    if psf.sweep_info is not None:
        for name in psf.names[:5]:
            wfm = psf.get_signal(name)
            print(wfm)
            wfm.plot()

        plt.show()
    else:
        for name in psf.names[:5]:
            signal = psf.get_signal(name)
            if isinstance(signal, dict):
                print(name)
                for k, v in islice(signal.items(), 5):
                    print(f"    {k} {v}")
            else:
                print(f"{name:<20} = {signal}")


if __name__ == "__main__":
    main()
