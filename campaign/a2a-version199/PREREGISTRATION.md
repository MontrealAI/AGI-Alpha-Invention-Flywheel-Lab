# P199 — pre-implementation registered HTTP protocol-version conformance witness

**Registration timing:** This document is the first commit on an independent review branch from current main `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. No P199 implementation or P199 test outcome preceded this branch registration. The PR498 implementation and its 12 successful self-authored checks are already exposed development evidence, not withheld evidence.

## Immutable source and official semantics
- Exact active adapter source **PR498**: `dec5cb10ce2ac3eb1ccb0de383a21ab8d063a360`; `campaign/a2a-interop198/a2a_adapter.py` Git blob **`9cd62b61fb84732511350a5aaa5820594b19f7d1`**.
- Exact original source consumer **PR484**: `b333a5f4ac9495b9c8259170597239a1792bf1ac`; `products/frontier_machine_asset_001/gate.py` Git blob **`115cf8531df65a66dcc679e2d35cb03394cea11a`**.
- Official A2A current specification **§3.6**: https://a2a-protocol.org/dev/specification/ . Clients must identify version; servers **MUST** process requested major.minor semantics, return `VersionNotSupportedError` when unsupported and interpret **absent/empty as 0.3**. A2A interface advertises JSONRPC `protocolVersion: "1.0"` only. This study targets this discrete semantics, not generalized third-party SDK conformance.

## Frozen cases (one unchanged valid v1 SendMessage body in all four)
| Case | HTTP A2A-Version | Normatively expected | Specific negative witness to preserve if observed |
| --- | --- | --- | --- |
| V1 | `1.0` | exact existing source accepted response | succeeds |
| V2 | absent | 0.3 assumed; v1-only interface refuses `VersionNotSupportedError` | v1 response improperly accepted |
| V3 | `0.3` | v1-only interface refuses version | v1 response improperly accepted |
| V4 | `2.0` | unsupported version refused | v1 response improperly accepted |

Tests must operate actual local HTTP with unmodified exact PR498 adapter and original PR484 `gate.py`. They must check both Git checkout SHA and Git blob before import. Use same payload for each. Reject drift or missing original; no mock replacement of owner gate. Assert historical v1 acceptance control first; each negative witness is an **expected defect finding** and may make the independent witness suite green, not the implementation conformant. If a negative is falsified, preserve evidence and revise conclusion without cherry-picking parameters. Cost/CPU/RSS evidence is engineering telemetry, not commercial margin.

## Protected comparison, constraints, stop rule
Compare four request-header treatments within one deterministic local transport session. No external network, SDK download, live RPC, payment, signer, API key, production service, paid runner, outreach, native account or manipulation of other owners' source. The executable endpoint is bound to 127.0.0.1. The next owner remedy, if confirmed, is a **prospective** fail-closed version gate and independent requalification on the owner's source branch, not merging this evidence branch wholesale. Preserve already failing runs without retagging.

**Decision gate:** If at least one unsupported/absent version is admitted under 1.0 semantics, mark advertised 1.0 conformance **FAILED within this parameter**, while retaining protocol-shape successes; NO BID / NO DEPLOY and no claim of paid market or new productive outcome. If every case conforms, report falsification rather than invent a defect. No complete A2A v1 compatibility, authorisation, external customer, paid collection, native earned funding, discovery improvement, or US$3B trailing-365 profit can follow from either outcome.
