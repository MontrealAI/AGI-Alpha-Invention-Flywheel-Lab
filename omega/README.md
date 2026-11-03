# FLYWHEEL Ω: local buyer pathway and coupled seller probe

A runnable, deliberately narrow self-service research edition. It constructs a
synthetic non-potable industrial water-sharing blueprint, independently verifies
its declared constraints, and compares fresh successor work with ordinary reuse.
It reuses the lab's mechanism planner and canonical native accounting.

**No Super Alpha result is claimed.** Existing water optimization is prior art.
Mathematical acceptance is not physical safety, an installed plant, a customer
outcome, actual commerce or a license to use water. See the [protocol](../campaign/omega-water-20261103/PROTOCOL.md)
and [complete alternatives](../campaign/omega-water-20261103/PRIOR_ART.md).

## Try it locally

Python 3.12. In an existing authorized environment with dependencies installed:

```sh
python -m pip install -r omega/requirements.txt
python -m omega solve --request omega/request.json --output /tmp/my-water-certificate.json
python -m omega serve --port 8879
```

Open http://127.0.0.1:8879 in your local browser. Edit the request, construct/check
and download a certificate. The server binds only to loopback, makes no model or
other network call and has no checkout or external action. Stop with Ctrl-C.
The synthetic unit is an integer volume unit; all contamination units are a
consistent authored mass/volume scale. Prices are modeled USD cents per volume
unit. Real calibration, treatment/transport, infrastructure and applicable
requirements are not established. Never use this as a water safety instrument.

The default path is entirely local deterministic computation. Alternatively,
change `model_route` to `buyer_owned_account_external`, use your own model account
**yourself** to produce a proposal matching the JSON plan schema, and import it:

```sh
python -m omega solve --request my-request.json --proposal my-plan.json --output /tmp/checked.json
```

This is a user-controlled file handoff, not an integrated paid-model adapter.
The request hash must match the exact request. No model key is requested, stored
or used. An imported model plan gets the same independent checks and no inherited
authority. We did not execute or benchmark an external paid-model arm.

## Reproduce the finite experiment

```sh
python -m unittest omega.test_buyer omega.test_seller omega.test_http -v
python -m omega experiment --output /tmp/omega-buyer-result.json
python -m omega.seller --output /tmp/omega-private-seller-NEW
python -c "from omega.seller import replay_audit; print(replay_audit('/tmp/omega-private-seller-NEW'))"
```

Seller account output destinations must be fresh. Buyer `solve` and `experiment`
reports accept either a new destination or a byte-identical completed retry;
conflicting files and symlinks are never overwritten. See recovery guidance below.
Do not delete another owner's account, reset a balance or copy signing/recovery
keys into public artifacts. The seller
source snapshot and native account are private continuation state. Its explicit
`native-public-export.json` is key-free audit data, not spending authority.
The seller is a separately registered US$100,000 reference arm, not a migration
or chosen global capital optimum. The fixed endpoint is hour 8760. It books only
registered research costs because no native product acceptance/collection adapter
exists; modeled optional choices never mint revenue.

## Packages are optional, not orders

- Free/core package: intended open-source release, **license/IP review unresolved**.
  The repository has no verified root open-source license; public source is not
  itself permission to redistribute. This PR does not invent or grant rights.
- US$299 self-hosted download: modeled convenience offer, not required for research.
- US$99 group webinar: at most 500 seats/session, optional and not scheduled.
- US$20,000 private founder session: 30 minutes, optional and not scheduled.

USD is an authored modeling convention pending commercial currency confirmation.
Self-service incumbents, ordinary providers, human-plus-AI and no purchase remain
available. Hypothetical preference changes are sensitivity calculations, not
customer consent, demand, contracts, revenue or proof of a viable enterprise.
Founder sessions consume human time and cannot support a fully autonomous claim.
Actual bills, taxes, demand, deployment costs and human/AI productivity are unknown.

## Exact controls and interpretation

