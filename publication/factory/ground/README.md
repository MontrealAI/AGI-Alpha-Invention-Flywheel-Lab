# TOI-216 c ground-only source replay

Run from the directory that contains the four files in this replay package.

```bash
python3 fetch_ground.py
OPENBLAS_NUM_THREADS=1 python3 fit_ground.py --output GROUND-ONLY-REPLAY.json
```

`fetch_ground.py` retrieves two public ExoFOP tables into `exofop/` and checks their exact byte counts and SHA-256 values against `EXOFOP-FILES.json`. The original filenames come from the archive. The same command verifies the files if they are already present. Running the fit itself requires NumPy and SciPy. The verified environment used CPython 3.12.14, NumPy 2.3.5 and SciPy 1.17.0.

The fit uses only the two BJD_TDB ground light curves and their acquisition metadata. The independent timing procedure and allowable transit-shape assumptions are recorded in `GROUND-ONLY-REGISTRATION.json`. `fit_ground.py` resolves sources relative to its own location and writes the result to the supplied output path.

| Instrument | Public ExoFOP ID | Original filename |
| --- | ---: | --- |
| LCOGT SAAO Sinistro | 5821 | `TIC55652896_20181216_LCO-SAAO-1m0_ip_RunB_measurements.tbl` |
| El Sauce CDK14 SBIG STT-1603-3 | 10172 | `TIC55652896-01_20190223_El_Sauce_Rc-filter_measurements.txt` |

The replayed data comprise the public observer-uploaded differential aperture measurements. Source links and checksums remain in the manifest. [ExoFOP service DOI](https://doi.org/10.26134/ExoFOP5)
