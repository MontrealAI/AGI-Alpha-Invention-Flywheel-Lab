# Make learning investable before committing to capability expansion

**Transformational intelligence: learn which new capability is worth constructing, choose the subsequent operating action, and anticipate how competitors react to that same information.**

This is a subordinate, opt-in addition to `portfolio_scale/`, not another enterprise runtime, financial ledger or success gate. The canonical `connected_enterprise`/Account path, current integration PR #28 and original operating evidence remain unchanged. Parent inspected: `c5eba47e8d1618847cb0235c5fac980d92a40816`.

## The concrete gap closed

The existing `transformational.choose` optimizes a finite set of supplied returns and synergies. It does not choose a paid observation and then condition its investment on the observation. The new `staged_coupling.choose` can compare:

- commit immediately to a complete commerce, capability or joint portfolio;
- pay for one bounded probe, observe its public signal, then commit or retain cash;
- a fair nonadaptive control that may buy the same probe but must choose the same follow-up portfolio for every signal;
- retain liquidity with zero expenditure and zero invented return.

The rival sees the chosen portfolio and any public probe result. Its response is reoptimized using the same posterior information set, **not the secretly realized state**. A favorable test can make imitation more attractive and reduce how much of the invention's benefit we capture. Costly or slow information can make immediate ordinary delivery preferable.

A project with unmodeled payoffs is retained as unresolved, not valued at zero or infinity. Quantitative probe selection requires explicit outcome/likelihood hypotheses; the code cannot make absent evidence appear. Those hypotheses must ultimately be supplied by actual independently checked service and instrument evidence, or remain conditional scenarios.

## Precisely specified strategic game

The scope is a single optional **public** probe followed by one pure portfolio commitment, one rival best response, and terminal cash. Both players share the declared prior and public signal; neither sees the latent state. The rival observes the realized portfolio before acting. This is a small sequential Stackelberg decision, not simultaneous-price Nash equilibrium, confidential R&D, coalition bargaining, repeated-game cooperation, or an unrestricted multi-period enterprise solution.

Every finite pure policy in that timing model is covered by backward induction: compute posterior -> all feasible follow-up portfolios -> rival's expected payoff maximizers -> pessimistic tie resolution -> best follow-up -> expected value before the probe. Linearity means randomization over *observed* realized portfolios adds no value in this restricted timing. A commitment to a mixture that the rival must answer **before** its realization is a different game and is not certified here.

The objective is expected discounted net incremental cash. No capability-score, forecast-revenue or information-value bonus is added separately. Instrument value appears only in the corresponding complete portfolio outcomes. Probability, rival payoff and demand authenticity are not established by valid input syntax. An exact solution to an incorrect market model remains an incorrect business recommendation.

### Cash and risk semantics

All quantities are integer simulated microUSD. The initial planning envelope is the minimum of supplied `available`, `unrestrictedEarned` and `authorized_allocation`. This prevents an inconsistent *supplied* capital field from expanding the envelope; it does not authenticate any of those fields.

Portfolio `cost` is the initial nominal cash expenditure. `net_receipts` is a signed horizon-end cash increment after **all later** modeled collections, expenses, refunds and obligations, excluding that initial expenditure. Negative net cash is supported. `future_cash_required` is a supplied conservative bound on additional cash needed before those receipts arrive; it must cover any negative terminal increment. Initial cost plus this reserve must fit the remaining envelope under **every** listed rival response and state in posterior support, not just the predicted best response. A separate worst-loss bound covers probe plus follow-up cost and every listed outcome. These conservative controls are declared for this instrument, not universal mandatory business policies.

Probe cost is paid first and reduces every follow-up budget. Its `discount_bps` explicitly discounts the follow-up net payoff for delay; the reserve and loss constraints remain undiscounted. Receipts cannot prefinance the probe, and an impossible signal cannot create a path to spend. A complete event-time working-capital path would require the canonical native ledger; this summary envelope does not reproduce that path.

When rival responses tie in its expected value, the solver uses the response with the lowest seller value. This removes optimistic equilibrium selection. Net cash and rival values are exact rational arithmetic, with no float rounding in posterior or policy comparisons.

## What actually ran

Twenty-seven new focused tests pass. They include **80 generated small games checked against a separate exhaustive enumerator of complete signal-contingent policies**. The enumerator does not call production backward-induction helpers. It is separate code in the same author/session/host, not external certification. Other tests cover censorship/hidden-state inputs, no mandatory invention, imitation, future obligations, expensive or uninformative probes, unaffordable follow-up, adverse rival ties, unknown funds and exclusive outputs.

