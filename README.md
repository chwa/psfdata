# Read PSF (binary) results in Python

roughly inspired by https://github.com/henjo/libpsf
see `example.py`

The following have been tested:

- tran.tran.tran from Spectre and AFS (not PSF-XL!)
- ac.ac AC simulation
- element.info
- dc.dc with and without sweep
- dcOp.dc
- dcOpInfo.dc

# Next steps

- can add psf.get_type_info() method to return additional data (properties) from e.g. element.info
- packaging
- regression tests:
  - collect PSF files for different analyses, different simulators
  - calculate various statistics (rms values of all signals, etc) for regression


# Waveform utils

x = wfm1 + wfm2 (combining x points and interpolating before adding)
wfm.cross(0.2, type='rising') -> list[float]
wfm.clip(start=1e-9, stop=2e-9)
wfm.real
wfm.imag
wfm.abs
wfm.phase(unwrap=True)

peak_to_peak(wfm)
delay(wfm1, wfm2, th1, th2, type1, type2)
moving_average()
conv(wfm1, wfm2)
clock_sample(signal, clock, clock_threshold, clock_edge)
linear_fit(wfm) # weighted or non-weighted
dnl(wfm)
inl(wfm)
derivative(wfm)





-----------------

unrelated...
```
vsense = Node()
vss = Node()
res_ctrl = Node(3)

def dcdc_vsense_res(vsense, vss, res_ctrl)
    unit_r = rhim(params={l=1.40e-6, w=0.2e-6})
    nmos_sw = nch_lvt(params={nfin=4})

    def switched_r(a, b, enable):
        x = Node()
        r = unit_r(a, x)  # instantiate and connect
        m = nmos_sw(g=enable, d=x, s=b)

    for i in range(2):
        unit_r(vsense, vss)

    for i in range(3):
        switched_r(vsense, vss, res_ctrl[i])
```