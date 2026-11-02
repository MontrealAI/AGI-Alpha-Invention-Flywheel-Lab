# Five original routes: scientific status and replay

This is a retrospective source review and reproducibility replay of [PR153 at commit `8c13a60859f58c5b0a332eaa433f2ff84c584e8a`][pin], not a newly sampled evaluation or a third portfolio. It is reporting outside the paired-acquisition scientific freeze. The original results below belong to that pinned portfolio and its disclosed receipts.

## Original results

The pinned [product decisions][approvals] accept **eight of ten computational K1/K2 products**: both products for purpose, interface, complementarity and foundry. **Both original arrangement products are rejected.** These decisions establish bounded computational contracts; they confer neither physical qualification nor commercial rights. The [scientific verdict][verdict] establishes no route's superiority over its strongest complete conventional alternative and admits no new-industry flagship.

| Route and K1 → distinct K2 | Evidence and strongest ordinary comparator | Counterexample and closure |
| --- | --- | --- |
| **Purpose:** finite-game delivery while preserving emergency recovery → safe observation-contingent active diagnosis. | All ten K1 certificates and four K2 cases replay. Independent checker: **10/10 checks**. Unrestricted memoized recursion matches winning sets; fresh and equal-content ordinary diagnosis match acceptance. | Goal-only acceptance can discard future recovery. Unsafe or unidentifiable diagnosis is refused. The shared recovery component explains much of the counter reduction; the full combination is not shown necessary, and conventional transition counts can be smaller. Closed computational prerequisite; no robot or continuous-control qualification. [Report][purpose-report], [receipt][purpose-check]. |
| **Interface:** reference-normalized three-energy Al/Cu areal-density inference → spatial density reconstruction and depleted-cell localization. | Independent checker: **10/10**; saved spectra and a 99-ray phantom replay. Standard normalization plus SVD/least squares, fresh reconstruction and equal-content reuse tie. | Coherent unequal gains on sample/reference paths yield an **accepted wrong composition**, despite spectral consistency. Authored bounded-noise floats are not measured photon data. Closed under the common-gain contract; the paired-acquisition successor addresses this explicit missing condition. [Report][interface-report], [receipt][interface-check]. |
| **Complementarity:** heat-pump/storage process-heat dispatch → water-recovery heat duty with salt/water balance. | Eight schedules replay; independent checker: **9/9**. Individually insufficient components become feasible jointly. Unrestricted LP, equal-content reuse and a separately formulated fresh LP tie in energy. | Lost heat source, a tighter electricity cap, lower COP and higher storage loss defeat feasibility. Water quality, fouling and actual plant performance remain unmeasured. Closed finite energy/mass-balance construction, with no measured water-recovery product. [Report][complement-report], [receipt][complement-check]. |
| **Arrangement, original:** coordinated orbital-avoidance participation contract → fixed-half-time two-impulse servicing endpoint design. | **0/4 original contracts accepted**, including the joint construction; all seven tested fees refuse. **0/12 producer K2 endpoints** meet the unchanged 5 m/s fuel cap. Independent original checker: **15/16 checks**, overall **failed**, with another **0/12 endpoints accepted**. Classical matrix-exponential reconstruction/equal-content reuse ties in numerical predictions. | Conservative participation outside options defeat the tested contracts; fixed burn timing exceeds fuel limits. Accurate dynamics and successful refusal tests do not make either product acceptable. Original products remain rejected. [Report][arrangement-report], [receipt][arrangement-check]. |
| **Foundry:** two-layer near-infrared antireflection coating → two fresh twelve-layer two-band spectral routers. | Independent checker: **13/13**. Saved designs satisfy their declared finite eighteen-scenario contracts. Complete conventional robust optimization, equal-content reuse and a separately rebuilt forward kernel tie. | Wider incidence and a 10% common thickness shift fail unchanged criteria. Finite scenario means are not pointwise/continuous manufacturing guarantees; fabrication, roughness, adhesion and lifetime remain untested. Closed computational optical-design construction. [Report][foundry-report], [receipt][foundry-check]. |

### Later extensions do not rewrite the original decisions

The arrangement timing extension changes the allowed second-burn time while retaining endpoint and fuel constraints. Its producer accepted **10/12**, and its separate independent follow-up accepted **21/24**, refusing three. The independent finite-menu specialist ties, including refusals. This is a distinct endpoint-only extension, not acceptance of the original arrangement or a continuous safe approach corridor. [Timing receipt][timing-check], [arrangement report][arrangement-report].

The later purpose extension supports a conventional constant-braking safety property in the declared ACC ODE. It does not qualify the full speed-tracking/comfort purpose or physical road safety. [Continuous-property receipt][continuous-check], [verdict][verdict].

The checks use procedural separation on a shared host, not external certification. Sources and protocols were committed locally before outcomes but published later; the record explicitly disclaims public-before-outcome preregistration. [Reproduction record][reproduction].

