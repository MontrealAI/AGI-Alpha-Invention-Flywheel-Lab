# P0-267 — adjudicated first-run failure (2026-11-24)

**Decision: reject full qualification.** Preserve the registered denominator and unchanged source. Do not rerun to seek a favorable outcome. This is a supporting research candidate, not financial-owner integration or a new commercial campaign.

- Frozen workflow head: `9b771b9869900e29f66185db450158a0b9f8f945`; [run 45434050616](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45434050616), job 138586901756. Setup and receipt upload succeeded; the registered execution step failed.
- [Artifact 14941756246](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45434050616/artifacts/14941756246): actual ZIP downloaded through a separate connector and checked locally. 1,347 bytes, SHA256 `09fa4354f991d7538f1538b8fef7897356a78ca37cd215920097b10dba68885c`, ZIP CRC verification clean, single member P0_267.json, 3,335 bytes, SHA256 `4a86976c0372b56fac078c258a9b184c05fb8fabc1ed05298b7dcf3c1d4ccd18`. The companion RESULT.json transcribes the safe receipt fields; the original artifact hash remains the authoritative byte identity.
- 115 audit launches, 7 authorization launches, 561 audit-cache hits, 122 isolated boots, 54 patched descendant requests, zero legacy descendant requests. The latter counts describe observed invocations, not independently proved closure or accepted child results. Total waited-child CPU 272.411287 s, wall 434.384236845 s; whole-episode billing unknown. Waited-child CPU excludes unobserved work and is not a complete cost estimate.

| Registered case | Result | Wall s | Waited-child CPU s |
|---|---|---:|---:|
| Canonical public CLI upgrade, resume, audit and scoreboard | PASS | 97.085 | 95.688 |
| Forward engine-only upgrade, prior transition and same business | FAIL: TimeoutExpired | 254.969 | 94.792 |
| Cache historical source/artifact tamper recheck | PASS | 82.241 | 81.929 |
| Seven context checks | PASS | | |
| Six static gates | PASS | | |
| Full native descendant qualification | FAIL (2/3 native cases) | | |
| Original owner checkpoint and exclusive custody | BLOCKED / unknown | | |
| Nested cache equivalence, protected integration, release from this candidate | UNQUALIFIED | | |
| Native US$3B T365 complete-cost milestone, actual commerce, recursive discovery benefit | UNESTABLISHED | | |

## Diagnosis and next decision

The second case accounts for all 54 patched descendant requests and 109/115 audit launches. The observed timeout remains despite fresh-bytecode isolation. It does not prove that bytecode caused the prior timeout or that a wider cache would be correct. Compared with P0-263, aggregate wall and waited-child CPU are higher; uncontrolled hosted runs with a failed case are not a causal performance benchmark. No acceptance threshold changes.

Source read at owner checkpoint ced6c1cb004887dcdafaea59a2976020be649f8e: `connected_enterprise/upgrades.py` lines 40–104 select a pinned historical verifier, load service jobs, and perform a subprocess audit. `connected_enterprise/finance.py` around lines 137 and 213 calls that verifier during both public historical-prefix validation and upgrade. `transition_evidence.py` around line 272 creates a fresh validation context per evidence-directory entry; a process-local dictionary does not automatically survive a historical child process. The second-transition test at lines 225–260 actually creates a forward engine-only source, preserves the old action prefix, rejects the replayed checkpoint intent and exercises resume/audit under original timeouts. Repeated nested replay is therefore a plausible mechanism, not a measured exclusive cause. Existing evidence identifies where to profile; it does not yet support nested caching.

Next decisive research boundary: trace safe per-operation invocation identity (digest only), parent/child edges, phase time and result-equivalence, distinguishing repeated leaf validation, source/data staging, evidence parsing and native replay, using the pinned second-transition fixture in a new registered diagnostic rather than calling this run a pass. Consider an audit-scoped verified dependency graph versus ordinary fresh verification only after exact transitive evidence/source/launcher/interpreter closure and mutation/race rejection can be demonstrated. No reuse of signing authorization or shared mutable global receipt. Retain the canonical verifier, owner authority and every original timeout. The new diagnostic is not yet implemented or registered here.

## Ownership and release refresh

Main inspected `53101fd1af33b2dec8335db0a7ae566adb94c0d7`, AGENTS.md, current operator/developer/resource guides, current connected014-release workflow and six overnight022 handoff records. Current main [release workflow 45438435098](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45438435098): qualification job succeeded, publication in progress at observation. Previous source 162ac807c6a7302fa8b4fd6fa1a03ff786fd1f41 has a published connected014 tag and [successful release workflow 45423567566](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45423567566). Do not represent those unrelated releases as this P0 candidate.

PR40 remains draft at ced6c1cb004887dcdafaea59a2976020be649f8e, dependent on closed-unmerged PR35 head 7d75766401adede49afd2427be82eb0302934b80. No original account or exclusive local signer custody verified. PR77 still draft at cd5281b0ae7b484572bfb35ccb7e51ef5b3be4b3; the named historical workflows 41251886324 and 41251886340 report successful jobs (not a new economic or integration verdict). No owner branch or protected account was modified. No spending, real transaction, outreach, private data, deployment or credential change. P0-262 and P0-263 failures unchanged; target remains open.
