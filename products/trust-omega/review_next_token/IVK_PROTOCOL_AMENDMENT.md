# Pre-test applicability amendment — 2026-11-16

**Preceding frozen document is immutable:** IVK_PROTOCOL.md at commit `14cdd4d7433ffc16af5146d84200c71c5a602eef`. The protocol included two incompatible requirements: (1) preserve the two unchanged pre-existing v1 positive tests; (2) make every v1 call fail before the mocked checker. Both cannot simultaneously hold. This conflict was identified in source review **before creating or executing new tests**; no test/holdout result motivated this amendment. Do not relabel the originally stated v1-rejection acceptance as achieved.

Prospective alternative, with narrower result:
- Keep v1 parsing and legacy verification semantics unchanged, including original five owner and two reviewer tests. Classify all v1 records explicitly as **LEGACY_UNBOUND_PUBLIC_KEY_DIRECTORY** in new documentation; no v1 record may be used as evidence of independently anchored complete verifier inputs. Do not add trusted receipt claims to v1.
- Add an independent v2 anchor contract with mandatory externally pinned `public_key_tree` SHA256 and strict fail-closed comparison before invoking upstream. A v2 UPSTREAM_EXACT_ACCEPTED record must include the public-key tree hash. No fallback to v1 if a v2 anchor is invalid.
- Tests and real upstream smoke MUST use v2 for any new complete anchoring claims; original v1 smoke and prior results remain historical. Move new smoke anchor to v2; preexisting original v1 tests are unchanged.
- For v1 deprecation, recommend owner-controlled separate migration with versioned back-compat and an explicit change to the original tests; this reviewer cannot silently change a legacy public interface. **Strict v1 fail-closed is NOT ACHIEVED** under this amended candidate.
- Keep all original preregistered test cases, stopping rule, strong alternatives and economic/financial gate unchanged. No adoption/release without owner review. Publish the amendment as a narrower qualification, not the original stronger security result.

This is a pre-test protocol correction of a logical incompatibility, not a post-hoc performance adjustment. If it fails, preserve failure and stop without tuning benchmark outcomes.
