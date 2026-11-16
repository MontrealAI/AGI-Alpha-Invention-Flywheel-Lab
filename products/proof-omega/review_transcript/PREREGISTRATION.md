# P0/P2-adjacent independent proof review — frozen protocol

Date: 2026-11-16. Review owner: independent proof-conformance reviewer. Source: PR #410 exact `85f391beec63d68e0ecb4f380da99b4e3a20ccaa`, current main `172ea7a9b96ad123a879dde76101b944aa9cf131`. No native account ownership or authority transfer. This is supporting technical assurance, not P0, a native funding instrument, or a release.

## Selection (before implementation)

The new-user-value route remains unqualified for every option. Three materially different routes were considered: (a) finite-policy conformance for private financial authorization products (PR #410, potentially strong consequences but existing formal-method incumbents), (b) authorized black-box migration of obsolete executables (PR #411, current lookup-based demo not generalizable), and (c) automatic compute-bottleneck invention (PR #409, strong incumbent required, live model blocked). Fourth option is **NO BID/NO DEPLOY**. Choice: investigate (a)'s precise prerequisite of independent binary conformance. This is an enabling safety check, not a claim of a newly possible commercial outcome. Existing TLA+/model-checking and mature security-engineering alternatives remain undefeated.

## Fixed falsification contract

Unchanged original certificate/source and finite escrow fixture. Two adversarial cases:

1. **Transcript-shaped executable:** a trusted, generated local program returns the exactly correct state-action outputs in the published fixed traversal order, but ignores its input. Directly show wrong answers under a different order. The current conformance verifier must **not** return `PASS_BOUNDED_EXECUTABLE_CONFORMANCE` for such an implementation if it purports to check deterministic per-request semantics. A PASS is an observed false qualification, not an external exploit.
2. **Non-Boolean guard:** a policy action guard with integer `1`, syntactically accepted by current validation, must not produce a `PASS` proof report (even if a subsequent audit rejects it).

Run all unchanged product tests alongside new tests. Preserve the first exact-head failing run as FAIL. Any repair must be prospective, without moving the independent acceptance check, inventing unobserved buyers or weakening authorization. Test at least a second challenge ordering and repeat individual requests; disclose that no finite black-box test establishes equivalence against a purposefully adaptive adversary. Additional initial-state and mutation checks may be added only as transparent supplementary diagnostics, not as replacements for these frozen conditions.

## Controls, costs, stop/decision

The adversarial binary is generated and executed **only as a trusted local synthetic fixture** via the existing `unsafe_local=True` test harness. No customer binary, external credentials, native financial account, paid API, Docker bypass for untrusted code, sale or deployment. Exact source SHA, test exit, source of failures, execution resource/cost unknowns remain in CI history. Stop after one preregistered falsification and one prospective corrective implementation attempt; preserve failure if unresolved. If the original kernel passes the adversarial challenge, do not invent a flaw. A focused pass is not whole-PR qualification or a novel invention claim.

Expected disposition: owner PR #410 retains sole integration responsibility; submit reviewer code in a separate dependent draft; no merge to protected main without independent whole-PR qualification and owner integration.
