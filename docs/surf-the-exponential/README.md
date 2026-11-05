# SURF THE EXPONENTIAL: The Missing Move

**Find what the answer missed. Build what the world is missing.**

Vincent Boucher · MONTREAL.AI / QUEBEC.AI  
Research edition 1.0.0 · 5 November 2026

This 28-page paper develops an evidence-grounded path from consequential
criticism to new capabilities, viable productive arrangements, and better
methods of discovery. It builds on **Transformational Intelligence**, **ALPHA
GENESIS FLYWHEEL Ω**, and **Invent the Economy**. The three source editions and
their public content identities are recorded in
[`SOURCE_LINEAGE.json`](SOURCE_LINEAGE.json).

- [Read the paper in your browser](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/surf-the-exponential.html)
- [Read the canonical PDF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/surf-the-exponential.pdf)
- [Versioned release and complete source package](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/surf-the-exponential-v1.0.0)

## What the paper contributes

The central object is a **Missing Move contract**: an exact claim, its evidence,
its consequence for the authorized purpose, a discriminating test, the means
that must be constructed, and the conditions under which the result applies.
The challenger searches both for defects and for removable restrictions that
make a valuable activity appear impossible. Independent checking precedes
repair; complete alternatives and costs determine whether construction is
worthwhile.

The paper separates finding a true discrepancy, improving a useful artifact,
constructing a viable arrangement, transferring a capability, and improving a
discovery procedure. It proposes a matched evaluation programme for the
stronger claims. A conventional method, direct execution, or retaining the
incumbent can legitimately win.

## Evidence in this edition

The executable evidence is an **authored exact arithmetic audit**. Its
probabilities, utility values, and cash paths are stipulated. It is not an
empirical frontier-model benchmark, observed market demand, accepted buyer
terms, realized revenue, or a demonstration of general self-improvement.

| Check | Scope |
| --- | --- |
| Six named scenarios and five controls | Exact values for useful criticism, adverse conditions, conventional ties and wins, and a separately labelled unavailable information bound |
| 2,304-point Cartesian grid | All declared points are checked by explicit eight-branch probability enumeration |
| Three dependent-critic cases | Detection 0.7 per critic; combined miss probabilities 0.09, 0.258, and 0.3 under specified joint distributions |
| Two successful cash paths | Minimum additional starting cash 90 or 50, with the same stipulated net contribution 30 |
| 15 focused tests | Mathematical boundaries, exact inputs, changed-source rejection, output tampering, byte-identical regeneration, and publication consistency |

The fixed-target model concerns **one prespecified material-defect proposition
per episode**. The truth event, allegation, and accepted revision refer to
that same target. Mixed true/false allegation batches and adaptive target
selection are outside this finite audit. A true target without an accepted
challenge is not a measurement of post-repair error or whole-artifact coverage.

The grounded-challenge scenario has incremental utility **9.8875**. An equally
equipped conventional review ties it; conventional review with identical
conditional rates and a cost one unit lower obtains **10.8875**. Five adverse
scenarios select the incumbent. These are consequences of the declared model,
not measured rankings of real workflows.

The cash examples assume successful delivery and an authorized deposit usable
for the stated production costs. Advance cash remains an obligation until
earned. Their arithmetic does not establish consent, failure reserves, contract
execution, or actual business profit.

See [`REVIEW.md`](REVIEW.md) for substantive methodological corrections and
[`protocol.json`](protocol.json) for the complete assumptions, scenario inputs,
grid, acceptance checks, and stopping rule. The protocol discloses that the
illustrative arithmetic was examined during design; no untouched empirical
confirmation set is claimed.

## Package contents

| Files | Purpose |
| --- | --- |
| `paper.tex`, `sections-*.tex`, `references.bib` | Complete editable manuscript, vector diagrams, and bibliography |
| `study.py`, `check_study.py`, `test_study.py`, `protocol.json` | Exact computation, separate branch enumeration, focused tests, and specification |
| `evidence/results.json`, `results.csv`, `results_table.tex` | Compact evidence and the table consumed by the manuscript |
| `build.py` | Clean temporary-directory pdfLaTeX/BibTeX build without shell escape |
| `package.py`, `PUBLICATION.json` | Deterministic export and exact source/PDF identity binding |
| `README.md`, `REVIEW.md`, `SOURCE_LINEAGE.json` | Reproduction, editorial disposition, and public-source provenance |
| `canonical/SURF_THE_EXPONENTIAL.pdf` | Canonical PDF included inside the downloadable source archive |

The archive is flat: `build.py`, `package.py`, and the manuscript are at its
root. It includes everything required for offline identity checks and, with a
compatible local TeX installation, rebuilding. Public references need internet
access only if you choose to retrieve and inspect those references.

## Verify and reproduce

