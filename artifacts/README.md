# Enterprise-011 source and evidence package

The original byte-exact ZIP is 49,513,883 bytes, SHA-256 `7e21fe606108d6625c0aa851f040638d09decf7a8f77ec9efe6fa82b6987cdb7`. It is stored as 17 bounded transport parts because the connected publisher rejects a single request of that size. The prepared GitHub release publishes the reconstructed original ZIP.

From a checkout, reconstruct and verify every part, the full hash and ZIP CRC:

```sh
python3 scripts/reassemble_enterprise011.py --manifest artifacts/enterprise011-parts/INDEX.json --output /tmp/AGI_ALPHA_Enterprise_011_source_evidence.zip
python3 -m zipfile -e /tmp/AGI_ALPHA_Enterprise_011_source_evidence.zip /tmp/enterprise011-extracted
cd /tmp/enterprise011-extracted/source
python3 -m pip install -r requirements-commercial010.txt
python3 -m enterprise audit --output ..
```

The package contains all 188 raw world ledgers and operating decisions, 96 delivered synthetic packets, independent acceptance, three rejected probes, the frozen exact source and protocol, the complete original report, scale trajectories and supplemental frontier evidence. The audit independently reconstructs native finances and deterministic operating decisions, including coverage, summaries and verdicts. A replay is engineering reproduction of the registered seeds, not a fresh market sample.

Actual commerce remains unexecuted; the conditional commercial result and its failure region are summarized in `evidence/enterprise011/REPORT.summary.json` and the paper.
