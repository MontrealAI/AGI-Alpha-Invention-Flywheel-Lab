# 🏗️♾️ LEARNING TO BUILD ✨

## How Intelligence Learns to Create What Makes New Possibilities Real

**Vincent Boucher · MONTREAL.AI / QUEBEC.AI**  
7 November 2026 · Research edition **1.0.0**

> When we build something new, we change what can be built next.

**Change the game → build what the new game requires → learn to build better.**

## Read or download

- [Read the illustrated browser companion and full paper](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/learning-to-build.html).
- [Download the complete PDF](LEARNING_TO_BUILD.pdf).
- [Download the editable LaTeX and executable source package](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/download/learning-to-build-v1.0.0/LEARNING_TO_BUILD_SOURCE.zip).
- [Open the immutable research release](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/learning-to-build-v1.0.0).
- [Edit the LaTeX](LEARNING_TO_BUILD.tex), inspect the [source map](SOURCE_MAP.md), or read the [review](REVIEW.md).
- [Résumé en français](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/learning-to-build.html#francais). The complete manuscript is in English.

## The contribution

Learning to build concerns the **complete, purpose-relative means** that make a worthwhile outcome attainable: knowledge, instruments, processes, resources and arrangements. The paper joins *Transformational Intelligence*, *Invent the Economy*, and *ALPHA GENESIS FLYWHEEL Ω* around the construction of those means and the evidence needed to show improvement.

It distinguishes the outcomes that can be delivered with current means from those reachable through an admissible construction path. It treats complementary prerequisites, transition costs, current rights, qualification, maintenance and funding as part of the complete problem. It then separates three claims:

1. **Useful inheritance:** retained means help on fresh work.
2. **New construction:** those means support a different executable capability.
3. **A better constructor:** experience improves construction on new tasks against strong alternatives with matched information and resources.

A reusable constructor can build a different instrument. That alone does not prove the constructor learned.

The long horizon is cumulative scientific and productive capability. Moving toward it requires demonstrated bridges among accepted value, usable funding, productive capacity, voluntary arrangements and further construction. A theoretical possibility or a financial projection does not establish those bridges.

## What the companion actually executes

The [study](study/STUDY_NOTE.md) emits **four standalone Python measurement programs** from supplied affine specifications. Their outputs match the declared reference calculation over **4,000 finite input cases**. The original artifact is incompatible with all three fresh successor schemas; the supplied compiler emits new instruments for those specifications.

An ordinary interpreter with the same specification also produces the required outputs. Program emission demonstrates an executable construction; it does not establish that a compiler was necessary or that the construction method was learned.

The complete-route illustration evaluates **288 authored grid cells**, each across three retained-means states, for **864 route decisions**. A conventional control with the same information and means ties **all 288** corresponding constructor-state decisions. These counts describe an enumerated illustrative grid, not a population sample or empirical success probabilities.

| Maintenance obligation in synthetic units | Fresh means: feasible cells | Retained fixture: feasible cells | Retained constructor: feasible cells |
| --- | ---: | ---: | ---: |
| 0 | 12 | 22 | 40 |
| 12 | 12 | 22 | 20 |
| 26 | 12 | 22 | 0 |

Each row is a 96-cell slice over supplied cash, deadline and current-consent conditions. The constructor's maintenance is an unavoidable current obligation, including when using the outside service or not entering. The apparent expansion can reverse once obligations are included. The accompanying lifecycle comparison also charges constructor acquisition.

The specifications, constructor, cost schedule and participation flags are supplied by the authors. The emitted programs and their finite executions are real computational artifacts; the model does not constitute an autonomous scientific discovery, actual customer acceptance, real receipts, or physical deployment. The independent checker uses separate source under common research authorship, not an independent institution or field certification.

## Reproduce the finite study

Requirements: **Python 3.10 or later**. The companion uses the standard library and makes no model API or network calls.

From this directory:

```sh
# Check the published programs, complete-route decisions and retained results.
python3 -B study/check.py

# Check the integrity regressions, including with Python optimization enabled.
python3 -B study/test_integrity.py -v
python3 -O -B study/test_integrity.py -v

# Execute a fresh reproduction in a new output directory.
python3 -B study/study.py --output /absolute/new/learning-to-build-replay
python3 -B study/check.py --evidence /absolute/new/learning-to-build-replay
```

The output directory must be new. The replay emits the programs, `RESULTS.json` and `frontier.csv`. `PROTOCOL.json` records the finite comparison and assumptions. Existing evidence stays unchanged; each reproduction is a fresh computation of that same authored study.

The targeted integrity regressions retain a genuine positive case and reject two changed-protocol probes and fourteen forged-report or missing-row probes. They address the source/report-binding defects found during review; they do not expand the study into a general configurable simulator or independent field validation.

## Rebuild the paper

Install a normal TeX Live distribution with `pdflatex`, `bibtex`, `texlive-latex-extra`, `texlive-fonts-recommended`, `texlive-science`, `texlive-plain-generic`, and `poppler-utils`. The publisher uses standard public GitHub Actions runners. No paid model service, API key, custom image or shell escape is needed.

```sh
# Keep the reviewed canonical PDF while rebuilding elsewhere.
python3 -B build.py --output /absolute/new/learning-to-build-rebuilt.pdf
python3 -B verify.py --check-build /absolute/new/learning-to-build-rebuilt.pdf
```

The build runs in a clean temporary directory with a fixed source date and shell escape disabled. It fails on unresolved references, missing glyphs, overfull boxes and final-pass LaTeX/package warnings. The generated `.build.log` is diagnostic output, not part of the publication.

`PUBLICATION.json` binds the canonical PDF and all packaged source files. A different TeX distribution may change PDF bytes or line wrapping. The build comparison checks the extracted manuscript text, while same-toolchain repository/archive rebuilds are also compared byte-for-byte. A hash proves identity with a recorded artifact; it does not prove the scientific claims.

## Verify or package an identified edition

```sh
python3 -B verify.py
python3 -B package.py --verify
python3 -B package.py --output /absolute/new/learning-to-build-publication
```

The package contains:

- `LEARNING_TO_BUILD.pdf` — the complete paper.
- `LEARNING_TO_BUILD_SOURCE.zip` — the editable manuscript, bibliography, scripts, finite study, compact evidence, source map, review and canonical PDF.
- `PUBLICATION.json` — the source and PDF identity manifest.
- `SHA256SUMS` — checksums for those three assets.

The source ZIP extracts directly into a user-chosen directory; it does not require the rest of the repository. Repeat the study and build commands from that directory to reproduce the released source. Existing output directories, historical releases and tags are never overwritten by the package workflow.

### Editorial updates

After reviewing an intentional source or manuscript change, build the canonical PDF with `python3 -B build.py`, then run `python3 -B package.py --refresh`. That explicit authoring operation refreshes the publication binding and, in a repository checkout, updates the website PDF copy, PDF manifest and reader identity fields. It does not publish, commit, merge, deploy, retag or replace a release. Qualification and release jobs only verify the recorded binding; they never refresh it to hide a mismatch.

Once an edition is published, substantive changes require a new reviewed edition and release tag. Preserve the prior edition and its evidence. The workflow compares downloaded release assets with the qualified package and executes the downloaded source companion.

## Citation

```bibtex
@techreport{boucher2026learningtobuild,
  author      = {Boucher, Vincent},
  title       = {Learning to Build: How Intelligence Learns to Create
                 What Makes New Possibilities Real},
  institution = {MONTREAL.AI and QUEBEC.AI},
  year        = {2026},
  month       = nov,
  note        = {Research edition 1.0.0},
  url         = {https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/learning-to-build.html}
}
```

[CITATION.cff](CITATION.cff) provides machine-readable attribution. Public source links identify the foundational papers; private conversation records and uploaded source-document copies are not included in this publication.
