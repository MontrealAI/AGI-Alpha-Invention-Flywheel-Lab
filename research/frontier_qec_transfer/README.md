# FRONTIER Ω: recovery, then nondestructive noise identification

This experiment constructs two different research capabilities for MONTREAL.AI:

1. Execute recovery for valid quantum codes whose error spaces can overlap or be degenerate.
2. Construct measurements that learn every identifiable combination of specified noise-mixture weights while preserving the arbitrary encoded logical state.

The first source and an independently implemented conventional alternative each passed **824/824 frozen independent checks**. The second construction comparison is in progress. No transfer, monetary benefit, hardware operation, or broader economic breakthrough is claimed by this initial checkpoint.

## Why this is useful

The existing `inventions/phase_codes/runtime_v2.py` deliberately supports a narrower orthogonal-error-sector domain. Removing its refusal would be incorrect. `recovery.py` constructs a proper channel for the wider, well-conditioned finite domain in `FIRST_CONTRACT.json`, including the published seven-qubit Pollatsek–Ruskai code, the degenerate nine-qubit Shor code, and the repository's archived fifteen-qubit controlled-S artifact. The original instrument and its pinned reproduction remain unchanged.

This is classical research software and mathematical protocol construction. It does not implement quantum hardware or establish a physical speedup. Known quantum-error-correction mathematics is a component; worldwide algorithmic novelty is not asserted.

## Current executable example

From the repository root, with NumPy and SciPy installed:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python research/frontier_qec_transfer/demo.py --stage first
```

The example encodes complex logical states, applies amplitude-damping noise, and executes recovery for the three named codes. The output reports the full mass accounting and logical-density error. It is separate from the frozen independent qualification.

To reproduce first-stage qualification:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python research/frontier_qec_transfer/verification/first/qualify.py \
  research/frontier_qec_transfer/recovery.py --output /tmp/frontier-first-qualification.json
```

The recorded environment is Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0, with one BLAS thread. See `ENVIRONMENT.json` for the exact observed runtime and limitations.

## Prospective successor comparison

`protocol/TRANSFER_PROTOCOL.json` and `protocol/COMMON_CONSTRUCTOR_TASK.txt` were frozen before second-stage construction. Three pairs of fresh-context constructors receive the same second objective, public fixtures, ordinary tools, research access and acceptance. One arm additionally receives the exact qualified first source. A separate ordinary-reuse arm receives the independently constructed conventional recovery source.

The distinct second outcome is specified in `SECOND_CONTRACT.json`. It must export an executable measurement instrument, a correct observation model, the maximal physically identifiable parameter subspace, and an estimator. Repeating recovery on fresh inputs is insufficient. Private inputs and the checker are frozen independently; no qualification feedback may repair a source within the registered experiment.

Every result will be retained. Construction latency is not inference compute, labor cost or monetary savings. First-capability acquisition, verification and failures remain part of the cumulative comparison. Unknown costs remain unknown. The same configured included model and procedural blinding are used; exact model weights and OS-enforced isolation are not available.

## Evidence and identities

- `SELECTION.json`: three materially different opportunities, the concrete installed gap and source identities.
- `FIRST_CONTRACT.json`, `FIRST_PUBLIC_FREEZE.json`: first public acceptance and freeze.
- `verification/first/`: exact frozen independent checker and six input cohorts, now released after first-source freezing.
- `evidence/first/`: first candidate, conventional comparison, construction and failure receipts.
- `alternatives/recovery_conventional.py`: independently constructed strong established-method alternative.
- `protocol/`: the frozen three-pair successor procedure and dispatch receipts.

The first source identity is `f8638af7b2532f8c2161fefe2169bb91788c9fc3a5e3321cf7a05ec717f7c134`. The conventional source identity is `c2b3ba3fde39b247ea4d81983e5a4bb6de1d5ed62053b205f8aa65138f99e261`. Both were qualified without private-feedback repair. Separate-agent verification is not external scientific or commercial certification.

## Primary mathematical references

- Knill and Laflamme, [Theory of Quantum Error-Correcting Codes](https://doi.org/10.1103/PhysRevA.55.900), 1997.
- Du, Zhang, Poon and Zeng, [Characterizing Quantum Codes via the Coefficients in Knill–Laflamme Conditions](https://faculty.sites.iastate.edu/ytpoon/files/inline-files/Characterizing%20Quantum%20Codes.pdf), equation 23 for the seven-qubit fixture.
- Wagner et al., [Optimal noise estimation from syndrome statistics of quantum codes](https://doi.org/10.1103/PhysRevResearch.3.013292), 2021.
- Wagner et al., [Pauli channels can be estimated from syndrome measurements in quantum error correction](https://quantum-journal.org/papers/q-2022-09-19-809/), 2022.

These establish relevant existing methods, not a prior complete implementation comparison or a claim that this finite experiment exceeds the literature.

## Français

Le premier outil de recherche et une solution conventionnelle indépendante ont chacun réussi les **824 vérifications indépendantes**. Ils corrigent les erreurs dans le domaine numérique déclaré, y compris des espaces d'erreur non orthogonaux et dégénérés. La comparaison prospective porte ensuite sur une autre fonction : construire une expérience qui identifie le bruit sans détruire l'information logique protégée.

Ce point de contrôle ne revendique pas encore un avantage de transfert. Les calculs sont classiques; aucun matériel quantique, revenu, profit ou avantage économique complet n'est démontré. Les coûts inconnus ne deviennent pas nuls. Les sources historiques restent intactes.
