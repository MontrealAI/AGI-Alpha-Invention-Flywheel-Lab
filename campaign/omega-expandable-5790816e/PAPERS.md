# Paper-to-decision map: compatibility recovery and funded expansion

This map was drafted before the new confirmation results and updated against the
implemented compatibility, market, native-account and operating-audit paths. It
does not certify that a citation or publication check implements an entire paper.
The registered confirmation comparison has not yet executed at this map revision;
its exact source and qualification receipts belong in the final report. No private
supplied text is reproduced here.

## Edition boundary and reading

The full current catalogue is [PR195 at a30c52b](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a30c52b18023e1bf0ba1361b5e137c450f0154c3/docs/harness/PAPER_APPLICATIONS.json):
20 PDFs, 19 works, including the preserved FLYWHEEL1.0. Its inspected publication
base is `54c50a3f9a96e140f42e7cb50c810607a75a2231`. This experiment's inherited
runtime base is `cb9c0b9cdd4dc6abd772b8f6b8c1507f5d1ebb47`; these are different
source identities. In particular its inherited `docs/research/super-alpha.pdf`
is **1.0**, SHA256
`37fc425350e752a416f8de88f8dd15f6fbe19c9194bfbd2a0bdc8b4245ca819d`.
The applicable published **1.1** was separately read from publication base54c50,
SHA256 `d57528596fb30a1ed3435b89cf1aebbf9f6a590cec75d05dc294ddc3de5ae7bc`,
matching the [release asset metadata](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/super-alpha-v1.1.0)
retrieved 3 November 2026. The inherited PDF is not silently upgraded or described
as 1.1. Live website requests failed in this pass; repository bytes and release
metadata are the evidence, not verified live deployment.

Substantive methods and limits were read for Invent the Economy §§2–7,
OUT-STRATEGISE §§2–3, OUT-THINK §§2–3, OUT-EVOLVE §§3–4,
OUT-ACCELERATE §§2,5–6, OUT-REFLECT §§1–2, Transformational Intelligence's
purpose/comparison discipline, and SUPER ALPHA1.1 §§3–5. Earlier catalogue entries
remain source pointers with explicit adoption decisions below; none is claimed
reproduced merely by being listed. Page numbers below are printed paper pages;
SUPER ALPHA PDF pages are one higher.

## Decisions, executable boundaries and falsifiers

The implemented boundaries are `omega/compatibility.py` (C),
`omega/expansion_market.py` (M), `omega/expansion_native.py` (N), and
`omega/expansion_audit.py` (A). Exact enforcement tests are listed below. Source
inspection establishes their call paths; final-source execution receipts establish
which checks pass. The substantive development result already changes the policy:
ordinary active learning and all eight successor arms tie at 3,280 learning
queries per successor, so M does not purchase the proposed enhancement or award
an inherited-method conversion bonus.

