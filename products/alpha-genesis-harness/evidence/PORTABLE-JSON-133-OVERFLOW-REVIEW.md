# HARNESS133 independent follow-up: finite-number overflow is not a JSON constant

**Frozen prior corrective head:** `326d24b9dcc694782875a4ba3d9f3ab1c4571b25`. This is a prospective *new* review case, not an edit to the already frozen original `PORTABLE-JSON-133-PROTOCOL.md` or its original tests.

Python's standard JSON parser with `parse_constant` rejection still materializes syntactically valid scientific-notation `1e309` and `-1e309` as nonfinite float values. When either occurs in an unused metadata field, `evaluate` does not traverse it and a seemingly accepted portable instrument may contain a nonfinite parsed value. This is a same-boundary but distinct parser-overflow condition; it was reproduced locally against the `strict_portable_json` algorithm from the previous head **before** this repair.

**Frozen new condition:** the standalone `RUN_INSTRUMENT.py`/source CLI must refuse both exponent-overflow values even if they occur only in inert instrument metadata, with a nonzero exit, empty stdout and a value-free `Invalid JSON` diagnostic. Ordinary finite decimal/scientific-notation values and previous successful expressions must remain valid. The old original six tests and original workflow outcomes remain immutable; any new source is prospectively qualified on its own commit. Not a claim about browser imports, model quality, paid commerce or financial authority.
