# ⚡♾️ OUT-ACCELERATE

## Intelligence that accelerates the means of acceleration.

**Vincent Boucher · MONTREAL.AI**  
**TRANSFORMATIONAL INTELLIGENCE ∞ · Research edition 1.0 · 2 November 2026**

[Read the PDF](../out-accelerate.pdf) · [Browser reader](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/out-accelerate.html) · [LaTeX](../out-accelerate.tex) · [Bibliography](../out-accelerate.bib)

**What should intelligence change now so that the next important advance becomes easier to discover, establish, and deliver?**

OUT-ACCELERATE studies the construction of the means of progress: instruments, representations, verification procedures, complementary processes, and voluntary arrangements. It asks whether an advance leaves useful capabilities that improve the next mission, and how to distinguish better inherited equipment from a better process for discovering it.

The paper's central distinction is practical: a prerequisite of the chosen method need not be a prerequisite of the required outcome. Replacing or removing it counts as improvement only when the intended result and material acceptance requirements survive.

[![OUT-ACCELERATE cover](cover.png)](../out-accelerate.pdf)

## Choose a reading path

| Interest | Start here |
| --- | --- |
| The idea and its connection to Transformational Intelligence | Paper §§1–3 |
| Exact mathematics, assumptions, and the worked example | Paper §§4–5 and Appendix A |
| Testing whether the inventor improved | Paper §§6–7 |
| New productive activities and funded expansion | Paper §§8–10 |
| Running the example and compiling the paper | Commands below |

## What is demonstrated

This is a conceptual research paper with an executed, exact analytical illustration. The illustration has two production stages, complementary trace-producing and checking components, charged acquisition and transfer, and an unchanged output contract.

| Supplied workflow | Primary time | Subsequent time | Total time | Total worker-time |
| --- | ---: | ---: | ---: | ---: |
| Original pipeline | 148 | 208 | 356 | 472 |
| Faster construction | 145 | 202 | 347 | 376 |
| Trace producer alone | 163 | 217 | 380 | 516 |
| Checker alone | 162 | 216 | 378 | 494 |
| Complementary bundle | 85 | 100 | 185 | 214 |
| Bundle and faster construction | 49 | 40 | 89 | 118 |
| Same bundle rebuilt for the subsequent batch | 49 | 64 | 113 | 142 |
| Ordinary reuse of the same supplied combination | 49 | 40 | 89 | 118 |

All main workflows accept the same 22 exact outputs. Durations and tool effects are **stipulated model quantities**, not measured AI speed or industrial throughput. The ordinary workflow ties. A single-output horizon makes the constructed bundle slower; incompatible transfer and corrupted certificates are rejected.

The subsequent inputs are different, public, and prespecified. They are an illustrative successor, not a concealed empirical holdout. The paper proposes, but does not run, the stronger discovery-policy experiments. It reports no commercial deployment or profit.

## Reproduce the example

Python 3.10 or later and the standard library are sufficient. From the repository root:

~~~sh
python3 docs/research/out-accelerate/acceleration_witness.py \
  --output-dir /tmp/out-accelerate-replay
cmp docs/research/out-accelerate/results/results.json \
  /tmp/out-accelerate-replay/results.json
cmp docs/research/out-accelerate/results/summary.csv \
  /tmp/out-accelerate-replay/summary.csv
~~~

The script checks exact scheduling, complete charges, component losses, output correctness, corrupted certificates, invalid transfer, fallback behavior, short-horizon loss, and the break-even inequality. It makes no network or model-provider requests.

[MODEL.md](MODEL.md) specifies the complete model and proof. [results/summary.csv](results/summary.csv) is the compact result table; [results/results.json](results/results.json) retains parameters, ledgers, traces, negative controls, and the conventional tie. The existing website workflow reproduces both files and compares their bytes.

## Build the PDF

Use XeLaTeX, BibTeX, latexmk, and standard TeX packages. The source prefers TeX Gyre Pagella/Heros, falls back to URW OpenType fonts on Linux or Latin Modern, and uses DejaVu Sans Mono.

~~~sh
cd docs/research
latexmk -xelatex -interaction=nonstopmode \
  -halt-on-error -no-shell-escape out-accelerate.tex
~~~

The cover emblem, architecture diagram, and analytical curves are vector graphics in the LaTeX source. No external images, model service, shell escape, or private documents are required. The checked-in PDF is readable without installing TeX.

## Cite this edition

> Boucher, Vincent. *OUT-ACCELERATE: Intelligence that accelerates the means of acceleration.* MONTREAL.AI, research edition 1.0, 2 November 2026.

[CITATION.cff](CITATION.cff) and [citation.bib](citation.bib) describe this paper. The separate [out-accelerate.bib](../out-accelerate.bib) contains its cited literature. No DOI or peer-review status is claimed.

The exact PDF size and SHA-256 are recorded in the [publication manifest](../publication-manifest.json). A Git commit permalink identifies an immutable source edition. [REVIEW.md](REVIEW.md) records the scoped technical and editorial review.

## Research foundations

- [Transformational Intelligence: Learning to Change the Game](../transformational-intelligence-202610.pdf)
- [The OUT research collection](../out-series.html)
- [Practical research guide](../../harness/RESEARCH_FOUNDATIONS.md)

The paper is a supporting research artifact for consequential construction. Its publication does not establish the lab's US$3 billion trailing-365-day profit objective.
