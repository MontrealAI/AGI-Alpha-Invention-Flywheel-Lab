# Constructed spectral interface: sources and candidate choice

Checked 2 November 2026. Primary-source facts support the physical model and relevance of inspection. They do not calibrate our commercial assumptions, validate a built instrument, or establish a new scientific method.

| Candidate | Useful outcome and nuisance | Strong complete alternative | Why selected or deferred |
| --- | --- | --- | --- |
| Reference-normalized spectral X-ray inspection | Infer material quantities despite variable illumination; then locate an internal depleted region. Industrial interior inspection has consequential structural uses. | Calibrated XCT, standard flat-field/log material decomposition, specialist reconstruction, supplier inspection, and in-house software. | Selected for an immediately falsifiable invariant, independently sourced coefficients, and a distinctly spatial successor. Existing complete XCT is strong evidence against pretending the interface creates a new industry. The residual industrial gap is unresolved. |
| Phase-referenced optical oxygen sensing | Estimate oxygen while rejecting excitation-intensity changes. | Commercial lifetime/phase fluorometry, temperature/pressure calibration and specialist optical probes. | Deferred: the core gain rejection is established and practical deployment depends on material aging and environmental calibration. A new residual would need measured evidence. |
| Differential transit photometry | Detect very small transit signals amid detector/source systematics. | NASA Kepler calibration and systematic-error correction pipeline, ensemble photometry and current specialist tools. | Deferred: an archival-data study is possible, but building a new valuable capability and collecting appropriate rights/revenue are less direct; established processing must remain the baseline. |

## Verified physical and incumbent sources

1. J. H. Hubbell and S. M. Seltzer, **NIST Standard Reference Database 126**, last data-content update July 2004; DOI [10.18434/T4D01F](https://doi.org/10.18434/T4D01F). [Database/version page](https://www.nist.gov/pml/x-ray-mass-attenuation-coefficients), [aluminum](https://physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/z13.html), [copper](https://physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/z29.html), [iron](https://physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/z26.html). The code uses only the following small factual numerical extract, in cm²/g. Mass attenuation, rather than mass energy absorption, is the relevant column.

| Photon energy | Al | Cu | Fe, rejection challenge only |
| --- | ---: | ---: | ---: |
| 50 keV | 0.3681 | 2.613 | 1.958 |
| 100 keV | 0.1704 | 0.4584 | 0.3717 |
| 150 keV | 0.1378 | 0.2217 | 0.1964 |

These are tabulated reference coefficients, not measured photons from this experiment. Real source bandwidth, scattering, detector response and coefficient uncertainty are unvalidated here. Remote HTML bytes were inspected through retrieval and not archived or assigned a fabricated checksum; exact local numerical/source bytes are frozen in `SOURCE_MANIFEST.json`.

2. NIST, [Inspection of embedded internal features in additively manufactured metal parts using metrological x-ray computed tomography](https://www.nist.gov/publications/inspection-embedded-internal-features-additively-manufactured-metal-parts-using), 2016. Supports the practical importance of interior features and existing XCT inspection; supplies no calibration of our idealized phantom.
3. Kim et al., [Merging experiments and computer simulations in XCT probability-of-detection analysis](https://www.nist.gov/publications/merging-experiments-and-computer-simulations-x-ray-computed-tomography-probability), 2021, DOI [10.1016/j.ndteint.2021.102416](https://doi.org/10.1016/j.ndteint.2021.102416). Establishes that actual qualification needs experimental flaw references, uncertainty and detection analysis. We do not import their accuracy or call our authored grids measured data.
4. [Quantitative material decomposition using spectral computed tomography with an energy-resolved photon-counting detector](https://doi.org/10.1088/0031-9155/59/18/5457), 2014, DOI/abstract inspected. Supports the existence of strong established spectral material-decomposition alternatives. Its physical results were not reproduced.
5. Original experimental article, [Optimization of All-Polymer Optical Fiber Oxygen Sensors](https://pmc.ncbi.nlm.nih.gov/articles/PMC7792574/), 2021. Phase measurement rejects intensity dependence under its stated sensor assumptions; this is an established comparator for candidate two, not our experiment.
6. Caldwell et al., [Instrument Performance in Kepler's First Months](https://doi.org/10.1088/2041-8205/713/2/L92), 2010, and [NASA processing-pipeline description](https://software.nasa.gov/software/ARC-16332-1A). The instrument/systematics burden is real and conventional processing already addresses it. No Kepler observations were processed here.

## Rights and actual resource boundaries

NIST SRD126 carries a Secretary of Commerce copyright notice; [NIST's SRD policy](https://www.nist.gov/open/license) explicitly distinguishes SRD from generally public-domain employee works. This small attributed numerical extract is used for transparent research; it is not a blanket commercial redistribution or exclusive-IP grant. Commercial database rights review remains unresolved and budgeted. No bulk dataset, third-party paper, private prompt or user document is republished. NumPy's BSD-family terms and notices apply to that dependency; no NumPy source is vendored. Our source uses conventional mathematical operations and no model API.

The public research manuscripts provide method guidance, not physical truth: **Transformational Intelligence**, §§2,5–6 (purpose/bridge/controls); **The World as an Output**, §§2,4,6–9 (nuisance scope, repeated use, changed successor and cash distinctions); **AGI ALPHA**, organizational evidence/job/validator/settlement sections (bounded authority and independent acceptance). Source PDF SHA-256 identities are in `SOURCE_MANIFEST.json`; the full World manuscript and flagship were read, and the applicable organizational foundation sections were inspected. This is application of the guidance, not reproduction of those papers' companion experiments.
