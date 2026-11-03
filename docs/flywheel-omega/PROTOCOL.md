# FLYWHEEL OMEGA exact analytical companion

## Status and purpose

This specification is written before executing this companion. It describes an **authored analytical finite verification**, not an empirical market experiment, an untouched holdout, an autonomous discovery evaluation, or a preregistration claim. The source prices in the historical witness are public facts at a pinned revision; all other values, costs, responses, and payment schedules are stipulated examples. Prior engineering accounts and their original single-purchase interpretation remain unchanged.

The calculations ask how the productive composition of accepted services changes available prices, voluntary buyer choices, and the cash needed to carry out a successor-producing arrangement. No account, currency transfer, remote service, customer contact, or operating ledger is created. The program uses only the Python standard library and exact integers/rational numbers.

## Productive and strategic semantics

A service is identified by a bit in a finite set. An accepted outcome is the union of its service bits. The explicitly declared outcome family must contain the empty outcome and be closed under union. Service identities denote the **same accepted output with the same rights** in each offer. Composition is explicitly authorized; services are delivered at most once; prices are nonnegative; and one composed purchase charges the sum of its offer prices. There are no omitted identity, capacity, switching, royalty, processing, or compatibility effects within this model. These are applicability conditions, not facts about arbitrary services.

A cart can contain every posted offer at most once without loss of a cheaper solution: repeating an offer adds no service, and its price is nonnegative. The exact cart oracle enumerates every subset of the posted offers. The independent dynamic program traverses the union-state graph. Missing union semantics, unauthorized composition, negative/inexact prices, or incomplete buyer valuations are rejected.

Buyer utility is the value of the delivered union minus payment and the declared outside utility. Hard budgets are enforced. A buyer declines at utility zero. Positive-utility ties are resolved against seller contribution, then lower payment, then the numerical outcome identity. Production cost depends only on the delivered union. The proof domain includes this tie convention. General collusion, resale, additional identities, stochastic private information, and dynamic strategic behavior beyond the stated staged example are outside it.

## Registered finite calculations and bounds

1. **Composition semantics:** all 2,187 complete three-service menus, with each of seven nonempty-outcome prices in `{1,2,3}`. For each menu, compare union-state dynamic programming with all 128 carts, check contractiveness, subadditivity, idempotence, and single-coordinate monotonicity. Check cart/closed-menu buyer equivalence for 27 additive valuations (three item weights independently in `{0,1,2}`) and seven budgets `0..6`: 413,343 buyer/budget/menu cases, with all outcomes including non-entry. These counts bound this exact calculation; they are not business-scale limits or a dollar cost.
2. **Pinned historical arithmetic:** offers `A=518`, `B=823`, `AB=1554` cents at public source `8cd375784c24b879ae1eb4835c6af4fb925cbf4c`; the equivalent two-component cart costs 1,341 cents, a 213-cent difference. This is a static public arithmetic witness, not a new native-account replay.
3. **Finite menu design:** all 4,096 two-service menus, each offer independently absent or at an integer price `0..14`. One authored buyer has values `A=7`, `B=7`, `AB=14`, outside utility zero, and budget 14 abstract units. Compare single-purchase and cart-capable choice. An independent exhaustive-cart optimizer receives the identical menu domain. Report all aggregate wins, losses, ties, non-entry outcomes, and optimal objective values. Optimality applies only to this finite domain, information, and tie convention.
4. **Productive arrangement:** compare four supplied route families at opening cash 6 and, as a stronger-capital contrast, 9 abstract units. Final-only routes enumerate 15 prices `0..14`; staged routes enumerate 225 component-price pairs. Staged buyers can decline each separately accepted, independently useful output. Stage prices below 7 are individually worthwhile, subject to the aggregate hard budget. No borrowing, deposits, or payment before acceptance is assumed. Include non-entry at zero.
5. **Inheritance:** compare a new second use of an already accepted connector with rebuilding the same connector and with ordinary reuse of the same artifact, holding the staged menu and schedule fixed for this ablation. Current-episode and complete two-episode costs must both be shown. A same-artifact tie is retained; no improved invention procedure is inferred. Also preserve the stronger adaptive continuation: after the first episode leaves cash nine, a retained connector can deliver both outputs for seven before collecting a pure-bundle price thirteen, earning six instead of the fixed staged route's five. Ordinary same-artifact construction can take that route too. The fixed ablation is not an optimal two-episode sequence.

All options are authored. Enumeration discovers their best use within the registered set; it does not discover unknown productive laws, real willingness to pay, or a new scientific instrument. The conventional constructor receives the same routes and choices.

## Exact staged witness

The public menu is `A=6`, `B=6`, `AB=13` **abstract units**. Its effective joint cart price is 12. Both separate stages have standalone buyer value 7 and can be declined independently. The quote 13 is not assumed to be collected. In the single-purchase model all three quoted choices have utility one, so pessimistic ties select a component for six; the cart has strictly greater utility two.

The complete declared process cost is nine in each route, paid at these times:

| Route | Cash obligations and accepted receipts at the reference prices | Minimum opening cash |
| --- | --- | ---: |
| Ordinary monolithic | Pay 9; collect actual cart receipt 12 after completion | 9 |
| Staging alone | Pay 7; collect 6; pay 2; collect 6 | 7 |
| Connector alone | Pay 2; pay 3; pay 4; collect 12 after completion | 9 |
| Connector and staging | Pay 2; pay 3; collect 6; pay 4; collect 6 | 5 |

At opening cash six only the joint route can finish. Its arithmetic cash path is `6,4,1,7,3,9` and surplus is three. The fixed connector construction cost two, first-stage cost three, and second-stage cost four are inclusive authored process envelopes, including their specified construction/acceptance work. They are **not measured development, discovery, model, host, or complete real-world lifecycle bills**. Logical enumeration work is reported separately, never translated into dollars.

A common additional lifecycle burden `h>=0`, if due before work, raises each required capital by `h` and reduces the joint surplus to `3-h`. At opening cash six the joint route is feasible exactly when `h<=1`; its standalone surplus is positive exactly when `h<3`. Numerical checks include `h` in `{0,1/2,1,3/2,3}`. The reference `h=0` is a stipulated boundary, not evidence that unknown costs are zero. A protected reserve is separately a liquidity restriction, not silently another cost or usable cash.

The stronger finite conventional alternative is retained: with opening cash nine, a final-only pure bundle at thirteen is individually worthwhile (buyer value fourteen), yields surplus four, and beats the twelve-receipt staged route in this tiny model. Thus the reference result is conditional enablement at six, not globally optimal capital or universal superiority of staging.

A projected ending cash of ten based on collecting the joint quote thirteen would incorrectly admit an upfront successor requirement of ten. Actual receipts twelve leave nine. This is a cash-eligibility illustration, not an instruction to spend the opening capital or a claim that all nine are earned profit.

## Output and preservation

`companion.py --output PATH` requires a new output file and refuses replacement. `results.json` records the exact finite results, model scope, public source link, and formulas as text. It excludes measured timing, machine-specific information, private inputs, and generated account authority, so the content is deterministic. `test_companion.py` checks meaningful semantic and funding boundaries and independent oracle agreement. Prior papers, source documents, campaigns, and balances are not changed.
