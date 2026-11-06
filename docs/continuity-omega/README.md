# CONTINUITY Ω — Keep the promise, prove the recovery

**The real product:** a business-continuity rehearsal that shows whether a defined customer promise can still be honored when normal IT is unavailable, and tests the missing means that could make an alternative fulfillment arrangement economically workable.

**This released prototype:** an entirely offline, source-bound **SYNTHETIC** order-handoff drill. It is not a production security product, not a penetration test, not a functioning multi-supplier reservation system, and not a certification. Its arithmetic is exact within declared inputs, while its supplier permissions, source history and demand are authored. It does not touch real customer data, infrastructure, contracts, or money.

## Who buys it?

Initial buyer hypothesis: **operations director of a 5–50-person regional B2B packaging-label printing company without a second production site**. A realistic paid pilot would involve one selected product, one real customer obligation, one backup producer, one approved isolated exercise, and their actual contractual and technical evidence. The owner/GM approves a purchase; the operations director owns acceptance. No such buyer has yet been recruited or agreed to pay.

## What is the missing move?

The obvious first test asks: *Does the restored application start?* The stronger test asks: **What customer commitments did the restoration miss?** The next change is structural: *Why must the original business's systems be fully restored before an already accepted order can be fulfilled?*

The prototype constructs a portable fallback handoff from a separately sealed pre-disruption event history, not from the potentially incomplete restored snapshot. Its independent code checker reconstructs the obligations again, checks supplier availability and cost consistency, and rejects falsified output.

## Run in one minute (Python 3.10+; no packages, network or API keys)

At repository root:

```bash
python3 -m continuity_omega demo --case nominal --out /tmp/continuity-omega-demo-001
python3 -m continuity_omega verify --in-dir /tmp/continuity-omega-demo-001
python3 -m unittest discover -s tests -p 'test_continuity_omega.py' -v
```

Use a **new** output directory; the CLI refuses to overwrite prior evidence.

Files created:

- `INPUT.json` — synthetic exercise assumptions and the separately recorded source-event digest.
- `HANDOFF.json` — currently outstanding commitments, requirements, provenance, capacity check, modeled completion window, and idempotency binding.
- `PASSPORT.json` — restoration discrepancies, model economics, explicit evidence boundaries, and successor hypothesis.
- `AUDIT.json` — separately implemented exact replay; `PASS_SYNTHETIC_ONLY` or `FAIL`.
- `PASSPORT.md` — readable Continuity Passport.

For safe negative controls, create a new directory and replace `nominal` with `tampered_source`, `overbooked`, `correlated_outage`, `unqualified`, `late`, `buyer_declines`, `uneconomic`, `unapproved_sharing`, or `no_order_source`. These cases return code 2 and produce `REJECTION.json` rather than an authorized handoff. `missing_from_restored` and `extra_restored` show how protected source evidence can expose a defective restoration while still enabling a separate proposed handoff. A mismatch in a restored database is **not** evidence that that database was safely recovered.

## Demonstration output (invented data and money)

The authored source accepts 1,000 units of `LBL-100`, 800 of `LBL-200`, and 600 of `LBL-300`. Later it amends the first to 1,100 units and cancels the third. **Outstanding: 1,900 units in two orders.** The restored snapshot still shows an outdated 1,000-unit `LBL-100`, entirely misses `LBL-200`, and incorrectly retains the canceled order.

A simulated printer has 3,200 units of capacity but 1,100 already reserved, leaving 2,100 under a conservative overlapping-interval rule; a competing supplier has 1,800 and is insufficient. The handoff chooses the capable simulated printer, whose quoted lead time is 22 hours against a frozen 48-hour limit. The modeled complete cost is USD 5,050, proposed price USD 5,700, hypothetical buyer budget USD 5,800 and modeled contribution USD 650. **No purchase, acceptance, capacity reservation, real delivery, or revenue has occurred.**

The independently reimplemented checker challenges all fields with a fresh source replay rather than calling the producer. It cannot independently establish the origin of the source, actual supplier truth, entitlement, legal rights, physical output, or buyer acceptance. Its "independence" is **separate code paths under shared research authorship**, never external certification.

## Limits that matter

- The event digest must be kept outside the damaged environment and authenticated by a real custody process. A SHA-256 digest in the same editable JSON file is **not** an authenticity guarantee. An attacker who can change both contents and digest can forge this synthetic evidence.
- A real incident may affect orders after the last protected source checkpoint. RPO, manual-work reconciliation and uncertainty must be explicitly addressed; absent records must **never** be fabricated from an AI guess.
- Provider availability, booking, terms, shared-failure domains and financing are synthetic declarations. A Boolean flag is not a signed supplier agreement or an atomic reservation against other customers.
- Quote arithmetic does not establish full actual lifecycle costs, post-failure remedies, employer obligations, insurance, collection or tax; legal terms and authorized rights require review.
- No vulnerability scanning, unsafe exploit tests, destructive simulations, supplier communications, production data access, payments or security setting changes occur.
- A competent conventional procedure with the same complete information and tools is a strong comparator. This prototype makes **no new-algorithm, unique advantage, measured cyber resilience or commercial success claim**.

## Prior work and integration boundary

The existing `campaign/genesis_commitment001` in this repository already includes a synthetic application recovery, native `JournalAccount`-backed resource commitments and simulated commercial accounting. Its central case lost USD 1,080 because the buyer chose not to purchase. This **new, isolated order handoff** addresses a different missing means; it does not duplicate or replace the canonical financial ledger, override its reservations, change that history, or relabel the earlier loss as success. A future customer integration must reuse the existing native cash and obligation authority, with actual provider evidence and genuinely accepted delivery.

## External foundations (precedents, not endorsements)

- NIST SP 800-184, *Guide for Cybersecurity Event Recovery* (2016): recovery planning, realistic tests and improvement. <https://csrc.nist.gov/pubs/sp/800/184/final>
- NIST SP 800-34 Rev. 1, *Contingency Planning Guide for Federal Information Systems* (2010): business impact, alternate processing, recovery priorities and exercised plans. <https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final>

Neither standard certifies this product. Existing managed recovery, backup-restore tests, and conventional capacity scheduling are strong alternatives, not fictional weak baselines.

## What makes the next invention possible?

A successfully tested, legally reusable handoff representation could support another product family or an independent manufacturer. The next campaign must **freeze fresh acceptance criteria first**, build the new adapter, verify it, include full acquisition/transfer costs, and compare against a competent team using the same source, tools and permissions. Success on a later task alone is not evidence that the earlier retained method caused it.

**Research state:** local executable synthetic prototype. **Market state:** not established. **Independent third-party assurance:** not established. **Authorized next action:** recruit one willing customer/backup provider for an explicitly permissioned, non-destructive drill; never activate an external action from these synthetic flags.
