# Exact public quote ranking, opt-in increment048

Set `strategic_policy.ranking_arithmetic` to `exact-rational-v1` in a fresh,
source-frozen simulation registration. The existing canonical `run_world` path,
`JournalAccount`, qualified native reservations and independent operating audit
remain authoritative. Existing policies without this field retain their prior
numerical behavior and receipt shapes; this increment changes no default.

This mode ranks the finite admitted one-order price/method alternatives using
exact rational expectations. Complete-offer atom weights, utility ties, remaining
public budget hypotheses and connected uniform-interval beliefs are rational.
Declared decimal scenario weights, acceptance and collection probabilities are
interpreted as their exact decimal values; this is an arithmetic convention,
not a claim that authored demand probabilities are calibrated. Evaluation,
production, method, payment and tax costs enter the same expression. Current
cash and principal protection still determine feasibility before ranking.

Rows retain float displays and add `expected_net_fraction`; scenario rows add
`win_probability_fraction`, `accept_collect_probability_fraction` and
`net_after_modeled_tax_fraction`. Exact fractions decide ranking and exact ties
use the existing method/price order. Independent replay reconstructs all fields.
The existing joint allocator receives the conservative floor of each exact
scenario contribution in native microUSD; therefore this does **not** establish
sub-microUSD rational basket optimality or monetize fractional simulated cash.
Display floats never supply that floor.

The regression has two roughly US$100million candidate quotes whose float
expectations tie. The higher quote has exactly 1/10000 microUSD greater expected
contribution. Another case shows a float contribution rounding upward across an
integer boundary; the exact floor prevents the forecast from creating an extra
microUSD. These are arithmetic counterexamples, not revenue or profit evidence.

Exact mode supports the public complete-atom market and `connected_range` with
an observed rival quote. Exact logit forecasting and finite numerical rival best
response remain explicitly unavailable. Scenario weights must sum to one
exactly. The existing single-order `repeat_horizon=0` and
`future_equivalent_jobs=0` contracts remain unchanged.

## Later quantity and sequence composition

The subsequent opt-in `complete-offer-quantity-v1` path now constructs the actual packet work/cost profile, counts purchased capacity units and expiry, costs future channel windows, shares requested-work identities and preserves the authorized first earned-funded action. See [COMPOSED_WINDOW049.md](COMPOSED_WINDOW049.md) for the explicit contract, tests and source-specific comparison. The earlier single-opportunity restrictions above still describe exact arithmetic used without that later composition policy; validation guards remain in force for unsupported combinations.

The four-world composed-window comparison did not beat the conventional incumbent. Unified owned/reachable access remains a separate integration dependency. Exact arithmetic and working composition do not establish general economic superiority, a better discovery method, trailing-year profit or actual commerce.

## Verification

Run from the final source root:

```sh
python3 -m unittest discover -s tests -p 'test_connected_strategic_exact048.py' -v
python3 -m unittest discover -s tests -p 'test_strategic024.py' -v
```

The new test operates a four-day fresh simulation through actual packet
production and collection, independently audits it, resumes the same account,
checks unchanged native financial history, audits again, and rejects a changed
rational certificate. Native authority is neither inspected nor exported.
Full source-matched qualification and downloaded-release operation remain
integration gates, separate from these focused checks.
