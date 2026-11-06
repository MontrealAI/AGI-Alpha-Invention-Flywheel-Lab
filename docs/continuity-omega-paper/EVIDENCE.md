# Reading the evidence

**English** · [Français](EVIDENCE.fr.md) · [Paper](README.md) · [Language contract](TRANSLATION.md)

Research edition 1.1.0 uses one shared set of evidence identities for both languages. This guide explains the records in ordinary language. It does not replace the records, turn them into field observations, or qualify a later prototype revision.

## What each record means

| Record | What it records | What it does not establish |
| --- | --- | --- |
| [REPRODUCTION.json](evidence/REPRODUCTION.json) | Execution of two existing source-pinned synthetic implementations, their test counts, fixture decisions and exact source identities. | Complete checker soundness, authentic customer history, actual recovery, physical delivery or commerce. |
| [COUNTEREXAMPLES.json](evidence/COUNTEREXAMPLES.json) | Five bounded observations against the same historical handoff source: one positive control, three weaknesses and an already-disclosed source-trust boundary. | A failure-rate estimate, an AI comparison or qualification of the proposed later repair. |
| [POOLING.json](evidence/POOLING.json) | Exact arithmetic for a deliberately authored shared-cost and simultaneous-capacity illustration. | Observed market prices, actual buyer willingness, a production schedule or a commercial transaction. |
| [QA.json](evidence/QA.json) | The preserved historical publication checks for edition 1.0.0, including that edition’s PDF identity and reader JavaScript checks. | Quality checks for the changed 1.1.0 files, current deployment, universal accessibility, or a new cyber-resilience experiment. |
| [TRANSLATION_QA.json](evidence/TRANSLATION_QA.json) | The actual local edition 1.1.0 checks recorded for bilingual structural parity, semantic review, layout and reader JavaScript. | Checks not recorded there, a verified live deployment, independent translation certification, or new operational or commercial evidence. |
| [PUBLICATION.json](PUBLICATION.json) | Canonical publication identities and the complete file inventory for this edition. | The truth of a scientific claim or authenticity of an external business record. |
| [CLAIMS.json](CLAIMS.json) / [CLAIMS.fr.json](CLAIMS.fr.json) | The same claim IDs, classifications, evidence anchors and limitations in English and French. | New evidence created by translation or a stronger claim in either language. |

Fresh reproduction commands also create local `RESULT.json` receipts and detailed logs. Those receipts document that execution; they do not silently replace the published historical record. A new run, a corrected source and a new publication edition have different identities.

## The two source-pinned reproductions

**Handoff source:** `a755d0375693465f8f31c0c919cc186eae74bbcc`.

The `tests.pr278` object records 29 passing implementation tests and zero failing tests. The `pr278` object records 12 supplied CLI cases: three handoff passes and nine refusals before a handoff. The nominal case reconstructs two outstanding commitments totaling 1,900 units. The restored snapshot still has three discrepancies; the handoff checker passing does not repair that snapshot.

The supplied provider has 3,200 capacity units, 1,100 already reserved and 2,100 remaining under the fixture's conservative interval rule. Its stipulated lead time is 22 hours against a 48-hour fixture requirement. None of those values is a measurement of actual manufacturing. The proposed pilot target of up to 20,000 units within 48 agreed business hours is a different, unqualified claim.

The fields `modeled_offer_usd=5700`, `modeled_cost_usd=5050` and `modeled_contribution_usd=650` describe authored arithmetic. They are not an invoice, collection, realized profit or complete measurement of real-world costs. The separate earlier GENESIS Commitment 001 central simulation's US$1,080 modeled loss belongs to a different source and remains a negative historical result.

**Recovery source:** `84c4288b4726a17a90f8462d1d6faf8b5f8f00b5`.

The `tests.pr277` object records nine passing implementation tests. The candidate and competent conventional comparator both return `[true, false, false, false]` on four authored cases. The first is accepted; the three defective cases are rejected. Verification of all four decision records does not mean four recoveries succeeded. The conventional tie remains a tie.

