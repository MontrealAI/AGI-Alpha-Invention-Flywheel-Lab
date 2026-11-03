# Omega native contractual-cost completeness witness — frozen regression protocol

Registration date: 2026-11-03 UTC. Exact owner source parent: `7b8d13b1f562bc076e9f53cb23c448725789b26e` (draft PR #201). This is a **separate, additive, read-only audit instrument**, not a second account, a new operating authority, or a modification of the owner's source.

## Claim and controls

The canonical JournalAccount independently verifies **recorded** actions, not necessarily the contractual actions omitted during construction. Check cost completeness against the original declared tariff and the source-bound per-order outcome, not just against a signed self-consistent summary. The witness may inspect key-free native exports but may never sign, edit or reset an account.

Predeclare one small distinct simulated original-engine fixture with `INDEXES=(8,)` and a fixed `policy(('unit','unique','text'), True)` using the existing public synthetic service source and local ephemeral account keys. Do **not** rerun frozen economic cohorts or alter them. Verify intact self-consistent native export and then run **six separate prospective fault-injected accounts**: omit and undercharge one collection fee, omit and undercharge annual maintenance, omit and undercharge modeled tax. Preserve all failing/negative outcomes; no seed selection, threshold relaxation or manual cash adjustment. Include refusal and no-seller-fee controls if feasible.

The read-only witness requires exactly one fee per accepted and settled order (at the declared rounded bps and day), no seller fees for declined orders, exactly one annual maintenance at the registered day/amount, exactly one tax cost computed from the independent pre-tax ledger summary, and correct order of expense and release/annual-close. Reject extra invoice identities as well as missing costs; preserve the signed ledger's authority and whole export via `audit_journal` separately. Native costing must use the existing `JournalAccount`, not a shadow ledger.

## Interpretation and stop

An independent checker detecting each omitted/undercharged entry is a **regression instrument**, not proof that the owner auditor already rejects it. Record whether the current owner `audit_operation` itself rejects or misses each fault. Do not turn a new test runner pass into commercial profit or current-source release qualification. Require current exact-head CI and a normal integration review for adoption; existing owner alone composes into production. Report actual spend/billing UNKNOWN, real paid commerce zero, no new external data. Stop this finite regression after all seven fixed cases, retaining negatives and source identities; prospective repairs are a distinct later step.
