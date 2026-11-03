# SUPER ALPHA

## Inventing Economic Possibility

**Vincent Boucher · MONTREAL.AI / QUEBEC.AI · 3 November 2026 · Research edition 1.1.0**

**Invent what becomes possible.**

[Read in your browser](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/super-alpha.html) · [Download the PDF](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/download/super-alpha-v1.1.0/SUPER_ALPHA.pdf) · [Editable LaTeX](paper.tex) · [Versioned PDF and source ZIP](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/super-alpha-v1.1.0)

SUPER ALPHA investigates how intelligence can construct valuable activities that existing complete methods cannot deliver economically, earn an extraordinary advantage in delivering them, and use retained resources and capabilities to enable more consequential successors.

The paper connects three questions: **What can become possible? Why can its creator sustainably prosper? What does success enable next?** The object of invention includes production, verification, voluntary cooperation, financing and operating policy. Its long horizon extends through scientific instruments, useful energy, manufacturing and progressively capable physical infrastructure.

### Contributions

- A scoped definition of economic enablement that compares complete routes, includes a nonempty tested alternative set and preserves unresolved alternatives.
- A commercial price window that becomes a construction target: identify how much complete burden must change, or how much additional voluntary demand is needed, for an activity to pay.
- An exact minimum-capital result for a declared, ordered cash plan and an explicit condition for qualifying a successor before an advantage closes.
- Four separately evaluated processes: commerce, capability inheritance, improvement of discovery and physical production.
- An exact analytical example in which production improvement and shared construction jointly enable profitable delivery; strong conventional construction ties the result.
- Counterexamples for collection delays, protected cash, imitation, failed acceptance and the distinction between financing, causal enablement and improved discovery.
- Three proposed industry families: scientific capability foundries, on-demand historical observation and adaptive industrial infrastructure.

### What the example establishes

Ten stipulated buyers each value an accepted output at 13 abstract units. At selected price 12:

| Production and construction arrangement | Complete model cost | Conditional receipts | Conditional profit |
| --- | ---: | ---: | ---: |
| Old, individual | 320 | 120 | −200 |
| New, individual | 370 | 120 | −250 |
| Old, pooled | 140 | 120 | −20 |
| New, pooled | 100 | 120 | **20** |

The joint route leaves 10 units of buyer benefit. A competent conventional constructor with the same choices ties. Loss rows are forced-delivery diagnostics; optional non-entry remains available at zero. Price 12 is selected, not an equilibrium or observed price.

### What edition 1.1 adds

The commercial condition becomes a specification for invention. When buyer value exceeds a qualified competitive price cap `r`, the gap `Δ = F + nc + m − nr` measures the complete-cost shortfall for a required total margin `m`. With fixed cost 30, marginal cost 7, ten buyers, price cap 10 and required margin 20, the gap is 20. Conditional targets are fixed cost at most 10, marginal cost at most 5, or at least 17 buyers with genuine demand and sufficient capacity. Each target still needs an accepted construction, with its own full burden included.

The revision then connects construction to funding and renewal. Three declared cash schedules require starting capital of 100, 105 and 225 while producing the same complete-history profit of 55. Their different commitments, collection timing and protected obligations explain why profit alone cannot determine whether a plan can run. A separate renewal example shows how available earnings and qualification time jointly determine whether a successor can arrive before the current advantage closes.

These are **authored analytical illustrations in abstract units**, with all cost and acceptance assumptions stated. They are not real buyer evidence, a native enterprise simulation, autonomous scientific discovery or a physical result. The source-reviewed public experiments retain conventional ties/wins, negative results and their original scopes. The US$3 billion trailing-365-day complete-cost profit objective remains unachieved.

### Reproduce the analytical example

Python 3.11+ and its standard library are sufficient. If you downloaded `SUPER_ALPHA_SOURCE.zip`, extract it and open a terminal in the extracted folder containing `companion.py` and this README. The archive has a flat source layout and includes the inspected paper as `SUPER_ALPHA.pdf`. Run:

```sh
python3 companion.py --output /absolute/new/results.json
python3 -m unittest discover -s . -p 'test_companion.py' -v
```

For a repository checkout instead, first run `cd docs/super-alpha` from the repository root, then use the same commands. The output path must name a new file in a directory you can write to.

Fourteen focused tests cover 8,320 price/participation combinations and 7,381 collection/reserve states, plus exact central results, failed acceptance, imitation, conventional ties and successor comparisons. Edition 1.1 extends the calculation with construction targets, 2,000 ordered funding plans and 1,440 renewal scenarios. These checks validate the finite analytical calculation, not the proposed businesses.

### Build and verify the paper

Install a standard TeX Live toolchain including `latexmk`, `lmodern`, `texlive-latex-extra`, `texlive-fonts-recommended`, BibTeX and Poppler. Then run:

```sh
make check
python3 verify.py
python3 package.py --output /absolute/new/super-alpha-publication
```

The supplied vector figures compile without plotting dependencies. To regenerate the exact threshold figure and CSV, use Python with Matplotlib and run `python3 make_figures.py`.

`PUBLICATION.json` binds the inspected PDF and source files. The verifier checks source hashes, normalized extracted PDF text, unresolved references, layout warnings, page count and exact analytical results. PDF bytes may differ between TeX distributions; the inspected publication is preserved separately. The source ZIP is self-contained for compilation and includes the inspected PDF.

### Read and build on the research

The manuscript follows [Transformational Intelligence](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/transformational-intelligence.html), the [AGI ALPHA foundation](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/agi-alpha.html), [Invent the Economy](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/invent-the-economy.html), the OUT collection, [Beyond the Production Frontier](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/beyond-the-production-frontier.html), and the [November experimental report](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/agi-alpha-flywheel-report-20261102.html). Its public evidence snapshot is `030de783ae67e9a9a2330264a099740c50740f87`; original studies retain their own identities. [Public source identities](sources.json) and [bibliography](references.bib) support traceability.

This is an additive publication. Earlier paper editions, operating accounts and experiment histories are unchanged. The companion performs no network calls, opens no business account and grants no execution authority. Private source discussions and uploaded documents are not distributed.

### Edition history

- [Edition 1.1.0](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/super-alpha-v1.1.0): constructive economic targets, exact capital requirements, renewal timing and clearer standalone source instructions.
- [Preserved edition 1.0.0](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/super-alpha-v1.0.0): original paper, PDF and reproducible source.

### Citation

Boucher, Vincent. *SUPER ALPHA: Inventing Economic Possibility*. MONTREAL.AI / QUEBEC.AI, research edition 1.1.0, 3 November 2026. See [CITATION.cff](CITATION.cff).
