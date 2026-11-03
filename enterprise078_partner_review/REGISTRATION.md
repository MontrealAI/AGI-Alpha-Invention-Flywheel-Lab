# Partner incentive and seller-payment audit — frozen registration, 2026-11-03

Base: PR179 exact `68cb47eba6070fb34c83e2a7019ceb01417a1551`, independent of owner PR174, financial owner PR176/180 and PR178.
Pinned buyer/partner comparator blobs: `choice.py ceff4afbfc4c680ade86f9fc536d99e4a64f730a`, `planning.py 537bb71dae621962f6787c16d69d51a8f12c7f46`. Verify them, fail closed on source drift. Keep source, accounts, finance, failed workflows and existing tests unchanged.

## Predeclared question

The prospective conditional planner currently treats an exact-quote partner `consent=True` as adequate participation evidence. That does not independently establish the partner's own payoff or that seller expenses include the proposed partner transfer. Test whether a seller-positive buyer-consented bundle can still be unsustainable under an explicitly stated partner outside option and own cost. This is an *authored counterexample* only, not evidence of any actual supplier's choices or contracts.

Review existing prospective planner output without writing source or native finance. For every partner in every registered full bundle and every registered predecision scenario, require an exact complete-partner-package receipt with integer microUSD compensation, own cost (including risk/friction), outside payoff, disclosed seller-cost category and exact original quote. A positive residual after own cost and outside option is necessary for strict voluntary preference; tie or negative residual refuses. The seller's matching complete package cost category must cover the sum of disclosed partner transfers for that category; missing/unknown economics refuses. Terms, package, buyer consent and budget must still pass the unchanged planner. Do not transform partner receipts into observed agreement, predecision payoffs into postdecision realizations or suggested payments into available capital. Do not alter historical source pins or six failed financial reviews.

## Fixed adversarial controls

1. The unchanged planner may conditionally accept an exact-quote consented partner while a partner-payoff review rejects its *negative* partner residual.
2. Explicit partner-positive residual with full seller cost provision can be conditionally retained without manufacturing money, execution or market demand.
3. A transfer exceeding its declared seller expense category fails even when buyer surplus and partner surplus are favorable.
4. An absent, `None`, malformed, boolean or changed quote/terms/package receipt fails closed, not zero-filled.
5. Every registered scenario must satisfy participation; a favorable case cannot erase a refused/adverse partner case.
6. Two partners paid from one cost category are charged together, not each against the same expense twice.
7. A no-partner bundle remains subject to the unchanged whole-buyer plan; no-entry remains eligible and wins ties.
8. Pin source bytes, refuse drift, retain all negative results; emit only a key-free review result and no native mutation.

Test exact source in ordinary public GitHub-hosted CPU workflow, platform 360 minutes, standard early execution marker; no paid APIs, customers, outreach, keys, real-world actuation, private data, merge or release. Source-bound engineering evidence is not actual commerce, partner agreement, Nash/Stackelberg equilibrium, native catalog admission or US$3B trailing profit.