24 authored fixtures, including infeasibility, withdrawal and changed quality.
Candidate dynamic programming versus independently written conventional MILP;
both use exact integer acceptance, and a separate exhaustive integer oracle
checks these small fixtures’ optima without floating-point tolerance. No hidden holdout or measured workforce is
claimed. Reusing equal-content ordinary code on a fresh request is permitted and
must win ties. A stale plan is rejected, while compatible code may be reused.
Construction time, paid-model cost and full site delivery costs are unmeasured,
so this code cannot substantiate economic superiority even if runtime differs.
The US$3B trailing-year complete-cost profit objective remains unachieved.

## Local diagnostics

```sh
python -m omega.help RESOURCE_CHECKPOINT_NOT_INFEASIBILITY
python -m omega.help "model unavailable"
```

This deterministic help command reads only this product README. It matches known
problems and returns current section excerpts with file, line and content-hash
citations. It is not a model assistant, does not execute commands, make network
calls, inspect arbitrary files or request credentials, and may return `UNKNOWN`.
No personal or continuing support is promised by this research prototype.

### Installation and runtime

Use Python 3.12 in an authorized local POSIX environment. The tested dependencies
are pinned in `omega/requirements.txt`. From the repository root, verify the
interpreter and installed versions; install the pinned requirements in your
chosen environment if needed. A `ModuleNotFoundError`, missing dependency or
unsupported interpreter is an installation issue, not a rejected buyer outcome.
The deterministic local route does not require a model to be running. A package
installation can require network access; the help command never performs it.

### Resource checkpoints

`RESOURCE_CHECKPOINT_NOT_INFEASIBILITY`,
`CORNER_RESOURCE_CHECKPOINT_NOT_INFEASIBILITY`, and
`EXACT_ORACLE_RESOURCE_CHECKPOINT_NOT_INFEASIBILITY` mean a finite computational
budget was exceeded. No infeasibility or acceptance certificate was established.
Keep the original request. Use a smaller copy only for diagnosis, or select a
qualified solver/resource allocation that can address the original constraints.
Do not treat success on a reduced request as completion of the original outcome.

### Invalid requests or rejected plans

Compare request fields with `omega/request.json`: exactly two contaminant values,
unique participant IDs, explicit Boolean consent, and nonnegative integer amounts
are required. `True` and `False` are not accepted as integer amounts. Unknown
fields, malformed JSON, incorrect dimensions and negative values are rejected.
`REQUEST_BINDING_MISMATCH` means the proposal belongs to different canonical
request content.
`WORST_CASE_QUALITY_EXCEEDED`, `SHARED_CAPACITY_EXCEEDED`, consent failures and
`OBJECTIVE_MISMATCH` are rejected plans. Preserve the rejection; correct genuine
input errors or construct a new feasible proposal and recheck it. Do not weaken
acceptance conditions or fabricate consent to make an output pass.

### External proposal handoff

`EXTERNAL_PROPOSAL_FILE_REQUIRED_NO_ACCOUNT_WILL_BE_CALLED` means the selected
external route has no proposal file. The implemented route never contacts a
provider or requests a key. Use the deterministic `local` route when suitable,
or supply a proposal matching the exact request through `--proposal` after your
own separately authorized provider use. Provider/model unavailability has no
automatic fallback that transfers data or spends money. Imported proposals still
face the independent checker. An imported claim of infeasibility is not a proof.

### Interrupted output and retries

On the supported local POSIX filesystem, a buyer report is fully written and
synced to a private temporary file, then committed atomically without replacing
an existing destination. Retry the same command after interruption: a missing
destination is completed; an identical completed file is accepted unchanged.
`OUTPUT_EXISTS_AND_IS_NOT_IDENTICAL_REGULAR_FILE` means an existing output differs
or is a symlink. Preserve it and choose a new output path. An older partial output
is not silently overwritten. Abrupt process exit may leave a `.partial` temporary
file beside the destination; it is not a certificate or required recovery state.
Buyer output replay does not resume, recreate or reseed a seller account.

### Unknown or unresolved issues

`UNKNOWN` means the local help has no sufficiently specific documented match.
Stop the affected step, preserve the request and outputs, and inspect the relevant
README section and local error manually. Share no keys, customer data or private
recovery state. Do not infer success, authorize spending or weaken validation from
an unanswered help request. The command cannot diagnose arbitrary environment,
security, physical-water or regulatory problems.