| Paper / exact passage | Decision and permitted observations | Executable effect and required falsification check | Strong alternative, cost and limitation |
| --- | --- | --- | --- |
| **Transformational Intelligence**, §§2.1,4.1,8.1–8.2 | Preserve the buyer's required stateful behavior while changing how it is reconstructed. A guessed simpler interface cannot redefine acceptance. | C must construct an executable interface from permitted observations, with an independently specified acceptance path. Reject an adapter that matches training traces but fails future transitions. | Ordinary active learning plus adapter construction receives the same queries, construction rights and resources. Accepted finite-model output is not a new industry. |
| **OUT-STRATEGISE**, p4 §§2.2–2.3; p5 Eq4/Theorem3.1 | A policy must choose one action for the information it actually has. It may obtain a distinguishing observation or construct an adapter valid throughout the remaining ambiguity. | C's `ActiveLearner.query` can query only the exposed oracle; M's `public_state`/`decide` receive declared public history and the current rival quote only. Equal public histories must produce equal actions. Unknown behavior or unsupported systems must remain unresolved/refused; no hidden-state/scenario-label lookup. | Conventional active learning is available. The paper's exact minimax Bellman result assumes a finite complete world set, deterministic nondestructive tests and an exact construction envelope. A heuristic query selector or nonstationary market does not inherit that optimality theorem. Charge queries, reset, construction and failed investigation. |
| **OUT-THINK**, pp3–5 Definition2.1 Eqs1–2 and §3.2 | Matching today's answer is insufficient; retained state must preserve future authorized operations. | C's independent bounded conformance acceptance checks outputs across future traces, not merely a success flag or learner transcript. Mutation of a future transition must be rejected. | Bisimulation/conformance checking are established alternatives. The supplied full-model paper is not an algorithm for learning arbitrary hidden systems. Persistent hidden state, timing and side effects outside the finite contract remain unverified. |
| **OUT-REFLECT**, pp2–4 §§1.1–2.2 | A counterexample should adjudicate a claim before repair. Agreement between duplicated sources is not independent evidence. | C separates learner observations from evaluator model access; wrong transitions and inconsistent oracles must fail. Corrections require fresh acceptance. | Independent software checking on the same host is narrower than independent physical metrology. No polynomial error-correcting evidence construction is claimed. Test-generation/checking costs stay in the complete path. |
| **Invent the Economy**, pp3–6 §§2.1–4, Eqs4–5 and10 | Separate technical possibility, simulated participation, accepted delivery and repeatable market evidence. Buyer choice uses budget, adoption cost and outside option. After-acceptance promises cannot fund construction. | M makes the buyer choose or decline; N admits each action using native unrestricted cash and protects obligations. A profitable but illiquid plan must wait. A sequence that can be funded order-by-order must not be rejected solely because its entire cohort cannot be prefunded. | The paper's Proposition4.1 explicitly assumes *all* delivery costs precede *all* receipts. It is not a universal whole-cohort prefunding rule. Ordinary entrepreneurship receives coordination and sequential delivery. Prior costs remain incurred. |
| **SUPER ALPHA1.1**, pp7–8 §§4.2–4.3 Eq3 | An economic shortfall can motivate lower complete cost, better terms, or qualified additional demand. It cannot be filled by inventing buyers. | M's `decide` chooses paid campaigns, prices, a survey/channel pivot or preservation using public outcomes; `MarketRunner` executes chosen work. Price follows the current rival quote, not inferred elasticity from refusals or a future quote. Expanded paid reach can exceed the initial cohort; duplicate/expired reach cannot mint new demand; additional capacity alone creates no customers. | Ordinary adaptive commercial policies have equal channel access. Reach/saturation/conversion inputs are sensitivity assumptions, not observed markets. Acquisition, qualification, failure and obligation costs belong in the window. |
| **SUPER ALPHA1.1**, pp8–11 §§4.4–5.1, Proposition2 and ordered-cash condition | Construction must be funded and qualify before its useful window expires. Actual collections, tax protection and dated expenses govern spending. | N uses authoritative JournalAccount transactions, actual reservations and replay. Its hypothetical immediate pay-as-earned tax schedule reports expense, payment and zero tax reserve separately; a deferred tax-reserve interface is not implemented. Future-money refusal, positive-profit illiquidity and restart idempotence have explicit tests. | The simple renewal inequality assumes monotone settled surplus and no interruption; changing reserves and lumpy receipts use ordered cash instead. Seed is capital, not revenue. Accessible unspent seed must not vanish merely because earnings exist. |
| **SUPER ALPHA1.1**, p9 §4.5 | Declare the game before calling a policy optimal. | M exposes permitted observations and compares registered policies on matched underlying opportunities. No hidden evaluator answers or future payments enter policy. | Best tested heuristic is not global optimality or a market equilibrium; an assumed rival response is a model. Count failed information and decision costs, including stopped development. |
| **OUT-EVOLVE**, pp7–10 §§3.2–4.4 | Freeze the useful artifact, scope and rights before fresh successor work; then requalify changed behavior. | C's `successor_comparison` crosses two changed protocols with no inheritance, cash only, retained probe content and ordinary equal content. All eight development rows accept with 3,280 learning queries each; M consequently buys no unproven enhancement. N can separately admit earned-funded work only from available native earnings. | Ordinary reuse receives equivalent useful information. A reusable model can save queries without improving discovery. Charge predecessor acquisition and fresh validation; privacy permission is not inferred from success. |
| **OUT-ACCELERATE**, pp3,9–11 Definition2.1 and §6.2 Eq11 | Measure the complete route to accepted outcomes; distinguish an asset effect from a discovery-policy effect. | C records oracle calls, construction, verification, corrections and acceptance. Compare old/new policy at fixed old/new assets if claiming improved discovery; otherwise report that claim untested. | The paper's strongest ordinary workflow ties. Machine time is not human attention. Any human benchmark needs separately grounded attention/rate assumptions, not arbitrary staff or slow software. |

