# Registered study · Resume an archived weather-data transfer

## Decision and limits

A weather-data operator has one verified prefix and receives the next partial response. Given normalized metadata, decide if the second response can extend the prefix. Check adjacency, forward order, object bounds, observed byte count and a matching strong validator. The upstream caller remains responsible for parsing `Content-Range`, verifying the identity and validator of the first response, and passing the actual body length. No instrument appends bytes or promotes itself. The applicable HTTP reference is [RFC 9110 §15.3.7.3](https://www.rfc-editor.org/rfc/rfc9110#section-15.3.7.3).

The earlier [S₁ trial](REFERENCE-MODEL-REGISTRATION.md) computed properties of a single interval. This new task decides whether two responses can be joined. Test whether named reuse of the already verified byte count and ordering expressions improves construction on that separate contract. The prior failed S₂ comparison remains frozen.

## Arms and stopping rule

| Arm | Construction access |
| --- | --- |
| Direct | New task and the ordinary formula compiler. |
| Ordinary reuse | Same task and the exact previous expression tree as inert background, plus the ordinary compiler. |
| Named reuse | Same task and identical expression tree. The compiler also accepts named outputs of that tree and expands them into inert expressions. |
| Conventional incumbent | Direct arithmetic supplied by an engineer, checked against a separate Python range oracle and the source observations. |

Use the already qualified pinned Qwen3-4B Instruct 2507 Q4_K_M weights and llama.cpp b12242 on local Linux CPU. Use four threads, 4096 context, one slot, temperature 0 and seed 283. Each model arm has one request with a 256-token output limit. No provider fallback, repairs, model switches or post-adjudication retries. Record construction wall time and reported usage for every arm. Use the same final evaluator for all runnable instruments. Treat a failure to construct as a distinct outcome. A successful instrument can be retained for this contract only. A tie or an incumbent that matches all cases leaves the incumbent in place pending independently accepted full-workflow evidence.

## Independent case preparation

The evaluator draws six sets of eight controlled cases with an unpublished seed before construction. The cases exercise a good continuation, gap, overlap, reversed range, end at the object boundary, short body, different validator, and a single-byte tail. The reference uses Python `range` membership/cardinality. The case sheet stays outside the model prompt. Freeze its hash before dispatch. Confirm the positive observation separately by fetching bounded slices `0–15`, `16–31`, and `0–31` of the same public [NOAA GFS object](https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20240124/00/atmos/gfs.t00z.pgrb2.0p25.f024). Require exact `206` and range headers with the same strong ETag and length, then compare the two small bodies concatenated to the independently acquired window. If acquisition fails, report it and grade the 48 generated cases without a live denominator. Retain the source identifiers, hashes and observations. Release the case sheet only for reproduction after all arms end.

Evidence here can establish construction, held-case correctness and tested acquisition agreement. The finite study does not measure human first use, complete labor, training, energy or maintenance costs. It does not grant production authority or establish improvement of the inventor. No money changes hands. See the companion’s bilingual `SUCCESSORS.md` to operate the protocol.

## Separately registered follow-up

In the first comparison, all three Qwen instruments were identical. Each accepted six incorrect cases because it checked `end <= object_bytes`. The named-reuse arm used no inherited symbol. The Python and retained conventional expression references agreed on all 49 cases, including the new NOAA observation.

For a new comparison, clarify the zero-based convention and name the exact boundary rejection in every model prompt. Keep the model, three one-call arms, reference, task semantics and validation thresholds fixed. Use another hidden generated cohort drawn with a new seed and fresh observations from the [January 25 NOAA object](https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20240125/00/atmos/gfs.t00z.pgrb2.0p25.f024). Grade after all construction. No repairs or retries within the second comparison. A success isolates an observed outcome under the clarified protocol. It does not show the system discovered the clarification autonomously. The first outcome remains part of the full record.
