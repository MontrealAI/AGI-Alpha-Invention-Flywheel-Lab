# N3 independent measurement-scope review before raw outcomes

Date: 2026-11-02. Reviewer: `independent_scientist`. The review concerns what the public instrument observes, not whether a new manufacturing process succeeds. No raw EDD strain arrays were retrieved or inspected during this review. Published methods, calibration/uncertainty discussion and qualitative result summaries were visible. Previously exposed part-deflection values are exploratory and are not fresh confirmation.

## Primary source and specimen identities

Sources:

1. [NIST AMB2022-01 benchmark description](https://www.nist.gov/ambench/amb2022-01-benchmark-measurements-and-challenge-problems), Sections 2.5, 2.7, 3.3 and 4.2.1.
2. Phan et al., [Elastic Residual Strain Measurements of 3D Additively Manufactured Builds of Nickel Alloy 718 AM Bench 2022 Artifacts Using Energy Dispersive Synchrotron X-ray Diffraction](https://doi.org/10.1007/s40192-024-00388-w), Experimental Procedure, Experimental Setup and Analysis Approach, and Uncertainty Analysis and Unstrained Lattice Spacing. Published 2025.
3. [NIST dataset](https://doi.org/10.18434/mds2-2711), [public metadata](https://data.nist.gov/od/id/mds2-2711) and [README](https://data.nist.gov/od/ds/mds2-2711/2711_README.txt). Data-use terms: https://www.nist.gov/open/license . Credit Levine, Phan, Seren and all dataset coauthors as listed in its record.

The NIST description assigns both synchrotron measurements and mechanical contour measurements to specimen `AMB2022-718-AMMT-B7-P3`. Neutron diffraction uses `B7-P4`, a nominally identical but different part. The unstrained lattice references are `B6-P3-O1` and `B6-P3-O2`. Nominally identical specimens are not the same physical reference object.

The specimen has no post-process heat treatment for these EDD measurements and remains attached to a portion of its build plate after separating the other parts. Destructive cutting/release and different support conditions change the physical question.

## What EDD measures

The paper documents 2248 nominal locations in the XZ plane at Y = 2.5 mm. These are source-reported locations, not 2248 independently executed tests in this series.

- Two directional effective diffraction strains are measured simultaneously. Their scattering directions are approximately 3.45 degrees from X and 3.22 degrees from Z; names XX and ZZ do not eliminate the small shear/rotation contributions.
- Incident slits are 0.2 mm by 0.4 mm; detector slits are 0.2 mm by 1 mm. The resulting gauge is rhomboidal and about 3.2 mm along its longest, approximately Y-directed dimension. It is not a point observation or a declared uniform box kernel.
- Each measurement position uses 60 seconds acquisition. The Y component could not be measured because the required specimen orientation entails an approximately 75 mm X-ray path.
- Actual positions were adjusted using measurements of the specimen edges. Nominal CAD coordinates alone are not an exact observation-registration map.
- Strains require an unstrained lattice reference. Its systematic uncertainty is not removed by a small fit residual. The authors used mean-corrected comparisons for the modeling challenge rather than absolute-level acceptance.
- The authors explicitly discuss hkl-dependent diffraction elastic constants and the difficulty of treating multiple fitted lattice strains as a unique representative bulk strain. A generic isotropic bulk compliance matrix is therefore an explicit model assumption, not a documented property of these reported effective strains.

The direct source supports evaluating the measurement functional under its calibration, location and averaging scope. It does not directly supply pointwise bulk stress, a full stress tensor, a fatigue limit, manufactured-part acceptance or an independent same-object stress map.

## Metadata identity and independent-reference limits

The retrieved metadata response was 38,397 bytes, SHA256 `9da162b4dbda49725bbb5c145ba4467ac3fc07e0b4f19d0462978e1e2da4431a`. This is a dynamic-response receipt; the full response is not retained here. The README was 7,111 bytes, SHA256 `6da6531af5871cdc0c000352a5373a9d7eb7c2aed7c6b843d6d376c538d36dc6`, version 1.0.0.

Two text-file names in the metadata, `AMB2022_EDD_results_V2.txt` and `AMB22_EDD_results_V2.txt`, each advertise 79,506 bytes and the same SHA256 `ce098ee2303a93ca2e66b769d81d60f9e31287689164bb9d6b4bcccd18e5e855`. They are byte-identity aliases, not independent reference datasets. Those advertised hashes were read from metadata; their payloads were not downloaded.

The inspected file inventory supplies EDD result files, images, checksum files and a residual-strain/part-deflection description document. It does not expose separate numerical neutron or contour files. The README says additional datasets will be added. Mention of a measurement campaign is not proof that its independent numerical truth is available in this publication. No assertion of exhaustive source absence is made.

## Preregistration implications

An exact-axis, common-kernel, isotropic linear-elastic model can establish conditional identities. With stress coordinates `(sigma_xx, sigma_yy, sigma_zz)`, two observed normal strains have the null direction `(nu/(1-nu), 1, nu/(1-nu))`. An additional matching normal-strain measurement resolves normal stresses within that model, not arbitrary shear, heterogeneous diffraction elasticity or pointwise fields. The relation `sigma_xx - sigma_zz = E/(1+nu) * (epsilon_xx - epsilon_zz)` likewise requires those declared assumptions. It is not automatically admitted by the NIST column labels.

A compact, self-equilibrated subgauge stress field can demonstrate why even complete averaged measurements do not identify pointwise stress. If an eigenstrain is introduced to realize that residual stress with zero displacement, it must be explicit; this is not a purely elastic compatibility construction without eigenstrain. A uniform through-thickness averaging witness must remain labeled a model witness, not a reconstruction of the actual NIST rhomboidal kernel or the measured artifact's stress.

For this source-bound stage, one dataset-level prerequisite rejection is sufficient if indispensable observation semantics are absent. Do not fabricate a per-row empirical denominator by counting uninspected rows as executed tests. A later numerical test needs a separate frozen contract, declared uncertainty treatment and matched independent references.
