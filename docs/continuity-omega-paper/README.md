# CONTINUITY Ω

**English** · [Français](README.fr.md)

## Keep the promise.

**Independently verified cyber resilience**  
**Cybersecurity Resilience — Invent the Economy of Continuity**

Vincent Boucher · MONTREAL.AI / QUEBEC.AI · 6 November 2026 · Bilingual research edition 1.1.1.

**Read:** [Versioned release 1.1.1](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/continuity-omega-v1.1.1) · [Complete English paper](CONTINUITY_OMEGA.pdf) · [Article intégral en français](CONTINUITY_OMEGA_FR.pdf) · [English browser reader](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega.html) · [Lecture française dans le navigateur](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-fr.html) · [English LaTeX](CONTINUITY_OMEGA.tex) · [LaTeX français](CONTINUITY_OMEGA_FR.tex) · [Evidence guide](EVIDENCE.md) · [Review](REVIEW.md).

**Visual collection:** [English animation gallery](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-media.html) · [Galerie d’animations en français](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-media-fr.html). Four English/French animation pairs have still previews, play/stop controls and complete transcripts; they are conceptual illustrations, not operational evidence. **Citation metadata:** [English](CITATION.cff) · [Français](CITATION.fr.cff).

Edition 1.1.1 supplies complete English and French reading paths over the same scientific claims and evidence. The [language contract and glossary](TRANSLATION.md) define what is translated and what remains byte-identical. The [original 1.0.0 release](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/continuity-omega-v1.0.0) retains its own tag, notes and assets. This bilingual publication does not qualify a new prototype revision. Edition 1.1.1 corrects the French main title to **CONTINUITÉ Ω**; the English title remains **CONTINUITY Ω**. The [preceding bilingual edition 1.1.0](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/continuity-omega-v1.1.0) remains unchanged. Scientific content and historical evidence are preserved.

> AI that finds the vulnerability is a breakthrough. Intelligence that helps businesses survive the vulnerability—and invents a viable market for continuity—is a different game.

A restored system can still contain a broken business: the accepted order that disappeared, the amendment that reverted, the cancellation that returned, or the fallback production slot promised to someone else. CONTINUITY Ω turns these omissions into a constructive question: **what must now exist so the business can still keep its promise?**

## The paper's contribution

The business commitment is the unit of evaluation. A challenger supplies a material objection; evidence or a controlled test adjudicates it; construction changes the permitted technical or commercial route; separate acceptance checks the original outcome; and a different successor tests whether the retained capability helps.

The paper connects the three foundations—**Transformational Intelligence**, **ALPHA GENESIS FLYWHEEL Ω**, and **Invent the Economy**—to source completeness, portable production obligations, common dependencies, simultaneous capacity claims, complete costs and a bounded Continuity Passport. Its formal observations are conditional and elementary, not claims to have invented disaster recovery, critique or market design.

The exact pooling illustration makes one constraint visible: costs can require at least three buyers while the emergency capacity can serve at most two. More sales cannot repair an incompatible promise.

## Who uses version one?

**Proposed buyer:** operations director at a regional B2B packaging-label printer without a second site; owner/GM approves commercial terms.

**Proposed service:** one authorized rehearsal, one product and one qualified fallback route. Reconcile the customer commitment, expose missing evidence, prepare a permitted production package, verify current reserved capacity and the complete delivery path, and produce a scoped result. Actual physical delivery and payment require their own evidence.

**Single commercial assumption:** within a prospectively registered campaign, at least one target buyer accepts and funds the complete rehearsed reservation/activation offer at a price covering its full costs, despite a credible incumbent or self-service alternative. A paid preparation exercise tests demand for that stage only.

The example target of up to **20,000 units within 48 agreed business hours** is a proposed contract to qualify. It is not demonstrated by the **1,900-unit synthetic record**.

## What was actually reproduced

| Pinned existing source | Reproduced result | Boundary |
| --- | --- | --- |
| PR 278, `a755d0375693465f8f31c0c919cc186eae74bbcc` | **29 tests pass**; all **12 CLI cases** match their documented outcome: 3 handoff passes, 9 refusals. Two obligations total **1,900 units**. | Authored records, supplied capacity, consent flags, prices and lead times. A handoff pass does not repair the restored snapshot. |
| PR 277, `84c4288b4726a17a90f8462d1d6faf8b5f8f00b5` | **9 tests pass**; four authored decisions are `[accept, reject, reject, reject]`. | The competent conventional comparator **ties all four decisions**. |

These are **38 distinct implementation tests**, not 38 real incidents or an empirical model benchmark. The current handoff source contains 29 tests; the older PR prose's 23-test count is not reused. The US$650 handoff contribution is authored arithmetic. The separate earlier GENESIS Commitment 001 central case's **US$1,080 modeled loss** remains unchanged.

### The passing suite is not the end of the challenge

