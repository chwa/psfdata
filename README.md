# Read PSF (binary) results in Python

Goal is to support the following:

- List full contents of psf simulation directory, based on `logFile`
- Expose all signals from PSF-ASCII, PSF binary, and PSF-XL files
  through suitable types/classes such as dict and numpy.ndarray


## details

roughly inspired by https://github.com/henjo/libpsf
see `example.py`

The following have been tested:

- tran.tran.tran from Spectre and AFS (not PSF-XL!)
- ac.ac AC simulation
- element.info
- dc.dc with and without sweep
- dcOp.dc
- dcOpInfo.dc

## Next steps

- can add psf.get_type_info() method to return additional data (properties) from e.g. element.info
- packaging
- regression tests:
  - collect PSF files for different analyses, different simulators
  - calculate various statistics (rms values of all signals, etc) for regression


## Waveform utils

```python
x = wfm1 + wfm2  # (combining x points and interpolating before adding)
wfm.cross(0.2, type='rising')  # -> list[float]
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
```