Python 3.10 or newer is sufficient for the arithmetic, tests, package creation,
and identity checks; they use only the standard library. PDF generation also
requires `pdflatex`, `bibtex`, and the TeX packages declared in `paper.tex`.
The reference build used pdfTeX 1.40.25 and BibTeX 0.99d from TeX Live
2023/Debian; the exact recorded versions are in `PUBLICATION.json`.

On Debian or Ubuntu, install the TeX dependencies and PDF inspection tools with:

```bash
sudo apt-get install texlive-latex-extra texlive-fonts-recommended poppler-utils
```

In a TeX editor or Overleaf, open or upload the complete source archive, choose
`paper.tex` as the main document, and select **pdfLaTeX**. Resolve the BibTeX
bibliography and compile again until references settle; the local `build.py`
does those passes automatically. The manuscript does not require shell escape.
An editor's different TeX version may produce different PDF bytes, as explained
below.

From this source directory, or the root of an extracted source archive:

```bash
python3 package.py --verify
python3 check_study.py
python3 -m unittest -v test_study
```

The checker does not import the producer's utility formula. It enumerates the
logical event branches and independently recomputes the cash-path prefixes.
This is independence of implementation, not external scientific replication,
an independently sampled empirical dataset, or a controlled multi-model trial.

To regenerate evidence in a separate directory and check its values:

```bash
python3 study.py --output /tmp/surf-recomputed-evidence
python3 check_study.py --evidence /tmp/surf-recomputed-evidence
```

To rebuild the paper:

```bash
python3 build.py --output /tmp/surf-rebuilt.pdf
```

The build fixes `SOURCE_DATE_EPOCH=1793836800` (5 November 2026, 00:00 UTC),
suppresses variable PDF metadata, disables shell escape, and resolves the
bibliography and references. It reports the output digest and any overfull
boxes, and rejects missing characters or undefined references.

### What reproducibility means here

`PUBLICATION.json` binds every substantive source file, the exact set of
compiled inputs, and the canonical PDF by size and SHA-256. The manifest
excludes itself from its source digest to avoid a circular hash. The recorded
source/PDF binding can be checked offline; its existence alone is not a proof
that a PDF was compiled from those sources. A clean rebuild supplies that
additional check.

With the same TeX toolchain, rebuilds are expected to be byte-identical. A
different TeX release, font package, or backend can produce different PDF bytes
and pagination from identical manuscript sources. Hosted checks therefore
compare two clean builds on the **same runner**, while retaining and verifying
the original canonical PDF. They do not silently replace its published digest
with a differently compiled PDF.

For an extracted archive and the reference toolchain, compare directly:

```bash
cmp canonical/SURF_THE_EXPONENTIAL.pdf /tmp/surf-rebuilt.pdf
```

For a repository checkout, the canonical file is
`../research/surf-the-exponential.pdf` relative to this directory.

## Build release assets

From the repository root:

```bash
python3 docs/surf-the-exponential/package.py --verify
python3 docs/surf-the-exponential/package.py --output-dir /tmp/surf-publication
python3 docs/surf-the-exponential/package.py --verify --output-dir /tmp/surf-publication
```

The exporter first verifies the manifest, then writes exactly four assets:

1. `SURF_THE_EXPONENTIAL.pdf` — the canonical PDF bytes.
2. `SURF_THE_EXPONENTIAL_SOURCE.zip` — complete sources, manifest, and canonical PDF.
3. `PUBLICATION.json` — the same inspectable identity manifest included in the archive.
4. `SHA256SUMS` — SHA-256 checksums for the other three assets.

The archive uses sorted paths, a fixed timestamp, normalized file permissions,
and stored ZIP entries. Omitting compression avoids dependence on a particular
compression-library version. It does not contain temporary TeX output,
intermediate review images, caches, account state, or credentials.

To check an exported package from a fresh directory:

```bash
cd /tmp/surf-publication
sha256sum -c SHA256SUMS
python3 -m zipfile -e SURF_THE_EXPONENTIAL_SOURCE.zip /tmp/surf-extracted
cd /tmp/surf-extracted
python3 package.py --verify
python3 check_study.py
python3 -m unittest -v test_study
python3 build.py --output /tmp/surf-extracted-rebuilt.pdf
```

A changed source or PDF fails verification. A new edition requires a deliberate
new manuscript build, review, and identity manifest; packaging does not rewrite
the recorded hashes to make a mismatch pass. Historical papers and their
evidence retain their own identities and scope.

## Cite this edition

```bibtex
@techreport{boucher2026missingmove,
  author      = {Boucher, Vincent},
  title       = {{SURF THE EXPONENTIAL}: {The Missing Move}---From Verified
                 Criticism to New Capabilities, Viable Markets, and Better Inventors},
  institution = {MONTREAL.AI and QUEBEC.AI},
  year        = {2026},
  month       = nov,
  number      = {Research edition 1.0.0},
  url         = {https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/surf-the-exponential-v1.0.0}
}
```
