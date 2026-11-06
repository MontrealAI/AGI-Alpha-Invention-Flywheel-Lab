# Original failure evidence

These two files preserve the exact pre-repair bytes identified by F01 and F02 in the independent review. They were recovered from the challenger's frozen **source** snapshots, not reconstructed from a description or reverse-patched from the repair. They contain source only, no account, signing material or private input.

| File | SHA-256 | Original defect |
|---|---|---|
| `F01_native.py.original` | `b2f7d9a3ebe89030a700b221095c70821d7aca39c662ebe8c0343717b05351d3` | Deadline can equal/exceed maturity. |
| `F02_runner.py.original` | `fe63f79c457ac2065f94a44a4f456562486ab79e58a524edcac7c1a74a6b422d` | Public export copies any root `*ARTIFACT.json` file. |

Use dependency source commit `ffcc65221ffaac28533c5f759d166b44ecc8b734` and its pinned Python dependencies. Then run:

```sh
python /absolute/path/to/this/fixture/reproduce.py --source /absolute/path/to/ffcc652-checkout
```

The harness copies the required source closure to disposable directories, substitutes one original file, and creates fresh synthetic accounts. It reproduces the deadline refusal and copies only a deliberately planted harmless marker through the flawed exporter. It never reads a historical account or existing private directory. Temporary accounts and ZIPs are removed after the observation is collected. Successful harness completion means both **failures were reproduced**, not that the original system passed.

This is a fresh counterexample replay of the preserved failed file with the specified repair-era dependencies. It does not assert that the rest of that dependency tree is the exact original historical execution environment. The original failure identity remains the file's SHA-256. Current regressions use fresh inputs to test the repair separately.

## Later failures frozen in Git

F03 and F04 preserve their complete pre-repair runtime through public Git ancestry rather than reconstructed copies:

- F03: checkout `4ace9a578ebae5a8ff44cf35a3b9edbe234779c4`, then run `python -m unittest discover -s tests -p 'test_connected_commitment_public_receipts.py' -v`. Six honest cases pass; 48 of 64 expected rejection checks fail (all 32 audit checks plus 16 contradictory/malformed package checks). Native finance and prepared output are unchanged by the probes.
- F04: checkout `6b520cd8574f82882f9473a0f90ec29203a54d9d`, then run `python -m unittest discover -s tests -p 'test_connected_commitment_startup.py' -v`. Six cases pass and pristine startup fails after an actual abrupt child-process exit before its first checkpoint.

Both use fresh disposable synthetic accounts only. Run the same unchanged tests on repaired source for prospective qualification. Set `PYTHONOPTIMIZE=1` when testing optimized subprocess execution. The original F01/F02 harness above is a separate historical counterexample and does not assert that a later runtime is the original execution environment.

The later independent challenge is portable:

```sh
python tests/fixtures/genesis_commitment001_failures/challenge_public_receipts.py --source /absolute/exact/source --output /absolute/new/challenge
```

It snapshots the runtime closure before creating six fresh accounts, checks honest exported copies, and challenges 28 new coherent/adverse mutations. It never copies an existing account or recovery authority. `F03_FRESH_RESULT.json` records the preserved original challenge and the portable replay, with their source hashes and declared boundaries.
