# Blue Sky 180 — prospective unverified external-observation intake

**Registration:** 18 November 2026, before implementing the intake. **Parent frozen exact head:** Blue Sky 179 `f6a40b6ac08490de51bfa7c0db92c002c89fc36e`. This is a dependent, independently reviewable addition only; the original failed 178 run and repaired 179 result remain unchanged.

## Concrete missing interface

The frozen Blue Sky 178 protocol permits a two-load, four-phase measurement contract, but its sole command currently emits predictions from the already published single-contact calibration. There is no executable **external input** interface. A physical engineer cannot use the registered test to calculate a result from four independently obtained observations without writing custom code. This is a useful portability gap, **not** evidence of a frontier invention or new beneficiary value.

Provide a separate command, `python -B -m research.blue_sky064.measurement180 --input /absolute/measurements.json --output /absolute/new/report.json`. It may read externally supplied measurements but must **never authenticate their provenance, calibration, realness, customer acceptance or industrial fitness**. No physical measurement will be carried out during this cycle. No public/private key, account, financial engine or authenticated ledger may be touched. No secrets or raw personal metadata should enter the payload or the output.

## Registered source and input

Pin `campaign/blue-sky-064/friction-probe/MIXED_REGISTRATION.json` to SHA256 `6eece869fb53ed7d6977a88b01ce0ba78af6a5d6931aea9df99c51b4c6f348fa`; its original load indices are `0.01` and `0.10` mm, and the target ratio difference is `>= 0.05`. Read that exact file, verify it is regular and unchanged, and derive the original threshold from it. No caller-supplied alternative target, source registration or load ordering is authorized.

Exact JSON input schema:
```json
{
  "schema": "agi-alpha/blue-sky180-unverified-force-input/v1",
  "indentation_mm": {"low": 0.01, "high": 0.10},
  "force_readings_N": {
    "low": {"static_force_N": 2.0, "dynamic_force_N": 1.0},
    "high": {"static_force_N": 5.0, "dynamic_force_N": 3.0}
  },
  "absolute_force_error_bound_N": 0.01,
  "measurement_authority": "UNVERIFIED_EXTERNAL_INPUT"
}
```
These numerical forces are **synthetic tests, not physical observations**. Reject missing/extraneous fields, nonfinite/boolean/nonpositive values, nonpositive denominator intervals, altered indentation, alternate labels, large/symlink/nonregular source or input, and existing/symlinked/nonabsolute output. Use the original `observation178.assess` interval computation without changing its acceptance threshold or boundary behavior. Record SHA256 of input **bytes**, frozen registration hash, conditional mathematical interval, and the distinction that input provenance, calibration, actual physical observation, beneficiary acceptance and economic value are **NOT VERIFIED**. A conditional positive ratio certificate must **never** become an authorized deployment decision.

## Frozen test matrix and stopping

1. Synthetic conditional positive, inconclusive and negative cases; verify direct `assess` equality, test sensitivity at the fixed threshold and reject malformed or spoofed authorization.
2. Adversarial input: changed load geometry, extra keys, booleans/NaN and nonpositive intervals, invalid registration or untrusted input symlinks, existing output; no report on error.
3. Run a clean source archive with only the pinned original observation module, this intake, frozen registration, and tests; independently download, checksum, extract and reproduce the deterministic synthetic result with the same SHA-bound input. Use a standard public GitHub runner; failures remain failures.
4. Stop after one registered implementation and independent verification. The output is `HOLD_NO_DEPLOY_UNVERIFIED_INPUT` regardless of conditional ratio result. If a test fails, preserve failure and repair prospectively instead of changing thresholds or sampling favorable readings.

## Complete alternatives and operating verdict

Compare at least four arrangements for the eventual **same complete industrial outcome**, without inventing costs or buyer demand: (1) competent conventional specialist performing the identical paired-load test; (2) independent calibrated metrology laboratory and manufacturing partner; (3) in-house automated four-channel sensing and production integration; (4) no-build/no-deploy. Costs of apparatus, calibration, fabrication, acceptance, support, contract obligations and financing are all UNKNOWN, as are partner agreements, real buyer acceptance and reachable demand. Existing passive mechanisms and conventional powered controls remain complete outside options. **Current decision: NO BUILD / NO DEPLOY of a physical device**; this one engineering addition is a measurement data interpreter only. No outreach, physical actuation, purchase, paid API, private data, financial transaction or production deployment is permitted. No $3B profit or recursive improvement claim.
