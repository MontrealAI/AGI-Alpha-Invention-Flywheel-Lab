# FRONTIER Ω — Independent measurement sensitivity 223

**Status: research qualification / draft / no deployment.** This additive reviewer is stacked on the exact source of PR #522 (`b211c461874051f29827345fc96f82d0d196fc12`). No owner file, data measurement, experiment outcome, financial ledger or original receipt is modified.

The original two chemistry tools optimize historical recorded measurements exactly. Their certificate of optimality is not a guarantee that their selected decisions remain valid if the underlying yields change. This review measures the distinction without claiming to know laboratory error.

## Frozen mathematical contract

The six hypothetical absolute per-cell uncertainty radii are **0, 0.25, 0.5, 1, 2, 5 percentage points**, fixed in [PROTOCOL.json](PROTOCOL.json) at commit `673992b297da827f4b68c71719e649eeb1953c5b` **before implementation**.

For amidation, a fixed recommended condition c for substrate s is robust under independent errors bounded by ε precisely when:

`y(s,c) − ε ≥ 0.90 × max(y(s,c) − ε, max{y(s,d) + ε : d ≠ c})`.

The same cell cannot be both raised and lowered simultaneously. Each original fixed five-condition portfolio is checked against all ten source substrates, then an independently certificate-checked minimum robust repertoire is computed where feasible.

For the nickel ethanol panel, a selected substrate robustly distinguishes any one of the original 253 ligand pairs at an absolute 20-point difference when the recorded difference is at least `20 + 2ε`. All 253 pairs stay in the denominator, including pairs with no feasible substrate under the assumed error radius. Those cases are **INFEASIBLE_FULL_UNIVERSE**, never success on a silently reduced subset. The original six-substrate panel is compared with a newly optimized robust panel.

Synthetic adversarial tests check exact equality boundaries, the correlation of a measurement with its own maximum, source pinning, proof checking and failure preservation. The existing separate `independent/verify_certificate.py` checks combinatorial optimality. Source URLs, hashes and provenance remain inherited from the frozen chemistry experiment.

## Operation

Run from the repository root after a clean checkout of this draft branch:

```bash
python3 -B -m unittest discover -s experiments/frontier_sensitivity223/tests -v
python3 -B experiments/frontier_first_proof_20261121/fetch_sources.py --data-dir /tmp/frontier223-input
python3 -B experiments/frontier_sensitivity223/sensitivity.py --data-dir /tmp/frontier223-input --output /tmp/frontier223-result.json
```

Use fresh paths; output creation is exclusive. Hosted CI preserves source hashes, all six results or the original failure, unit-test output and the exact pinned source identity.

**Interpretation:** ε is an assumed independent perturbation envelope, not measured assay error. The study does not qualify future laboratory reproducibility, previously unrealized outcomes, avoided experiments, acquisition/maintenance costs, adoption, customer payment, profits or recursive invention. Under strong conventional alternatives, robust finite set cover is established mathematics, not a proprietary or frontier-model breakthrough.

---

## Français — Sensibilité des décisions scientifiques

Cette qualification indépendante utilise les outils figés de la PR #522 sans les modifier. Les six erreurs hypothétiques maximales par mesure, **0 / 0,25 / 0,5 / 1 / 2 / 5 points de pourcentage**, ont été inscrites avant le code.

Pour l’amidation, nous vérifions si les cinq conditions d’origine restent valables pour les dix substrats lorsque chaque rendement peut varier dans son intervalle. Pour le panel catalytique, chaque différence entre deux ligands doit atteindre **20 + 2ε** points pour rester garantie. Les **253 paires** demeurent dans le dénominateur, même si certaines ne peuvent plus être distinguées.

Un algorithme classique exact construit les solutions robustes; un vérificateur indépendant contrôle leurs certificats. L’expérience ne mesure ni l’incertitude chimique réelle, ni les économies de laboratoire, ni la valeur économique. Les résultats négatifs, les limites de calcul et les échecs restent explicitement enregistrés. **Recherche uniquement — aucune mise en production ni transaction.**
