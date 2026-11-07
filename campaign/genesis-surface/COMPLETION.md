# Completion increment: uncertainty becomes an executable next question

The interrupted source build is continued in PR #239. The added calibration
constructor does not treat a nominal pass as a product:

```sh
python -m research.genesis_surface.calibration --design /absolute/new/surface \
  --out /absolute/new/calibration.json --target-relative-error 0.0025
python -m research.genesis_surface.distribution build --out /absolute/new/distribution
```

The original uncertainty boxes fail a separate exact rational necessary-condition
proof: no nonnegative mixture of the supplied families can guarantee the required
ratio inside that rectangular shear model. This is **not physical impossibility**.
The fixed 36-contact design requires at most approximately **0.15396%** symmetric
relative shear uncertainty when every other modeled quantity is held fixed.
A 37-contact redesign passes the independently checked **hypothetical 0.25%**
requirement, including all 16 coefficient-box vertices. No such accuracy has been
measured, and missing geometry, interactions, wear and discrepancy remain material.

This continuation passed **64 tests in normal and optimized Python locally**.
The added tests cover the proof, robust construction, a separately reconstructed
worst-case check, fixed-design boundary cases, honest counterfactual labeling,
ZIP extraction, source/output binding and changed/missing/extra files. The initial
36-test hosted source run passed at `eba64205477689013f8d6c7ee41a9b76cc2abc28`.
Changed source requires its own hosted qualification; consult the exact PR head.

The download contains source, both exposed development cases, editable CAD, a
sampled STL, the calibration diagnosis and `START_HERE.html`. Viewing needs no
installation. Computing needs the declared Python dependencies. The distribution
contains no account, credentials or third-party source archive. It is a usable
research capability, not a self-sustaining enterprise, customer offer, validated
material recipe, new AI discovery algorithm or achieved physical breakthrough.
