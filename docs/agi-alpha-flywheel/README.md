# AGI ALPHA FLYWHEEL

## Inventing What Becomes Possible

**Vincent Boucher · MONTREAL.AI · 2 November 2026 · Research edition 1.1**

**Build the next starting point. Then test what it makes possible.**

[Read in your browser](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/agi-alpha-flywheel.html) · [Open the revised PDF](../research/agi-alpha-flywheel-20261102-v1.1.pdf) · [Publication release](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/agi-alpha-flywheel-v1.1.0) · [Download source ZIP](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/download/agi-alpha-flywheel-v1.1.0/AGI_ALPHA_FLYWHEEL_SOURCE.zip) · [LaTeX](paper.tex) · [Bibliography](references.bib)

The research aim is to make useful invention a repeatable autonomous activity: find an important outcome that current arrangements leave unavailable or unaffordable, construct the missing means, and test whether the resulting capability helps open another activity. The object of invention is the **complete productive arrangement**—the beneficiary outcome, production and verification, voluntary participation, financing, and continuing obligations. A stable authorized charter can support opportunities beyond the enterprise’s current product or business category.

Edition 1.1 makes a constructive mechanism executable. A small compiler builds a measurement program from existing observations, checks it, and can retain it as a callable ingredient for a different request. This finite computational study gives the broader architecture a concrete object to inspect. Its information, computational, economic, and physical claims remain distinct.

## Start here

| What you want to understand | Where to start |
| --- | --- |
| The idea and consequential application | The paper’s opening case and constructive study |
| What was actually constructed and measured | [Study report](examples/FOUNDRY.md) and [complete results](examples/foundry-results.json) |
| Whether the comparison is fair | [Registered protocol](examples/FOUNDRY_PROTOCOL.md), including all four arms and adverse controls |
| How to reproduce the calculations | The commands below and [example notes](examples/README.md) |
| What changed from the first edition | [Release notes](RELEASE_NOTES.md) |

## The actual construction study

The registered workload contains **12 authored episodes, three requests per episode, and four arms**. The compiler receives the observation operator, requested quantity, type, permitted primitives, and eligible program archive. It constructs exact executable expressions; the checker validates their identities and executes them on fresh inputs.

The arms are fresh construction, retention of only the first-generation program, accumulation of later programs, and a conventional rank-aware compiler with the same construction and reuse permissions. Information-boundary cases must produce independently checked nullspace witnesses; search exhaustion is a separate outcome.

**Result:** All four arms constructed **30 accepted programs** and certified **six nonidentifiable requests** out of 36. None was rejected or exhausted; all seven separate acceptance controls passed.

| Arm | Exact scalar arithmetic operations |
| --- | ---: |
| Fresh construction | 51,633 |
| First-generation programs retained | 49,041 |
| Accumulating programs | 48,141 |
| Conventional rank-aware reuse | 13,566 |

Accumulating later programs saves 900 operations against retaining only the first generation in the aggregate. It helps shared-substructure episodes and adds work on disjoint targets. Changed identities and rank deficiency show no arithmetic reduction from accumulation. The **conventional compiler uses the fewest operations in every family**. All arms use the same 141 execution arithmetic operations; accumulation reduces construction work and adds checking work. These counts do not establish faster measurement execution or a wall-time improvement.

The first shared-structure episode contains a concrete lineage, shown here as readable expressions:

```text
p1(y) = y0 + y1
p2(y) = call(p1, y) + y2
p3(y) = call(p2, y) + y3
```

Both accumulating and conventional arms generated those same typed programs. The third calls the second, which calls the first; each executes on the current input. The saved JSON contains the full program identities, syntax, coefficient certificates, and request-level checks. This establishes executable succession in the supplied language, with no claim that the compiler learned a better discovery procedure.

The report includes all workload families, successful and unsuccessful construction, full episode arithmetic counts, archive traffic, and descriptive runtime. A retained call expands into its actual arithmetic; reuse does not receive a free-operation discount.

### Interpret the result at its actual scope

The primitive language, task families, and compilers are supplied. The workload is public and authored; it is not protected statistical confirmation or a sample of market demand. The discovery procedure stays fixed. The experiment can establish construction and retained-program effects within this language; it cannot establish an improved inventor or recover information outside the available observations.

