import logging
import struct
import time
from pathlib import Path

import blosc
import numpy as np
from matplotlib import pyplot as plt

from pypsf import PsfBinFile
from pypsf.psfxl import FakeBufferedReader, read_xl_signal
from util import hexprint

np.set_printoptions(threshold=10)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)-7s] [%(name)-18s %(lineno)4d] %(message)s")

    # fn = Path("examples/frequencySweep")
    fn = Path("examples/simpledc2.dc")
    fn = Path("examples/abc.tran.tran")
    # fn = Path("examples/mc1_dc.montecarlo")
    fn = Path("psf_examples/psf_dcsweep_tran/tran.tran.tran")
    # fn = Path("psf_examples/psf_dcsweep_tran/dc.dc")
    # fn = Path("psf_examples/psf_dcsweep_tran/element.info")
    # fn = Path("psf_examples/psf_dc/dcOp.dc")
    # fn = Path("psf_examples/psf_dc/dcOpInfo.info")
    # fn = Path("psf_examples/psf_medusa_dc/dcOpInfo.info")
    fn = Path("psf_examples/psf_sparam/tran.tran.tran")
    # fn = Path("psf_examples/dc.dc")
    # fn = Path("examples/element.info")
    # fn = Path("psf_examples/result/ac.ac")
    # fn = Path("psf_examples/psfxl_tran_1signal/tran.tran.tran")
    # fn = Path("examples/bcd.tran.tran")
    # fn = Path("examples/abc.tran.tran")
    # fn = Path(r"\\winlnx\walter\psf_examples\psfxl_large\tran.tran.tran")
    # fn = Path("examples/simpledc2.dc")
    # fn = Path("psf_examples/psf_afs_tran/tran.tran")
    # fn = Path("psf_examples/psf_spectre_ac/ac.ac")
    # fn = Path("examples/frequencySweep")

    psf = PsfBinFile(fn)

    print(f"{psf.header = }")
    print(f"{psf.sweep_info = }")
    print(f"{psf.names = }")
    print(f"{psf.get_signal(psf.names[0]) = }")

    print("=====================================================")
    print("PSF summary:")
    print(psf)

    name = psf.names[0]
    wfm = psf.get_signal(name)
    wfm.plot()
    plt.grid()
    plt.legend()
    plt.show()
    return

    fn = Path(fn.parent / (fn.name+".psfxl"))
    # fn = Path('examples/bcd.tran.tran.psfxl')

    with open(fn, 'rb') as f:
        rdr = FakeBufferedReader(f)

    traces = list(psf._trace_section.traces.values())
    if len(traces) == 1 and traces[0].is_group:
        traces = traces[0].children

    t0 = time.time()
    for signal in traces[:8]:
        print(f"SIGNAL: {signal.name}")
        psfxl_idx = signal.properties['psfxl_idx']
        wfm = read_xl_signal(rdr, psfxl_idx[1])
        plt.plot(wfm.t, wfm.y, label=signal.name)

    print(f"TIME = {time.time() - t0}")
    plt.grid()
    plt.legend()
    plt.show()
    return

    if False:

        chunk = xl_data[0x78:0x78+0x34f]
        dis = blosc.decompress(chunk, as_bytearray=True)
        t_array = np.frombuffer(dis, dtype='float')
        print(t_array)
        chunk = xl_data[0x78+0x34f:0x78+0x34f+0x353]
        dis = blosc.decompress(chunk, as_bytearray=True)
        v_array = np.frombuffer(dis, dtype='float')
        print(v_array)
    if True:
        traces = list(psf._trace_section.traces.values())
        if len(traces) == 1 and traces[0].is_group:
            traces = traces[0].children

        # return
        last_start = None

        for signal in traces:
            name = signal.name
            psfxl_idx = signal.properties['psfxl_idx']

            print("___________")
            print(name, psfxl_idx)
            start_offset = psfxl_idx[1]

            print(f"start is {hex(start_offset)}")
            if last_start is not None:
                print(f"{hex(start_offset-last_start)} from last")
            last_start = start_offset

            desc_str = xl_data[start_offset+1:].split(b'\0')[0].decode()

            desc_str = desc_str.replace('.', ':')
            desc = [int(s, 16) for s in desc_str.split(':')]
            print(desc_str)
            print(desc)

            data_offset = start_offset + len(desc_str) + 2  # plus 2 for the \0 at beginning and end

            next = 8*((data_offset+7) // 8)  # aligned to word boundary
            print(f"Data at {hex(next)}")
            hexprint(xl_data[next:])
            if (desc[5] == 0x22):
                print(f"y Data at {hex(next + desc[6])}")
                hexprint(xl_data[next+desc[6]:])
            elif (desc[5] == 0xa2):
                print(f"X! Data at {hex(start_offset - desc[6])}")
                hexprint(xl_data[start_offset-desc[6]:])
            if xl_data[next:next+1] == b'\x02':
                csize = struct.unpack('<i', xl_data[next+12:next+16])[0]
                print(f"length={hex(csize)}")
                chunk = xl_data[next:next+csize]
                dis = blosc.decompress(chunk, as_bytearray=True)
                print(f"uncompressed length={hex(len(dis))}")
                t_array = np.frombuffer(dis, dtype='float')
                np.set_printoptions(threshold=10)
                print(t_array)

    return
    print("Sweep:")
    print(psf.sweep_info)
    print([s for s in psf.signals if len(s) < 3])

    # selected = 'ANT_CM'
    # selected = random.choice(psf.signals)
    # print(f"Choose random signal: {selected=}")
    # print("signal_info():")
    # print(psf.signal_info('I0\\<47\\>.M3'))
    # print(psf.signal_info(selected))
    # print(f"get_signal():")
    # print(psf.get_signal('I0\\<47\\>.M3'))
    # print(psf.get_signal(selected))
    # print(psf.get_signal(selected))
    # print(len(psf.get_signal(selected).t))
    # print(psf.get_signal(selected).y)
    # return

    # for name in psf.signals:
    name = 'Vo'
    s = psf.get_signal(name)
    print(s.t)
    print(s.y)
    plt.semilogx(s.t, np.abs(s.y))

    plt.ylim(-1, 2)
    plt.grid()
    plt.tight_layout()
    plt.show()

    # print(psf.ndarray)
    # ts = psf.ndarray["sweep: time"]
    # print(ts[:200])
    # plt.plot(ts[:-1], np.diff(ts))
    # print(psf.ndarray["sweep: time"][:100])
    # plt.plot(psf.ndarray["sweep: time"], psf.ndarray['n\\<3\\>'])
    # plt.plot(psf.ndarray["sweep: vdd"], psf.ndarray["va"])
    # plt.plot(psf.ndarray["sweep: vdd"], psf.ndarray["vb"])
    # plt.show()


if __name__ == "__main__":
    main()
