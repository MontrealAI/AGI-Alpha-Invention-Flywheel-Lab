# Compact offline replay evidence

The final scientific source was frozen at commit `0efb91e4e477339e171cfdb1123a739b7590667b`. These files add measured results and a portable replay adapter; they do not alter the frozen models, targets, source selection or independent checker.

`EVIDENCE_CHUNKS.json` describes a deterministic ZIP payload split into 49 parts of at most 60,000 bytes. The adapter checks every part, the assembled payload, its exact member set and each extracted member hash. It rejects unsafe paths and writes only into the requested temporary output directory.

The payload contains the held-out input/height arrays, decoded author input/prediction arrays, their lineage, fixed pre-truth decisions, results, and training/development **mask-only** arrays. It does not contain large microscopy archives or frozen floating-point prediction arrays. `DATA_DERIVATION.json` binds each mask-only file to the original local NPZ hash and exact mask-array hash; training heights were omitted because replay performs no fitting.

The adapter reconstructs all six prediction arrays from the frozen parameters and compact evidence, requires their exact pre-truth hashes, then runs the unchanged independent checker. Existing `SPLIT.json.gz` is expanded only in temporary storage and used under the filename required by the frozen checker. No duplicate plain split file is published.

Run with NumPy 2.3.5, SciPy 1.17.0 and Pillow 12.3.0:

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python offline_replay.py --out /tmp/n3-replay
```

This uses no network, retraining, new optimization or physical action. The repository evidence remains read-only. The replay establishes software/input/metric consistency, **not** manufacturing qualification or commercial profitability. All four computational HOLDs and the unprinted status of all nine new masks remain intact.
