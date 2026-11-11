# Matched-market integrity 138 — prospective protocol (frozen before implementation)

**Source under test:** main `960153fb0ae1f339177fe3965266e8e5419ba45d`, `connected_enterprise/scale.py::compare`. **Owner:** isolated independent qualification; no finance/operating writer. **Status:** preimplementation protocol. **Scope:** source-bound analytical comparison, **not** native audit or a new economic observation.

## Specific failure to test

The existing `compare` joins two results using only simulated seed, world/case, customer-pool size and account opening cash. It does **not** test whether external voluntary buyer prices/values, arrival/retention, supplier/channel contracts, taxes, service costs, operating horizon and evidence/source identity agree. A candidate may therefore receive a reported matched profit advantage solely because its configured demand or costs differ. This is an unqualified *causal-parity* comparison even when both ledgers are internally valid.

## Frozen acceptance checks

1. Two otherwise identical baseline/growth fixture results with the same configured environment and equal opening capital retain one valid comparison and unchanged profit deltas.
2. Holding seed, world, customer-pool size and capital equal, altering `arrival_bps` or `value_bps` in the candidate MUST reject the comparison; no spurious matched winner.
3. Changing `setup_cost`, `profit_tax_bps`, a supplier/channel contract or `complete_offer_policy` MUST reject. No cost, terms, scope or demand changes hidden as an arm treatment.
4. A missing/mismatched root source manifest on one arm MUST reject; exact-equal or both-absent manifests in old minimal fixtures remain allowed. This is only identity parity, **not** a substitute for independent source/native audit.
5. A legitimate explicitly named **policy treatment** (strategic choice, allocation, mechanism, channel menu, refusal recourse or startup acquisition policy), with all exogenous fields fixed, MUST remain comparable. Report the treatment keys. Baseline/growth `arm` is itself a valid policy treatment.
6. Existing `tests.test_connected_scale` compatibility, native immutable accounting, the stronger direct audit, current signed accounts, tails, and all historical failures remain unchanged. No newly authored toy fixture counts as paying commerce, forecast calibration, independent causal improvement or the US$3B milestone.

**Implementation boundary:** update the observer's `compare` only, add adversarial tests in `tests/test_connected_matched_market138.py`; no account/engine/financial migration, no replaced archives, no modified evaluation thresholds or seed retuning. Existing identified mismatch must not silently return an eligible pair. `analyze`, `trailing_profit` and the freshly qualified Streaming137 algorithm are outside this change.

**Qualification:** run the exact committed tests, existing scale tests and full connected release CI on the candidate head; preserve initial failures, repair before retry, require protected normal integration and separately published/downloaded release before asserting runtime qualification. No financial or source-authority transition is authorized by this protocol.

**Commercial decision:** retain the incumbent/no-deploy if an apparent advantage disappears under matched exogenous conditions. The proposed safeguard prevents false attribution; it does not itself create customers, income, new useful services or a qualified joint commercial policy.
