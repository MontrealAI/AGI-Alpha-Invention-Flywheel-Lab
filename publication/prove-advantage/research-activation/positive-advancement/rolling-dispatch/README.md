# Feasibility-preserving rolling dispatch

**FAIL at the registered adoption gate. Retain ordinary rolling CP-SAT.** A bounded continuation estimate reordered release-visible tasks and preserved the original commitment, resource and acceptance rules. The independent checker accepted all 48 plans across six real held days, four arms and two repeats. The results were identical in sign and score across repeats. The candidate improved two days, tied three and worsened one. The gate required at least four strict improvements per repeat. [Preregistration](REGISTRATION.md) · [Complete accepted and adverse cases](HELD-RESULT.json)

| Scope | Strongest observed ordinary control | Candidate |
| --- | ---: | ---: |
| Aggregate benchmark score, each repeat | 47,932.8 | 47,246.4 |
| Median planner and independent checker elapsed | 2.690 s | 3.178 s |

The candidate's 1.43% score reduction was accompanied by 18.14% greater median elapsed time. On the strongest improvement day it used two fewer trucks, cut travel by 100.8 minutes and cut lateness by 25 minutes in the declared model. One day had a 12.0 score regression. The benchmark score and modeled minutes do not constitute a financial return. No actual schedules, orders or prices were changed. [Public historical dispatch source](https://data.mendeley.com/datasets/b78bc94d95/1)

The DFL paper guided the separation of feasibility from future-value estimates. This trial used a deterministic continuation rule on at most six orderings per native three-load window, with the same OR-Tools budget and current visibility across the four arms. Research code from the paper was outside the trial. The ordinary controls included native rolling hints, an ordinary cold mode and a fixed lead-time rule. [Research mechanism](https://arxiv.org/abs/2611.34419v1)

## Reproduce offline

Use a fresh private directory, Python 3.12, OR-Tools 9.15.6755 and NumPy 2.5.4. Copy `REGISTRATION.md`, `trial.py` and `preflight-verified.json` there. Export the pinned public source and data into `runtime` under that directory from the repository checkout. The retained preflight was independently evaluated on the published development day and is required by the batch recorder.

```sh
mkdir runtime
git -C /path/to/AGI-Alpha-Invention-Flywheel-Lab archive \
  f0c8db6c7a1110dc614ab8a02c7a0bd5f79260de production060 | tar -x -C runtime
PYTHONPATH="$PWD/runtime" python3 -B trial.py batch
```

The batch writes a new held run in this directory. It verifies the independent acceptance contract and original files on each pass. Native wall-limited search and timing may vary by host. [Availability preflight](preflight-verified.json)

**Résultat.** Les 48 plans ont satisfait le vérificateur indépendant. Le nouvel ordre a amélioré deux journées, fait jeu égal sur trois et dégradé une journée. La méthode CP-SAT habituelle reste en service selon le seuil fixé avant l’essai. Le rejeu utilise des commandes historiques et ne déclenche aucune livraison réelle.
