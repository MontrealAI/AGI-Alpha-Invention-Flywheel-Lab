# Separate-role verification: DC contingency probe

Candidate `grid_screen/__init__.py` SHA256 `72d14ed2fe728b669e8a77834f88f7b3c6c7521537c30b616286719933874f01` was frozen before import by this verifier. The immutable specification SHA256 is `a34c63f23c3f136a8cabadc8981482347dac1d370e93124d195bf80225ad9a90`. Verifier source SHA256 at evaluation was `fc1bb31a7c45cc9b9d27f3d8eb871758c50cd37766a90554c36ff5c344a250c4`.

The separate verifier agent did not edit candidate source. Its reference directly assembles and solves each connected post-outage DC nodal system, independently of the candidate's LODF calculation. Public MATLAB case files are parsed as data by a second implementation; no MATLAB code is executed. Analytic verifier self-tests passed 6/6 before importing candidate source.

## Executed result

`run-01/verification.json` records 33/33 engineering checks passing: 13 generated networks/counterexamples; independently parsed IEEE14 (20 contingencies) and IEEE30 (41 contingencies); two parser comparisons; ten cache mutations; and six malformed-input classes. The reference applies absolute tolerance 1e-6 MW and relative tolerance 1e-8. The evaluation duration was approximately 0.0905 seconds and is verifier runtime, not complete intelligence or project cost.

All connected flows and overload classifications matched the independent reference. Islanding outages returned `ISLANDING_UNKNOWN` without fabricated balancing supply. Cache changes covered tap, phase, rating, reactance, injection, base MVA, endpoints, branch status, branch ordering and bus ordering. Tests rejected nonfinite injections, duplicate buses/branches, invalid references, zero reactance and oversized input.

`transition-01/criticism_repair.json` preserves a deliberately seeded naive implementation failure under the same specification: a bridge outage was reported CONNECTED. The guarded implementation reports ISLANDING_UNKNOWN, and its remaining connected outages pass the reference. This is a reproduced engineering criticism-to-repair transition. The defect was seeded by the builder for the probe; it is not a recovered historical failure, autonomous structural discovery or evidence of novelty.

`failure_controls.json` records refusal of a mismatched candidate hash and refusal to overwrite an existing evidence output. The original run remains intact. `check_inputs.py` and `data_manifest.json` bind both public case files to frozen expected hashes. A mutated input was refused. A constructed interrupted-output state was also preserved on attempted restart; this tests recovery refusal without claiming a process-kill experiment. The integrated reproduction runner calls this checker before evaluation. The original 33-check run remains unmodified; these are separately recorded integrity controls.

## Exposure and scope

Before candidate freeze the builder read part of verifier source, including panel construction. This exposure is retained and the panel was not regenerated. The entire run is engineering development evidence. It does not qualify as protected fresh statistical confirmation. Zero campaign confirmation alpha was spent; no previous campaign budget is reset.

Both roles share model family, libraries, tools, host and filesystem. The separation is procedural, not independent external certification or OS-enforced builder exclusion. The independent implementation reduces shared-code error, but it does not remove common conceptual/model errors.

This qualifies the executed lossless DC equations and selected safeguards only. PGLib is an AC-OPF benchmark; its DC reduction, declared first-bus slack mismatch, and unknown island states cannot complete AC security/interconnection obligations. Ordinary guarded LODF is an established competent alternative. No scientific novelty, operating-queue speedup, negative-to-positive commercial economics, buyer demand, unrestricted earned resources, causal successor advantage or complete flywheel is established.

## Reproduce

```sh
python verification/check_inputs.py --directory research --manifest verification/data_manifest.json
python -m unittest discover -s verification -v
python verification/verify.py --candidate grid_screen/__init__.py --sha256 72d14ed2fe728b669e8a77834f88f7b3c6c7521537c30b616286719933874f01 --case research/pglib_opf_case14_ieee.m --case research/pglib_opf_case30_ieee.m --output /tmp/alpha-verify-NEW
```

Output must not already exist. Paths can be adapted when integrated; source hashes and specification must be retained.

Primary equation source: MATPOWER `makeBdc` reference and original implementation, https://matpower.org/documentation/ref-manual/legacy/functions/makeBdc.html and https://matpower.org/docs/ref/matpower7.1/lib/makeBdc.html (accessed 29 October 2026). The verified branch flow equation is baseMVA/(x*tap) times angle difference minus phase shift; original PGLib bytes and license remain separate source artifacts.