These rows are deliberately narrower than the papers' complete constructions.
In particular an observation history hash does not prove a full sufficient-state
theorem; a valid financial replay does not prove intelligent strategy; a local
adapter does not prove real equipment recovery; and a positive conditional market
does not prove observed willingness to pay.

## Complete current catalogue: scoped adoption status

Edition/file hashes are inherited from the exact PR195 catalogue above rather
than duplicated in another authority. Historical papers outside the current
website catalogue remain available through their original reports; their results
are not silently rerun or renamed.

| Work / edition | Decision for this experiment |
| --- | --- |
| SUPER ALPHA1.1 | Adopt scoped commercial-window, dated funding, successor timing and claim discipline; preserve inherited1.0 separately. |
| OUT-ACCELERATE | Adopt complete accepted-route accounting and asset/policy separation; no better-inventor claim without factorial evidence. |
| AGI ALPHA FLYWHEEL1.0 | Historical edition; not the current constructor or a new confirmation result. |
| AGI ALPHA FLYWHEEL1.1 | Do not insert its linear-observation constructor into stateful protocol learning. Preserve its stronger ordinary-constructor result; operation counts are not prices. |
| AGI ALPHA FLYWHEEL 2026-11-02 Report | Retain negative/tied conclusions and separate account denominators; no pooled enterprise balances. |
| Transformational Intelligence | Adopt fixed buyer purpose and strong complete comparisons. |
| AGI ALPHA foundation | Reuse native authority, acceptance, obligations and recoverability. No claim to implement the whole organizational proposal. |
| Invent the Economy | Adopt voluntary participation and complete cash path; collective commissioning remains an alternative, not a manufactured buyer coalition. |
| The World as an Output | Related interface-construction principle, but no physical nuisance-removing instrument or its theorem is implemented here. |
| Beyond the Production Frontier | Keep cash, qualified artifacts and delivery capacity distinct. No physical productive-frontier claim. |
| Beyond the Original Problem | Keep acceptance and authority fixed when changing reconstruction means; no unilateral easier contract. |
| Foundry v2 | Not applicable to the local finite-state prototype's physical calibration: no thermal instrument or actual plant is constructed. |
| Transformational Autonomous Enterprises | Revalidate inherited behavior under a changed task; do not infer authority from retained data. Existing specialist wins remain intact. |
| OUT-REFLECT | Use counterexample-driven independent checking; no fault-correcting polynomial evidence implementation. |
| OUT-LEARN | Its gain/reversal/drift physical calibration is not the selected mechanism. No sensor or physical-identifiability claim. |
| OUT-THINK | Enforce future-transition behavior, not just present output; no claim to solve its canonical compression objective. |
| OUT-DESIGN | No live topology/resource migration is selected. Startup/restart tests alone do not reproduce its migration construction. |
| OUT-STRATEGISE | Enforce common information sets and costed probes. Do not claim its exact finite minimax optimum for the heuristic market. |
| OUT-EXECUTE | Reuse current witnesses and native idempotent settlement; no arbitrary semantic boundary-cache equivalence claim. |
| OUT-EVOLVE | Freeze, transfer and requalify with no-inheritance/equal-content controls; distinguish financed from enabled and merely later. |

