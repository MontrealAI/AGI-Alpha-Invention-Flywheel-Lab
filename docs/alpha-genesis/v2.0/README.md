# ALPHA GENESIS FLYWHEEL Ω · Research edition 2.0

**Riding the Exponential: Three Orders of Intelligence for an Enterprise That Discovers What Becomes Possible**

Vincent Boucher · MONTREAL.AI / QUEBEC.AI · 4 November 2026

## Read first

Open **START_HERE.html**, or open **ALPHA_GENESIS_FLYWHEEL_OMEGA_v2.pdf** directly. No installation, model account, payment, or internet connection is required to read the paper.

This is a research paper and reproducible companion, not the complete production GENESIS application. It separates external frontier progress, useful capability construction, inheritance, improved invention, and commercial self-sustainability.

## Edit and build

The editable manuscript is `ALPHA_GENESIS_FLYWHEEL_OMEGA_v2.tex`; references are in `references.bib`. Vector figures are embedded in the source.

With a full TeX Live or comparable distribution installed, run:

```sh
python3 build.py
```

The build uses pdflatex and BibTeX, no shell escape and no network. Packages include newpx, natbib, tikz, pgfplots, tcolorbox, booktabs, tabularx, longtable, geometry, fancyhdr, and hyperref. The generated `.bbl` is included so the supplied bibliography remains readable even before rebuilding.

## Reproduce the independent analytical study

Python standard library only:

```sh
cd analysis
python3 -m unittest -v
python3 exact_studies.py --out ../my_exact_studies.json
```

The output must be new. It should match `evidence/exact_studies.json` byte for byte. The independent oracle reimplements the decision dynamics instead of calling the original planner's actions or transitions. Its 54 sensitivity comparisons concern a declared finite model, not real-market optimality.

## Reproduce the other reported suites

The small prototype source snapshots and their original tests are included:

```sh
cd reproduction/decision_v01
python3 -m unittest discover -s tests -v
# 19 tests
cd ../composition_001
python3 -m unittest discover -s tests -v
# 25 tests
```

## Reproduce the native operating study

See `reproduction/README.md`. It contains the exact historical public reference archive and additive Native Enterprise 002 source. A private local POSIX working directory is required. These are simulated accounts, never actual payments.

The paper's new verification completed **62 native tests**, **19 supplied Bayesian tests**, **25 supplied composition/observer tests**, and **15 analytical-companion tests**. Results are disaggregated because passing each suite supports a different claim. Four new six-cycle native runs passed local audit and unchanged resume. Current-main compatibility, real demand and autonomous open-world discovery remain unestablished.

## Inspect evidence

- `evidence/exact_studies.json`: exact planning and counterexample results.
- `evidence/native_runs.json`: four separate reproduced accounts, including losses.
- `evidence/native_REPORT.json`: the central source-bound simulation summary.
- `evidence/native_ROUTING_STUDY.json`: the conventional tie, retained rather than relabeled.
- `evidence/*tests.log`: completed test transcripts.
- `CLAIM_REGISTER.json`: claims and evidence boundaries.
- `PROVENANCE.json`: input archive hashes and source revisions.
- `RELEASE_VALIDATION.json`: publication checks performed for this edition.
- `SHA256SUMS`: release file identity, not semantic certification.

The central simulated result is **US$143.20 modeled profit**, not actual revenue. Opening capital still backs protection reserves. No credentials, operating account databases, private recovery authority, or private source documents are included.
