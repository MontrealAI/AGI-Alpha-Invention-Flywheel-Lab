# Constructed phase-code instrument, cycle004

This is executable code and exact data, not a completed business or a hardware resource breakthrough. It constructs a four-dimensional quantum code on15 data qubits. One physical S on every data qubit implements logical controlled-S, `diag(1,1,1,i)`. Exact checks establish distance≥3. The ideal recovery corrects arbitrary single-qubit errors without discarding noisy branches.

The intended enabling capability is to construct a code around a required logical interaction and carry it into an executable encoder and recovery test. The commercial horizon would be a device-qualified code/operation delivery for quantum-computing teams constrained by controls and connectivity. Existing methods already implement the unrestricted interaction; this cycle does **not** establish previously inaccessible practical work, global novelty, a complete protected processor or a business advantage.

## Execute

Use Python3.12 on Linux, with at least4GiB address-space allowance. No GPU, credentials, provider calls or raw research dataset are required for this mathematical construction.

```sh
python -m venv /tmp/phase-code-venv
/tmp/phase-code-venv/bin/python -m pip install -r inventions/phase_codes/requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/phase-code-venv/bin/python inventions/phase_codes/reproduce.py --output /tmp/phase-code-replay
```

The output directory must not exist. `REPORT.json` and `COMPLETE.json` bind the completed replay; a partial run is not complete. This replays exposed engineering evidence and creates no new statistical confirmation. The runner verifies the distribution's Python source set, source/artifact hashes and original candidate freeze before executing fixed reviewed mathematical routines. Candidate amplitudes/circuits are data, not arbitrary executable programs.

The command reconstructs the candidate, compares exact mathematical fields, executes the frozen independent certifier and process probes, reproduces the known controls, executes the native encoder and recovery, runs two fresh equal-content reuse tasks, and exercises the existing protected exchange's refusal gates. Successful replay still reports `commercial_success:false`.

## Evidence and comparison

- `artifacts/controlled_s15.json` contains122 exact rational probabilities; amplitudes are their positive square roots. SHA256: `df75e8119f67a54fa8cc6ffe0f2a51a7b80caf0ca71bb8480d875a1c69351556`.
- The independent exact certificate checks all991 identity/weight≤2 Pauli conditions. This implies correction of arbitrary one-qubit errors by Knill–Laflamme; arbitrary two-qubit correction is not claimed.
- Independent ideal process probes passed242 cases×19 logical inputs, including coherent faults, both amplitude-damping branches, and errors before/after the transversal gate. Five defective implementations were rejected; a two-X scan contains fidelity0.
- The coherent native encoder uses17 peak wires:15 data and two wires initially carrying the arbitrary logical input. The latter return to zero. It executed8188 Ry and8229 CNOT gates,16417 total. The ideal all-to-all dependency depth is16375, with118 distinct directed CNOT edges. Routing, finite gate-set synthesis, noisy preparation and a physical recovery circuit are unqualified.
- The exact strong local-phase control composes the published six-qubit `((6,4,2))` controlled-S code with Steane blocks:42 data qubits, distance6. Its stronger protection differs from the candidate. Ordinary complete logical synthesis also gives controlled-S with three T/T† and two CNOT operations; two Steane blocks use14 data qubits, with magic-state/preparation/correction costs still to measure. **15 versus42 does not prove overall superiority.**
- SSLP, prescribed-transversal code design and exact reconstruction are prior art. The scaffold/residue/parity-color adaptation is model-supplied mathematics. This is a new campaign artifact, not an established first-ever code or improved autonomous discovery policy.

See [decision](../../campaign/cycle-004/DECISION.md), [mechanism trace](../../campaign/cycle-004/MECHANISM_TRACE.md), [independent assessment](../../evidence/cycle-004/confirmation/FINAL_ASSESSMENT.md), [full cost boundary](../../campaign/cycle-004/COSTS.json), and [resource audit](../../evidence/cycle-004/RESOURCE_AUDIT.json).

The strict verifier initially rejected extra metadata. A lossless projection of its five declared mathematical fields passed; the rejection and projection receipt remain preserved. A reporting serialization failure, baseline-script timestamp incident, reuse-wrapper resource-limit failure and all unsuccessful constructions remain in evidence. Large repeated process logs are losslessly gzip-encoded with raw hashes in `LOSSLESS_ARCHIVES.json`.

The previous negative grid edition is qualified from immutable commit `0ca2ea08723f338efafb16b939c5b782d4f3794d`. Its source-set guard intentionally rejects newly added Python source in the current checkout. Current CI reuses the qualified `flywheel.legacy` adapter to check current inherited bytes and materialize the exact old closure, then qualifies the mechanism pilot and this component separately; it does not expand the old edition's manifest. Its known interruption-marker race remains unresolved.

The operation allocation remains byte-identical at `campaign/cycle-004/OPERATION_ALLOCATION.json`. The shared `ALLOCATION.json` belongs to the separate mechanism pilot. Technical coexistence is not evidence that its discovery mechanisms generated this code.
