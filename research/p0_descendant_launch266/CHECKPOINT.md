# P0-266 execution checkpoint — 2026-11-24

First local execution after frozen protocol fe1eb807c54d0845235e1ed17a52b6c22539675e, exit 0. Executed probe SHA256 0b08783260e1fc674e05291037b520c35d9f1f1f0a65e0c17fc139f3c764760a, Git blob 46b388f15231ad583ee4745cfc5e3572a7f24db8, matches published source. Nine of nine fixed checks passed. No retries.

| Acceptance | Result |
|---|---|
| Ordinary launch loads stale bytecode | PASS: OLD |
| First mediated launch | PASS: NEW |
| Second mediated launch | PASS: NEW |
| Injected Python startup environment ignored | PASS |
| Unauthorized root | PASS: rejected |
| Unregistered call | PASS: rejected |
| Altered source | PASS: rejected |
| Restoration parity | PASS |
| All launch receipts | PASS: 11/11, isolated=1, no_site=1, no_write=true, prefix_empty=true |

Four accepted child launches and seven accepted parent launches. Parent code digest c87cb99bbf5ce3dd75588b14b8221130836da29035f36b00702352b73c3ebfcb; child code digest 4c1b607fc3406f95600b43f99597c4c551d66df66f093a4ac71180c8128ba51b. Receipt order: parent/child, parent/child, parent/child, parent (unauthorized root), parent (unregistered call), parent (altered source), parent/child (restored). Ordinary flags isolated=0, no_site=0, no_write=true, prefix=false; mediated flags isolated=1, no_site=1, no_write=true, prefix=true. Waited-child CPU 3.781901 seconds; elapsed 2.9827026970000077 seconds; actual billing unknown.

## Decision and remaining gates

The exact historical call shape can cooperatively propagate a controlled interpreter invocation to a descendant without editing historical source. This is a useful development component, not a security sandbox. Arbitrary executable invocations can bypass it; the policy file, launcher, interpreter, stdlib, native libraries, service data and evidence store need external binding, and TOCTOU/concurrency and authentic root authorization are unqualified. Do not enable nested audit caching or claim native financial equivalence based on this result. Next decisive work is a source-pinned native invocation comparison with all of those controls and unchanged acceptance. P0-262 and P0-263 remain failed at full qualification.

Main read d2f0d5d585a35443729100bc0c74df1f2c323ac4. Current AGENTS.md, connected014 release workflow and six historical handoff records refreshed. PR40 remains draft/open at ced6c1cb004887dcdafaea59a2976020be649f8e, not exclusive original-account custody. Original owner task state remains unknown. Direct local GitHub DNS unavailable; public connector reads/writes succeeded. No protected source or accounts touched; no real transactions, expenditure, credentials or deployment. Native migration, economic milestone and recursive improvement remain unqualified. US$3B T365 complete-cost profit remains open.
