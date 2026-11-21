# FRONTIER Ω — FRAMEFIX225: a physically anchored noise readout

**Status: independently tested mathematical research, DRAFT / NO DEPLOY.**

Upstream PR #525 discovered source-identical runs producing different *physical* measurements. The cause under investigation is an arbitrary syndrome eigenbasis. FRAMEFIX225 provides a distinct physical POVM constructor that explicitly removes the arbitrary unitary gauge from its definition. It does not rewrite PR #524 or #525, and it is not a proof that the older measurement was stable.

## Constructor and operator

The independent module at research/frontier_framefix225/framefix.py first anchors the syndrome basis to the fixed physical computational-basis order using twice-reorthogonalized Gram–Schmidt. It transforms both recovery Kraus operators and syndrome states consistently. It builds an informationally complete readout using a deterministic Cholesky normalization and checks physical effect conservation, probabilities and nonempty source pins.

Run from the repository root in the unchanged scientific Python environment (requirements file: research/frontier_qec_transfer/requirements.txt), with OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1. Run the source-bound unittest discovery over research/frontier_framefix225/test_*.py, then run research/frontier_framefix225/run.py with --output pointing to a new JSON file. The program refuses overwriting an existing result.

The exact preregistered protocol is research/frontier_framefix225/PROTOCOL.json at commit 9f2eb4d722d250cfe5211c7de6ac3e50bfdf6a10. The execution uses four immutable upstream Git blob hashes.

## Actual bounded evidence

- Two fixed historical fixtures: 22 hypotheses / 231 pairs (7-qubit), 28 hypotheses / 378 pairs (9-qubit). All 609 registered pairs retained, including nine indistinguishable Shor pairs.
- Three registered complex gauge rotations, seeds 1, 7 and 257; no favorable seed selection.
- 6/6 scientific/source tests passed; maximal response drift 4.17e-17, maximal physical-operator drift 8.69e-17 against tolerance 2e-8.
- Uncorrected frame changed response up to 0.04590 under the same gauge rotations. This is a mathematical negative control; it is not proof that the earlier hosted-run instability had no other cause.
- Two independently invoked processes agreed at the recorded numerical precision across all pair distances (maximum gap 0). Both supported mixture ranks remained 22.
- Hosted source-exact run: https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44950692959 ; artifact ID 14724838251, ZIP passed integrity, SHA-256 ddbaf6743e67e4557439c33aa0d25668d0f011621cd8a10c18136dad34a12f21 matches the platform digest.

## Limits and next decision

This is not deployed quantum hardware, actual finite-shot sufficiency, measured physical or commercial cost, a new paying customer, demonstrated business advantage, better invention, native earned investment or the $3 billion trailing-365-day profit milestone. Model/host billing remains unknown. Existing financial accounts, private keys, obligations, main and releases remain unchanged. The owner of PR #524/#525 should independently evaluate the new physical POVM against realistic measurement hardware and competent conventional alternatives before selectively integrating it. Original failures are retained unchanged.

---

# Français — Mesure de bruit avec référentiel physique fixe

**Statut : recherche mathématique qualifiée dans un cadre limité; brouillon, aucun déploiement.**

Le précédent instrument pouvait produire une mesure physique différente selon une base arbitraire du syndrome, même avec des sources identiques. FRAMEFIX225 construit une **nouvelle mesure**, ancrée dans des coordonnées physiques fixes, afin d'éliminer cette dépendance de représentation.

Les 609 paires prédéclarées ont été conservées, y compris neuf paires indiscernables. Les six tests ont réussi, les trois rotations prévues respectent la tolérance numérique, et deux processus distincts ont produit des résultats concordants. L'ancienne défaillance reste documentée; elle ne devient pas rétroactivement une réussite.

**Non établi :** exécution sur du matériel quantique, coûts physiques réels, avantage économique, paiement, amélioration de l'invention ou bénéfice durable. Aucun compte financier, engagement, clé privée, version publiée ou branche d'un autre propriétaire n'a été modifié. Une revue indépendante et une comparaison complète restent nécessaires.