## Account-free replay closure and commands

Use an **isolated checkout of the exact commit above**, preserving the full five route trees and `verification/`, their saved artifacts, protocols and annexes, and the repository package initializers. In particular, the optical kernel reads `foundry/tantalum_pentoxide.yml`; the artifact replay reads the purpose/interface/foundry `results/` and complementarity `evidence/` artifacts. Route source inventories include every nested Python/YAML file and `PREREGISTRATION.json`, so a handpicked minimal extraction changes identity. Inspected initializers and scientific imports do not open financial accounts.

The pinned [workflow][workflow] uses Python 3.12; its [numerical requirements][numerical-requirements] resolve to NumPy 2.3.5 and SciPy 1.17.0. Those are sufficient for these scientific entrypoints. Financial adapters, recovery/dispatch entrypoints and commercial-account tests are outside this replay.

From the isolated checkout, with those dependencies already available:

```bash
export PYTHONDONTWRITEBYTECODE=1
portfolio=experiments/public_portfolio_20261102
replay_out="$(mktemp -d /tmp/five-route-replay.XXXXXX)"
stage1_nonce="$(python -c 'import json; from pathlib import Path; print(json.loads(Path("experiments/public_portfolio_20261102/verification/REPRODUCTION.json").read_text())["stage1"]["nonce"])')"

for route in purpose interface complementarity foundry; do
  python "$portfolio/verification/verify_science.py" \
    --route "$route" --nonce "$stage1_nonce" \
    --output "$replay_out/$route.json" || exit "$?"
done
python "$portfolio/verification/verify_artifacts.py" \
  --output "$replay_out/artifacts.json" || exit "$?"

# The recorded original arrangement outcome is failed, not accepted.
python "$portfolio/verification/verify_arrangement.py" \
  --nonce "$stage1_nonce" --output "$replay_out/arrangement.json"
```

The final command should reproduce **exit 1, `passed: false`**, with the specific endpoint check recording `cases: 12, accepted: 0`. Inspect that receipt: an arbitrary exception or other failure is not a successful reproduction. [Original arrangement checker][arrangement-entry].

[`verify_science.py`][science-entry] has no `--route all`; its base arrangement route omits the wrapper's added participation/endpoint checks. [`verify_artifacts.py`][artifact-entry] checks **only four routes**, so its passing status cannot cover original arrangement. The disclosed nonce is a public reproduction seed, not an account credential. Output timing fields and inventories need not be byte-identical to earlier receipts. Replaying exposed cases is reproducibility, not fresh independent confirmation.

### Actual account-free replay

On 2026-11-02, all five original verifiers were rerun sequentially from an isolated, read-only materialization of **54 files whose Git blob identities and sizes matched the pin**. Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0 were already available. The exact disclosed stage-one nonce was used. An execution-only wrapper invoked unchanged entrypoints, recorded imports and exit codes, and prohibited financial/operating imports and network/subprocess operations inside each scientific process.

**Purpose 10/10, interface 10/10, complementarity 9/9 and foundry 13/13 passed with exit 0. Original arrangement reproduced 15/16, exit 1**, with exactly the recorded endpoint failure: twelve cases, zero accepted, no exception. Check names and pass/fail sequences matched all five original receipts. The separate saved-artifact replay passed both stages for its four routes. All 54 files remained unchanged; observed repository imports matched the verified scientific closure. No accounts or campaigns ran. Timing and continuous-ACC extensions were not rerun. Source hashes, exits, counts and runtime identities are recorded in [FIVE_ROUTE_REPLAY.json](FIVE_ROUTE_REPLAY.json).

[pin]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/8c13a60859f58c5b0a332eaa433f2ff84c584e8a
[approvals]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/PRODUCT_APPROVALS.json
[verdict]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/SCIENCE_VERDICT.json
[purpose-report]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/purpose/RESULTS.md
[purpose-check]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/SCIENCE_purpose_001.json
[interface-report]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/interface/REPORT.md
[interface-check]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/SCIENCE_interface_001.json
[complement-report]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/complementarity/RESULT.md
[complement-check]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/SCIENCE_complementarity_001.json
[arrangement-report]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/arrangement/REPORT.md
[arrangement-check]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/SCIENCE_arrangement_001.json
[foundry-report]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/foundry/REPORT.md
[foundry-check]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/SCIENCE_foundry_001.json
[timing-check]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/TIMING_FOLLOWUP_001.json
[continuous-check]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/CONTINUOUS_PROPERTY_001.json
[reproduction]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/REPRODUCTION.json
[workflow]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/.github/workflows/public-portfolio-20261102.yml
[numerical-requirements]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/requirements-cycle004.txt
[science-entry]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/verify_science.py
[arrangement-entry]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/verify_arrangement.py
[artifact-entry]: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/8c13a60859f58c5b0a332eaa433f2ff84c584e8a/experiments/public_portfolio_20261102/verification/verify_artifacts.py
