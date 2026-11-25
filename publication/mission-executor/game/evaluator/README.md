# Independent costly-observation confirmation

The evaluator froze 11 synthetic games before receiving candidate source. The practical sources, exact hashes, results and commands below apply to finite one-shot zero-sum allocation with a private observation instrument draw. One administrator controls the shared workspace. These are separate authored cases and independent computations within that workspace. The separate administrative custody requested in issue #565 remains open.

The independent normal-form control enumerates every feasible allocation, instrument and signal-contingent action profile. It constructs the explicit payoff matrix from exact rational channels before solving separate primal and dual LPs with SciPy HiGHS. The independent certificate checker treats the candidate strategy as data. It validates feasible mass and recomputes lower and upper responses on every pure allocation, using Python fractions. The checker's mathematical dependency is the declared finite game and the conditional factorization, independent of the candidate's arc-flow, shortest-path and rounding code. Post-release cases are public regression cases.

The registered threshold for independent narrowness is half a part per million of the maximum scenario weight sum with a floor of one. Independent normal-form primal and dual points must agree with the exact interval within the registered numerical tolerance. Invalid summed mass and a differently bound game are exercised as negative controls.

From this directory within the assembled package, start with fresh destination paths and SciPy available.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 grade_strategic_games.py /tmp/frontier-held-replay \
    --candidate .. --freeze EXACT-STRATEGIC-FREEZE.json
```

The issued report binds the exact held input and candidate bytes. New replays produce their own timestamps and runtime measurements. These can differ without changing the numerical agreement or its scope.

To replay the frozen full-suite double-oracle comparison and private-versus-announced controls, reconstruct the small registered input files below. The stored independent report is checked by SHA-256 before use.

```bash
python3 - <<'PY'
import json
from pathlib import Path
for case in json.loads(Path('held_games.json').read_bytes()):
    p = Path('strategic-final-v1') / case['id']
    p.mkdir(exist_ok=True)
    (p/'setting.json').write_text(
        json.dumps(case['game'], ensure_ascii=False, indent=2, sort_keys=True) + chr(10)
    )
PY
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 grade_strategic_competitors.py /tmp/frontier-competitor-replay --candidate ..
```

The strongest conventional alternatives qualify the same mathematical class on the held cases. Information-structure gains are improving the payoff within a declared model. These experiments provide no measured business outcome or evidence of recursively improved invention.
