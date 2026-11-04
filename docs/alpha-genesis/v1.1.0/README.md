# ALPHA GENESIS FLYWHEEL Ω

## Turn the next advance in AI into your next ability to autonomously discover at scale.

**Vincent Boucher · MONTREAL.AI / QUEBEC.AI**  
Research release **1.1.0** · Evidence cutoff **4 November 2026**

**Start here:** open `START_HERE.html` in a browser, or read the **32-page** `ALPHA_GENESIS_FLYWHEEL_OMEGA.pdf`.

This is a publication and reproducible research release, not the deployed GENESIS Discovery Studio. It includes the paper, editable LaTeX, analytical code, exact results, an interactive arithmetic illustration, tests and a static-publication toolkit. It does not run a frontier model, operate laboratory equipment, collect payments or contain the proposed general autonomous discovery runtime.

## What changed in 1.1

The release review found and corrected a material verification weakness: the previous conventional replay-control result was copied from the selective-policy result. The conventional control is now calculated separately. Its tie remains, but is now checked instead of assumed in the implementation.

The update also replaces optimization-removable scientific assertions with explicit checks, executes the generated observer, checks every emitted study artifact, rejects incomplete or tampered package inventories, and adds adverse replay and cost cases. The paper now includes a concrete conversion contract and separate publication, computational-pilot, physical and commercial deployment gates. See `REVIEW_NOTES.md`.

## Reproduce the evidence

Use **Python 3.10 or newer**. The analytical companion and verification tools use the Python standard library. They make no network calls, require no credentials, spend no money and operate no equipment. The recorded execution environment is identified in `source/BUILD_REPORT.json`; no untested platform is claimed as qualified.

From the extracted **source package** folder:

```sh
python3 verify.py
```

This checks the complete file inventory and hashes, local HTML links, all four regenerated study artifacts, and **68 tests in both normal and optimized Python modes**. The checksum file is unsigned: it detects accidental changes relative to the supplied manifest, not publisher impersonation. Verify its provenance through a trusted release channel.

To generate your own new result directory:

```sh
python3 study/companion.py --output /absolute/new/genesis-results
```

Choose a new directory. The companion refuses an existing or symlinked output target instead of silently replacing evidence. Its supplied models establish:

| Study | Reproduced result | Scope |
|---|---|---|
| Observation construction | 8 candidate rows, 6 full-rank choices, 225 exact checks; best error bound 0.1 | Supplied two-effect linear model; conventional algebra ties. |
| Supplied constructor reuse | Four coefficient variants, 1,764 exact checks | Not autonomous cross-domain discovery or improved invention. |
| Dependency replay | 25 versus 5 evaluations; the same five completions; independent conventional control ties | Complete supplied prerequisites; not real relevance detection. |
| Adversarial replay | Inaccessible announcement, revoked access, a missed alternative; +17, −5 and −13 net gains under three cost assumptions | Synthetic state and economic examples; not a live authority service. |
| Funding and lag | 44 versus 80 opening units at the same surplus of 40; conditional adoption-lag identities | Authored accounting and growth assumptions; no real demand or revenue. |

`compiled_observer.py` is an **abstract algebraic observer**, not an EIT simulator, sensor driver or physical sensing invention. `source/CLAIM_REGISTER.md` maps each result to its actual support and boundary.

## Build the PDF

Install a normal TeX Live distribution containing `pdflatex`, New PX, TikZ/PGFPlots, tcolorbox, natbib, upquote and the standard packages in the manuscript preamble. Full verification also needs Poppler's `pdftotext`. No font files are bundled.

```sh
python3 build_paper.py
python3 verify.py --full
```

The build uses three passes with **shell escape disabled**, rejects unresolved references, missing characters, overfull boxes and LaTeX warnings, and writes into `build/`. It never overwrites the inspected PDF at the root. Full verification compares normalized extracted text from the rebuilt and inspected PDFs. PDF bytes may differ between TeX distributions or build dates.

The bibliography and vector figures are embedded in the `.tex`; BibTeX is unnecessary. The complete package includes `assets/successor_reference.png`. An isolated `.tex` build without it uses a labeled fallback; use the full package to reproduce the complete visual edition.

## Publish the research

A separately supplied **WEBSITE.zip** contains an immediately usable static site: `index.html`, assets, PDF, editable source, source archive and supporting evidence. Extract that website archive into a new, versioned directory on your chosen static host. Do not upload the private input conversations. See `DEPLOYMENT.md` for validation and rollback.

To reproduce the publication bundles from this source package:

```sh
python3 publish.py --output /absolute/new/genesis-publication
```

Add `--full` to include the PDF rebuild in preflight. This command only prepares local files; it uploads nothing and changes no repository or service.

After publication, use the **trusted local** manifest from the exported `site/` directory to compare the actual served files:

```sh
python3 check_published.py \
  --base-url https://YOUR-HOST/your-versioned-directory/ \
  --expected /absolute/path/to/genesis-publication/site/SHA256SUMS
```

This is the only provided utility that performs network requests, and only when explicitly invoked with a host. It verifies served bytes, not host ownership, HTTPS configuration, application security or commercial readiness. A successful localhost test is not a public deployment receipt.

## Package map

| Location | Purpose |
|---|---|
| Root PDF / LaTeX | Inspected 32-page manuscript and editable source. |
| `START_HERE.html`, `assets/` | Responsive reading guide and explicitly labeled arithmetic explorer. |
| `verify.py`, `release_tools.py` | Inventory, integrity, regeneration, tests and local-link checking. |
| `build_paper.py` | Warning-checked, no-shell-escape three-pass PDF build. |
| `publish.py`, `check_published.py` | Prepare versioned static publication and compare served files. |
| `DEPLOYMENT.md`, `RELEASE_STATUS.json` | Publication procedure, rollback and the exact deployment boundary. |
| `study/companion.py`, `study/test_*.py` | Analytical calculations and 68 analytical/release-integrity tests. |
| `study/results/`, `study/TEST_RESULTS.txt` | Exact retained artifacts and normal/optimized test logs. |
| `source/CLAIM_REGISTER.md` | Claim–evidence distinctions. |
| `source/FRONTIER_RECHECK.json`, `source/WEB_SOURCES.json` | Targeted source recheck and the larger bibliography register. |
| `source/BUILD_REPORT.json` | Recorded environment and publication checks. |
| `source/SOURCE_PROVENANCE.json` | Input identities; private input files are not distributed. |
| `source/original/` | Preserved original results, test/build records and source identity for correction history. |
| `SHA256SUMS` | Complete release-file digests, excluding this manifest itself. |

The conceptual reference art is not experimental data. Private research dialogues, credentials and font files are not bundled. The release has not received external peer review. A passing test suite is not a certificate of autonomous discovery, universal security, scientific novelty, physical performance or demand.

## Citation

Boucher, Vincent. *ALPHA GENESIS FLYWHEEL Ω: Riding the Exponential—From Frontier Intelligence to Compounding Discovery and Productive Power*. MONTREAL.AI / QUEBEC.AI, research release 1.1.0, 4 November 2026. See `CITATION.cff`.

**Invent the means. Expand what becomes possible. Compound the ability to discover.**

## Public filename-redaction revision

This public revision of research edition 1.1.0 replaces private input filenames with neutral source labels, with author approval. The manuscript substance and analytical companion are unchanged. The PDF was rebuilt and package hashes refreshed; do not use original pre-redaction PDF or archive hashes to identify this revision. See `REVIEW_NOTES.md` and `source/BUILD_REPORT.json`.
