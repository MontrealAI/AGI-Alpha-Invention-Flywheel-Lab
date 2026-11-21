# FRONTIER Ω — FRAMECOST226
## Real sample burden is the missing practical qualification

**Research-only candidate · HOLD / NO DEPLOY · November 21, 2026.**

FRAMEFIX225 (PR #526) solves a bounded *physical-gauge reproducibility* issue for a mathematical syndrome receiver. This independent follow-up asks a different, practical question: **Does a stable physical receiver provide a statistically useful decision with a finite number of repetitions, and how does a little reported-outcome noise change that requirement?**

It uses the *unchanged* physical receiver from source commit `04767e2b7628e9e4b470c910fd7a3c3c03202135`. Both original scientific fixtures, all 609 hypothesis pairs and the three **preselected illustrative** reporting-noise levels (0%, 1%, 5%) are included. The frozen pre-implementation contract is [PROTOCOL.json](PROTOCOL.json), committed before code at `a5e4bcb055fd51fcb9fdee99f8b06948dbd84dfb`.

For an equal-prior binary distinction with fixed-outcome distributions p and q, set `BC = sum(sqrt(p_i*q_i))`. For N independent and identically prepared shots, the optimal error probability is bounded by

`(1-sqrt(1-BC^(2N)))/2 <= error_N <= BC^N/2`.

Therefore, a 5% average-error target gives **necessary and sufficient** (possibly very conservative) N values. The sufficient value assumes the optimal likelihood-ratio decision *on samples from this very receiver*, not guaranteed quantum-hardware preparation or practical readout. Numerical indistinguishability is never converted into a favorable finite count.

The strong alternative is the *ideal pair-specific Helstrom quantum receiver* on exactly the same states: it is the best known-binary single-copy decision under the mathematical model, but it does not solve a general unknown-mixture decision for free. The general fixed receiver and NO DEPLOY are the other registered choices.

### Reproduce from exact source

Install the unchanged `research/frontier_qec_transfer/requirements.txt` in a standard Python 3.12 environment; from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m unittest discover -s research/frontier_framecost226 -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python research/frontier_framecost226/evaluate.py --output /absolute/new/FRAMECOST226.json
```

Never overwrite a prior result. The dedicated free hosted GitHub Actions job repeats the whole evaluation in **two independent processes**, checks every pair and retains exact source, tests, dependency versions, outcome digests and failures.

### Acceptance and economics

Success means exact-source numerical **shot bounds** and cross-process agreement for all registered cases, not physical realizability, hardware fees, practical beneficiary advantage, buyer acceptance or economic profit. The 1% and 5% values are hypothetical classical reporting-noise mixtures, *not* laboratory-calibrated noise. A bound exceeding reliable precision stays unresolved, never rewritten as a cheap shot. An indistinguishable pair remains in the denominator.

The deployment decision is **NO DEPLOY** until a beneficiary defines a useful accepted decision, a feasible measurement implementation and independently audited costs, then beats capable conventional/AI/human/self-service alternatives with the same complete obligations. The US$3 billion trailing-365-day complete-cost profit objective remains unachieved. This PR does not write or fund a native Account, change a ledger/queue/key, alter other owners' branches or authorize external commerce.

---

# Français — Qualification du coût en mesures

**Recherche seulement · AUCUN DÉPLOIEMENT.** FRAMECOST226 évalue si la mesure quantique mathématiquement stable de FRAMEFIX225 permet une décision binaire à erreur moyenne de 5 %, avec un nombre fini de mesures et sous trois hypothèses fixes de bruit de lecture (0 %, 1 % et 5 %). Ce bruit est **simulé**, non mesuré sur du matériel.

Les 609 paires préalablement enregistrées sont conservées à chaque niveau. Les calculs fournissent une borne **nécessaire** et une borne **suffisante**, sous l'hypothèse de préparations indépendantes et identiques, et comparent une mesure générale avec une alternative quantique idéale spécialisée pour une paire connue. Une paire indiscernable ou incertaine numériquement ne reçoit pas un nombre de mesures artificiellement favorable.

Les coûts réels, le besoin d'un client, la mise en œuvre physique, les gains économiques et l'amélioration de l'invention restent à démontrer. Aucun achat, compte financier, transaction, clé ni déploiement ne fait partie de cette recherche.
