# Independent synthetic construction review

**Three concrete defects were repaired before public-image scoring; their exact reproductions now pass.** The review used generated arrays and temporary emitted instruments only. It did not decode public microscopy pixels, inspect predictions on public data, or alter implementation files. A separate collaborating agent provides procedural separation, not an external institutional audit.

| Finding | Counterexample and consequence | Repair and retest |
|---|---|---|
| NumPy inverse-array shape | Under NumPy 2.3.5, `np.unique` returned 2D inverse arrays. An identical 5×5 mask caused `np.bincount` to raise `ValueError`, so ordinary metrics could not run. | Flatten the combined indices before `bincount`; identical-mask TP=1 and F1=1. |
| Reference border asymmetry | A closed rectangular contour on the top image edge acquired frame pixels during reference reconstruction. Reference count=1, but the same prediction was removed by the declared border policy. | Exclude reconstructed reference objects touching the frame after assigning contour pixels; both sides now count zero, with exclusion diagnostics retained. |
| Vacuous boundary acceptance | Ten correctly segmented isolated objects plus two merged adjacent-cell pairs gave all-field boundary F1=0.833, Dice=1, count error=0.083 and acceptance, despite boundary F1=0 on every relevant field. | Add a boundary-bearing-only mean gate, require a relevant calibration field and two relevant heldout fields, and update selection order before scoring. The same cohort is rejected. |

The independent script passes ten test groups under normal Python and `-O`. Checks include 52 mask pairs compared with a separate brute-force metric implementation, 48 recipe/task pairs whose predictions are unchanged by replacing both reference arrays, empty-marker and malformed-input behavior, outline polarity and border counts, the exact 24-recipe grammar, deterministic coverage and empirical orders from identical synthetic history, five rejected emitted-artifact mutations, and first-accepted versus full-enumeration execution semantics.

These are implementation checks, not evidence of real-data quality or general construction learning. Runner-level resource accounting, protocol binding, and interruption/resume review are pending until that implementation is available. Exact source hashes and reproductions are in `REVIEW_FINDINGS.json`; detailed outputs are in `SYNTHETIC_REVIEW.json` and `SYNTHETIC_REVIEW_OPTIMIZED.json`.
