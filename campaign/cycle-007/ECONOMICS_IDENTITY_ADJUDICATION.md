# Commerce delivery identity adjudication

**Decision: the original exact-byte delivery claim is FALSE and is not qualified. Canonical JSON content equality is demonstrated.**

This addendum preserves the original source, freezes, acceptance receipt and `commerce007-001` outputs. It corrects interpretation; it does not repair the byte-identity contract or retroactively change which check the old code executed.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Independently accepted raw `evidence/cycle-007/verification/ACCEPTED_DELIVERY.json` | 11,303 | `2fe6d6ea18864fc203997554a2a0d9b41a58ab3b13b8aa24cde74aa709ad8e1d` |
| Released `evidence/cycle-007/commerce007-001/artifacts/DELIVERED.json` | 6,008 | `afe550c329ddb07e1d0a65ade8fefca5e0f070ad2d87f3e8f95060050e8eba4a` |

The raw byte sequences and their hashes differ. Parsing both as JSON produces equal values. Serializing the accepted JSON with sorted keys, compact separators and nonfinite numbers disallowed produces the delivered bytes exactly.

The reused `ProtectedExchange` stores and releases canonical JSON. The adapter correctly bound the raw accepted input and compared the downloaded output against canonicalized JSON, but labeled that check `accepted-exact-artifact-duplicate-settlement` and described the delivery as exact accepted bytes. That label and the accompanying exact-byte wording overstate what was tested. The passing check establishes canonical-content delivery and duplicate-settlement behavior, not preservation of the independently accepted raw serialization.

The verifier identified the discrepancy; read-only comparison of the preserved files reproduced it. No missing or altered parsed JSON field was established. The independent scoped compatibility acceptance, ordinary coordinated-upgrade result, payment/reversal records and zero commercially qualified earned funds remain unchanged. The 15 passing software checks must not be cited as a pass of the untested raw-byte preservation requirement.

No frozen source, prior receipt, acceptance threshold or original artifact is replaced by this adjudication. A future raw-byte preservation implementation would need an explicit byte-preserving envelope or equivalent interface and a separately frozen acceptance check and new execution. None is claimed here. A future canonical-content contract could instead declare its canonical identity explicitly; it would not retroactively qualify the original exact-byte claim.

The read-only comparison is reproducible from the two preserved artifacts using their SHA-256 hashes, raw lengths, parsed JSON equality and canonical reserialization. This is a wording-and-identity adjudication, not a new scientific confirmation, a new commercial experiment or an earned-funding event.
