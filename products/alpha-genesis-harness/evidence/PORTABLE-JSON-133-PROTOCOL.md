# HARNESS133 — preregistered portable instrument JSON ambiguity check

**Source freeze:** main `1d64b69dcadb494d60f666c635fbecf74ebeeefc`, prior to this patch. The workflow-generated `RUN_INSTRUMENT.py` is a byte-for-byte copy of `bridge/instruments.py` at construction time. **Status at registration:** defect reproduced by the unmodified Python standard JSON parser; prospective product acceptance remains unqualified.

## Exact vulnerable boundary
`bridge/instruments.py:main` currently calls `json.loads` on the standalone instrument file and user input. Standard `json.loads` silently retains the last value of repeated object keys, including escaped spellings that decode to the same name. Thus two textual instructions that disagree may be silently collapsed before the independently exported instrument is executed. A shipped evaluator should reject ambiguous inputs rather than silently decide which definition was intended. This is a portable evidence-interoperability and integrity boundary; it is **not** an established exploitable compromise, and this narrow repair does not modify the browser UI or the existing internal Python-dict evaluator.

## Frozen prospective tests (before repair)
1. Refuse an instrument file containing two `outputs` fields (conflicting complete result definitions).
2. Refuse a nested expression with duplicate `op` fields, even if the last operation happens to produce a valid result.
3. Refuse an input file containing both `"x"` and its JSON-escaped equivalent `"\\u0078"` (one decoded identity with two values).
4. Refuse identical duplicate input members, not merely contradictory duplicates.
5. Refuse nonstandard `NaN`/`Infinity` JSON tokens in otherwise unused instrument metadata; raw data must be strict JSON, not Python's extended JSON.
6. Continue accepting an ordinary portable, finite, nonduplicated file pair and return the preexisting correct result.
7. Confirm that disallowed artifacts exit nonzero with no accepted JSON emitted on stdout and no disclosure of arbitrary supplied values in diagnostic messages.

**Scope:** exact standalone Python CLI; applies automatically to future generated `RUN_INSTRUMENT.py` files because the trusted runner is copied verbatim from this module. Already published archives are historical and unchanged. The in-memory `evaluate(spec, inputs)` contract, frozen numerical bounds, instrument grammar, signed accounts, HARNESS G1/G2/G3 evidence and existing deployments are unchanged. Browser import and independent real-world commercial claims require separate tests.

## Pre-registered acceptance
The above tests must first fail where specified on the frozen source, then pass with a minimal source-parser repair. Existing instrument and release tests must pass on the exact prospective head, including the extracted-archive check and relevant GitHub Actions; any negative results remain negative. No model sampling or data selection to obtain a favorable result, and no relaxation of an existing source or finance guard.

**Owner boundary:** independent, additive security-and-customer-output review on current main. Does not edit financial P0, PR #330/#339's release evidence reconciler or their branch, and is not an instruction to merge those branches. No claims of physical invention, paid commerce, superior discovery, or US$3B profit.
