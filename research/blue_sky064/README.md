# Portable Blue Sky prerequisite probes

This small research reproduction tests three concrete prerequisites for a proposed friction instrument. It is **supporting evidence with a HOLD verdict**, not a flagship, a new physical discovery, CAD validation, a commercial offer or attainment of the profit objective.

Run all frozen probes offline from the repository root with NumPy and SciPy installed:

```sh
python -m pip install --only-binary=:all: -r requirements-cycle004.txt
python -m unittest tests.test_blue_sky064 -v
python -m research.blue_sky064 --output /absolute/new/blue-sky064-reproduction
```

The one CLI verifies the exact compact public fixture and both original registration files before execution. It preserves the original targets, seed 640112, 32 arrays of 64 asperities, 257 compression steps, alternating 8/7 published-point split and the separate mixed-family first-three-row calibration split. New output directories do not alter the original records in [`campaign/blue-sky-064/friction-probe`](../../campaign/blue-sky-064/friction-probe).

The default replay independently implements the published positive-radius Hertz formula twice: scalar loops and vector arithmetic. It does **not** describe that comparison as running downloaded author code. To execute that additional comparator, explicitly retrieve the 11,919-byte public code archive and verify both archive and member hashes:

```sh
python -m research.blue_sky064.fetch_author_model --output /absolute/new/ga_bilinear_hr_friction_law_core.py
python -m research.blue_sky064 --author-code /absolute/new/ga_bilinear_hr_friction_law_core.py --output /absolute/new/blue-sky064-with-author-comparator
```

The retrieval helper makes one bounded public request and accepts only archive SHA256 `5bfb83a1e0c9f048e44bf1dfbfa35f75bd09ffd18b2286f6b471b597a8ee9671` and source SHA256 `94da2880d1afdc140f6e8e00bbae4e2a56015bf1511f2dcf76b0eab5d170bb84`. The comparison extracts only the inspected `_compute_F_P_numba` function from that exact source and removes its JIT decorator; it does not execute the authors' optimizer or import its optional GA dependencies. No network operation occurs in the probe runner.

The probes retain these distinctions:

- The nonmonotonic diagnostic has a mathematical uniform-error obstruction inside the fixed-height Hertz grammar. Ordinary passive clutches, force limiters, snap-through grippers and other negative differential contacts remain complete alternatives. The diagnostic is not an accepted buyer contract.
- One scale is calibrated using eight published observations, with seven published points held out. These are measurements of one previously published device, not a new experiment or an independent device.
- A prescribed mixed-family array nominally changes the static/dynamic friction ratio, whereas a homogeneous family has a constant ratio. The registered uncertainty test fails. Single-contact calibration does not validate mixed-material macroscopic transfer, dynamic velocity dependence or safety.
- Three of six calibration family/phase blocks cannot fit one origin-linear coefficient inside every supplied row-error box without additional discrepancy. This is an interval consistency statement under an explicit interpretation of those errors. It is not a simultaneous confidence statement, physical falsification or a future error bound.

An equally resourced ordinary constructor may compose the same families. No algorithmic superiority, proprietary access, physical construction, simulated account mutation, actual sale or universal game optimum is inferred.

## Public inputs and attribution

Credit: **Li Fu, Djibril Gabriel Kashala, Davy Dalmas and Julien Scheibert**, “Automated inverse design of metainterfaces with tailored friction laws,” *Nature Physics* (2026), [paper DOI](https://doi.org/10.1038/s41567-026-03503-0); [public versioned source record](https://doi.org/10.5281/zenodo.22142148), licensed **CC BY 4.0** ([license](https://creativecommons.org/licenses/by/4.0/)). The archive was available before the 30 October journal publication; the journal date is not a new code-availability claim.

`public_calibration.json` is a 28,460-byte extracted/renamed numerical fixture, not a raw archive. It contains Figure 4B's 15 static-friction measurements and 500 design-curve pairs, plus the six static/dynamic microcontact calibration blocks used in the calculations. Original row order is preserved. Geometry and modulus constants identify the source batches; assigning those measured families to one new array is an explicitly unvalidated composition hypothesis.

Re-extraction sources and byte identities:

| Archive/member | Retrieval or location | SHA256 |
| --- | --- | --- |
| SourceData.zip | [Pinned public archive](https://zenodo.org/api/records/22142148/files/SourceData.zip/content) | `9d8e41cfd762874522eb67b82232d3a8401d9207f9bfe0abfdf3092ae409682f` |
| SourceData_SI.zip | [Pinned public archive](https://zenodo.org/api/records/22142148/files/SourceData_SI.zip/content) | `a70aba2ee98491f0d95977fa24306d238bb511f086ee076e4920fdc01d5074fb` |
| Figure 4 workbook | `SourceData/Fig4.xlsx`, sheet `b_case_3_experimental_data` | `522924c1c57ccbd3bd04f3bacd0be27451575ca4bac6fb506c25120227a43497` |
| Force calibration | `SourceData_SI/FigS9_c_calibration_f_af.csv` | See the fixture's exact `source_hashes` |
| Area calibration | `SourceData_SI/FigS9_b_calibration_af_a0.csv` | See the fixture's exact `source_hashes` |

For Figure 4B, retain `P_tilde,Fs_tilde` from `exp_data` rows and `P_tilde,A_tilde` from `design_curve` rows. For both FigS9 CSV files, parse semicolon-delimited Latin1, locate the static/dynamic marker blocks, and retain numeric four-column rows at group offsets 0, 6 and 12. The fixture records member hashes, attribution and these extraction details. Reproduction uses the exact fixture SHA256 `7aedc8e4c3e7181e381055d3815378b3f5bfe7b5b9386fd5748803d495ab1ced`; modified fixtures or registrations fail before computation.