## Implemented enforcement and current observations

The following symbols exist in the inspected source. This table records behavior
and development conclusions, not a claim that final confirmation has run. The
final report must supply the frozen source identity, actual command results and
all registered comparison outcomes; no test count is invented here.

| Requirement / paper connection | Implemented path and exact test symbols | Observation or remaining limit |
| --- | --- | --- |
| Construct and independently accept the promised behavior; Transformational Intelligence, OUT-THINK | `C.build_product`, `C.accept_product`, `C.independent_acceptance`; `omega.test_compatibility.CompatibilityTests.test_downloaded_learner_constructs_fresh_workflow`, `test_buyer_local_callable_and_explicit_assumptions`, `test_self_report_and_updated_hash_cannot_authorize_wrong_delivery`; `omega.test_expansion_acceptance.IndependentCapabilityAcceptance.test_new_finite_machines_against_independent_state_pair_oracle` | Download contains the learner, adapter runner, documentation and bounded conformance checker. The independent development test constructs16 additional finite systems and checks reachable state pairs through a different implementation. This is authored software evidence, not equipment restoration. |
| Purpose/assumption boundary, not acceptance by a persuasive claim; OUT-REFLECT | `C.validate_contract`, `C.independent_acceptance`; `CompatibilityTests.test_wrong_observed_state_bound_rejected`, `test_repeated_reset_failure_rejected`, `test_learning_and_verification_resource_limits`; `IndependentCapabilityAcceptance.test_unverified_state_bound_is_not_established_by_finite_success` | The longer-memory adversarial oracle can pass the finite test when its declared bound is false. That retained counterexample forbids universal equivalence claims. A caller must justify determinism, reset and the bound. No physical calibration is supplied. |
| Voluntary participation, decline and usable self-service; Invent the Economy | `C.build_product`, `C.diagnose`, `M.buyer_choice`; `CompatibilityTests.test_decline_has_no_delivery_or_queries`, `test_local_help_uses_actual_documentation_and_admits_unknown`; `omega.test_expansion_market.ExpansionMarketTests.test_independent_budget_and_nonpurchase` | Buyer budget is independently authored and includes adoption cost. Help reads actual documentation, diagnoses known conditions and admits unknown ones. It is a deterministic help lookup, not a universal model assistant. |
| Information sets and current competitive response; OUT-STRATEGISE, SUPER ALPHA§4.5 | `M.public_state`, `M.decide`; `ExpansionMarketTests.test_hidden_information_rejected`, `test_current_rival_quote_changes_price_without_future_or_decline_inference`, `test_refusals_alone_do_not_change_posted_price`; `omega.test_expansion_audit.OperatingAuditTests.test_fabricated_available_cash_cannot_change_policy`, `test_recorded_collections_cannot_be_observed_before_native_release` | Public rival price can change a posted offer; buyer values, future draws and scenario labels are excluded. This is a declared response heuristic, not learned elasticity, a global optimum or an equilibrium proof. Audit binds each observed financial field to a native prefix. |
| Optional spending, acquired reach and economically justified stopping; SUPER ALPHA§§4.2–4.3 | `M.decide`, `M.MarketRunner._contacts`, native `ChannelBook`; `ExpansionMarketTests.test_nonentry_never_forces_cost`, `test_paid_acquisition_can_expand_beyond_initial_cohort`, `test_no_spend_no_reach_or_order`, `test_overlap_cannot_be_fresh_demand`, `test_observed_loss_stops_commerce`, `test_qualified_alternative_channel_can_receive_a_paid_pilot`, `test_zero_capacity_cannot_grant_reach` | Campaigns can grow beyond their initial eight contacts; a completed loss can trigger a paid survey, channel pivot or stop. Known overlap cannot be resold as fresh demand. Audience, reach, values and failure probabilities are assumed sensitivity worlds; tests do not create empirical demand. |
| Ordered funding, available seed and honest tax schedule; Invent the Economy§4, SUPER ALPHA§5 | `N.NativeBridge.snapshot`, `spend`, `deliver`, `advance`, `_tax`, `report`; `omega.test_expansion_native.NativeExpansionTests.test_delayed_collection_profit_is_not_spendable_cash`, `test_seed_remains_available_after_earning`, `test_sequential_cash_feasible_pair_is_not_whole_cohort_prefunded`, `test_individual_orders_costs_acceptance_budget_and_full_year`; `OperatingAuditTests.test_available_native_cash_cannot_be_falsely_called_unfunded`, `test_affordable_voluntary_order_cannot_be_falsely_deferred` | A future receipt cannot fund present work. Sequential acceptance/release can finance a later order when the full cohort cannot be prefunded. The hypothetical25% immediate tax policy has zero deferred tax reserve and is not actual Canadian tax advice. All cost-rate/demand inputs remain declared assumptions or sourced estimates. |
| Equivalent batching, present state and recovery; OUT-THINK, OUT-EXECUTE's limited relevance | `N.NativeBridge`, `A.RecordingBridge`, `A.audit_market`, native snapshot path; `NativeExpansionTests.test_chunked_restart_and_sequential_native_execution_are_identical`, `test_grouped_invoice_and_individual_components_preserve_financial_outcomes`, `test_interrupted_fund_restarts_same_account_without_intervening_open`, `test_crash_after_tax_keeps_native_contribution_receipt`; `OperatingAuditTests.test_interrupted_segment_replays_with_same_native_account`; `tests.test_account_snapshot_expansion.ExpansionSnapshotTests.test_empty_accepted_uncollected_release_refund_claim_and_maturity_equivalence`, `test_fresh_history_and_configuration_identity_no_cached_snapshot`, `test_snapshot_avoids_full_export_without_skipping_live_owner_check` | Grouping cost components or restarting between orders must preserve financial results. The selected snapshot avoids a full export but still checks live ownership, current source, configuration and history; it is tested against the existing full-export observation. It is not a lossy cache or proof of exactly-once arbitrary remote effects. |
| Retained assets must earn investment; OUT-EVOLVE, OUT-ACCELERATE§6.2 | `C.successor_comparison`, `M.decide`; `CompatibilityTests.test_successor_equal_content_conventional_control`; `ExpansionMarketTests.test_no_invented_upgrade_cost_or_reuse_bonus` | All eight changed-protocol development arms accept and tie at3,280 learning queries. Equal-content ordinary reuse produces identical adapters. No discovery-policy benefit is established; the market policy purchases no unsupported enhancement. Verification queries and predecessor acquisition remain additional cost, not hidden savings. |
| Independent operating and native accounting agreement; AGI ALPHA foundation | `A.audit_market` first calls native `audit_journal`, verifies financial observations against prefixes and regenerates the market; `OperatingAuditTests.test_native_prefixes_and_complete_market_replay_accept`, `test_changed_private_buyer_world_cannot_keep_accepted_orders`, `test_native_spend_cannot_be_removed_from_operating_history`, `test_invented_prebuilt_initial_state_is_rejected` | A financially balanced ledger alone cannot establish paid reach, voluntary choice or causal strategy. The separate replay rejects changed market histories and invented assets. It checks the registered model, not the truth of its commercial assumptions. |

**Cost and evidence limits.** Measured query counts and process timing are distinct
from assumed commercial rates, buyer effort and complete actual costs. See
[OFFERS_COSTS.md](OFFERS_COSTS.md). There are no paid model calls or invented
software staff. Physical queries, real demand, legal/redistribution rights and
full actual host/model costs remain unresolved. The new registration uses USD
and a fresh US$100,000 account; prior accounts and losses remain separate.

The development successor tie is an operational decision input: keep the ordinary
method and decline that enhancement. It does not show that all future research is
unprofitable. Final confirmation still has to establish commerce, funded expansion
and the exact rolling-year result under the registered worlds; none follows from
this paper map or the presence of these tests.

