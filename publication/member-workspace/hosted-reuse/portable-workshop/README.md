# Retained workshop instrument

The retained instrument produced the same artifact bytes in the first and successor runs. The original local workshop gates verified 18 initial and six fresh observations for this instrument. It takes a synthetic affine calibration record and returns the corrected reading and scoped defect and drift flags.

Run the separate public example with Python from this folder.

```sh
python3 RUN_INSTRUMENT.py instrument.json example.json
```

The example's corrected value is 3.5. Both flags are false. See `PORTABLE-REPLAY.json` for the executed result and exact file fingerprints. The applicability evidence covers the registered synthetic workshop scope.