The total of 38 implementation tests is an inventory count. It is not a statistical sample of customers, incidents or model-generated discoveries.

## The verifier itself has counterexamples

The five-probe record preserves the distinction between a known weakness and a successful qualification test.

| Probe | Observation at the historical source |
| --- | --- |
| `positive_control` | The nominal synthetic case passes with two obligations totaling 1,900 units. |
| `boolean_currency` | In a coherently adjusted zero-cost case, the constructor rejects a Boolean offer, but the checker and `verify` CLI accept it with zero reported audit failures. |
| `malformed_top_level` | A `null` top-level input causes `AttributeError`, rather than a structured refusal. |
| `stale_inspection` | After `required_units` is changed to 1, `inspect` returns the stored readiness Passport without a fresh audit. A fresh `verify` returns `FAIL`; the old stored audit still says `PASS_SYNTHETIC_ONLY`. |
| `coherent_reseal` | Rewriting the amendment and recomputing the package's internal identities produces 2,000 units and a pass. This is the previously disclosed difference between internal consistency and binding to an externally retained original scenario. |

The probes were prompted by [the later hardening report at its inspected revision](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/6cd7e1bb7197cabdf8f3d093eead662cde5351f4/docs/continuity-omega/HARDENING.md), then executed against the unchanged earlier source. The proposed repair is not integrated or qualified here. The five observations are separate from the 29 original tests, which still pass.

## Read the raw verdicts without strengthening them

| Immutable token | Meaning in this publication |
| --- | --- |
| `PASS_SYNTHETIC_ONLY` | The program returned a pass for the supplied synthetic artifact. The known false pass shows why this is an observed software decision, not proof of general checker correctness. |
| `FAIL` | The checker reported a failed condition in the particular check. This does not prove that the business objective is impossible. |
| `REJECTED_BEFORE_HANDOFF` | Construction was refused under the supplied case conditions; no real external action or reservation occurred. |
| `READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT` | The producer's readiness marker, not independent acceptance or a current audit result. |
| `REPRODUCED_SYNTHETIC_ONLY` | The reproduction runner obtained the expected historical software outcomes. It does not erase the separate counterexamples. |
| `COUNTEREXAMPLES_REPRODUCED_NOT_CHECKER_QUALIFICATION` | The expected counterexample observations were reproduced. Exit code 0 here means successful reproduction of weaknesses, not a safe checker. |
| `DEMONSTRATED`, `FAILED`, `NOT ESTABLISHED` | Proposed Passport verdicts for a named stage and its declared conditions. Evidence for one stage cannot be promoted to another. |
| `TIE; HOLD / NO DEPLOY` | The recovery study's recorded conventional tie and lack of an established case for deployment. It is not a change to another task's operating authority. |

## The exact pooling illustration

The illustration fixes common cost `K=900`, cost per buyer `c=100`, fee ceiling `B=400`, usable capacity `C=2000` and quantity per buyer `q=750`, for a common period in which all buyers may activate together. Economics requires `n_min=3`; simultaneous capacity permits `n_max=2`. Two buyers give contribution `-300` in hypothetical monetary units. Three break even but require 2,250 capacity units. The feasible-count list is empty.

Under the paper's stated assumptions, an arithmetic overlap exists exactly when `ceil(K/(B-c)) <= floor(C/q)`. Operational feasibility, actual participation, rights and cash timing remain separate. Changing a slider or an input explores a different authored arrangement; it does not reveal a market price or actual spare capacity.

## Identity, completeness and independence

`source_files` and `source_sha256` bind the reproduced bytes to a Git blob and SHA-256. A hash proves neither that a source contains every obligation nor that its supplier declarations are true. The observation cutoff, external custody, out-of-band commitments and competing reservations need their own evidence.

Separate checker code and separate AI tasks can share source omissions, assumptions and authorship. The recorded review occurred within one assistant workflow. It is neither third-party certification nor a two-frontier-model experiment. The bilingual edition changes the available reading languages; it does not change those limits.