The example is deliberately an authored engineering fixture, not a business experiment. It assumes a 50/50 useful/non-useful instrument, a hypothetical 90%-informative public test, and 100 units of available earned funding. No native account was opened and no experimental observation or actual cash was generated.

| Declared model | Selected route | Expected net value, SIM units |
| --- | --- | ---: |
| Best nonadaptive policy in the base model | Build the combined portfolio immediately | 50.00 |
| Public test plus observation-contingent choice and responding rival | Pay 5; build if favorable; repeat delivery otherwise | 65.50 |
| Incorrectly remove the rival's imitation option | Test then choose | 79.00 |
| Make the test cost 30 | Build immediately; skip test | 50.00 |
| Discount the delayed follow-up by 50% | Build immediately; skip test | 50.00 |
| Easy, profitable imitation compresses the prospective benefit | Repeat ordinary delivery; no test/invention | 30.00 |
| No available earned allocation | Retain liquidity | 0.00 |

The **15.50 modeled difference** is the exact value of the best conditional plan over the best nonadaptive alternative in this supplied example. It is not measured enterprise profit, proof of a capability-compounding flywheel, a population-level inference or support for these exact model parameters.

For the base model, the favorable signal raises the useful-state posterior to 0.9. The rival then chooses imitation. The chosen portfolio's conditional net value is111. The unfavorable signal selects ordinary delivery worth30. Thus `-5 + 0.5*111 + 0.5*30 = 65.5`. Ignoring the rival's response would incorrectly yield79. Neither figure is spent, booked or claimed as an observed return.

## Reproduce

From the repository root:

```sh
python3 -m unittest discover -s tests -p test_staged_coupling.py -v
python3 -m portfolio_scale.staged_coupling \
  --input campaign/staged-coupling-017/EXAMPLE.json \
  --output /tmp/staged-choice-NEW.json
python3 campaign/staged-coupling-017/reproduce.py --output /tmp/staged-comparison-NEW.json
```

Only the existing exact `portfolio_scale/transformational.py` utilities are reused. The file's Git blob `465e752db419b5077314b91136e2b4e8e8784226` was verified against the current parent before local tests. Local source recovery came from an existing source-matched package after one public raw-file DNS attempt failed. No complete fresh GitHub checkout, full-repository installation, current-head hosted CI or market qualification is claimed.

The root test file is discoverable by ordinary unittest discovery; existing workflows and source freezes are untouched. A separate clean package replay verifies the bundled code and values. Historical operating tests, demand, capital and results are not re-labeled as evidence for this new module.

## Integration without a parallel financial authority

This solver returns a conditional recommendation, not an executable authorization. Outputs always state `execution_authorized: false` and `funding_authenticated: false`.

The next owner integration should supply a public observation/evidence record derived from the canonical account and approved capabilities, then create a source/current-state bound request. Reserve only the chosen **current** step through the existing native Account. Charge actual probe resources, independently validate its observation, and re-evaluate with a fresh state. Conditional future budgets are not present reserves or promises. Never silently route a negative-direct-cash research step through a delivery gate that requires positive returns; it needs its own explicitly authorized experiment allocation. No presumed probability, payoff or local Boolean flag supplies that authority.

When enough native service and instrument evidence exists, test commerce-only, capability-only, joint and fixed-split controls under equal resources and stronger buy/reuse alternatives. Mere gain in this example cannot substitute for the causal chain of actual earnings -> funded construction -> verified reusable tool -> better fresh work -> reconciled economic contribution. Private signals, irreversible commitments, rival learning, multiple rivals and further stages require explicit extensions and fresh checks, not broader interpretation of this certificate.

Keep ordinary profitable operation independent of invention. Keep scientific/capability measurements distinct from money. No artificial revenue ceiling is introduced. The purpose is more selective, better-timed investment—not forcing every business to conduct research.

## Research basis and boundaries

Value-directed information collection: Frazier, Powell and Dayanik, *A Knowledge-Gradient Policy for Sequential Information Collection*, DOI10.1137/070693424, https://doi.org/10.1137/070693424 . Dynamic rival investment: Ericson and Pakes, *Markov-Perfect Industry Dynamics*, https://academic.oup.com/restud/article-abstract/62/1/53/1568000 . These motivate questions, not an optimality theorem for this repository.

This contribution executes no service, protected campaign, paid frontier inference, customer contact, real transaction, reserve release, deployment or automatic merge. It changes no default commercial runtime and asserts no new commercial or physical achievement. The inherited integration/release resource failure is neither reopened nor erased.
