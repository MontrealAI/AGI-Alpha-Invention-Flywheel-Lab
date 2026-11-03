# Post-confirmation independent review

## Frozen experiment

The executable comparison was frozen at commit `85c8a3e98f31bac9d3867a022aaa758623335083`, with freeze digest `80aec9bd90d6416e531fef3b5d2c49bc3dd62bf48359f350568631c762ad9bb5`, before confirmation outcomes. This note is subsequent analysis and does not modify the frozen method, generator, trial set or acceptance conditions.

## Technical result inspected

The single registered comparison contains 48 paired K2 worlds, six authored mechanism-composition families and four declared fault schedules per world. All 96 constructed programs were valid, and both methods were safe across all 48 worlds. Neither caused a harmful scored outcome. Safe refusal is recorded separately from delivery.

| Fixed technical outcome | Retained constructor | Ordinary constructor |
| --- | ---: | ---: |
| Complete delivered schedules | 56 / 192 | 60 / 192 |
| Safe abort schedules | 136 / 192 | 132 / 192 |
| Worlds with at least one accepted delivery | 20 / 48 | 20 / 48 |
| Total modeled probe cost | $759.60 | $669.75 |
| Total modeled operation cost, all challenges | $92.80 | $116.70 |
| Harmful schedules | 0 | 0 |

The equal count of 20 worlds with some accepted delivery does **not** mean equivalent delivered outcomes. The ordinary constructor completes four additional fault-schedule deliveries while spending less on acquisition. At the preregistered $600 conditional value per complete delivery, the retained-minus-ordinary primary effect is **−$14.2473958 per K2 request**. The descriptive family-resampling interval is **[−$40.7989583, $0.3828125]**, below the declared +$3 material-effect condition. A retained-method advantage is not established.

There are no exact world duplicates or permutation-normalized mechanism duplicates in this registered set and no normalized K1/K2 overlap. The experiments still share one authored simulator and reuse some provider primitives; these facts do not imply independent real-world provider samples or externally blinded evaluation.

## Why the difference occurred

Read-only inspection identifies two worlds with different completion counts: index 9 (`cc3236c9067baa70`) and index 11 (`d8b79279d5737554`). In each, the treatment delivers only in the healthy schedule and aborts under lost request, lost acknowledgement and refusal. Its probe spending is $23 and $22. After expensive discrimination, its constructed fallback compensates on uncertainty and stops.

The ordinary method spends $15 and $9.60 respectively. It constructs compensation-before-retry, completing the healthy, lost-request and lost-acknowledgement schedules, while still aborting cleanly on provider refusal. This is an established corrective construction removing a need for further state discrimination. It is not a newly invented transaction mechanism.

The resulting operating decision is to retain the ordinary method for this finite simulated support domain. The failed advantage claim remains preserved. Adding compensation-before-retry to the frozen treatment after observing these cases and rescoring them would be development on exposed evidence, not fresh confirmation; no such change is made here.

## Fixed-row value sensitivity

Let q be a hypothetical nonnegative dollar value for each of the same accepted schedule deliveries. Holding the executed rows, methods and declared probe/operation costs fixed, the treatment-minus-ordinary mean contribution is:

`(-4 * q - 335.50) / 192 USD per request`.

The $335.50 is four times the treatment's extra probe cost minus its operation-cost saving. Consequently, merely changing the $600 reference value cannot make the aggregate treatment advantage positive for any q ≥ 0 on these same fixed rows. This is posthoc arithmetic, not a second experiment, a revised primary endpoint, evidence of demand at other prices, or dominance over untested providers. Buyer choice, competition and actual business operation may change when prices change.

## Native completion and replay

The original native sequence stopped after nine completed accounts because the POSIX writer guard detected an account already held by a concurrently launched worker (`TAPE_ALREADY_OWNED`). The guard was not weakened. The two separately launched workers completed; the coordinator then resumed the original accounts under unchanged frozen source. The original failure receipt remains preserved. No scientific trial or native balance was replaced, pooled or reseeded.

