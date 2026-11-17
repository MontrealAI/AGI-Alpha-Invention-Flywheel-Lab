# A prospective Pairing Lab field study

For a private engineering backlog, compare accepted **delivered work** under a fixed selection rule and the same beneficiary requirements. The retrospective Pairing Lab selected two historical configurations. This companion carries that selection forward, prospectively measures an incumbent single and three contemporary alternatives, and accounts for the cost of every attempted delivery. Its qualification uses synthetic adverse cases. A production study still needs real inputs, independent operators and actual observations.

## Before collection

Use local files only. Register fresh rights-authorized issues drawn from the beneficiary's actual backlog, disclose sampling exclusions, and bind the same outcome, receipt deadline, rights and support terms across arms. Identify gate and final acceptance owners outside the construction arms. The gate can run during selection; only the independent acceptance operator sees the outcome labels. All parties should retain the registration hash before work. The software cannot establish chronology, authority or organizational independence from a hash alone.

Use two successive custody transfers. After all arms submit, give the selector only gate records. Retain its printed delivery commitment with the independent assessor **before** revealing outcomes. Give the assessor the frozen selected artifacts. A second attempt that would have passed in hindsight earns no benefit unless the frozen rule selected it.

From this directory, the commands are:

```sh
python3 operational_pilot.py register --evidence vault --spec spec.json --out plan.json
python3 operational_pilot.py select --evidence vault --plan plan.json --plan-sha "$PLAN_SHA" \
  --attempts attempts.json --out deliveries.json
python3 operational_pilot.py score --evidence vault --plan plan.json --plan-sha "$PLAN_SHA" \
  --attempts attempts.json --deliveries deliveries.json --delivery-sha "$DELIVERY_SHA" \
  --finals finals.json --out result.json
```

Set each shell variable to the digest received in the preceding custody transfer. Outputs use new paths. The command hashes local evidence, validates receipt bindings and replays the selection; external operators execute and grade the actual work.

## Registration and observed records

Place original private bytes in `vault/<lowercase-sha256>`. References below identify those bytes. Never publish this directory. The unit-test setup is a complete executable **synthetic** example of all JSON structures.

| Input | Required fields and meaning |
|---|---|
| `spec.json` | `tasks` maps fresh issue IDs to frozen contract references. `currency` is a three-letter code, e.g. CAD. `authority` and `configurations` are reference maps described below. |
| `authority` | `rights_and_distribution` records actual authorization and the sampling method. `gate_procedure` and `acceptance_procedure` identify independent procedures. `gate_qualification` and `acceptance_qualification` contain `procedure` plus a `controls` list, with distinct artifact references, expected/observed booleans and underlying `source_sha256`. Both positive and negative controls must pass. `accounting_and_deadline` fixes timing, nonoverlapping cost definitions, rate sources, unsuccessful deliveries, setup/overhead allocation and outstanding obligations. |
| `configurations` | Bind `qwen/agentless`, `glm/acr`, `current_agent`, `direct_tool`, and `human_conventional` to their actual configurations, model/harness versions and tool rights. Select the strongest applicable current agent and direct method; the conventional arm uses competent fully human work and conventional software. Make each arm genuinely available before collection. |
| `attempts.json` | Each `issue:arm` maps scheduled configuration keys to ordered nonempty lists of attempts. Submit all five arms: `historical_single`, `historical_pair`, `current_agent`, `direct_tool`, `human_conventional`. Independently run each. Include failures and retries. Each row contains unique `run_id`, integer `tokens`, optional `artifact` reference (null on failure), boolean `gate_pass`, and `receipt` reference. |
| Selection receipt | JSON includes `type` = `selection`, `task_contract`, `arm`, `configuration` reference, `grader` reference, `run_id`, `tokens`, `artifact`, `gate_pass`, and `source_sha256` referencing the underlying run and grade observations. The selector picks the first gate-passing candidate in the registered configuration order, then retry order. It prefers the historical single when both members of the primary pair pass. |
| `finals.json` | For every scheduled `issue:arm`, provide `delivered` (exact selected reference or null), boolean `accepted`, `decision_receipt`, `meter_receipt`, `human_ms`, `delivery_ms`, and `cost_micros`. Record actual time from issue release to receipt or terminal failure; sums are task-time, not parallel makespan. |
| Final receipts | Both JSON objects include `task_contract`, `arm`, `delivery_sha256` (the entire blind delivery manifest), and `source_sha256` for the underlying evidence. A `type` = `acceptance` receipt also binds the final `grader`, `delivered`, and `accepted`. A `type` = `costs` receipt binds `currency`, `human_ms`, `delivery_ms`, and the exact `cost_micros` map. |

Use integer millionths of the same currency for `production`, `selection`, `verification`, `infrastructure`, `human_labor`, and `delivery_and_obligations`. Include every unsuccessful attempt and intervention. Allocate common costs under the preregistered rule. Monetary categories must be disjoint: for example, separately reported human labor should not be counted again in verification. Mark an unmeasured cost `null`; it blocks that arm's total and corresponding economic differences. Support measured zero with evidence. Some future obligations may remain unknown after delivery.

The result reports each denominator, accepted deliveries, tokens, elapsed task-time, human intervention and pair-minus-alternative differences. There is no automatic commercial verdict. Inspect sampling, graders, substrate access, receipts, uncertainty and costs before interpreting a difference. A separately retained digest and underlying records support review; their truthfulness and comprehensiveness require an independent audit.

## Portable, offline qualification

Build and transfer this private study companion from the public source. A fresh Python 3.10+ recipient can run the synthetic protocol controls without model access:

```sh
python3 -m zipfile -c Pairing_Pilot.zip operational_pilot.py pilot.py pairing_lab.py runs.csv test_operational_pilot.py OPERATIONAL_PILOT.md
python3 -m zipfile -e Pairing_Pilot.zip recipient
(cd recipient && python3 -B -m unittest -v test_operational_pilot)
```
