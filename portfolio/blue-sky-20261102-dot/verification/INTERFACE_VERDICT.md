# I1 independent verdict — 2026-11-02

**PASS-CODE / PASS-MODEL-CONDITIONAL. Physical and commercial qualification unresolved.**

After public preregistration commit `97df4404b4f51e5043657f66d4a1eb8430883e65`, independent replay passed 27/27 exact reciprocal linear-model cases (three seeds, mode counts4/8/16, condition numbers1/3/10). Minimum target intensity relative to matched-filter optimum was0.9999999999999993; maximum K2 field error after one allowed global sign was1.7414e-14. Separate SciPy generalized eigenvalue checks agreed. All six invalid/ambiguous-input challenges rejected: NaN calibration, infinite field, rank deficiency, repeated reflector spectrum, disconnected phase graph, and using intensity-only K1 for phase reconstruction.

Independent analytic witnesses confirm that two diagonal reflectors cannot identify row signs, one reflector permits a larger orthogonal gauge, and a connected third reflector separates the selected sign pair. This supports different *model functions*: coordinate intensity focusing and coherent-field reconstruction. It does not establish economic consequence or novelty. Ordinary equal-content algebra is available to the comparator; no AI-superiority claim follows.

A decisive limitation is also verified: nonreciprocal return operator0.81Tᵀ produces the same calibration data as reciprocal effective transmission0.9T under every reflector (numerical discrepancy1.95e-16). Calibration residuals therefore cannot independently certify the reciprocity/absolute-field premise. Source predecessor Gordon et al., https://arxiv.org/html/1904.02644, uses wavelength-dependent reflectors and a dispersion model; the tested selectable fixed-wavelength reflectors are an unconstructed engineering assumption, not a validated substitute.

Static review before confirmation found and prompted repair of a NaN-acceptance bug; the tested source is the repaired version. Missing stale/wrong-reflector controls in the original driver were explicitly identified; they remain separate pending supplemental execution, not silently credited by the27-case result.

Evidence: `INTERFACE_REPLAY_RESULT.json` SHA25640a317ef7d8272edc66e246c4145d7279115350a514da1c452e29848c506fe24 contains exact source/dependency identities. Shared public fixtures are not secret holdouts. This is finite code/model verification, not statistical population evidence, a physical instrument, paid customer acceptance, or a flagship-admission verdict.

## Supplemental completion
After supplemental public commit `a64eaec35f147779545c718fd74f6a628d1aedfb`, verifier re-executed `remaining_controls.py`; its JSON exactly matches the constructor's three cases. Stale calibration gave relative field errors1.411–1.673; recalibration reduced them below4.70e-15. A21% common reflector-calibration scale error caused9.09% recovered-field bias while residuals remained below1.23e-14; all true reflectors remained passive (maximum norm0.847). This completes the two previously omitted controls without changing the original27-case result. The calibration-bias failure is expected and material: low internal residual is not an external accuracy certificate.

Constructor's189-case stress output was inspected, not independently regenerated in full: all27 cases returned at each small-noise/small-drift level; 1% noise returned only2/27 and5% drift returned0/27. Among returned cases,0.1% drift reached2.09% field error. These are authored finite stress conditions, not calibrated physical probabilities. Returned is not synonymous with acceptable accuracy.
