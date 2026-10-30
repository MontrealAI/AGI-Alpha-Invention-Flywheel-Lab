# Reproduce the energy exploratory construction

Python 3 with NumPy and SciPy is required. The development run used the available primary Python runtime; no network or model/API inference is used by the arithmetic/physics programs. Run from a fresh copy because the programs refuse to replace original result files.

```bash
mkdir -p /tmp/alpha-energy-replay
cp thermal_observability.py excitation_probe.py enumerate_controls.py refine_thermal_model.py /tmp/alpha-energy-replay/
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I /tmp/alpha-energy-replay/thermal_observability.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I /tmp/alpha-energy-replay/excitation_probe.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I /tmp/alpha-energy-replay/enumerate_controls.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -I /tmp/alpha-energy-replay/refine_thermal_model.py
```

Expected engineering outcomes: all64 sequences retained; raw/repaired/ordinary robust designs all `111111`; ordinary D-optimal `111000`; numerical refinement errors fall approximately by half. Runtime/CPU and source hashes are recorded. These outcomes reproduce a failed enabling-gap proposal in a source-informed reduced model. They do not establish physical thermal breakthrough, full-field-model superiority, calibrated measurement uncertainty, profitable commerce or funded successor advantage.

No claim-level protected confirmation was consumed. All scenarios and outputs were exposed to the construction role. Shared author, Python, NumPy/SciPy and host are disclosed. Independent parent verification may audit the candidate without modifying it.
