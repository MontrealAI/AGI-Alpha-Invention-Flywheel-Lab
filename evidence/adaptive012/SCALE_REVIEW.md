# Adaptive-012 scale review

The frozen conditional projection supports profitable growth under its authored operating assumptions. It does not establish actual revenue, an empirical growth forecast or native earned funds. Both ordinary and full adaptive controls can purchase the same expansion actions; the fixed-share control is an intentionally restricted historical policy baseline.

Source commit: `cff284ffdbd930f63c2dd182870aa9f952672624`. Freeze: `28e752b69a17ed2a4763f3bf794c4d0507ff6a027b11d84fc1cddfafeb16a66a`. Source digest: `805a6e047ec655b161ca1d0e76e4c479af7134b3f3d0a060c9de31f21dc19dcc`. Scale source SHA-256: `6c780203f8613a19025fcf095227a212a3975e9c19e611fcb0f0af3318e63dea`.

The base design contains eight fresh seeds `2610302301`–`2610302308` and 120 months per trajectory. Each of the six preregistered sensitivity cases uses the first two of these seeds, matched across all three controllers. All outcomes, including early failures and nonreach, are retained.

## Base outcomes

All monetary ranges below are USD within the projection, including every trajectory. Collected revenue is net of projected refunds; profit includes projected complete costs. These are cumulative 120-month results, distinct from annual revenue.

| Controller | Cash survival | $1B trailing-year milestone | Cumulative collected revenue | Cumulative profit |
| --- | ---: | --- | --- | --- |
| adaptive | 8/8 | 8/8; month 22–23 | $19,338,954,043.95 to $19,463,927,175.15 | $16,511,791,456.49 to $16,622,276,577.91 |
| fixed_shares | 8/8 | 0/8; not reached | $168,739,790.52 to $189,779,038.39 | $144,804,976.21 to $162,778,019.98 |
| ordinary_adaptive | 8/8 | 8/8; month 27–33 | $18,182,552,603.79 to $18,475,900,898.42 | $15,564,181,733.05 to $15,813,648,119.79 |

| Controller | $10B trailing year | $100B trailing year | $1T trailing year |
| --- | --- | --- | --- |
| adaptive | 0/8; not reached | 0/8; not reached | 0/8; not reached |
| fixed_shares | 0/8; not reached | 0/8; not reached | 0/8; not reached |
| ordinary_adaptive | 0/8; not reached | 0/8; not reached | 0/8; not reached |

Full adaptive minus ordinary adaptive cumulative profit ranges from $804,960,688.43 to $1,006,141,908.36; full adaptive is higher in 8/8 paired base trajectories. These finite-policy comparisons do not prove a market optimum or general learning superiority.

## Registered sensitivities

The sensitivity cases are individual changes, not a calibrated joint distribution. Their two-seed counts do not estimate real-market probabilities.

| Case | Full adaptive $1B | Ordinary adaptive $1B | Full / ordinary cash survival | Full adaptive cumulative profit |
| --- | --- | --- | --- | --- |
| channel_cost2 | 2/2; month 25 | 2/2; month 31–36 | 2/2 / 2/2 | $16,483,291,158.07 to $16,512,607,850.66 |
| channel_delay3 | 2/2; month 27 | 2/2; month 29–34 | 2/2 / 2/2 | $16,320,790,374.95 to $16,330,617,558.78 |
| conversion_half | 2/2; month 26–27 | 2/2; month 30–31 | 2/2 / 2/2 | $8,148,443,157.65 to $8,153,565,944.05 |
| demand_half | 2/2; month 24 | 2/2; month 27–29 | 2/2 / 2/2 | $8,195,348,646.05 to $8,217,117,064.04 |
| buffer0 | 0/2; not reached | 1/2; month 33 | 0/2 / 1/2 | -$252,610.80 to -$248,109.51 |
| buffer4 | 2/2; month 26 | 2/2; month 31–37 | 2/2 / 2/2 | $16,360,944,217.31 to $16,371,942,653.73 |

## What the comparison identifies

Ordinary and full adaptive use the same paid channel-entry, capacity, retention, supplier-diversity, instrument and service-entry candidates, the same public observations, physical delays, starting resources, prudential buffer and eight-round planning budget. Ordinary ranks public predicted value per upfront cost; full adaptive ranks predicted joint net value. Planning is charged at $0.25 per executed round for both, an authored cost envelope rather than measured provider billing. Purchased monthly channel exposures cannot be bought twice. Both use the same keyed demand, quality, payment and supplier shocks; different customer counts produce count-conditional aggregate outcomes.

Most expansion relative to fixed shares therefore tests removal of controller-created restrictions and costed access to new actions. The full-versus-ordinary comparison is narrower: it tests the selected ranking policies under these assumptions. Neither establishes superior invention, broad opponent learning, empirical demand or universal scalability. A controller missing a milestone is not evidence that every feasible controller fails.

Hard cash conservation and restricted obligations are distinct from the revisable prudential buffer for future uncommitted work. The `buffer0` and `buffer4` cases test that policy. The earlier exposed controller-insolvency probe is preserved separately; its results are not reclassified as fresh confirmation.

## Assumptions and remaining constraints

The projection starts with a hypothetical **$250,000** scale allocation, 20 initial customers and 200 monthly production slots. This is separate from the native small-cohort seed and earned balance; the small-cohort anchor is `null`. Base inputs include $400 per work product, $40 attempt resource cost, 98% technical acceptance and collection assumptions, 2.5% monthly churn before retention investment, and 2,000,000 reachable unique opportunities. A paid channel costs $5,000 to enter and supplies at most 120 monthly exposures after its delay; exposures/qualification cost $5 each. A 100-job capacity block costs $5,000 and becomes available after one month. These values and intervention effects are authored hypotheses, not measured customer demand or a demonstrated scale business.

The finite reachable opportunity pool, supplier capacity, conversion, retention, acquisition friction and work-product economics remain binding assumptions. Supplier diversity adds one modeled fallback, not unlimited supplier expansion. No $100B or $1T conclusion should be generalized beyond that action space and the 120-month horizon. Higher targets remain configurable; their nonreach here is not a hard-coded revenue ceiling. The six ranges do not exhaust joint adverse conditions, structural model error, legal/geographic permissions or long-run competition. Forecast technical-success draws are not actual service acceptance receipts.

## Arithmetic and integrity checks

A separate arithmetic pass read serialized outputs without importing `evaluate_scale` and checked **60 trajectories / 6,897 completed monthly rows**. It verified frozen source hashes; exact registered seed/config coverage; current-cash conservation; restricted cash; recurring profit identities; per-round planning costs; paid channel/capacity/contact costs; action cash deltas; production capacity; finite exposure counts; matched-controller arithmetic; and every first milestone crossing from rolling 12-month collected revenue. Annualized current-month run rate was checked separately and never used to qualify a milestone.

Early-failure terminal payables and partial months are kept distinct from completed monthly rows. A separate team checker independently confirmed zero errors across the same 60 trajectories, 6,897 monthly rows and 15,550 paid actions, including customer conservation and supplier/outage capacity checks, without evaluator imports or file edits. The component author also performed the arithmetic pass above; shared model family and host do not constitute external certification. Forecast receipts never enter or authorize spending from the native Account.

Output SHA-256: `SCALE.json` `5aff7e1def8153c306a9af4ffb60063a025b8311c28ca86538b58739d77727b6`; `SCALE_SENSITIVITIES.json` `df7c91f1cada1142dd408af602191c1d97707eb73c68fe4fde49db9f3cd0a7fe`.
