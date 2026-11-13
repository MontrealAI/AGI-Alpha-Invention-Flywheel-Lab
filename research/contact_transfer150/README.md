# Contact-transfer150 — measurement contract before claiming mixed-surface function

**Research status:** SOURCE-MODEL PREFLIGHT ONLY; **NO BID / NO DEPLOY**.

The active Blue Sky passive-mechanics question is whether a real mixed contact surface can acquire a load-selective difference in static-hold versus dynamic-slide friction ratio. The published single-contact source model predicts an increase ~0.17212 over the original two indentations, compared with the original authored 0.05 target. The published source-calibration and original geometry-only adversarial results do **not** guarantee that physical transfer. More geometry search with unchanged uncalibrated data cannot resolve it.

This work constructs an executable **measurement uncertainty contract**, not a new contact material or physical test. Four force observations at two frozen indentations must carry independently justified absolute uncertainty envelopes. It then computes the worst possible increase from the four intervals using positive-denominator ratio bounds. The logic can only certify arithmetic **if** all four measurement values, units and errors are valid and physically defensible. A declaration or source-model prediction alone is not such validation.

## Decisive, bounded result

The frozen 2026-11-13 [preregistration](PROTOCOL.md) gives one source-model-only test. The nominal forces imply an increase of ~0.172121; if each of the four positive forces has an independently conservative symmetric relative absolute-error bound, the original 0.05 difference would require a bound **strictly below about 2.79995%** of each force (or equal to the mathematically exact critical value). In the worked synthetic input, 2% passes the conditional arithmetic; 4% fails. This is an *instrument design requirement under a hypothetical model realization*, **not measured instrument precision**, a 95% CI, a simultaneous calibration guarantee, an experimental result, or a mixed-material safety claim.

Run offline with Python 3.12 (standard library only):

```sh
python3 -B -m unittest -v tests.test_contact_transfer150
python3 -B -m research.contact_transfer150.metrology demo --output /absolute/new/preflight150.json
```

To evaluate a new *declared* two-load force record (without physical acceptance), use `python3 -B -m research.contact_transfer150.metrology evaluate --input /absolute/declared.json --output /absolute/new/receipt.json`. A new input must match the exact `source_model_demo` JSON schema and its original fixed load/velocity/unit contract. It should carry explicit source and provenance declarations. Numeric fields are finite decimal strings and *absolute* errors, not assumed Gaussian standard deviations. Both output paths must be new absolute paths under existing directories. The receipt SHA-256 binds input bytes; it never signs sensor provenance or attests external calibration.

## Strong alternatives and unresolved construction

1. **Geometry-only source model:** the existing candidate's nominal gain is insufficient, and source-admissible reversal worlds block a uniform geometry-only guarantee for the tested uncertainty set.
2. **Physical mixed-surface acquisition:** requires real transfer specimens, independently justified error bounds, simultaneous loading/velocity/conditioning, a calibrated force protocol and mixed-surface measurement. This module supplies only the arithmetic acceptance instrument.
3. **Competent complete passive / active engineering:** existing compliant mechanisms, clutches, active control and independently validated contact design may already serve a beneficiary's actual end use. Not costed or beaten.
4. **NO BID / NO DEPLOY:** current supported decision; no beneficiary-specific acceptance contract, commissioned device, real materials or measurements, buyer choice, delivery economics or accepted funded successor.

**Stop rule:** do not conclude physical feasibility, physical impossibility, customer value or profit from this preflight. Next consequential evidence is an actually permitted, independently traceable physical mixed-surface measurement and a complete-alternative comparison for a concrete use case. No hardware actuation, money, keys, paid calls, customers, historical account or financial source were involved. The US$3 billion trailing-365 complete-cost profit target remains unqualified.

Sources: [Fu et al. (Nature Physics, 30 Oct 2026)](https://doi.org/10.1038/s41567-026-03503-0), public [source records](https://doi.org/10.5281/zenodo.22142148), frozen [calibration fixture](../blue_sky064/public_calibration.json) with SHA-256 `7aedc8e4c3e7181e381055d3815378b3f5bfe7b5b9386fd5748803d495ab1ced`, and [mixed registration](../../campaign/blue-sky-064/friction-probe/MIXED_REGISTRATION.json) with SHA-256 `6eece869fb53ed7d6977a88b01ce0ba78af6a5d6931aea9df99c51b4c6f348fa`.
