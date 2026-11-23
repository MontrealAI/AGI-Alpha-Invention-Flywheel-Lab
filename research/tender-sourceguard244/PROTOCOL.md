# TENDER-SOURCEGUARD244 — frozen prospective engineering protocol

Date: 2026-11-23 UTC. Base: `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. This file was committed **before** implementation and test execution. Owner: independent source-only research; no native financial/account/source writes and no procurement response.

## Concrete problem and evidence

Real public solicitation: Fisheries and Oceans Canada RFP **30008508**, development of a Strategic Interpretation Framework for Artificial Intelligence Results, closing **23 Nov 2026 at 2:00 p.m. EST** according to the base RFP (5 Nov) and both Addendum 1 (13 Nov) and Addendum 2 (17 Nov). The three official documents are:

- RFP https://canadabuys.canada.ca/sites/default/files/webform/tender_notice/112395/30008508---rfp.pdf (page 1);
- Addendum 1 https://canadabuys.canada.ca/sites/default/files/webform/tender_notice/112395/30008508---addendum-1.pdf (page 1, A19);
- Addendum 2 https://canadabuys.canada.ca/sites/default/files/webform/tender_notice/112395/30008508---addendum---2.pdf (page 1, A47).

Independent web inspection of published PDF text and first pages supports that date/time; no PDF byte hashes were acquired, so this is **URL/page/quotation provenance, not cryptographically pinned bytes**. A competing third-party listing https://tendercomps.com/tender/cb-292-29950599 describes **Nov 23 14:00 UTC** (9 a.m. EST), whereas 2 p.m. EST is **19:00 UTC**. Source-time discrepancies matter to offerors, but third parties do not set the legal deadline. Addendum 2 further says internal/self-used projects cannot substantiate Offeror experience (A31), offers need eligible external project evidence (A46), and translation subcontracting requires separate prior written authorization (A36). Addendum 1 A9/A15 and Addendum 2 A39 disclose firm all-inclusive milestone-four support with no anticipated volume bound. No actual supplier eligibility, client references, support tail or pricing is established for MONTREAL.AI.

## Preregistered scope and stopping rule

Implement a **single read-only local Python standard-library instrument**, not a tender submission bot. Inputs are manually extracted, explicitly labeled provenance records; refuse unrecognised source roles, missing sequence members, contradictory authoritative dates, ambiguous/unrecognized timezone, unclosed source inventory, impossible date and solicitation ID disagreement. Distinguish `PROVISIONAL_CONSISTENT` from independently complete live inventory; `INDETERMINATE` whenever completeness is not established; `CONFLICT` when authoritative versions contradict. Never proclaim a government-certified legal conclusion. Emit canonical UTC only for a consistent authoritative schedule; label third-party discrepancy separately. Unknown public amendments after 17 Nov invalidate freshness until rechecked.

Freeze these tests *before code*: real registered official sequence 0/1/2 with consistent EST and a conflicting 14:00 UTC aggregator; 2+ negative controls for missing/duplicate official sequence, conflicting official amendment, ambiguous ET, DST discrepancy, evidence identity tamper, absent inventory closure, and unqualified bid. No seed searches, no invented bid/no-bid probabilities. A qualified UTC conversion is necessary but not sufficient for bid eligibility or profitable business.

A practical internal decision may be `HOLD_NO_BID` when eligibility/cost/rights are unknown, never `ELIGIBLE` by default. Contract obligations, submissions and outreach are out of scope. Any genuine proposed bid requires formal business/legal review and action-specific approval.

## Strong complete alternatives and commercial possibilities (no assumptions of wins)

1. **Strong ordinary:** manually check base and all amendments directly on CanadaBuys using competent procurement staff and calendar conversion; fastest/easiest for one tender, cost unknown.
2. **Procurement monitoring platforms:** incumbent discovery/alert products, which may offer similar functions and should not be crippled. In this recorded case one third-party listing supplies an inconsistent UTC instant, not a general indictment of that or other vendors.
3. **Complementary verification component:** a reusable source-binding and conflict instrument added to existing procurement workflows; any customer willingness, licensing, rights, distribution and support cost unknown.
4. **No deploy/no bid:** zero newly assumed buyer revenue and no contractual liabilities, valid default when prerequisites absent.

**Decision gate:** Produce a reproducible **internal source conflict witness** and regression, not a commercial adoption claim. No full customer outcome, buyer data, actual sale, earnings, superiority to manual/human/AI competitors, scale or $3B profit can follow from this instrument. Stop this finite experiment after executing the registered unit/control tests and exact source provenance review; preserve every failure.

## Ownership, security and costs

Additive `tools/tender_sourceguard244.py`, `tests/test_tender_sourceguard244.py`, read-only workflow, compact evidence. Touch no canonical `Account`/`JournalAccount`, `connected_enterprise`, financial signing/keys, owner PR40, main, released asset or paid API. One source and one account remain authoritative. No new spend, outreach, tender email, contract, bid, production deployment or persistent credentials. Actual host resource/billing unmeasured. Historic Connected014 source/release and all failed tests remain immutable.
