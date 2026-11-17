# Direct construction and verified repair

A release reviewer who already has an independently trusted list of file hashes can receive a working verifier without a model call. A research editor whose input/output examples leave the mapping to infer can ask the configured model to construct it immediately. Both paths freeze the mission contract before construction, check the actual candidate against it, and issue a portable program only after acceptance.

## Operating the private workspace

Start the local service from the product directory with `python3 -B -m ignition serve`. Choose an example or supply your own ambition. Select the strategy under the execution options. Each mission records its beneficiary, requirements, permissions, scope, budget, comparison and reasons for selecting a route. A source, provider or mission change requires a fresh revision.

| Resource option | Effect |
|---|---|
| `execution_strategy: "adaptive"` | Default. A supported, specified mission takes the direct route. The installed specialist compiles exact declared operations. Example-induced mappings use the permitted model. An open ambition with sufficient direction enters research. A missing objective or uncovered requested effect can return a clarification. |
| `execution_strategy: "direct"` | Request a model construction from the purpose-bound software contract. A missing supported contract returns a targeted clarification. |
| `execution_strategy: "research"` | Request discovery, challenge and selection. A source-linked proposal, incumbent, deferral and stop remain distinct outcomes. |
| `direct_method: "model"` | Use the same construction interface and model in direct and adaptive comparison arms. A declared local or assisted permission and an available provider are still necessary. |
| `direct_method: "specialist"` | Compile literal data-only operations. A mapping that has to be inferred from examples is outside this exact-specification specialist. |
| `direct_after_research: true` | Separately authorize a direct attempt on an existing supported specification after an unsuccessful selection. The original research verdict remains inspectable. |
| `max_model_calls` and `max_repairs` | Enforce integer budgets within this mission. By default one fresh repair is possible. Unchanged rejected proposals, contradictory reference answers, an exhausted call budget or limits on the selected specialist stop repair. |
| `research_economics` | Supply `unit`, `decision_value` and `marginal_cost` on the same basis. An adaptive open investigation whose estimated value does not cover its marginal cost returns clarification. Without estimates, monetary value remains unmeasured. |

The data-only model language supports record migration and checking file bytes against a trusted manifest. The private workspace also offers a separately scoped Pairing Lab specialist. Frozen software acceptance covers the enumerated behaviors. The operator should inspect requirements outside the frozen cases. The router identifies selected explicit physical and external actions that a passing software table or digest comparison cannot verify. It does not understand all possible natural-language contradictions.

## The original failures

The frozen migration run produced five candidates and deferred before freezing a contract. The direct run on the same machine and model then passed nine checks. The archived primary receipt omits the challenger's full response, the selected identifier and its reason for deferral. Attributing the original deferral to a particular model judgment or an individual controller condition would exceed that record. A direct path removes dependence on either for a specified construction. The historic times, 597.08 and 71.16 seconds, came from sequential arms and include unequal server warmth. [Original qualification and receipts](../../../docs/frontier-omega-ignition/qualification/89f2196d/REPORT.md)

The [recovered original release-integrity proposal](../trials/historical-integrity-proposal.json) matches its published model response digest. The model replaced the eighth hexadecimal digit of the trusted `ignition.css` digest, changing its prefix from `23675652` to `23675657`. It preserved the second file's digest. Testing these exact bytes with the original source showed that the clean package was incorrectly classified as changed. Eight of nine behavioral checks passed, exact declaration conformance failed, and the conventional comparator passed all nine. [Frozen cohort run](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44163276348)

| Object | SHA-256 |
|---|---|
| Original canonical model response | `9bef7cd8787ba4397137da29dce7e4b450f70c31eb26dacfa8910a6c38bf42b3` |
| Frozen integrity contract | `9349cab7eed8ad480458c3f1655f659fc36455aaccb11b4e8fb56cb9094070a4` |
| Compiled rejected artifact | `2997e2978470afe5818f42a697c5797436ea077e46e683fc2bb53890e550bae8` |

The negative verdict demonstrates that the acceptance instrument detected a real defect. The candidate failed its mission.

A model can now select `{"kind":"manifest_audit","program":{"use_frozen_manifest":true}}`. The trusted compiler binds the already frozen hashes and produces the existing ordinary artifact format. Literal proposals remain supported and subject to exact digest comparison. An independently rejected proposal receives structural diagnostics identifying mismatched public specification paths and counts of failed check groups. No held-out case name, example value or answer is included in the repair request. The independently supplied contract remains frozen throughout.

From the product directory, run `python3 -B -m unittest discover -s tests -p test_adaptive.py` to replay the hash-matched rejection, an explicitly synthetic repair, a model-free specialist, an explicitly authorized fallback, and refusal on an unsupported action. These software tests do not measure live model performance. For a historical replay use a separate checkout of [the frozen product](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/89f2196d552810bc56696a7f380ae66c55f8763a/products/frontier-omega-ignition) and run the following in its product directory.

```python
import json
from pathlib import Path
from ignition import construction, evaluation

spec = json.loads(Path("examples/integrity.json").read_text())["mission"]["construction_spec"]
contract = construction.freeze_contract(spec)
proposal = {"kind": "manifest_audit", "program": construction.build_view(contract)["definition"]}
proposal["program"]["manifest"]["ignition.css"] = (
    "23675657f7ffa6fbdbd0d085580ef56687f731e9066e28e1f6a5ad0c449b8668"
)
assert construction.fingerprint(proposal) == "9bef7cd8787ba4397137da29dce7e4b450f70c31eb26dacfa8910a6c38bf42b3"
artifact = construction.build(contract, proposal)
receipt = evaluation.evaluate(contract, artifact)
print(contract["sha256"], artifact["sha256"], receipt["comparison"]["outcome"])
print([(case["name"], case["candidate_pass"]) for case in receipt["cases"]])
```

## What the mechanisms changed

| Decision or instrument | Executable consequence | Remaining uncertainty |
|---|---|---|
| Choose a simpler direct arrangement | A fully specified manifest can be compiled and verified with zero inference or source requests. | Developer effort and full service economics remain unpriced. |
| Transfer the binding of a trusted reference into construction | An exact reference to the frozen manifest removes model transcription of long digest strings. | The operator still needs an independent ground of trust for the manifest. |
| Challenge the artifact with independent observations | The exact historic bad program is rejected despite eight passing checks. Conflicting reference answers quarantine the candidate. | More extensive tests can expose additional faults. |
| Repair from verified failure and preserve evidence | Each trial reports proposal, artifact and evaluator receipt identities, observed check counts, comparison, contract identity and result. The current source re-executes acceptance on export. | Correction within one frozen contract establishes task performance within that scope. General construction, demand and historical frontier advantage require separate evidence. |
