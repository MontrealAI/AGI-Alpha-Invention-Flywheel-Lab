# Adaptive-012 source and evidence package

The package is 59,775,697 bytes, SHA-256 `29aaa1e6ec81b145753550b3394c1684f503f804e8bc565af404d13e8d92be34`, in 20 bounded parts. Local full audit replayed all 160 native accounts and operating trajectories. See [results](../evidence/adaptive012/RESULTS.md) and the current [publication status](../evidence/adaptive012/PUBLICATION.json).

**Use an absolute extraction root.** The frozen package's internal README suggests `--output ..`; that form does not normalize parent segments and may repeat subprocess delegation. This is a documented reproduction-interface defect, not a change to financial results. Use this corrected command:

```sh
python3 scripts/reassemble_enterprise011.py --manifest artifacts/adaptive012-parts/INDEX.json --output /tmp/AGI_ALPHA_Adaptive_012_source_evidence.zip
python3 -m zipfile -e /tmp/AGI_ALPHA_Adaptive_012_source_evidence.zip /tmp/adaptive012-extracted-NEW
cd /tmp/adaptive012-extracted-NEW/source
python3 -m pip install -r requirements-commercial010.txt
python3 -m adaptive_enterprise audit --output /tmp/adaptive012-extracted-NEW
```

Use a new extraction directory and supply its actual absolute path. The default audit verifies full operating semantics; financial-only mode explicitly reports zero operating replays. Signing keys are omitted. All commerce and scale assumptions are simulated. The original package and frozen source are preserved byte-for-byte; public-copy replay status is recorded separately.

---

# Enterprise-011 source and evidence package

The original byte-exact ZIP is 49,513,883 bytes, SHA-256 `7e21fe606108d6625c0aa851f040638d09decf7a8f77ec9efe6fa82b6987cdb7`. It is stored as 17 bounded transport parts after the single-request transfer failed in this environment. The prepared GitHub release publishes the reconstructed original ZIP.

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
