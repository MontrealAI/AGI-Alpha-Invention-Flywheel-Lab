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
