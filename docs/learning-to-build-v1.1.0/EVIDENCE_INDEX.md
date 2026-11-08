# Evidence index · Learning to Build 1.1.0

This index distinguishes the frozen original comparison, the new exposed-data
diagnostics, the failed practical composition, and publication engineering.
The [cost ledger](COST_LEDGER.md) identifies measured boundaries and missing
costs. [REVIEW.md](REVIEW.md) records the actual degree of review independence.

## Claims and where to test them

| Claim or question | Governing source | Executed evidence and limit |
| --- | --- | --- |
| What do the 116 specialist fields mean? | [Specialist protocol](construction/INCUMBENT_PROTOCOL-amendment-2.json) | 50 source-validation + 50 source-test + 4 successor-calibration + 12 successor-test outputs. The 100 donor-training fields are additional. |
| Which methods qualify? | [Classical protocol](construction/PROTOCOL-amendment-2.json), specialist protocol | [Derived results](construction/RESULTS.md), [complete machine-readable report](construction/RESULTS.json), [claim bindings](construction/CLAIMS.json). Only the existing specialist nucleus route qualifies on both required source cohorts. |
| Were all scores independently recomputed? | [Separate checker](construction/check.py) | Main archive: `PROJECTED_CLASSICAL_INDEPENDENT_CHECK-002.json` regenerates 2,632 unique classical predictions and rescores 196 saved outputs; `INCUMBENT_INDEPENDENT_CHECK.json` rescores all 116 specialist outputs. The latter does not rerun neural inference. |
| Why did six policies choose r12? | [Diagnostic registration](construction/diagnostics/PREREGISTRATION.json), [frozen program](construction/diagnostics/run.py) | [Diagnostic results](construction/diagnostics/RESULTS.json): four original orders, identical per-recipe scientific outcomes, and 33 cached-score order replays all exhaust 24 failing candidates. These are deterministic policies, not independent language-model judgments. |
| Which input branch explains the failure? | Same fixed-r12 four-calibration-field diagnostic | [Diagnostic guide and table](construction/diagnostics/README.md), all masks and controls in its bound archive. Reference foreground improves the numerical gate; seed/foreground coupling and reference assistance limit causal and deployment claims. |
| Can an available practical composition repair it? | [Repair registration](construction/repair/PREREGISTRATION.json), [composition](construction/repair/composition.py), [evaluation](construction/repair/evaluate.py) | [Failed repair results](construction/repair/RESULTS.json): boundary F1 0.296809 on four calibration fields, below 0.60; zero test fields scored. Actual cached-constituent composition was executed. No new neural inference or end-to-end raw repair operation is claimed. |
| Are the residual raw files preserved? | Main archive: `classical-residuals/PROJECTION.json` | [Portable verifier/reconstructor](construction/projection.py) checks the 416-path partition: 278 canonical files and 138 residuals. Reconstruction reproduces the raw bytes and preserves the expected strict-inventory rejection. Origin and associated additional cost remain unknown. |
| Is the measurement instrument operable? | [Exact setup](construction/INCUMBENT_SETUP.md), [operator](construction/release_operate.py) | Main archive retains observed model invocation and raw-image operation; [qualification packet](qualification/README.md) preserves a failed extracted setup, its repair and real one-field candidate operation. The actual downloaded release receives its own operation receipt only after execution. |
| What changed from 1.0.0? | [Release notes](RELEASE_NOTES.md), [source map](SOURCE_MAP.md) | The original finite study, source edition and release are preserved. The continuation adds microscopy, qualified negative findings, diagnostics, practical repair failure and reproducibility machinery. |
| What is demonstrated about learning? | [Evaluation design](sections/evaluation.tex), complete reported comparisons | Zero primary candidate-evaluation savings. No accepted whole-cell successor, fresh retained-method advantage, complete-cost saving or general learning claim is established. |

## Archives and identities

The main archive is [construction/evidence/REPRODUCTION.tar.gz](construction/evidence/REPRODUCTION.tar.gz),
identified by [EVIDENCE_MANIFEST.json](construction/evidence/EVIDENCE_MANIFEST.json).
It contains **776 files** and remains unchanged from the recovered completed
reproduction. Its SHA-256 is
`f397d7d49e2a11ab82a6bcc759d866bc56cdcad7de5a82eb57cd91f0d61dadfb`.
It includes canonical predictions, all raw residuals, source-bound verification,
measured sessions, setup attempts, historical-failure replays and recovery
receipts. It does not claim to recover the unavailable earlier full run.

The follow-up packets are separate:

- [Diagnostic evidence manifest](construction/diagnostics/EVIDENCE.json) and
  [complete observed diagnostic output](construction/diagnostics/OBSERVED_RUN.tar.gz).
- [Failed repair evidence manifest](construction/repair/EVIDENCE.json) and
  [complete observed repair output](construction/repair/OBSERVED_RUN.tar.gz).
- [Publication qualification and preserved setup failure](qualification/README.md).

`PUBLICATION.json` binds every packaged source and the canonical PDF. It is an
identity record, not a scientific acceptance certificate. The source ZIP's
`SHA256SUMS` identifies the released asset bytes; the hosted workflow and
downloaded-operation receipt establish publication and operation separately.

## Reproduction route

1. Verify the release checksums, extract the source ZIP, and run `python3 -B package.py --verify`.
2. Follow [construction/README.md](construction/README.md) for the exact numeric
   environment and independently acquired public dataset archives.
3. Extract and verify the main evidence with `python3 -B construction/evidence.py --extract /absolute/new/evidence`.
4. Verify or reconstruct the original raw files with
   `python3 -B construction/projection.py --evidence /absolute/new/evidence --reconstruct /absolute/new/raw`.
   The reconstructed raw tree is expected to fail strict inventory. Use the
   unchanged canonical `evidence/classical` projection for the scientific replay.
5. Run the separate scientific checker, diagnostic replay and failed-composition
   replay using their documented commands. Each requires a new output location.
6. Use the exact specialist installer and operator for actual inference. Rechecking
   saved masks alone does not execute the generating model.

Public source data and model weights are fetched separately by exact identities
and under their own terms. Pretraining overlap, all-environment bitwise identity,
external beneficiary acceptance and complete monetary costs are not established.
No credentials, private correspondence, private source uploads or signing material
belong to these archives.
