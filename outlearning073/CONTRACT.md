# Outlearning073 evaluator contract

This experiment checks software constructions in an independently authored finite sandbox. It does not qualify a real archive, laboratory, network service, buyer or physical process. The world/verifier author is procedurally separate from the constructor and baseline authors, on one shared host; there is no external blinding or certification.

K1 preserves two exact-content objects, each with a content digest. K2 has a different operation graph and outcome: reserve a computation slot, compute an exact integer-data summary, then publish it using the actually acknowledged reservation token. Both outputs are actual JSON artifacts and effects of Python-executed tools. Numeric rows are authored data, not measured assays. A correct policy alone is insufficient: accepted effects must contain the independently recomputed output.

`development_requests()` declares four exposed K1 semantic worlds. `confirmation_requests()` prospectively declares 24 K2 tasks, three data instances across eight semantic families, not 24 independent industrial sites. Fresh families contain new joint combinations of key scope, read visibility and delay plus noisy and unaffordable diagnostics. Seeds do not constitute independent physical replication. These generator functions must be source-frozen before constructors run on confirmation. Do not tune constructors after exposed confirmation results.

`make_session(request)` returns a session. A constructor may read `session.public`, call `session.probe(actions)` and inspect returned observations. It may not read private world fields, request family/seed, hidden fault schedules, evaluator results or future outcomes to choose a plan. Public data includes task inputs, required intents, operation dependency, deadline, declared maximum in-flight and visibility bounds (or an explicit absence of a guarantee), diagnostic budget and cost unit. Key semantics remain initially unknown.

Probe calls run on fresh sacrificial p0/p1 tool namespaces sharing the modeled service contract. Their first writes use lost acknowledgements and late completion respectively. A probe can execute any bounded admitted low-level action sequence. Its independently observable effect-count receipt is a stipulated diagnostic instrument; the experiment does not claim such a receipt exists for arbitrary live services. Noise can withhold the effect counts. If quoted probe setup plus operation units exceeds the remaining budget, the instrument is unavailable and charges zero. No production delivery occurs during probes. Every affordable diagnostic and operation is charged in resource units; conversion into USD is an explicitly separate economic assumption.

Artifacts have exactly `steps` and `output`. Low-level steps are:

* `{"op":"write","intent":"archive0","key":"request/intent","value":"$output:archive0"}`. K2 publish also has `"dependency":"$token:reserve"`.
* `{"op":"read","intent":"archive0"}`.
* `{"op":"wait","ticks":3}`.
* `{"op":"if","test":{"intent":"archive0","is":"committed"},"then":[],"else":[]}`.
* `{"op":"stop","reason":"unresolved contract"}`.

## Public input and exact product schemas

Every public task has `id` (opaque task identifier), `stage`, `intents` (ordered required operations), `dependencies` (dependent intent → prerequisite intent), `deadline`, `max_inflight`, `visibility_bound`, `diagnostic_budget`, `probe_setup_units`, `operation_unit_cost`, and `scope`. A missing guarantee is JSON null. These are contract facts; they are not observations of the current hidden write fault.

For K1, `objects` is a list of `{"intent":"archive0","content":"..."}` and `{"intent":"archive1","content":"..."}`. The exact artifact output is `{"archive0":{"content":CONTENT_0,"sha256":HASH_0},"archive1":{"content":CONTENT_1,"sha256":HASH_1}}`. Each content is copied exactly from the corresponding public object. Each hash is SHA-256 of that exact content's UTF-8 bytes, displayed as lowercase hexadecimal.

For K2, `rows` is a public integer list, `intents` is `["reserve","publish"]`, and `dependencies` is `{"publish":"reserve"}`. The exact artifact output is:

```json
{"reserve":{"job_id":"PUBLIC_ID","rows":0},"publish":{"job_id":"PUBLIC_ID","count":0,"sum":0,"sum_squares":0,"source_sha256":"LOWERCASE_SHA256"}}
```

The zeros above are field placeholders, not a fixture or a scored answer. Both `job_id` values equal `public.id`; `reserve.rows` and `publish.count` equal the length of the public integer list. `publish.sum` is its integer sum and `publish.sum_squares` the integer sum of each element squared. `publish.source_sha256` hashes the canonical JSON encoding of the entire integer list: Python-equivalent `json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')`, followed by SHA-256 lowercase hexadecimal. No rounding or string-number substitution is admitted.

An included-agent constructor interface may be `build(session,retained=None) -> (artifact,trace)`. The evaluator only accepts the artifact's exact `steps`/`output` schema; construction trace and retained content stay separate. Constructors must compute the product themselves from these public facts, rather than import the verifier's expected-output function. The evaluator rederives the product independently.

Only the most recent returned status for the named intent is available to `if`; it is not a hidden ledger query. Statuses are committed, timeout, absent and unknown. A committed observation stores its actual token. Write values can be literal JSON or an `$output:intent` reference. Tokens come only from acknowledged write or read results. Missing tokens remain missing, making an invalid dependency fail acceptance. Keys can be `null` when unsupported; global key scope and intent-specific key scope differ, so sharing one key across distinct intents can suppress required effects.

`verify(request,artifact)` executes all 16 combinations of first-write ACK, dropped-before-write, lost-ACK and late-commit faults for the two required intents. Subsequent calls acknowledge. The verifier drains pending effects after plan termination, so late duplicates cannot disappear from accounting. Acceptance requires correct exact output, exactly one effect per intent, valid K2 causal dependency, completion by the public deadline, no interpreter error and no refusal. A refusal is neither accepted delivery nor automatically an incorrect decision. It can be the defensible action under an unsupported contract. The finite model permits both initial explanations (already committed versus not committed) and neither (still pending); a noisy/expensive diagnostic may leave these unresolved.

Resources, maximum duplicate/dependency losses and all rejected schedules remain visible. The deadline is part of this authored task contract, not an engineering mission timer or general business ceiling. The sandbox has no external calls, transactions, API keys or physical actuation.
