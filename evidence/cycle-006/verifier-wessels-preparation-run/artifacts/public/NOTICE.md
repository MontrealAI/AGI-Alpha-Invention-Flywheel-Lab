# Derived Wessels raw-count mean panel

Source: `WesselsSatija2023.h5ad`, [scPerturb Zenodo record13350497](https://zenodo.org/records/13350497), MD5 `6897bfdcda928a678208fecf4eeb282e`, SHA-256 `5da0485aed81b23bda57b4a7b4510a394682d54911416db89b4846ff6dd34732`. The primary record declares Creative Commons Attribution4.0; credit the original dataset authors and scPerturb. The original rights/source metadata is preserved in `evidence/cycle-006/wessels-access/`. This derivation does not relicense the upstream dataset.

Changes by the AGI ALPHA implementation team: all-cell, full-library normalization to10000 followed bylog1p; condition-level mean calculation; CONTROL-onlytop1000gene panel; canonical labels and geneaxis; label-only100development/58protected pair split. `SPLIT.json` identifies complete source/cohort and exactfiles. No arbitrary gene truncation before library normalization, outcome-dependent readout selection or cell filtering occurred.

This is a separately identified raw THP-1 humanCRISPR-cas13 pilot, not the authors processedS3/downsampled/HVG benchmark. Raw158pairgroups differs from the published157processedpair count. It is not a new wetlab observation or clinical result. The builder receives development AB and heldout A/B/ctrl only; raw X and heldout AB remain verifier-owned until evaluation.
