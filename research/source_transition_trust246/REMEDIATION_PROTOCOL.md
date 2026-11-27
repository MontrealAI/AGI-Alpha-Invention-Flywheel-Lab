# P0-247 — pre-registered owner-trusted transition codec reference

Frozen **23 November 2026 UTC**, separately after P0-246's completed negative witness. This is an **additive source-only proposal in review PR #553**, not a change to PR #40, an active signer, any native account, any queue, or the released canonical enterprise.

## Fixed source and failure
- Main: `f0987aa48d5c9136b28540f54eabf5367e63bbe6`.
- Historical owner PR #40: `ced6c1cb004887dcdafaea59a2976020be649f8e`, `connected_enterprise/upgrades.py` Git blob `9866d004c412fc05c9f6292cf898307f177359df`.
- P0-246: target-root `transition_evidence.py` is executed by `exec(p['codec_source'],codec)` inside the *historical* `JournalAccount` context. The target source must never supply executable bytes to the key-bearing signer.

## Fixed positive reference
Construct an isolated, pure **old-owner-trusted data codec**, with no target-source read, import, `exec`, key, HMAC, account, file write or native transition. Encode only the two large pre-existing historical ticket fields (`prior_record`, `prior_envelope`) into content-addressed canonical JSON blobs; preserve every other field unmodified, including original operating queue, liability history, counters, source identity and day. Produce an explicit exact-size/hash-addressed envelope. Require the signer to regenerate the original body from its own authenticated state and **reconstruct and exactly compare it** against any proposed externalized representation *before* the owner signs, using trusted code only. The proposed test fixture is synthetic and contains no real keys, external records or financial authority.

## Frozen adversarial checks
1. Valid synthetic nonempty acceptance queue and settlement queue round-trip byte-for-byte canonical-equivalent, including all liabilities, source identifiers, counters and obligations. Original caller data remains immutable.
2. Modified cash, omitted outstanding claims, changed queue, changed source, changed counter or delayed day fail equality against the original owner-constructed body.
3. Modified blob bytes, mismatched digest or length, missing blob, surplus blob, swapped blob type, duplicate JSON property, nonfinite JSON, malformed references and excessive input fail closed.
4. Passing executable-looking text as data must never execute it. Module itself must contain no runtime dynamic import/`eval`/`exec` and require no target-root access or secret.
5. The candidate preflight must not be described as a migration implementation: durable CAS staging, crash-safe writes, historical HMAC, exclusive writer, process races, stale/fork proof, release composition and real native account state are **NOT** established by the reference.

## Fixed acceptance
- Pass one standalone Python stdlib unit-test suite with independently fixed positive and negative cases, preserve every failure and test identity. A passing test means only **trusted-data-codec reference**.
- If approved by the financial owner, selectively compose it only into historical owner-controlled source as an immutable, source-bound trusted component, with existing migration/account and recovery checks and no execution of target source in signer. Requalify nonempty legacy queues, crash, race, liability preservation, released bytes and audit **separately**. 
- No user outreach, credentials, spending, paid APIs, new operating account, protected merge, release or deployment.