Exact arithmetic-operation counts are a declared computational measure, not dollars, calibrated energy, or complete business costs. Software development and workload-authoring effort are outside the runtime counter. Physical measurement, calibration, customer acceptance, and commercial demand require their own evidence.

The broader architecture distinguishes four relations:

- **Reused by:** a later task invokes a qualified existing instrument.
- **Constructed with:** inherited means participate in building a different instrument; an intervention tests their contribution against complete alternatives.
- **Financed by:** identified earnings, seed funds, or financing receipts paid for the successor’s commitments.
- **Discovered better by:** an improved discovery procedure found better arrangements from matched starting means.

The construction study concerns executable means and their reuse. The US$3 billion trailing-365-day complete-cost profit milestone remains unachieved and is not a ceiling. Prospective capital and financing remain design variables, with US$100,000 preserved as a historical reference.

## Reproduce the study

From this directory, check the saved source-bound result:

```sh
python3 examples/check_foundry.py
```

The portable replay checks source and protocol identities and all scientific result fields. It permits recorded Python-version metadata and timing to differ; the original registered implementation and result remain unchanged.

To write a separate reproduction without overwriting the published evidence:

```sh
python3 examples/instrument_foundry.py --run --output /tmp/agi-alpha-foundry-reproduction.json
```

Only Python’s standard library is required. The protocol was published before substantive execution in [commit fa7a1117b913](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/fa7a1117b91340afb27288ec09adbc33926d9ba4). See the [registered protocol](examples/FOUNDRY_PROTOCOL.md) for the frozen workload, permissions, operation counting, stopping rules, and interpretation. The [constructor and checker](examples/instrument_foundry.py) and [saved results](examples/foundry-results.json) make the individual artifacts inspectable.

### The separate financing illustration

```sh
python3 examples/succession.py --check
python3 examples/succession.py
```

This earlier example is exact arithmetic over **stipulated costs and receipts**. It explains how a capability and available earnings can jointly cross a funding threshold, and why profit does not imply spendable cash. It does not measure a constructed instrument’s cost advantage. Its adverse cases and conventional tie remain part of the result. See [its assumptions and interpretation](examples/README.md).

Neither companion opens native business accounts, contacts customers, calls models, or accesses the network. The existing native financial engine remains the authority for operating experiments.

## Build the paper

Install TeX Live with pdfLaTeX, BibTeX, the recommended fonts, `latexmk`, and Poppler (`pdfinfo` and `pdftotext`). On Debian or Ubuntu, the packages are `texlive-latex-extra`, `texlive-fonts-recommended`, `latexmk`, and `poppler-utils`.

From this directory:

```sh
make
make check
```

The PDF is written to `build/paper.pdf`. The source archive is ready for a LaTeX editor such as Overleaf: choose `paper.tex` as the main file and pdfLaTeX as the compiler.

The release includes the inspected PDF, editable source, both executable companions, their protocols and results, and SHA-256 checksums. A rebuild can differ in PDF metadata or bytes across TeX distributions. The publication manifest binds the inspected edition to its exact source files. `verify_publication.py` checks the public edition and its source identities; `--build-only` checks the local compilation and companion verification.

## Evidence and citation

The [public source map](SOURCE_MAP.md) identifies the foundations and the original scope of previously published findings. Historical repository studies remain pinned to `e67aa09031583f976a39c8406ae86585b02cde76`. The new construction study is bound to the protocol, implementation, and saved results included in this versioned publication; it does not relabel those earlier records as fresh confirmation.

```bibtex
@techreport{boucher2026agialphaflywheel,
  author = {Vincent Boucher},
  title = {AGI ALPHA FLYWHEEL: Inventing What Becomes Possible},
  institution = {MONTREAL.AI},
  year = {2026},
  month = {November},
  note = {Research edition 1.1, 2 November 2026},
  url = {https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/agi-alpha-flywheel.html}
}
```

Machine-readable metadata is in [CITATION.cff](CITATION.cff). This is a research publication, with no claim of peer review or qualification of an enterprise-runtime release.

## Previous edition

The [edition 1.0 PDF](../research/agi-alpha-flywheel-20261102.pdf) and [v1.0.0 publication release](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/agi-alpha-flywheel-v1.0.0) preserve the first publication and its exact sources. The revised PDF has a separate filename and release. See the [change log](RELEASE_NOTES.md) for the substantive changes.
