# FLYWHEEL Ω

## The Economy as an Output

**Vincent Boucher · President of MONTREAL.AI · MONTREAL.AI / QUEBEC.AI**  
**Transformational Intelligence ∞ · Research edition 1.0.0 · 3 November 2026**

**The next breakthrough may be the game that makes it possible.**

[Read in your browser](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/flywheel-omega.html) · [Download the PDF](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/download/flywheel-omega-v1.0.0/FLYWHEEL_OMEGA.pdf) · [LaTeX source](paper.tex) · [Versioned PDF and source ZIP](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/flywheel-omega-v1.0.0)

FLYWHEEL Ω studies intelligence that constructs complete productive arrangements: useful outcomes, the means of producing and verifying them, voluntary participation, payment, financing and the capabilities left for subsequent work. Its central connection is practical: **what participants can actually do determines which payments can be collected, and those payments help determine what can be constructed next.**

The paper develops this connection through productive composition, an exact constructive example, independent finite checks and a source-bound examination of the public Omega mechanism experiment. It follows [Transformational Intelligence](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/transformational-intelligence.html), [Invent the Economy](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/invent-the-economy.html), [SUPER ALPHA](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/super-alpha.html) and [OUT-ACCELERATE](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/out-accelerate.html).

### What the exact companion establishes

- A dynamic program for the cheapest composition of accepted services agrees with an independent exhaustive-cart oracle on **2,187 menus**, **279,936 carts** and **413,343 buyer/budget/menu cases** in the declared finite domain.
- A separate **4,096-menu** study shows that allowing productive composition can raise, lower or preserve seller receipts. An ordinary exhaustive optimizer receives the same choices and ties the optimum.
- A supplied connector and a staged voluntary contract jointly make a complete production route financeable at opening cash six. Its cash path is **6 → 4 → 1 → 7 → 3 → 9**. Neither change alone suffices at that capital.
- The constructor preserves stronger alternatives: with opening cash nine, a final-only pure bundle earns more; ordinary reuse of the same connector matches inherited capability; and a better-funded second episode can change its contract again.
- A source-pinned historical menu quotes the joint services at 1,554 cents while its two components cost 518 + 823 = 1,341 cents. The **213-cent** gap exposes a limitation of checks that consider only single purchases. The optional historical replay reproduces the original solver and verifier; the standard-library companion preserves the arithmetic separately.

The new numerical work is an **authored analytical verification**. Values, productive effects, process costs and timing are stipulated. An additional upfront lifecycle burden `h ≥ 0` changes the staged route's required capital to `5 + h` and surplus to `3 − h`. Unknown actual model, hosting, development and discovery costs are not measured or assumed to be zero. The work does not establish empirical demand, open-world incentive compatibility, autonomous invention superiority, physical deployment or the lab's unachieved US$3 billion trailing-365-day complete-cost profit objective.

### Start with the source ZIP

Download and extract **FLYWHEEL_OMEGA_SOURCE.zip**. Open a terminal in the extracted folder containing `README.md`, `companion.py`, `paper.tex` and `Makefile`. This is a flat source archive; **do not add `cd docs/flywheel-omega` when using the ZIP**. It includes the inspected paper as `FLYWHEEL_OMEGA.pdf` and preserves `sections/` and `figures/` beneath the root.

For an existing repository checkout, instead run this once from the repository root:

```sh
cd docs/flywheel-omega
```

All subsequent commands work from either of those two starting locations.

### Reproduce the analytical results

Python 3.10 or later and its standard library are sufficient:

```sh
python3 -m unittest discover -s . -p 'test_companion.py' -v
python3 companion.py --output /absolute/new/results.json
```

Choose a new output file; the companion refuses to overwrite existing evidence. Compare the generated JSON with the supplied `results.json`. The 24 focused tests include independent enumeration, missing composition rights, unavailable unions, budgets, refusal, adverse ties, protected cash, collection timing, lifecycle costs, non-entry and strong ordinary controls. The [protocol](PROTOCOL.md) declares the finite domains and what the results mean.

### Compile and verify the manuscript

You need `make`, Python, a standard TeX Live installation with `latexmk`, BibTeX, Latin Modern and Palatino/mathpazo fonts, and Poppler's `pdftotext` and `pdfinfo` commands. On Debian or Ubuntu:

