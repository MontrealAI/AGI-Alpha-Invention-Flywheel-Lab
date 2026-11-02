# NEXT072: finite experimental-allocation construction

The public protocol is [`experiments/next_series_20261102/PREREG_K1.md`](../experiments/next_series_20261102/PREREG_K1.md). This code is a research replay, with published experimental condition means as reference observations and policy-specific masked reveals. It does not actuate or simulate a laboratory sale.

Before any measured-data run, publish the protocol and source code, then substitute the actual public commit below. The source workbook must match its registered Git blob. Run from the repository root with Python, NumPy and read-only openpyxl available.

```bash
python -m unittest next072.test_experiment -v
python -m next072.run --execution-kind registered_confirmation --freeze PUBLIC_COMMIT_SHA --download --workbook next072/downloads/suppl-qqplot.xlsx --output experiments/next_series_20261102/attempts/confirmation_001
```

The output contains compact source-derived evidence, every policy's ordered reveal receipt, complete denominators, result status and resource usage. The raw workbook remains outside git. Downloading the registered source is a single finite public retrieval; a transport failure is retained as a failed attempt, not a physical observation.

An offline policy replay uses the compact evidence after it has been published and does not revalidate original expression means:

```bash
python -m next072.run --execution-kind engineering_reproduction --freeze PUBLIC_COMMIT_SHA --compact experiments/next_series_20261102/attempts/confirmation_001/compact_evidence.json --output experiments/next_series_20261102/attempts/compact_replay_001
```

The independent verifier should read the original pinned workbook directly, recompute pair identities, RMS residuals, split/target sets and all receipt counts without importing the constructor's data or metric functions. The ordinary equal-content policy intentionally has the same scientific output as the proposed policy. No human labor advantage is inferred from that equality.

The dedicated public CI workflow repeats this same frozen scientific test with `--execution-kind engineering_reproduction`. These repeats verify source-matched engineering; they do not add fresh biological observations or new confirmation denominators. The workflow's first step records the platform job clock, uses standard public Ubuntu/Python resources, and uploads compact evidence only. Raw source workbooks are not uploaded.
