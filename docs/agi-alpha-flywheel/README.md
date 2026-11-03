# AGI ALPHA FLYWHEEL

## Inventing What Becomes Possible

**Vincent Boucher · MONTREAL.AI · 2 November 2026 · Edition 1.0**

The output of one invention can become the means of the next.

[Read in your browser](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/agi-alpha-flywheel.html) · [Open the PDF](../research/agi-alpha-flywheel-20261102.pdf) · [Download the publication package](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/agi-alpha-flywheel-v1.0.0) · [LaTeX](paper.tex) · [Bibliography](references.bib)

This paper develops a single account of how knowledge, productive capability, and available earnings can improve the starting point for a consequential successor. It connects **Transformational Intelligence** to complete productive arrangements: the outcome, its production and verification, voluntary participation, financing, and continuing obligations.

Three claims remain separately testable:

- **Financed by:** available predecessor resources paid for the successor.
- **Enabled by:** an inherited means changed what the successor could achieve under the declared comparison.
- **Discovered better by:** an improved discovery procedure found better arrangements from matched starting means.

The paper includes an original vector flywheel, two elementary conditional propositions, an exact explanatory construction, a crossed experiment for testing an improving inventor, and a review of public evidence. Its scientific contribution is an architecture and evaluation synthesis. Current results do not establish actual commercial profit, a new industry, general recursive improvement, or the US$3 billion trailing-year profit milestone.

### Read by interest

| Interest | Sections |
| --- | --- |
| The central idea and visual architecture | 1–4 |
| Reachability, cash, profit, and the finite example | 5–7 |
| How to distinguish better equipment from a better inventor | 8 |
| Current evidence and the research frontier | 9–11 |
| Reproduction and sources | Appendix A and references |

## Reproduce the example

```sh
python3 examples/succession.py --check
python3 examples/succession.py
```

Only Python's standard library is required. The result is static exact arithmetic in an authored model, with no network calls or native financial accounts. The four treatments expose a tool-and-liquidity complement. Adverse cases retain expenses and profit correctly, and a strong conventional constructor ties the successful sequence. See [the assumptions and full interpretation](examples/README.md).

## Build the paper

Install TeX Live with pdfLaTeX, BibTeX, the recommended fonts, `latexmk`, and Poppler (`pdfinfo` and `pdftotext`). On Debian or Ubuntu, the required packages are `texlive-latex-extra`, `texlive-fonts-recommended`, `latexmk`, and `poppler-utils`.

From this directory:

```sh
make
make check
```

The PDF is written to `build/paper.pdf`. The source archive is ready for upload to a LaTeX editor such as Overleaf: choose `paper.tex` as the main file and pdfLaTeX as the compiler. No model API, external service, or image-generation step is needed to build the manuscript.

The release includes the inspected PDF, source and exact example, and SHA-256 checksums. A rebuild may differ in PDF metadata or bytes across TeX distributions; the publication manifest binds the inspected edition to its exact source files. `verify_publication.py` checks the public edition and its source identities. Its `--build-only` option checks the local compilation, citations, text extraction, and example.

## Evidence and citation

The [public source map](SOURCE_MAP.md) identifies the paper's foundation and the original scope of each experimental record. All repository evidence is pinned to `e67aa09031583f976a39c8406ae86585b02cde76`; subsequent repository development does not silently rewrite this edition's reported findings. The current capital policy treats prospective capital and financing as design variables while preserving historical fixed-capital studies.

```bibtex
@techreport{boucher2026agialphaflywheel,
  author = {Vincent Boucher},
  title = {AGI ALPHA FLYWHEEL: Inventing What Becomes Possible},
  institution = {MONTREAL.AI},
  year = {2026},
  month = {November},
  note = {Research edition 1.0, 2 November 2026},
  url = {https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/agi-alpha-flywheel.html}
}
```

Machine-readable citation metadata is in [CITATION.cff](CITATION.cff). The publication release identifies a research edition, not peer review or a release of the enterprise runtime. Existing research editions and operating evidence retain their own status.
