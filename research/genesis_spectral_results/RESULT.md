# GENESIS spectral study: registered target rejected

Recorded 5 November 2026. This is a result audit of [PR #243](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/243), not another experiment.

**The hosted program completed successfully; the registered scientific target failed.** The validation-selected six-band ANOVA plan identified 10 of 36 held-out condition means correctly (27.8% balanced accuracy), against the registered 90% target. Vegetation was 7/18 (38.9%) and water was 3/18 (16.7%), both below the 80% substrate minimum. It tied the validation-selected 22-band reference, so the relative-loss gate passed, but that cannot rescue the failed absolute gates.

## Exact source and evidence

- Tested source: `f9978202a765e235dd92f6d940661233306677f5`.
- Protocol freeze: `5e1bf15a7fdf21a9afb83bd1bdb846042b982d06`; the protocol blob is unchanged.
- [Run 41939835460](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41939835460), job `126957505128`, completed on 5 November 2026.
- [Artifact 13376087275](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41939835460/artifacts/13376087275), SHA256 `9b824cb792b0a2ae35606906c5d5b28d0f6615e034d3cb0589f775d8b6492055`. The workflow retains this artifact for seven days; this compact record preserves all arm totals and provenance, not the full artifact.
- [RESULT.json](RESULT.json) records source/data hashes, frozen-plan and prediction hashes, every arm, runtime, resource measurements and verification scope.
- [Unchanged source and reproduction instructions](../genesis_spectral/README.md), [frozen protocol](../genesis_spectral/PROTOCOL.json).

The source archive downloaded by the hosted study contains 269,149,782 bytes, publisher MD5 `22b9ea6d1da22df688b4cc2bbff3cff3`, SHA256 `df41b3afbeac129f9c79e78fbf57f0b8e284512daa77b3b6d625e6ceb36f1521`. Credit: Holt, Khan and Rodrigues, [Zenodo 14419753](https://doi.org/10.5281/zenodo.14419753), CC BY 4.0. No raw spectra are copied here.

## All registered arms

Each test arm has 36 condition means, with six conditions per polymer; accuracy and balanced accuracy therefore agree. Each substrate contributes 18 conditions. Classifiers were selected on concrete validation, not on these test scores.

| Plan | Inputs | Classifier | Correct / 36 | Balanced accuracy | Vegetation / 18 | Water / 18 |
|---|---:|---|---:|---:|---:|---:|
| all_bands | 22 | rbf_svc_C100 | 10 | 27.8% | 7 | 3 |
| anova6 | 6 | rbf_svc_C100 | 10 | 27.8% | 7 | 3 |
| full_spectrum | 1551 | rbf_svc_C10 | 11 | 30.6% | 8 | 3 |
| group_forward6 | 6 | rbf_svc_C10 | 12 | 33.3% | 9 | 3 |
| random6_00 | 6 | rbf_svc_C100 | 10 | 27.8% | 7 | 3 |
| random6_01 | 6 | rbf_svc_C100 | 8 | 22.2% | 5 | 3 |
| random6_02 | 6 | rbf_svc_C100 | 8 | 22.2% | 5 | 3 |
| random6_03 | 6 | rbf_svc_C100 | 10 | 27.8% | 7 | 3 |
| random6_04 | 6 | rbf_svc_C10 | 10 | 27.8% | 7 | 3 |
| random6_05 | 6 | extratrees_leaf1 | 8 | 22.2% | 5 | 3 |
| random6_06 | 6 | rbf_svc_C10 | 8 | 22.2% | 5 | 3 |
| random6_07 | 6 | rbf_svc_C10 | 9 | 25.0% | 6 | 3 |
| random6_08 | 6 | rbf_svc_C10 | 8 | 22.2% | 5 | 3 |
| random6_09 | 6 | extratrees_leaf3 | 8 | 22.2% | 5 | 3 |
| uniform6 | 6 | rbf_svc_C100 | 9 | 25.0% | 6 | 3 |

The selected sparse plan was `anova6` with RBF SVC C=100 and band centers 1650, 1700, 1750, 2050, 2100 and 2150 nm (ideal half-width 10 nm). The selected reference was `all_bands`. The full-spectrum arm obtained 11/36; the best test score happened to be group-forward selection at 12/36. Neither may replace the previously selected plan after seeing test outcomes.

## Verification and resources

The checksum-verified hosted artifact's source matches the public Git blobs. The source, tests and protocol were also matched to the supplied source package. All 28 tests passed locally in normal and optimized Python, consistent with the hosted logs. This review independently recounted all 540 prediction rows, all 15 confusion matrices and balanced accuracies, and all 30 substrate counts. It verified disjoint 54/18/36 train/validation/test memberships, the frozen-plan hash and all three acceptance gates.

The study averaged 4,171 instrumental repetitions into 108 condition means. These are not 4,171 independent specimens. It performed 75 classifier fits and 351 forward-selection fits. Recorded study process CPU was 18.32 seconds and wall time was 136.00 seconds; setup, review, model and complete economic costs are not included. Actual billing remains unknown. Hosted runtime was Python 3.12.15, NumPy 2.3.5, SciPy 1.17.0 and scikit-learn 1.8.0. Local test review used Python 3.12.14 with the same numerical package versions.

This review did not rerun the raw-data comparison and does not provide independent instrument metrology or a newly collected holdout. It audits the existing hosted execution and reproduces software tests and result arithmetic. The original implementation, protocol, failed result and owner branch remain unchanged.

## Lesson and next boundary

**Tried:** construct a six-band material-identification pathway from raw laboratory spectra, train on soils, choose on concrete, and evaluate once on vegetation and water.

**Outcome:** the registered target was rejected. All registered methods performed poorly on the held-out substrates. The current evidence does not isolate why; substrate shift, measurement behavior and model limitations require separate diagnosis.

**Retain / avoid:** retain the raw-only projection boundary, source-bound software and negative result. Do not advertise a useful sensor, hardware savings, commercial viability, AI superiority or an improved discovery method. Do not tune on these exposed test results and call the same data a fresh confirmation.

Any successor needs a separately justified and registered question, independent evaluation data and strong complete alternatives. A later computational success would still need physical acquisition, complete-cost and buyer qualification. No new sensor, physical measurement, customer revenue, spending, account change, merge or deployment is established here.

