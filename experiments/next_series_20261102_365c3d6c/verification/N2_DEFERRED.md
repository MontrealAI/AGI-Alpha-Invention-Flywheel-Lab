# N2 deferral after primary-source inspection

Date: 2026-11-02. Reviewer: `independent_scientist`. This source-only decision does not activate a new optical confirmation. I1's frozen results and ambiguity witnesses remain unchanged.

## What the actual public source supplies

The [published PRX article](https://doi.org/10.1103/PhysRevX.9.041050) describes a proposed wavelength-dependent reflector stack and software reconstruction using simulated reflection observations together with experimentally measured fiber transmission matrices. Measured fiber support does not independently qualify the fabricated reflector stack, its calibration or a new inspection decision.

The article's actual [Cambridge dataset record](https://www.repository.cam.ac.uk/items/17696038-7088-4120-accc-55f96b27565b), DOI [10.17863/CAM.45121](https://doi.org/10.17863/CAM.45121), explicitly states that the code generates reflection matrices, then reconstructs the transmission using known reflectors and wavelengths. The [author archive](https://api.repository.cam.ac.uk/server/api/core/bitstreams/746cf81f-a23f-48ef-9ec7-ede28d878393/content) was inspected without execution: 685,338 bytes, SHA256 `143f580df04ca36cf73e77c0282a9d52bdef4334bf898359890e2d0d96677a07`, CC BY 4.0. Credit Gordon, Gataric, Ramos, Mouthaan, Williams and coauthors as listed in the repository and article.

Files are `instructions.txt`, `localoptimisation.py`, `reflectors.mat`, `simSettings.mat`, `target.mat` and a sample response plot. Static source inspection of `localoptimisation.py`, lines 106-107 and 175-182, shows `C_true` constructed from the supplied target matrix and reflector matrices. Numerical target arrays and solver outcomes were not inspected or run in this review. These generated observations cannot independently test the assumed reflector calibration.

The other linked [Carpenter dataset](https://doi.org/10.14264/uql.2016.678) concerns a wavelength-dependent multimode-fiber optical transfer function. Its identity is corroborated by the [University of Queensland author publication record](https://about.uq.edu.au/experts-publication/11891/4749). No measured reflector-stack acquisition or independent beneficiary reference objects were obtained from that metadata check.

## Decision

Defer physical N2 confirmation. A further ideal reconstruction sweep would not resolve the known gain/reciprocity ambiguity. Route A remains a legitimate separately specified model construction if an independently calibrated one-way/reference measurement is included with its actual distal-access, uncertainty and acquisition burden. Route B remains eligible only after defining a consequential invariant beneficiary decision and independent reference labels; none were established here.

The decisive control must preserve the old indistinguishable physical pair and show that a genuinely independent new observation distinguishes its target values, or prove that a new purpose is invariant across the entire declared nuisance class. Model residuals, passivity and measured fiber matrices alone do not provide that test. Scalar calibration repair does not identify an arbitrary nonreciprocal return path or spatially varying reflector error.

Reopen only for a concrete independent observation/reference contract that can change the investment choice. No physical impossibility, achieved invariant inspection service, new business or N2 confirmatory result is claimed.
