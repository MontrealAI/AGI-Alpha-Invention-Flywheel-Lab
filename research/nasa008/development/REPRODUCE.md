# Reproduce the development baseline

Use Python 3.12 with NumPy, SciPy, Pillow and Matplotlib (exact observed versions in `RESOURCE_LEDGER.json`). There is no source-provided executable dependency and no model/paid API call.

Start in a clean copy of this directory containing the scripts, frozen `PROTOCOL.json` and source receipts, with sufficient authorized storage/CPU/network. The exact original download is 218,003,291 bytes. `acquire.py` refuses to overwrite existing downloads and checks source-declared lengths. Verify the resulting SHA-256 values against `ACQUIRE.json` in this package. A fresh download consumes its own explicit resource allocation; do not count the old allocation twice.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python acquire.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python intake.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ordinary_baseline.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python ordinary_refined.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python sensitivity.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python check_arrays.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python plane_comparator.py
```

Run in a new output copy to preserve original outcomes. `intake_v1_executed.py` retains the exact first intake code; the reusable `intake.py` only removes its pre-execution protocol-file rewrite. The scoring code and frozen protocol are unchanged. The single preserved sensitivity syntax error was repaired before any sensitivity outputs were generated.

Expected outputs are the two ordinary result receipts, sensitivity, saved registered fields and arithmetic check. The coarse-to-fine optimization uses exposed data and can vary by dependency/library platform. Report differences and actual runtime rather than fabricating exact byte equality for floating-point derived arrays. Original source file hashes must match before interpreting results.

No hard physical uncertainty, buyer acceptance threshold, hidden protected cohort, internal pore truth or commercial result is established by reproducing this computation. The reference is separately measured but already exposed, quantized, and lacks a complete dataset-specific error budget. Current code is an ordinary executable development baseline, not complete reproduction of the source papers' supervised classifiers, manual labels or fitted plane-normal ray tracing.

Publication recommendations: include scripts, protocols, reports, receipts, manifest, plots and small derived arrays as appropriate; use original primary-source URLs plus pinned byte hashes for the large source files. Keep raw/derived bulk arrays outside normal Git blobs. This does not itself qualify a downloaded release package.