All **18** registered native accounts are complete and independently audited: treatment, ordinary and no-deploy, each under positive, weak and adverse demand, at separately funded $10,000 and $100,000 opening capital. All report zero remaining payables. The larger-capital reference produces the same operating results within this finite opportunity set; its additional initial equity remains cash. This is not a general claim that capital cannot enable a different expansion opportunity.

| Authored demand region | Treatment profit | Ordinary profit | No-deploy profit after common research cost |
| --- | ---: | ---: | ---: |
| Positive | $4,458.80 | $4,712.44 | −$1,300.00 |
| Weak | −$2,168.20 | −$1,851.15 | −$1,300.00 |
| Adverse | −$6,112.80 | −$5,142.30 | −$3,900.00 |

These are separate conditional simulated businesses, and the table applies separately at each tested opening capital. They are not pooled profits. In the positive region, both productive arms collect $8,700 on nine accepted outcomes: six K1 and three K2. The treatment's complete declared expenses are $4,241.20; the ordinary arm's are $3,987.56. The $10,000 treatment business ends with $14,458.80 available cash; the ordinary business ends with $14,712.44. Opening equity is not income.

The positive treatment account reserves and spends $300 for K2 construction from audited **EARNED** funds after K1, when unrestricted earnings are $2,881.45. In weak/adverse demand, the analogous construction is seed-funded and earns no delivery revenue. Earned funding in the positive case is established within the simulation. It does not establish that the retained treatment was needed for K2: the equal-content ordinary business reaches three accepted K2 outcomes too.

### Preserved verifier failure and separate correction

The frozen `independent_replay.py` initially failed with `CONSTRUCTION_REPLAY_MISMATCH:construction`. Its source SHA-256 is `6bb4f74fe3b81b8a2d9df72aeb500933dbae34c3fbb6a833535a57e75abc7bec`. The first mismatch was metadata representation: regenerated Python phase-cache keys are integers, but JSON object keys are strings; role tuples also become JSON arrays. Recorded and regenerated construction metadata had identical canonical JSON bytes and digest (`504c8472928cd533cdcc98f178e6a7bad2c2578ec13450bea457fa1e8c052938` for the first ordinary row). The original failure and diagnosis remain in `INDEPENDENT_REPLAY_FAILURE.json`.

A separate additive `postfreeze_replay.py` preserves the frozen checker and applies exactly one comparison correction: canonical JSON equivalence for **construction metadata only**. Program, probe, outcome, account, source-freeze, identity and denominator checks remain unchanged. Six new regression tests verify that changed facts, changed role assignments and missing evidence still fail, and that program/probe fields do not gain a normalization exception. No producer, cost, world, sampling, method or acceptance rule was changed.

The corrected full independent replay completed with exit status zero and `accepted: true`. Its `INDEPENDENT_REPLAY.json` verifies:

- The original freeze digest and original failed verifier source identity.
- All 96 submitted programs and regenerated construction/probe transcripts across the exact 48 paired worlds.
- All submitted graph outcomes and the complete scientific aggregation.
- Exactly 18 distinct expected native accounts, their declared arm/region/capital, public export hashes, independent financial audits and recognized-profit identities.
- Final scientific/economic execution-receipt bindings.

The replay uses public exports and does not require or open private account keys. It is reproduction of the same frozen generated confirmation, not a new independent empirical sample or an externally blinded experiment.

## Decision and claims

For the positive authored-demand region, the supported combination is **conditional commercial success without established discovery-method advantage**. For weak and adverse demand, neither commercial success nor a discovery advantage is established; no deploy preserves more capital after the common research burden. No region establishes a new physical capability, a new industry, general self-improvement, or a global optimality claim.

Adopt the ordinary constructor for this bounded simulated service; retain the useful observation, graph and obligation machinery and the negative method comparison. A consequential next construction must establish a real residual beyond competent conventional integration, with accepted outcomes and independently grounded demand/costs. The present short cohort has no validated expansion channel or $3 billion trailing-365-day profit result. Actual customers and actual revenue remain zero.
