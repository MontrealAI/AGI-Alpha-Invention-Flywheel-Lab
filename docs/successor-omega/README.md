# SUCCESSOR Ω — The Institution That Compounds

**Manufacturing mission advantage, preserving inventive capability, and financing the physical frontier.**

Vincent Boucher · MONTREAL.AI / QUEBEC.AI · 3 November 2026 · Research edition 1.0.0

> Own the institution. Replace the models. Preserve the mission.

[Read online](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/successor-omega.html) · [PDF](../research/successor-omega.pdf) · [Versioned edition](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/successor-omega-v1.0.0)

## The result
A lower-contribution portable capability yields **230 units of modeled cash surplus** versus **200** for the best no-portable alternative in the declared 16-period environment. The ordinary equal-content planner ties the result. Across 162 supplied environments, adding the option helps 19 and ties 143. Forced retention is infeasible in 108, loses in 43 and wins in 11. These are exact conditional model results, not market frequencies or real profit.

The paper formalizes renewal-adjusted Alpha, separates institutional knowledge from current proof and authority, derives a renewal crossover and throughput bound, and proposes an Industrial Requalification Foundry. Its physical horizon is expressed through explicit energy, material, heat and qualification requirements rather than extrapolated money.

## Reproduce

Python 3.10+ and standard library suffice for the numerical study:

```sh
python3 -m unittest -v test_companion
python3 companion.py --output results.json
```

For the paper and publication package, install PDFLaTeX, BibTeX, the standard TeX Live recommended/extra/fonts packages, Poppler and CairoSVG, then run:

```sh
python3 build.py --output /tmp/successor-publication
```

The output directory must be new. The build runs the tests and exact study, checks the registered values, typesets the PDF, records hashes/tool versions, and writes a deterministic source ZIP. The `--publish-site` option is reserved for the repository publication workflow and requires the expected repository paths. It adds only this paper and its discovery links; prior PDFs remain byte-for-byte unchanged.

## Scope
This is a framework, exact authored computational study and local state-machine witness. It does not establish autonomous invention, general ASI, real customer demand, production security or physical deployment. The designations in the four-stage vocabulary are conditional on mission-specific evidence; no model earns Specialist ASI in this study. The separate US$3 billion trailing-365-day complete-cost profit objective remains unachieved.

The supplied programme documents and visual materials informed the synthesis; private original files and conversations are not redistributed. Public foundation references are preserved. All new numerical inputs and code are in this directory.

## Files
`paper.tex`, `sections/`, `references.bib`: editable manuscript. `companion.py`, `test_companion.py`, `PROTOCOL.md`: exact study and local state witness. `reader.html`, `share.svg`: accessible research reader and original share artwork. `build.py`: deterministic packaging, validation and site integration. Generated evidence and source/PDF bindings accompany the released assets.
