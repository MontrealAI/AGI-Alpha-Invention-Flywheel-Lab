# Public construction interface

The experiment models **synthetic** provider transaction semantics. Sandbox ledger observations are permitted, costed instrumentation. Production exposes responses only. No property here certifies a real provider.

`construct(task, probe)` returns an inert graph. It may call `probe(provider_id, sequence)` adaptively. The returned graph is either the direct return value or the `program` field of a return object containing additional `trace` and `retained` metadata.

`task` contains opaque provider IDs with `probe_unit_microUSD` and `call_microUSD`, a total `probe_budget_microUSD`, `max_steps` (48), stage and outcome. No hidden family, true state or fault schedule is supplied. Both methods get the same task, K1 evidence, operation vocabulary, maximum budget and acceptance contract. Policy code must not import `world.py` or `evaluate.py`, inspect closure/private attributes, read files other than its own frozen knowledge, or use scenario IDs as labels. This is audited procedural separation, not an adversarial security sandbox.

Each probe uses a new reset namespace. A sequence has 1–16 dictionaries with `op`, optional `token` (default `probe`), optional `fault` (`none`, `request_lost`, `ack_lost`) and `ticks` (1–8 for waits). Every step costs the provider's published probe unit. A probe exceeding remaining budget returns `BUDGET_EXHAUSTED` with no observations or charge. Invalid probes fail. Repetition is charged; no free production trial exists.

Probes return `observations`: response, independent sandbox `effect_count`, `hold_count`, tick and measurement status for each operation. Missing/noisy measurements are explicitly `null` with response `UNKNOWN`; they must not be interpreted as zero. Probe observations are not production inputs.

| Operation | Requested behavior; actual support must be established |
| --- | --- |
| `execute` | Create one productive effect for the token. It may be non-idempotent. |
| `reserve` | Create a reversible hold, if supported. It may expire. |
| `commit` | Consume a live hold. Repeated committed-token commits are idempotent within this simulated interface. |
| `cancel` | Release a hold; remove effects only when compensation is supported. |
| `status` | Query token state. It may be stale or opaque. |
| `fence` | Request current token state. It may be unsupported. |
| `wait` | Advance local provider time by a bounded number of ticks. |

Responses are `DONE`, `ABSENT`, `RESERVED`, `CANCELLED`, `TIMEOUT`, `UNSUPPORTED`, `REFUSED`, `UNKNOWN`. A timeout distinguishes neither missing request from missing acknowledgement. Reusing a token does not grant idempotence. A successful short replay does not establish an infinite key lifetime. Compensation can be unavailable.

Graph format:

```json
{"entry":"n0","nodes":{"n0":{"op":"reserve","provider":"opaque-id","token":"order","next":{"RESERVED":"n1","*":"stop"}},"n1":{"op":"commit","provider":"opaque-id","token":"order","next":{"DONE":"done","*":"unknown"}},"done":{"finish":"delivered","obligations":[]},"stop":{"finish":"aborted","obligations":[]},"unknown":{"finish":"unresolved","obligations":["opaque-id"]}}}
```

Each call node has `op`, provider, token, optional bounded wait ticks, and a `next` response map with mandatory `*`. Finish nodes have `finish` (`delivered`, `aborted`, `unresolved`) and an obligations list. There are at most 256 nodes and 48 total calls. Graph edges may loop, but the evaluator stops at the fixed cap and checks remaining effects/holds. Tokens are inert strings, not executable expressions. Every production token must equal the current task's `order_token`, which is `order`. Nodes cannot provide a fault override in production. Each call advances time for all providers; waits advance every provider by the stated ticks, so a hold may expire while another provider is being used.

Four schedule challenges are always scored: `healthy`; `lost_request` (first productive request lost for each provider); `lost_ack` (first productive acknowledgement lost for each provider); and `provider_refusal` (one hidden seed-bound provider refuses new execution/reservation). The refused provider is not revealed to the constructor; it can be any provider, independently of the constructed execution order. Prepared holds protect a later commit from refusal while live. All non-rejected requests finish immediately in this finite model; indefinite partitions, crashes, externally visible irreversible delivery and Byzantine providers remain outside scope. These four selected challenges are not exhaustive conformance certification.

K1 means exactly one effect at a single provider. K2 means exactly one effect at **every** complementary provider. Clean abort/no deploy earns no delivery credit. Honest unresolved obligations are recorded, incur loss/exposure, and cannot earn accepted-outcome payment. False completion, duplicate effects, abandoned holds and partial unreported effects fail independently. A refund is not completed production.

The evaluator will return schedule-level delivery, safe abort, unresolved/harm, actual counts, complete operation cost and residual obligations. All four rows remain in the denominator. No hidden schedule is selected after the outcome. A method that cannot resolve uncertainty within its budget may decline before effects.

Confirmation is 48 paired K2 worlds in six disclosed mechanism-composition strata with eight fixed seeds each. Development uses K1 singleton providers only. Fresh families add composition, varying delays/expiring holds and measurement gaps. This is finite generated confirmation, not independent empirical provider sampling. The parent will publish the source freeze and exact seed rule before any confirmation execution.
