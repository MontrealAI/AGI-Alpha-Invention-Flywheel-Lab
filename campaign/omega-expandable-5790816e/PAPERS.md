# Paper-to-decision map: compatibility recovery and funded expansion

This map was drafted before the new confirmation results. It constrains the
implemented experiment; it does not certify that a citation or publication check
implements an entire paper. Source-bound results and exact test names must be
attached after execution. No private supplied text is reproduced here.

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

The assigned implementation boundaries are `omega/compatibility.py` (C),
`omega/expansion_market.py` (M), and `omega/expansion_native.py` (N). Tests belong
beside those modules. At registration these are implementation obligations,
**not passing-test claims**. The final report must distinguish implemented,
executed and still missing behavior.

| Paper / exact passage | Decision and permitted observations | Executable effect and required falsification check | Strong alternative, cost and limitation |
| --- | --- | --- | --- |
| **Transformational Intelligence**, §§2.1,4.1,8.1–8.2 | Preserve the buyer's required stateful behavior while changing how it is reconstructed. A guessed simpler interface cannot redefine acceptance. | C must construct an executable interface from permitted observations, with an independently specified acceptance path. Reject an adapter that matches training traces but fails future transitions. | Ordinary active learning plus adapter construction receives the same queries, construction rights and resources. Accepted finite-model output is not a new industry. |
| **OUT-STRATEGISE**, p4 §§2.2–2.3; p5 Eq4/Theorem3.1 | A policy must choose one action for the information it actually has. It may obtain a distinguishing observation or construct an adapter valid throughout the remaining ambiguity. | C can query only the exposed oracle; M gets public history only. Equal public histories must produce equal actions. Unknown behavior or unsupported systems must remain unresolved/refused; no hidden-state/scenario-label lookup. | Conventional active learning is available. The paper's exact minimax Bellman result assumes a finite complete world set, deterministic nondestructive tests and an exact construction envelope. A heuristic query selector or nonstationary market does not inherit that optimality theorem. Charge queries, reset, construction and failed investigation. |
| **OUT-THINK**, pp3–5 Definition2.1 Eqs1–2 and §3.2 | Matching today's answer is insufficient; retained state must preserve future authorized operations. | C's independent product/state-pair acceptance checks outputs and subsequent transitions, not merely a success flag or training transcript. Mutation of a future transition must be rejected. | Bisimulation/conformance checking are established alternatives. The supplied full-model paper is not an algorithm for learning arbitrary hidden systems. Persistent hidden state, timing and side effects outside the finite contract remain unverified. |
| **OUT-REFLECT**, pp2–4 §§1.1–2.2 | A counterexample should adjudicate a claim before repair. Agreement between duplicated sources is not independent evidence. | C separates learner observations from evaluator model access; wrong transitions and inconsistent oracles must fail. Corrections require fresh acceptance. | Independent software checking on the same host is narrower than independent physical metrology. No polynomial error-correcting evidence construction is claimed. Test-generation/checking costs stay in the complete path. |
| **Invent the Economy**, pp3–6 §§2.1–4, Eqs4–5 and10 | Separate technical possibility, simulated participation, accepted delivery and repeatable market evidence. Buyer choice uses budget, adoption cost and outside option. After-acceptance promises cannot fund construction. | M makes the buyer choose or decline; N admits each action using native unrestricted cash and protects obligations. A profitable but illiquid plan must wait. A sequence that can be funded order-by-order must not be rejected solely because its entire cohort cannot be prefunded. | The paper's Proposition4.1 explicitly assumes *all* delivery costs precede *all* receipts. It is not a universal whole-cohort prefunding rule. Ordinary entrepreneurship receives coordination and sequential delivery. Prior costs remain incurred. |
| **SUPER ALPHA1.1**, pp7–8 §§4.2–4.3 Eq3 | An economic shortfall can motivate lower complete cost, better terms, or qualified additional demand. It cannot be filled by inventing buyers. | M chooses paid campaigns, prices, information, preservation or construction from observed outcomes. Expanded paid reach can exceed the initial cohort; duplicate/expired reach cannot mint new demand; additional capacity alone creates no customers. | Ordinary adaptive commercial policies have equal channel access. Reach/saturation/conversion inputs are sensitivity assumptions, not observed markets. Acquisition, qualification, failure and obligation costs belong in the window. |
| **SUPER ALPHA1.1**, pp8–11 §§4.4–5.1, Proposition2 and ordered-cash condition | Construction must be funded and qualify before its useful window expires. Actual collections, tax protection and dated expenses govern spending. | N uses authoritative JournalAccount transactions, actual reservations and replay. Test future-money refusal, positive-profit illiquidity, reservations, tax accrual/reserve/payment separation and restart idempotence. | The simple renewal inequality assumes monotone settled surplus and no interruption; changing reserves and lumpy receipts use ordered cash instead. Seed is capital, not revenue. Accessible unspent seed must not vanish merely because earnings exist. |
| **SUPER ALPHA1.1**, p9 §4.5 | Declare the game before calling a policy optimal. | M exposes permitted observations and compares registered policies on matched underlying opportunities. No hidden evaluator answers or future payments enter policy. | Best tested heuristic is not global optimality or a market equilibrium; an assumed rival response is a model. Count failed information and decision costs, including stopped development. |
| **OUT-EVOLVE**, pp7–10 §§3.2–4.4 | Freeze the useful artifact, scope and rights before fresh successor work; then requalify changed behavior. | C compares fresh learning, inherited artifact, equal-content ordinary reuse and changed/incompatible predecessor controls. N can fund a successor only after accepted collections and qualification. | Ordinary reuse receives equivalent useful information. A reusable model can save queries without improving discovery. Charge predecessor acquisition and fresh validation; privacy permission is not inferred from success. |
| **OUT-ACCELERATE**, pp3,9–11 Definition2.1 and §6.2 Eq11 | Measure the complete route to accepted outcomes; distinguish an asset effect from a discovery-policy effect. | C records oracle calls, construction, verification, corrections and acceptance. Compare old/new policy at fixed old/new assets if claiming improved discovery; otherwise report that claim untested. | The paper's strongest ordinary workflow ties. Machine time is not human attention. Any human benchmark needs separately grounded attention/rate assumptions, not arbitrary staff or slow software. |

These rows are deliberately narrower than the papers' complete constructions.
In particular an observation history hash does not prove a full sufficient-state
theorem; a valid financial replay does not prove intelligent strategy; a local
adapter does not prove real equipment recovery; and a positive conditional market
does not prove observed willingness to pay.

## Complete current catalogue: prospective adoption status

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

## Enforcement status

Final qualification must replace this paragraph with exact executed test symbols
and source-bound observations. Unimplemented relevant behavior stays an explicit
gap, not a passing map entry. The intended bypass tests reject hidden observations,
acceptance by self-report, unbudgeted queries, false future equivalence, fabricated
reach, unfunded spending, duplicated settlement and unsupported superiority claims.
