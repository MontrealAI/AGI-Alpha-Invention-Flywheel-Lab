# P0/126 — same-source signed settlement restart (10 November 2026)

**Verdict:** engineering continuity **PASS**; canonical source-tamper rejection **PASS**; authenticated *cross-source* transition **NOT TESTED / BLOCKED**; short-world commercial selection **FAIL / NO ADOPTION**. This is an additive owner-safe witness, **not** a financial engine patch, new operating account replacing an owner's account, or a basis for merging PR #40.

## Source and prospective freeze

- Executed directly from the **actual public** `connected014-1d64b69dcadb494d60f666c635fbecf74ebeeefc` downloaded-operation source, identity `1d64b69dcadb494d60f666c635fbecf74ebeeefc`.
- Registered native source identity: `1fffc99faef369607ec05e0cdd30ee4cc6f3ec42d1fda3797c3e731ce0a87613`.
- Fixed **before registration/execution**, `PREREGISTERED_126.json` SHA-256 `a207aa257fb073e48fcf45436b686423126c27922df72b6fee37a33e9deaf1a5`; complete input SHA-256 `cf9c115d9bbfeb795d3257c69211c6abee6e7d5b5ad833a63fb0aa24ab7b733f`.
- Source input: `campaign/overnight-022/OPERATOR_INPUT.json` from the pinned public release. Mechanically change only `label="p0-126-due-settlement-restart-boundary"`, `evidence_role="development"`, `seeds=[126001]`, `service_cohort_seed=126002`, `configs.central.horizon_days=5` and append two explicit limits: `New source-bound, distinct fresh native-account engineering witness only: no legacy or private owner accounts used.` and `Do not treat same-source due settlement as authenticated cross-source migration.`. Serialize Python `json.dumps(config, indent=2, sort_keys=True) + "\n"` to reproduce the input digest.
- **Two distinct fresh ephemeral simulation accounts**, baseline/growth, each opening with 5,000,000,000 microUSD of *modeled* initial capital. These are not pooled or credited to the inaccessible original enterprise. Same fixed five-day horizon and same modeled world/seed in both arms.
- Frozen acceptance before execution: register; operate four events/arm; verify nonempty queued financial `clear` due hour 51; operate two further events/arm from the **same account**; canonical resume to terminal queue drain; canonical audit; completed-resume idempotence; no migration claim. Failure does not authorize reseeding or a different horizon.
- Separately frozen before tamper operation, adversarial protocol SHA-256 `58f4a72f3e050c7d53c96766bf56baf4d154e9b36fb6a11055b08a7ad350cfcb`. It permits one comment-byte mutation of **only this fresh account's registered frozen `engine.py`**, then requires fail-closed `resume`, immutable signed finance, byte-exact source restoration and passing canonical audit. No original owner account, key or signer was accessed.

## Actual canonical execution and audit

| Canonical command on the registered fresh output | Exit | Actual observation |
| --- | ---: | --- |
| `python3 -m connected_enterprise register --config INPUT_126.json --output /absolute/new/output` | 0 | Two separate planned arms, no accounts created at registration |
| `python3 -m connected_enterprise operate --output /absolute/new/output --max-events 4` | 0 | Four processed each; two queued, including a real `clear` event at hour 51 |
| `... operate --max-events 2` | 0 | Six processed in the **original same accounts** |
| `python3 -m connected_enterprise resume --output /absolute/new/output` | 0 | Nine processed each, queued events drained, a `COLLECTION` recorded in each |
| `python3 -m connected_enterprise audit --output /absolute/new/output` | 0 | `accepted:true`, two worlds, 104 source-registered service jobs independently rederived |
| Completed `resume` again | 0 | Six examined signed financial files unchanged byte-for-byte |
| Tampered frozen-source `resume` | **1 (expected rejection)** | `FROZEN_SOURCE_OR_CONFIGURATION_CHANGED`; signed financial files unchanged |
| Restored original frozen source and reran `audit` | 0 | `accepted:true` |

This is a *fresh authored source-bound regression*, not evidence of cross-source signing-authority transition, new frontier profit or real commerce. Private native accounts, signers, original account paths and action tapes were **not published**.

## Full negative economic outcome, retained

Each arm accepted **one** synthetic job from **one** modeled buyer. Each collected 42,780,000 microUSD ($42.78), incurred 80,040,620 microUSD ($80.04062), and recognized **−37,260,620 microUSD (−$37.26062)**, with 42,980,000 microUSD native tail reserve, 142,980,000 microUSD equity protection backing, **zero unrestricted earned funds**, zero productive investment and zero profitable continuation. The two arms tied; adaptive did **not** beat the fixed baseline. Model registration's original high commercial minima were not achieved: `conditional_simulated_commercial_success:false`. Buyer demand is authored, not observed. Actual model/host/engineering campaign billing is unknown, not zero.

## Integration boundary / next decision

PR #35 documents original account recovery but a correctly failed >16 MiB signed transition v1; PR #40 adds owner-authenticated content-addressed v2 evidence and nonempty-queue continuation on an older dependent source. Its current-main semantic forward port remains **unqualified** and the original private signer/sole-writer checkpoint is unavailable. This witness isolates what must survive: a signed nonempty queue including a due settlement, later collection, tail liability, source/config guard, original authority, financially unchanged completed resume and independent audit. **Do not** soften the source guard, create a replacement operating ledger, substitute old runner/engine files for current released interfaces, or merge this evidence branch as a financial runtime.

Original historical failures, PR #35/#40 ownership, separate frozen 073/075 worlds and all earlier account evidence remain unchanged. Claimed actual collected commerce **$0**, trailing-365 complete-cost US$3B milestone **not achieved**, recursive-discovery gain **unqualified**. No spending, paid APIs, outreach, real transactions, new credentials or production deployment.

**Reproduction caveat:** The specified input reconstructs the published setup; canonical commands create new local ephemeral private signers. Their checkpoint and per-world artifact digests necessarily differ across independent new runs. An independent rerun is a *new engineering reproduction*, not replacement evidence or stronger profit confirmation.