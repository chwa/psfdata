> [!CAUTION]
> Early development. Everything may change, anything may break.

# Read PSF simulation results in Python

Loads PSF-ASCII and PSF-bin files (including experimental support for PSF-XL).

Data is returned as dict/list and waveforms in a lightweight `Waveform` dataclass containing the x and y components as `numpy.ndarray`s.

```pycon
>>> from psfdata import PsfFile

>>> psf = PsfFile.load("/my/path/tran.tran.tran")
<psfdata.psfbin.PsfBinFile object at 0x7fe371bcc110>

>>> psf.header
{'PSFversion': '1.1', ..., 'errpreset': 'conservative', 'method': 'gear2only',
'relref': 'alllocal', 'cmin': 0.0, 'gmin': 1e-12, 'rabsshort': 0.0}

>>> psf.names
['n\\<0\\>', 'vdda', 'n\\<3\\>', 'n\\<2\\>', 'n\\<1\\>', 'M0_G', 'V0:p', 'V1:p']

>>> psf.sweep_info
{'sweep_direction': 0, 'units': 's', 'plot': 0, 'grid': 1, 'name': 'time'}

>>> psf.get_signal("M0_G")
Waveform(t=array([0.00000000e+00, 2.62865500e-14, 3.86983269e-14, ...,
9.99771753e-10, 9.99885876e-10, 1.00000000e-09]), t_unit='s',
y=array([0.5, 0.5, 0.5, ..., 0.5, 0.5, 0.5]), y_unit='V', name='M0_G')

```

The `PsfDir` class can be used to open the various analysis results based on the contents of the `logFile` in the PSF directory.

A `psfinfo` command-line utility is provided to list the contents of a PSF directory or data file.


## Details

Main dependencies:

- https://github.com/pyparsing/pyparsing for ASCII format parsing
- https://github.com/Blosc/python-blosc2 for reading the compressed data chunks in PSF-XL
- numpy for arrays


## Next steps

- can add psf.get_type_info() method to return additional data (properties) from e.g. element.info
- PyPI packaging
- regression tests:
  - collect PSF files for different analyses, different simulators
  - calculate various statistics (rms values of all signals, etc) for regression
