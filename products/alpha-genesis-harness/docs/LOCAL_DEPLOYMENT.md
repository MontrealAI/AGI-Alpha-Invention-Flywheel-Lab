# Local deployment and support lifecycle

This increment makes an existing HARNESS **bounded JSON instrument** installable into a versioned, owner-controlled local target. It is a reusable local lifecycle, not an arbitrary-enterprise deployment agent, hosted service, cloud connector or production authorization.

From the extracted HARNESS product directory:

```sh
python3 -m bridge.deployment install --root /absolute/private/store --target operations \
  --instrument /absolute/export/instrument.json --cases /absolute/cases.json --approve-local-change
python3 -m bridge.deployment run --root /absolute/private/store --target operations --input /absolute/input.json
python3 -m bridge.deployment status --root /absolute/private/store --target operations
python3 -m bridge.deployment rollback --root /absolute/private/store --target operations --approve-local-change
```

`cases.json` is a nonempty array of `{"input": {...}, "expected": {...}}`. Supply independently determined expected outputs, not the model's self-rating. Workshop `PROOF.json` observations contain input/expected fields; the caller must deliberately select appropriate acceptance cases and discard observation metadata. Cases establish only their recorded coverage. Install/reinstall/rollback are explicit local operator actions; no approval of external changes is inferred.

## Actual behavior

- The existing HARNESS expression evaluator executes the instrument without arbitrary Python, shell, network or filesystem effects.
- Installation runs acceptance before changing the active revision. Releases are content-addressed; identical installation preserves the rollback predecessor.
- Every run and status check verifies release bytes, evaluator identity and acceptance cases. Loaded evaluator/disk disagreement refuses execution. Changed dependencies require restart and fresh qualification.
- A single local lock prevents overlapping mutations/runs. An interrupted operation that leaves a lock refuses further operations until the owner has reconciled the process and local state; it never steals the lock on an assumed deadline.
- A failed runtime operation writes a minimal blocked health record, without retaining raw runtime inputs or error strings. Successful receipts retain input/output hashes; outputs are returned to the caller, not persisted as incident payloads.
- Rollback requalifies the prior release with the current evaluator before atomically changing the head. It can recover from a corrupted current release when the prior bytes remain intact.

## Security and operational boundary

Use a private, owner-controlled directory. This store is **not authenticated against a malicious local owner**: hashes detect changed content, but anyone who can rewrite the store can select other valid bytes or roll back the head. It supplies no multi-tenant isolation, cryptographic authorization, secret management, audit retention SLA or high-availability guarantee. Filesystem atomic replacement prevents partial head writes under ordinary process interruption; complete hardware/power-loss durability has not been qualified. Acceptance cases may contain sensitive business data, so do not publish the store.

No zip-extracted program or model-written script is executed. Path-like target names and symlink targets/records are refused. Actual OS permissions remain essential. This CLI is not exposed as an HTTP endpoint and does not grant a model permission to install or roll back.

Support here means local health detection, blocked execution and operator-authorized rollback. It is not autonomous customer communication, enterprise account administration or support of every possible deployment. Enterprise adoption still needs an authorized target adapter, target-specific acceptance, secrets/access boundaries, monitored service objectives, incident ownership, rollback/recovery testing and appropriate human authorization. Live frontier-model inference and ChatGPT Pro connection are separate existing pathways; this module does not claim either was executed.

## Qualification

```sh
python3 -m unittest discover -s tests -p test_deployment.py -v
```

The tests execute local install/run/reopen/update/rollback and negative cases for failed acceptance, content mutation, evaluator drift, invalid inputs, duplicate JSON members, types, target paths, symlinks and overlapping/interrupted locks. They are development tests, not universal enterprise certification or independent customer acceptance.

## Existing workshop admission and revocation

The CLI above is deliberately a **low-level local install** with caller-supplied cases; it does not impersonate a workshop admission. When integrating with an already-open, owner-authorized `WorkflowService`, use:

```python
from bridge.deployment import LocalDeployment
from bridge import workshop
view = workshop.operate(workflow_service, "get", {"run_id": run_id})
target = LocalDeployment(private_store, "operations", workshop_service=workflow_service)
target.install_workshop(run_id, view["revision"], approved=True)
result = target.run(new_input)
```

This path requires a current passing docket and exact mission revision, reads only the instrument/proof JSON from the existing workshop export (never its Python program), binds the deployed bytes/cases and exact `max_operations` to that source and rechecks the live mission at every use. Revocation, changed revision, source drift or inability to reopen the bound `WorkflowService` refuses use. It is a Python service integration; no new browser route or broader model permission is added. The regression test exercises actual workshop registration, authored construction, admission, deployment and revocation, explicitly **not live model inference**.

Runtime receipts say `executed_local`, with `runtime_acceptance_established: false`. Replaying previously qualified cases does **not** prove a fresh input's result correct. Applications need an appropriate independent runtime validator before accepting a business outcome.
