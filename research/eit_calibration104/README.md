# EIT104 — Can a trained decision correction replace additional physical measurements?

**Decision: REJECT position-wise recalibration; NO BID / NO DEPLOY.** The publicly frozen, previously exposed 21-specimen experiment produced a negative result using seven heldout *physical-level* groups. The strong existing conventional 40-pattern inverse was better than the proposed fixed decision correction on the primary balanced-accuracy criterion. This is useful evidence against an unnecessary software detour, not a new physical instrument or a real-market verdict.

## Source and prospective integrity

The [protocol](PROTOCOL.md) was published **before** analysis implementation at commit `7f6c0375abb06c0251ec6068ffd7245c45a543b8`. The code consumes the exact original decision-bit projection from EIT103 commit `10b25ce984c22aff861da3d295f5b5d3b8d7299c`, SHA256 `3717c65a9f1c1a8fd2171ac83307aadd8bc60e84f7f2a8391062d1f181f8d22c`. EIT103 pinned those 21 already observed physical specimens to EIT102 artifact13632633072, ZIP SHA256 `8efee93d9e4b142907bea786701c6b78047b68a51e248b498c3df9e9c01e37b2` and exact experimental source `e1493a8d71abcad67a6e26d043ce05cec71a7d4d`. No new raw KTC acquisitions, inverse solves or data fetches were made. The original owner and earlier failed results remain unchanged.

Each heldout set is an entire physical `level` (three specimens, 24 decisions); policies C/D train on the six other levels (18 specimens). A stronger ordinary comparator chooses among unmodified direct40, material-pooled, and position-wise correction by **inner leave-level-out** validation only, never by the heldout level. The candidate D is a fixed per-decision Laplace-smoothed conditional correction. Every method is deterministic and uses only source decision bits (the 76-pattern reference is separately labeled as using more acquisitions). This is **post-hoc cross-validation on already exposed physical data**, not genuinely undisclosed or independently prospective physical confirmation.

## Registered results

| Policy | Correct / 168 | Pooled balanced accuracy | Acquisition context |
| --- | ---: | ---: | --- |
| No measurement, always absent | 112 | 0.500000 | 0; negative control |
| Competent ordinary direct inverse | **146** | **0.892857** | 40 patterns |
| Original full inverse | **147** | **0.897321** | 76 patterns |
| Ordinary material-pooled recalibration | 141 | 0.839286 | 40 patterns, level-heldout trained |
| **Fixed position-wise challenger** | **145** | **0.857143** | 40 patterns, level-heldout trained |
| **Nested strong ordinary chooser** | **147** | **0.892857** | 40 patterns, six-level training and nested selection |
| Original imputed40 | 146 | 0.892857 | 40 patterns |
| Majority of all three raw outputs | 146 | 0.892857 | Requires full76; not a 40-pattern policy |

The candidate lost to both registered controls on balanced accuracy and raw correct decisions, and therefore fails its frozen minimum **+0.05** balanced-accuracy advantage. The outcome is not repaired by tuning the source, choosing another fold or relabeling the protocol. Material 1 achieved 81/84 correct for all three main 40-pattern policies. Material 2 is where the fixed recalibration worsened: position-wise 64/84 correct versus direct40 65/84, full76 66/84 and the nested ordinary policy 66/84. On material 2, balanced accuracy fell from 0.825 for nested ordinary to 0.728 for position-wise. Group-specific counts and false-positive/false-negative denominators are in the generated JSON output.

The nested chooser selected direct40 in six of seven outer folds, and positional correction in one. It improved one correct decision in aggregate relative to always-direct40, but had no improved aggregate balanced accuracy; it is not claimed to be a robust successful innovation. Full76 and three-output majority are separately labeled because their measurement budget differs.

## Reproduce and qualify

From the exact branch source, in a clean standard Python3 environment with no paid API or third-party dependency:

```sh
python3 -m unittest discover -s tests -p 'test_eit_calibration104.py' -v
python3 -O -m unittest discover -s tests -p 'test_eit_calibration104.py' -v
python3 research/eit_calibration104/analysis.py > /absolute/new/eit104-result.json
```

Run locally and in `.github/workflows/eit-calibration104.yml`. The standalone workflow preserves a downloadable exact-source JSON. Check actual hosted statuses and artifacts; a locally passing test is not hosted release qualification. Protect the negative result and historical failed runs; the result is a scientific-engineering development test, not a new paid or modeled enterprise observation.

## What would actually change the decision?

Existing source predictions have **20 unanimously wrong bits**. Training a conditional flip on only 18 other specimens per physical-level fold did not resolve that deficiency. A new *physical information channel* or a different independently valid continuous inverse method still merits a genuinely new preregistered physical test, **only after** a beneficiary decision and accepted modern conventional specialist alternatives are specified. The best direct40 method remains the technical incumbent in this dataset. Under current permissions the commercial decision is NO BID / NO DEPLOY: no customer permission, no genuine heldout acquisition, no tested hardware, no measured actual billing, no native account action and no opportunity for funding or real collection is established. Even a positive retrospective proxy result would not authorize deployment.

**Acceptance matrix:** Protocol pre-code **achieved**; local 20 ordinary + 20 optimized adversarial tests **passed**; source-exposed seven-level comparison **executed/rejected**; independent hosted exact-source CI **must be inspected**; physical prospective and buyer acceptance **unqualified**; original-account P0 integration **blocked on authoritative source/owner handoff**; protected merge and downloaded runtime release **not performed**; US$3 billion trailing-365-day complete-cost profit **unqualified**. Synthetic or real commercial earnings from this analysis: **none**. Complete host, model, labor and lifecycle costs remain **unknown**. No additional spending, credential, outreach, transaction, production deployment or competing financial ledger was introduced.
