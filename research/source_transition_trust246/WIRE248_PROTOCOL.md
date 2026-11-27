# P0-248 — owner-wire interoperability and nonempty-queue externalization

Recorded on 2026-11-23 for **additive research** after P0-247. This is a follow-on engineering protocol; exploratory local construction and nine local tests occurred before this GitHub registration. Do **not** describe those as a previously blinded experiment. The hosted exact-head test, if executed, is an additional engineering reproduction, not new economic evidence.

## Exact immutable parent and compatibility contract
- Current main at inspection: `f0987aa48d5c9136b28540f54eabf5367e63bbe6`.
- Historical owner draft PR #40: `ced6c1cb004887dcdafaea59a2976020be649f8e`; `connected_enterprise/transition_evidence.py` defines `v2-cas`, outer signed ticket <=16,000,000 bytes, per-blob bound <=64,000,000 bytes, total evidence <=512 MiB and <=10,000 blobs. Its `externalize` stages `prior_record`, `prior_envelope`, **and `operating` when present**, using SHA256(canonical JSON bytes) and refs containing exactly `sha256` and `bytes`. The currently proposed P0-247 reference has only two externally stored fields and a 16 MB blob cap. Neither proves live owner interoperability.
- Review branch and implementation are **not** authenticated account owners. No historical key, native account, signer subprocess, account state, ledger or source of PR #40 may be modified by this work.

## Fixed follow-on engineering checks
1. Construct an isolated **pure Python / data-only owner-wire reference** matching three-field optional `operating` v2-CAS body shape and owner's existing bounds, with no dynamic source import, target `exec`, secret, filesystem I/O or signer.
2. Check two-field compatibility when operating state is absent; check **nonempty settlement queue** and old claims/cash/source/counter/day identity against an immutable trusted original. Exercise a synthetic operating value that exceeds 16 MB so the total compact signed-ticket representation stays within the original guard while each referenced blob remains <=64 MB.
3. Fail closed for missing/swapped/modified/extra blobs, altered money, liability, queue, account path, source/counter/day, invalid schema, wrong digest/length, duplicate or noncanonical/nonfinite malformed JSON and excessive depth. Keep any failed result.
4. Require an exact **owner-reconstructed v1 body comparison before signing**. Source and all prior original-account evidence must come from the historical owner; untrusted v2 data is never a substitute for verifying history. This proposed helper is **not itself an authority**.
5. Host the tests on an exact PR-head standard public GitHub Actions runner, with no persistent checkout credential or paid API. Preserve workflow exit status and digest when available.

## Strict scope of any success
Passing proves only compatibility of a synthetic owner-wire **research reference**, not that PR #40 has been repaired, that original signed account and nonempty operating queue were migrated, or that a 64 MB owner production blob has been safely handled. It does **not** qualify durable CAS staging, crash/race writer controls, original HMAC, stale/fork rejection, canonical public CLI, current-main composition, protected release, clean downloaded operation, commerce or US$3B trailing-year profit. Any actual owner change must be owned/reviewed by the authoritative financial integration owner, preserving all historical liabilities and failures.
