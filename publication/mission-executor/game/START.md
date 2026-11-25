# Private costly observations · Observations privées à coût explicite

The owner ambition was **Build Frontier AI for Game Theory.**

The solver returns a privately randomized acquisition policy, allocations after each observed signal and an exact worst-case payoff interval after acquisition charges. The opponent sees the policy and chooses its scenario and allocation before observing any draw or signal. When instrument choice is visible, run the public-menu comparison.

Use Python 3.12 with NumPy and SciPy for the solver. The proof replay uses only the Python standard library and the pinned prior verifier. Keep the package paths shown below. Both players' allocations are finite, on common lanes and with integral nonnegative budgets. Give each instrument the same signal alphabet in every scenario, with exact rational rows summing to one. Enter acquisition cost in the payoff's units. The optional free, constant-signal instrument represents doing the work without observing.

~~~text
publication/
  mission-executor/game/
  universal/game-theory/{verify.py,solve.py,baselines.py}
~~~

From the repository root, use new paths for output files.

~~~sh
game=publication/mission-executor/game
python3 "$game/solve_observation.py" "$game/EXAMPLE.json" \
  --certificate new-certificate.json --receipt new-receipt.json
python3 -S "$game/observation.py" "$game/EXAMPLE.json" new-certificate.json
python3 "$game/compare_observation.py" public-menu "$game/EXAMPLE.json"
python3 "$game/compare_observation.py" double-oracle "$game/EXAMPLE.json"
~~~

The included model has a certified exact net payoff of **7** for private mixing and **6** for the best announced instrument. The mathematical payoff, exact deviation witnesses, admissible scope, comparison and held checks are in the [report](REPORT.md).

## Version française

Le solveur choisit aléatoirement et en privé un instrument de mesure, puis détermine une allocation pour chaque signal. Le certificat borne exactement le gain garanti après les coûts de mesure. L’adversaire connaît la politique annoncée et choisit un scénario ainsi que sa propre allocation avant de connaître le tirage ou le signal. Si l’instrument retenu est observable par l’adversaire, utilisez la comparaison `public-menu`.

La construction utilise Python 3.12, NumPy et SciPy. Le rejeu du certificat utilise la bibliothèque standard de Python et la version exacte du vérificateur précédent. Les budgets sont des entiers non négatifs, alloués aux mêmes postes. Pour chaque instrument, les scénarios utilisent un alphabet de signaux commun. Les probabilités, exprimées par des fractions ou des chaînes décimales exactes, ont une somme de 1 par scénario. Le coût est exprimé dans les mêmes unités que le gain. Pour comparer avec l’option sans mesure, fournissez un instrument gratuit à signal constant.

Les commandes ci-dessus permettent de reproduire l’exemple. Le mélange privé garantit exactement **7** unités, contre **6** pour le meilleur instrument annoncé. Ces garanties s’appliquent au jeu déclaré et aux conditions d’information indiquées. La calibration réelle des instruments et les gains commerciaux restent à vérifier. [Rapport et preuves](REPORT.md)
