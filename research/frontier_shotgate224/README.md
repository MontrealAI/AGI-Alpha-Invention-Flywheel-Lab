# FRONTIER Ω — SHOTGATE224

**Research-only independent qualification · 21 November 2026 · NO DEPLOY**

This instrument audits a gap in the [FRONTIER QEC research chain](../frontier_qec_transfer/REPORT.md): exact linear identifiability of quantum noise mixtures does not establish a useful finite-shot operating decision. It compares the existing informationally complete measurement to a competent **pair-specific conventional Helstrom receiver** on the same syndrome state, and calculates a **necessary** shot threshold for a 5% equal-prior binary error target.

## Preimplementation freeze and source ownership

- [PROTOCOL.json](PROTOCOL.json) was committed at `52d85e0730c94901bae913dc76ebb237eb917273` before this code, tests or workflow.
- The source is frozen at owner PR #524 head `7501e83ea37b0d933e2318be2099b37308de0574`. The original recovery, successor, fixture, verification and owner-report paths are unmodified.
- A separate test fails if the original recovery or selected successor source byte digest differs from the independent owner's published identity.
- Only `research/frontier_shotgate224/` and a dedicated workflow are new. This is not financial source/account migration, new owner integration, or a released runtime.

## Execute

Within the scientific Python environment already required by the frozen owner:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
 python -m unittest discover -s research/frontier_shotgate224 -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
 python research/frontier_shotgate224/shotgate.py --output /tmp/shotgate224-NEW/RESULT.json
```

Do not reuse an existing output path. The test enumerates all pairs of public registered pure noise hypotheses for the seven-qubit Pollatsek–Ruskai and nine-qubit Shor fixtures. For every pair it computes the fixed 484-outcome frame's total variation and squared Hellinger distance and a separate syndrome-space Helstrom bound; it retains *all* pairs (including numerically indistinguishable ones). The reported hardest numerically distinguishable pair is chosen by maximum Bhattacharyya overlap, with deterministic index tie-break. No seed or favorable subset is selected after results.

For single-shot outcome distributions `p` and `q`, `BC=sum(sqrt(p_i*q_i))`. For `N` independent identically prepared shots and an equal prior, the optimal binary Bayes error is **at least**

```
e_N >= (1 - sqrt(1 - BC^(2*N))) / 2
```

Therefore `N >= ceil(log(4*a*(1-a))/(2*log(BC)))` is **necessary, not sufficient**, for a target average error `a=0.05`, for `0<BC<1`. If `BC=1`, this frame cannot distinguish the pair at any sample count; if `BC=0`, a single shot suffices. The bound follows the classical Bhattacharyya/total-variation inequality and product overlap under i.i.d. draws. Exact synthetic enumeration verifies that the bound never exceeds actual optimal Bayes error on the tiny checked worlds.

## Conventional and economic comparison

Helstrom gives the best **pair-specific single-copy** binary decision on two known syndrome density operators. The existing 484-outcome frame solves a different, broader multi-hypothesis identification problem. The comparison is intentionally strong but **not** evidence of a superior complete end-to-end competitor or a replacement instrument. It also does not establish optimal measurements for an unknown multi-hypothesis mixture, device fabrication, calibrated hardware readout, or an economic acceptance threshold. Unknown model host costs, shot costs, buyer willingness, physical noise and integration work remain unknown.

Three alternatives retain their appropriate roles: the existing general frame (construct and analyze), a specialized conventional Helstrom decision (only where a known binary distinction is the actual task), and **no deployment** without an accepted measured-use case. All other owner experiments and historical failures retain their original qualifications.

## Acceptance and next gate

The fixed engineering gate requires two complete fixture inventories, fail-closed normalization and source checks, independent exact small-world Bayes controls, and source-matched hosted execution. A passing gate proves only mathematical resource constraints; it cannot claim monetary savings or improved discovery. A valuable future test requires a beneficiary's real decision tolerance, feasible measurement preparation and calibration, independently measured shot/readout costs, and comparison with a capable entire conventional workflow. If those inputs are not available, the correct economic decision remains **HOLD**.

## Français

**Qualification mathématique indépendante, sans déploiement.** Le rang d'identifiabilité ne garantit pas une décision fiable avec un nombre limité de mesures. SHOTGATE224 recense toutes les paires d'hypothèses quantiques des deux cas publiés et calcule une **borne inférieure nécessaire**, et non une garantie suffisante, du nombre de mesures pour un risque binaire moyen de 5 %. Le récepteur de Helstrom spécialisé est une alternative classique compétente pour une décision binaire connue, mais il ne remplace pas automatiquement l'instrument général. Aucun matériel physique, coût économique, client, revenu ou avantage commercial n'est établi.
