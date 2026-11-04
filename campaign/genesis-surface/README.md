# GENESIS: from a frontier source to an executable physical-function candidate

**Construct the means. Check the consequence. Do not sell the uncertainty.**

This additive construction module turns a declared two-state friction requirement into a mixed-family contact geometry, independently reconstructs its numerical behavior, and exports editable CAD, a placement map, response data and a physical acceptance plan. It is an actual digital artifact, not a hypothetical revenue simulator.

## Use it

From the repository root, with Python and NumPy/SciPy installed:

```sh
python -m pip install -r campaign/genesis-surface/requirements.txt
python -m research.genesis_surface build --out /absolute/new/surface
python -m research.genesis_surface audit --out /absolute/new/surface
python -m research.genesis_surface mesh --design /absolute/new/surface --out /absolute/new/surface-mesh
```

Open `surface/OPEN_ME.html`. Edit a copy of `REQUEST.json` to supply a different declared target, family calibration, height menu or site limit, then pass `--request your-request.json`. Outputs are create-only. No model API, account, device, credentials or network is used at runtime. `surface.scad` is the editable analytic geometry; `surface-preview.stl` is an approximate sampled mesh, not a manufacturing qualification or a mixed-material recipe.

## The real frontier input

Fu et al., *Automated inverse design of metainterfaces with tailored friction laws*, Nature Physics, published 30 October 2026: https://doi.org/10.1038/s41567-026-03503-0 . This paper and its underlying code predate this implementation; its recent publication is NOT evidence that the technique became possible only this week.

Strong related work: Bilotto et al., *Inverse Design of Metainterfaces Towards Static Friction Control: Beyond the Hertzian Limit*, published 26 October 2026: https://doi.org/10.1007/s11249-026-02210-4 . Public implementation: https://github.com/JBil8/frictional_metasurfaces_inverse_design . No third-party implementation is copied here.

The request's numerical calibration is explicitly derived from the repository's pinned public-data prerequisite probe, Git blob `ac9e857a78830bde0f4f1ad8db674f29da698a28` at main `1626d46e1260dba686b866365cacfc4bddf971f0`. Effective shear coefficients are `B_s*sigma_s` and `B_d*sigma_d`; positive marginal endpoint products define sensitivity boxes. Those boxes are NOT simultaneous confidence regions, physical transfer bounds, or new measurements. The old probe already identified calibration inconsistency. This work preserves that warning.

## What was selected, and why

The active Blue Sky cards compare passive mechanical function, interior-property observation and resource-to-capital conversion. This work selects only a low-resource **digital construction experiment** in passive mechanics: a consequential end use could be a contact interface with separately chosen holding and sliding behavior. Existing numerical models permit a directly inspectable geometry now; the other tracks still need new observation or process evidence. Buyer demand, complete incumbent alternatives, mixed-family fabrication and physical transfer remain unresolved. No card is promoted to an achieved Blue Sky breakthrough or an investable commercial offering.

## What the model actually says

For an independent spherical contact with penetration `delta`, `area = pi*R*delta`, `normal = 4/3 * E_star * sqrt(R) * delta**1.5`, and static/dynamic force equals area times its declared effective shear coefficient. Units are mm, N and MPa=N/mm^2. A common fixed family has a constant static/dynamic force ratio regardless of height arrangement. Two disjoint required ratio intervals are therefore impossible **inside that homogeneous model**. This says nothing universal about other passive mechanisms, active control or real nonlinear friction.

An ordinary SciPy/HiGHS integer optimizer selects counts at allowed family/height sites. It is the strong conventional tool in the portfolio, not a weaker comparator to defeat. Scalar acceptance is implemented separately from its matrix construction. Solver optimality is a numerical status within the declared finite grammar, not an independently proved global, scientific or enterprise optimum.

The first exposed development specification produces 36 sites (6 first-family, 30 second-family), with calculated ratios approximately 1.00588 and 1.17809. A second, reversed-trend development specification produces a different 26-site design. Neither specification is hidden confirmation or observed buyer demand. Both pass nominal numerical checks and fail the supplied sensitivity-box qualification. Normal-force modulus, geometry, contact interactions and wear are not included in those shear-only boxes.

**Decision: HOLD for physical calibration, transfer, complete alternatives and buyer evidence.** Printing a homogeneous geometric mockup does not reproduce two distinct surface/batch families.

## Three orders of intelligence — actual scope

1. A current primary-source development and its access limitations were inspected in this assistant session. The module is not a live global monitor.
2. The assistant implemented and executed a reusable constructor producing actual digital geometry and checkable responses. Runtime construction uses an established optimizer; it is not autonomous open-world invention.
3. Reuse on a second target exercises the tool. It does not demonstrate an improved discovery process or causal successor advantage.

No changes to `JournalAccount`, adaptive `Account`, PR229/233/235, existing bridge source locks, operating accounts or release authority are made. No transaction, real revenue, paid API, outreach, model training, hardware actuation or production deployment occurred. The dependency this instrument removes is a concrete executable **joint-response geometry candidate** for the passive-mechanics investigation; it does not replace the missing scientific/commercial tests with another framework.

## Test and reproduce

```sh
python -m unittest discover -s tests -p test_genesis_surface.py -v
python -O -m unittest discover -s tests -p test_genesis_surface.py -v
python -m research.genesis_surface build --request campaign/genesis-surface/SUCCESSOR_REQUEST.json --out /absolute/new/reversed-surface
python -m research.genesis_surface audit --out /absolute/new/reversed-surface
```

36 tests passed locally in normal and optimized Python. The supplied primary mesh was separately checked with trimesh: watertight, consistent winding, Euler number 2 and positive volume. This checks geometry, not contact behavior. Two OpenSCAD-to-STL development attempts were interrupted by tool wall limits; they are not counted as successful rendering. The standard-library/NumPy mesh exporter is the working alternative. No new repository license is inferred or imposed. Source-bound CI and review are separate from these local checks.
