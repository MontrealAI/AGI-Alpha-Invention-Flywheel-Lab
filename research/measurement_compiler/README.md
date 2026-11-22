# A compiled measurement protocol for real tank data

This prototype reconstructs missing electrical boundary responses from a selected
set of current injections. It uses known linear algebra, current geometry and a
homogeneous-tank calibration. It does not reconstruct unexcited current directions,
establish a novel physical law, control hardware or operate a business account.

The first ideal-physics model was inadequate for the supplied measurements. The
retained construction adds one reference-derived response mode, then estimates
fresh specimen coefficients. Acquired values remain unchanged. Geometry and
calibration hashes bind reuse; changed inputs require requalification.

The frozen 48-pattern method achieved <=5% signal error on 20 of 21 held-out
physical tank targets, with 3.7402% median and 6.0599% worst error. It uses 36.84%
fewer patterns than the 76-pattern reference, but **misses the registered target
of at most 40 patterns**. This is physical-data replay, not new measurements or
industrial validation. The conventional same-algebra comparator matches it.

See [the experiment](../../campaign/measurement-compiler-001/RESULTS.md) for full
comparisons, development corrections, the image-level check and reproduction.