```sh
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  python3 make latexmk lmodern texlive-latex-extra \
  texlive-fonts-recommended poppler-utils
```

On another operating system, install the equivalent TeX Live and Poppler tools and make them available on your command path. The supplied vector figure is already included; compiling the paper does not require Matplotlib, NumPy or SciPy.

Then run:

```sh
make check
python3 verify.py
python3 package.py --output /absolute/new/flywheel-omega-publication
```

`make check` compiles into `build/`, runs the analytical tests and checks the compiled PDF. Full verification additionally checks the source hashes in `PUBLICATION.json`, the inspected PDF's bytes and page count, and equality of normalized text between the rebuilt and inspected PDFs. Missing glyphs, unresolved citations/references, overfull boxes and duplicate PDF destinations fail verification. These checks complement the publication's visual review.

The new output directory contains:

| File | Purpose |
| --- | --- |
| `FLYWHEEL_OMEGA.pdf` | The inspected publication, preserved byte for byte |
| `FLYWHEEL_OMEGA_SOURCE.zip` | Self-contained LaTeX, figures, exact companion, provenance, checks and the inspected PDF |
| `SHA256SUMS` | SHA-256 checksums for the two release files |

The package command refuses an existing output directory and leaves `build/` intact. Its ZIP entries have fixed metadata and use storage without compression to avoid compression-library variation. TeX distributions can still produce different PDF bytes; the original inspected PDF is preserved, and normalized rebuilt text must agree.

To verify downloaded release files on a system with `sha256sum`, run from the folder containing all three files:

```sh
sha256sum --check SHA256SUMS
```

On macOS, `shasum -a 256 -c SHA256SUMS` provides the corresponding check.

### Optional replay of the historical public mechanism

This step is separate from the new standard-library companion. It reruns one pinned public mechanism with its original source, original solver call and independent verifier. It does **not** create or replay native business accounts.

The recorded environment used NumPy **2.3.5** and SciPy **1.17.0**; the complete observation is in [public_replay.json](public_replay.json), with public file identities in [sources.json](sources.json). Install those optional dependencies in an isolated Python environment if you want to reproduce that solver run. A changed solver/version may produce a different tied program; the replay rejects a program-hash difference and asks you to inspect it rather than silently substituting a different result.

From the paper source directory, this Unix-shell recipe downloads only a separate public source checkout and extracts the relevant paths:

```sh
paper_dir="$(pwd)"
replay_dir="$(mktemp -d -t flywheel-omega-replay.XXXXXX)"
git clone --filter=blob:none --no-checkout --depth 1 \
  https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab \
  "$replay_dir/repository"
git -C "$replay_dir/repository" fetch --depth 1 origin \
  8cd375784c24b879ae1eb4835c6af4fb925cbf4c
mkdir "$replay_dir/source"
git -C "$replay_dir/repository" archive FETCH_HEAD \
  mechanism_harness commercial experiments/commerce006.py \
  | tar -x -C "$replay_dir/source"
python3 "$paper_dir/replay_public_case.py" \
  --source-dir "$replay_dir/source" \
  --output "$replay_dir/public-replay.json"
```

Run the final command with the Python environment containing the optional solver dependencies. The replay verifies all eleven imported project-source files before import. The expected single-report verifier checks 72 deviations, accepts the historical program and records the 213-cent composed-purchase obstruction. This is a source-bound reproduction of one modeled case, not production-release qualification or real-market evidence.

### Figures and publication provenance

`make_figures.py` can regenerate the construction figure from the exact companion if Matplotlib is installed. The supplied figure already participates in the source manifest; changing it creates a different source edition until the publication record is deliberately updated. No figure regeneration is necessary for the standard build.

The [bibliography](references.bib), [public sources](sources.json), [analytical protocol](PROTOCOL.md), [exact results](results.json) and `PUBLICATION.json` make the edition inspectable. The publication workflow builds the actual candidate source, checks the artifact, packages only the manifest's explicit source list, and creates or verifies the versioned release. It never overwrites a different existing release or moves an existing tag. Earlier papers, original experiments, accounts and private source documents remain outside this additive publication.

### Citation

Boucher, Vincent. *FLYWHEEL Ω: The Economy as an Output*. MONTREAL.AI / QUEBEC.AI, research edition 1.0.0, 3 November 2026. See [CITATION.cff](CITATION.cff).
