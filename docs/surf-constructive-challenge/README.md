> **Constructive-challenge technical companion, 23 pages.** This manuscript has the subtitle *From Counterexamples to New Capabilities, Viable Markets, and Better Discovery*. It contains a separate 192-case exact study and 38 tests. The concurrently published 28-page [The Missing Move](../surf-the-exponential/README.md), its 2,304-case study, reader, release tag and canonical PDF are preserved unchanged. Neither edition's test counts or results should be attributed to the other. This folder and its local reader are self-contained; the reader is not a separately deployed Pages URL.

# 🌊 SURF THE EXPONENTIAL

## From Counterexamples to New Capabilities, Viable Markets, and Better Discovery

**Vincent Boucher · MONTREAL.AI / QUEBEC.AI · 5 November 2026 · Research edition 1.0.0**

> **Do not merely find the flaw. Build the possibility it reveals.**

A second AI can expose the crucial chapter missing from a persuasive book summary. The more consequential move is to use a verified objection to construct a better way of achieving the original purpose. This paper connects that move to **TRANSFORMATIONAL INTELLIGENCE ∞**, **ALPHA GENESIS FLYWHEEL Ω**, and **Invent the Economy**.

**Read:** [PDF](SURF_THE_EXPONENTIAL.pdf) · [Browser reader](reader.html) · [Editable LaTeX](SURF_THE_EXPONENTIAL.tex) · [Exact evidence](evidence/exact-results.json) · [Adversarial review](ADVERSARIAL_REVIEW.md).

## The contribution

Challenge a claim against its original sources and purpose; adjudicate the criticism; turn an upheld counterexample into a missing-means construction; compare complete alternatives; and test whether the retained result helps a different successor. Challenge premature impossibility as seriously as premature success.

The new finite laboratory:

- distinguishes source-grounded coverage from agreement about an incomplete summary;
- independently adjudicates a critic's claim against the actual source/output, ignoring self-reported presence flags;
- exposes two individually feasible commitments that double-book the same capacity;
- constructs an adapter plus reservation arrangement that jointly changes modeled viability after a supplied capability-cost change;
- preserves the case in which an ordinary existing route wins;
- compares a max-flow constructor against a separately implemented subset-capacity oracle across **192 cases**: **63 model admissions and 129 refusals**;
- passes **38 tests** in normal and optimized Python.

The central authored example reduces complete **modeled** cost from 17 to 13 against 16 units of **conditional modeled receipts**. These are not customer quotes, actual payments, frontier-LLM benchmark scores, or proof of a generally self-improving invention enterprise. The conventional oracle ties. Actual revenue and separate LLM reviewer runs are both zero.

## Reproduce the computation

Python 3.10+; standard library only. No network, credentials, model access, account or paid service is used.

```sh
cd analysis
python3 -m unittest -v
python3 -O -m unittest -v
python3 run_study.py --out ../my-exact-results.json
```

The output must be new. Compare it byte-for-byte with `evidence/exact-results.json`. All declared cases are retained, including refusals and ordinary-method wins. This exact finite enumeration is not a sample of real markets.

## Build the paper

Requires `pdflatex` and TeX Live packages: `newtx`, `sourcesanspro`, `geometry`, `microtype`, `tikz`, `tcolorbox`, `booktabs`, `tabularx`, `longtable`, `enumitem`, `fancyhdr`, `titlesec`, `caption`, `needspace`, and `hyperref`. On Ubuntu a standard installation is `texlive-latex-extra texlive-fonts-extra texlive-fonts-extra-links texlive-science texlive-plain-generic tex-gyre lmodern`. No font files are redistributed.

```sh
python3 build.py --tests-only
python3 build.py
python3 package.py --output /absolute/new/publication-package
```

The build runs all tests normally and with assertions disabled, regenerates the exact evidence, and compiles the LaTeX three times without shell escape. It rejects overfull boxes and undefined references/citations. The `evidence/build-check.json` record describes the specific build. Different TeX distributions can produce different PDF bytes; the stable numerical JSON is byte-reproducible. Source identities and PDF checksums qualify files, not the truth of assumptions.

## Provenance and publication

The three foundational manuscripts are attributed in [SOURCE_MAP.md](SOURCE_MAP.md); their privately supplied original files and conversation records are not redistributed. The older papers' study results are not silently imported as results of this new experiment. Established CEGIS, max-flow/min-cut, critique and prover-verifier work are explicitly credited.

The adjudicator and oracle are separately implemented under common authorship. The same assistant performed drafting and adversarial review. No second frontier LLM, external reviewer or institution independently certified this paper. The supplied models and prospective natural-study protocols are labelled separately.

**Research direction:** Challenge the claim. Change the game. Build what becomes possible.