Five additional probes against the same unchanged handoff source preserve a nominal positive control, reproduce three weaknesses, and demonstrate an already-disclosed trust boundary. The verifier accepts a Boolean monetary offer in a coherently adjusted zero-cost case; malformed top-level input raises an exception; and `inspect` displays an old readiness Passport after the handoff has changed, although fresh `verify` rejects it. A coherently rewritten and resealed scenario also passes, demonstrating consistency rather than authenticated origin.

These probes were motivated by the [subsequent hardening review at its inspected revision](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/6cd7e1bb7197cabdf8f3d093eead662cde5351f4/docs/continuity-omega/HARDENING.md). The paper reproduces the weaknesses in the earlier source; it does not qualify the proposed repair. See [the compact observations](evidence/COUNTEREXAMPLES.json) and [the replay](counterexamples.py). The 29 original tests still pass. The counterexamples remain counterexamples.

No frontier-model benchmark, real cyberattack, production recovery, supplier booking, physical manufacturing, customer acceptance, payment, new financial account or third-party certification was performed for this publication. Model superiority, actual demand, sustainable profit, market formation and improved discovery remain unestablished.

## Build and verify

Requirements: Python 3.10+, `pdflatex`, `pdftotext`, `pdfinfo`, and a standard TeX Live installation with `texlive-latex-extra`, `texlive-fonts-recommended`, `texlive-science`, `texlive-plain-generic`, `texlive-lang-french` (for French Babel), and `lmodern`. No model API, key, paid service or shell escape is needed.

```sh
python3 build.py --language all
python3 verify.py --check-build
python3 pooling_example.py
```

`python3 build.py` also builds both languages by default. Use `--language en` or `--language fr` for an individual manuscript; `verify.py --check-build` checks both rebuilt language versions, so build both before that verification.

The two canonical PDFs are identity-bound by [PUBLICATION.json](PUBLICATION.json). A different TeX distribution can change PDF bytes; the build check compares each rebuilt manuscript's extracted text with its own canonical language version. To intentionally update the canonical manuscripts after review, use `python3 build.py --language all --publish` and regenerate the publication manifest and reader metadata as a new reviewed edition.

## Reproduce the original engineering

The implementations remain at their original pinned revisions. They are not copied into or merged by this paper. The [reproduction record](evidence/REPRODUCTION.json) lists each fetched file's exact Git blob and SHA-256.

```sh
# From a clean checkout of PR 278's pinned revision:
python3 -m unittest discover -s tests -p 'test_continuity_omega.py' -v
python3 -m continuity_omega demo --out /absolute/new/continuity-run
python3 -m continuity_omega verify --in-dir /absolute/new/continuity-run

# Separately, from PR 277's pinned revision:
python3 -m unittest discover -s tests -p 'test_connected_continuity_omega.py' -v
python3 campaign/continuity_omega_20261106/continuity_proof.py
```

The optional `python3 reproduce.py --output /absolute/new/reproduction` downloads only the pinned public source files, verifies their identities, executes the two offline test suites and all documented cases, and writes a compact fresh result. Network access is needed only for those public source downloads. It creates no account and does not resume any existing business. The public repository and its live branches retain their own adoption and release status.

Challenge the freshly downloaded handoff source separately:

```sh
python3 counterexamples.py --source278 /absolute/new/reproduction/source278 --output /absolute/new/counterexamples
```

A successful counterexample replay means the stated observations and weaknesses were reproduced. It is not a qualification pass for the checker.

## Downloadable source package

The release provides `CONTINUITY_OMEGA.pdf`, `CONTINUITY_OMEGA_FR.pdf` and `CONTINUITY_OMEGA_SOURCE.zip`. The ZIP includes both complete editable manuscripts and canonical PDFs, bibliographies, bilingual claim registers and documentation, shared compact evidence, and all build/reproduction scripts. Each bibliography is inside its LaTeX source; no separate `.bib` file is required.

```sh
python3 package.py --output /absolute/new/continuity-publication
```

Packaging checks the complete publication inventory and refuses to overwrite an existing output directory. To reproduce from previously downloaded sources without network access, add `--source277 /absolute/source277 --source278 /absolute/source278` to the reproduction command; every source file must still match both published identities.

## Publication and reuse

[Source lineage](SOURCE_MAP.md) identifies the foundation pages. [CLAIMS.json](CLAIMS.json) and its [complete French translation](CLAIMS.fr.json) distinguish formal, reproduced, proposed and unestablished claims using identical claim IDs, status tokens, source anchors and measurements. The [evidence guide](EVIDENCE.md) explains the shared machine-readable records; those records are not translated into different experimental results. Separate AI workstreams challenged sources, theory and the manuscript within one assistant workflow. This is not an independently certified field result or a two-model comparative experiment.

The user-supplied source documents and private conversation records are not redistributed. Public source links are provided for attribution. Earlier papers, prototype branches, historical failures and financial authority are preserved.
