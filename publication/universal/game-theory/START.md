# Frontier AI for Game Theory

Owner ambition preserved verbatim

> Build Frontier AI for Game Theory.

The first executed mission built a local research instrument for strategic resource allocation with hidden payoff scenarios. Give it finite budgets and weighted lanes. It constructs a common randomized strategy, a randomized adversary strategy and a certificate of their worst-case payoff bounds. The verifier uses exact integer arithmetic and the Python standard library.

A neutral example uses one credit split between two lanes. The adversary can select which lane carries 100 of the 101 payoff points. Equal randomization guarantees **−49.5**. Committing to the nominal first-lane policy yields **−99** under the other scenario. Knowing the payoff scenario before choosing would allow a value of **0**. These are three different information conditions.

## Replay

Verify the already constructed example using Python 3.12 or later. To create a new certificate, install NumPy and SciPy with HiGHS into a local environment. The measured versions and independent comparisons are in `REPORT.md`.

```sh
python -I -S verify.py EXAMPLE.json EXAMPLE-CERTIFICATE.json
python solve.py EXAMPLE.json --certificate new-certificate.json --receipt new-receipt.json
python -I -S verify.py EXAMPLE.json new-certificate.json
```

Use fresh output names. A `QUALIFIED` result bounds the game value to one part per million of the largest scenario weight total, with a scale floor of one. `BOUND_ONLY` provides valid bounds with a wider interval. The CDF-based sparse LP constructs a candidate, and the exact deviation check decides whether to admit it. The objective and interpretation are limited to the described game model. Broader game-theoretic analysis, learning and calibrated real-world use still require evidence.

From this folder, replay the independent assessment into a new directory and run the follow-on disclosure experiment.

```sh
python ../evaluator/run-held-games.py ../new-held-replay
python information-value.py ../evaluator/game-run-v1/shared-policy/input.json
```

A separate evaluator accepted all six previously unseen games with exact payoff bounds. The largest involved 211,775,256 possible pairs of pure actions. A conventional double oracle also passed all six. Full-matrix optimization agreed in the five cases within its preregistered matrix budget. The follow-on experiment used the solver to measure how much a truthful yes-or-no answer could improve the guarantee. The evaluated model showed an improvement of at least **1.83438** payoff units. [Full report](REPORT.md)

## Version française

La première mission a réalisé un outil local d’allocation stratégique lorsque le scénario de gains est caché. À partir de budgets entiers et d’enjeux pondérés, l’outil calcule une stratégie aléatoire commune, une stratégie adverse et des bornes du gain garanti. La vérification est indépendante du solveur et s’effectue en arithmétique entière avec la bibliothèque standard de Python.

Dans l’exemple, un crédit doit être affecté à l’un de deux postes. L’adversaire peut choisir lequel concentre 100 des 101 points d’enjeu. Le tirage équiprobable garantit **−49,5**. Le choix du premier poste selon le scénario nominal donne **−99** dans l’autre scénario. Si le scénario était connu avant le choix, la valeur serait de **0**.

La première commande vérifie le certificat fourni. La deuxième calcule un nouveau certificat local à l’aide de NumPy et de SciPy. La troisième vérifie ce nouveau certificat. Le verdict `QUALIFIED` est limité au modèle déclaré et aux bornes calculées. Les résultats indépendants et les limites figurent dans `REPORT.md`.

Une évaluation distincte a confirmé les bornes exactes sur les six nouveaux jeux, dont un avec 211 775 256 paires d’actions pures possibles. La méthode du double oracle a également réussi les six essais. L’optimisation matricielle a donné une valeur concordante dans les cinq cas compris dans sa limite fixée au préalable. Une expérience complémentaire a mesuré l’apport d’un renseignement exact d’un bit. Dans le jeu examiné, il a relevé le gain garanti d’au moins **1,83438** unité. Les deux dernières commandes relancent ces expériences.
