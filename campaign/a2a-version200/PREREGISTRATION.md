# P200 — prospective repair reference for A2A 1.0 version negotiation

## Frozen before implementation
This is an **additive, independent research reference**, not a change to the A2A198 owner source, a merge, or a production service. Source baseline `main=f0987aa48d5c9136b28540f54eabf5367e63bbe6`. Source producer `PR498=dec5cb10ce2ac3eb1ccb0de383a21ab8d063a360` (`campaign/a2a-interop198/a2a_adapter.py` Git blob `9cd62b61fb84732511350a5aaa5820594b19f7d1`); unchanged asset consumer `PR484=b333a5f4ac9495b9c8259170597239a1792bf1ac` (`products/frontier_machine_asset_001/gate.py` Git blob `115cf8531df65a66dcc679e2d35cb03394cea11a`). The P199 original-source negative witness at `ce2722ecf192c48352a6cca7b0bf2af71b058206` is already observed, exposed development evidence. Never retroactively mark its failures a pass.

Normative reference: [A2A 1.0.1 specification §3.6, §5.4](https://a2a-protocol.org/v1.0.1/specification/) and [official Python SDK version validator](https://a2a-protocol.org/v1.0.1/sdk/python/api/a2a.utils.version_validator.html). The adapter advertises **JSONRPC 1.0 only**. Missing/empty `A2A-Version` means 0.3; mismatched Major.Minor must return `VersionNotSupportedError` (JSONRPC code -32009). A correctly formed `1.0.<numeric patch>` denotes the same major.minor in SDK matching. Reject ambiguous repeated header fields instead of silently choosing one.

## Frozen finite tests
All valid cases use the same fixed data-transform contract and the exact original PR484 gate. All POST tests operate over actual 127.0.0.1 HTTP to a wrapper of the pinned unmodified PR498 handler, never a substitute evaluator. Compare against the competent direct original adapter and no-deploy:
- **V1**: header 1.0, accepted exact original output/receipt parity;
- **V2**: header absent, reject code -32009 without executing the original gate;
- **V3**: explicit 0.3, reject -32009 without gate execution;
- **V4**: explicit 2.0, reject -32009 without gate execution;
- **V5**: header 1.0.3, accept with same original gate result under patch-insensitive matching;
- **V6**: empty header, reject -32009;
- **V7**: duplicate 1.0 and 2.0 header values, reject -32009 without execution;
- **V8**: duplicate 1.0 fields, reject -32009 without execution;
- **V9**: malformed combined '1.0,2.0', reject -32009;
- **V10**: malformed 'v1.0', reject -32009;
- **V11**: GET discovery remains unchanged and v1 is advertised;
- **V12**: original wrong-path POST still returns 404 and does not invoke gate.
- **V13**: original A2A198 baseline HTTP test helper omitted the A2A-Version header, so after enforcing v1, its former accepted expectation must be updated; identify this testing impact without altering frozen A2A198 results.

Include exact source SHA verification and self-contained stdlib regression tests, measured CPU/wall/RSS, immutable CI logs even on failure. The reference must fail closed on source drift, use no private credentials, no payments/outreach, no API keys, no actual native account, no production deployment, no hosted external HTTP and no paid runners. Do not change original PR498/PR484, current main, financial-owner PR40, or the canonical ledger.

## Fixed decision
If any V2–V4/V6–V10 is accepted instead of refused, reference conformance **FAILS**. If V1/V5 or unchanged direct-original parity fails, reference fails. A passing reference proves only bounded corrected header behavior, not general A2A interoperability, live asset commerce, buyer benefit, third-party SDK support, newly enabling intelligence, safe native finance, external revenue or US$3B profit. Reject deployment; provide a small selective owner handoff. **Stop after these fixed cases and competent direct/no-deploy comparison.** No seed/threshold substitution.
