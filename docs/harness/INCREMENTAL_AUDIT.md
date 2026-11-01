# Native pre-entry verification

Canonical adaptive-service accounts reuse a private, process-local verifier prefix before new journal entries. The first prefix is fully replayed. Later calls compare actual complete prefix bytes and rebind account, writer epoch, key, source, configuration and manifest; only appended native actions need replay. Every derived financial field, reservation proof, obligation resolution and journal coverage check remains current. Prior deterministic adaptive service acceptance is reused only after rereading and checking every bound source/input/artifact/receipt byte.

Rewind, changed prefix or identity rebuilds the verifier. Verification errors discard it. Closing/reopening an account discards it; an inherited child cannot remove its parent's verifier. Other service schemas retain full replay. Public audits, recovery and final portable audits remain complete independent replays, not cached receipts.

This is an engineering optimization, not new profit, commercial scale or invention evidence. The small source-matched benchmark is a synthetic cost-only prefix audit, not a forecast of full-business runtime. Existing failure lessons and financial results are not rewritten.
