# EIT183 preregistered physical-pair conventional control

Registered **before EIT183 implementation and any EIT183 physical trial**, against main `f0987aa48d5c9136b28540f54eabf5367e63bbe6`. An independent, additive read-only research arm; never alter EIT182 owner source, historical runs, the native financial account, signer, queues or liabilities. EIT182's exposed metadata and physical inventory are prior knowledge, **not a fresh hidden holdout**.

## Consequential choice, complete competitors and no deployment

Prospective beneficiary function: distinguish two specified conductivity phantom states from physical EIT readings with justified uncertainty and an end-user acceptance requirement. The actual beneficiary, reliable acquisition, clinical application and market are unestablished. Compare (A) *ordinary direct difference* on the same current/electrode patterns, (B) strong standard Jacobian/Tikhonov and modern regularized reconstruction using the original dataset's example and qualified specialists, (C) a separately constructed new/adaptive observation operation if residual ambiguity remains, and (D) no deployment. **This one trial executes (A) only** to expose its real physical signal, not a contest it claims to win against (B), (C) or (D). No billed service, human-time invention or demand assumption. D is the standing economic decision. A single positive contrast cannot imply identifiable interior properties or commercial benefit.

## Exact preselected source, all readings, no favorable selection

Public DOI https://doi.org/10.5281/zenodo.24120439. Single fixed archive URL:
`https://zenodo.org/api/records/24120439/files/AgarCylinderPhantom.zip/content`.
Expected 12,482,688 bytes, MD5 `658694f69f64075b6fefec2e2c597131`, source ZIP SHA256 `42fa038c0c1b4d5bb5769f4d8a8575eef300e8eef559137767e5ab0bb1bd9f70` (independently observed in EIT182 public push run #44445681522, artifact #14493351292).

Two, and only two, preselected original HDF5 members:
- `AgarCylinderPhantom/Data/1o0_AgarCylinderPhantom_NoInc.mat`: SHA256 `79c43b785433d63e8d1e7eed36348843799bb38825ac885da46b21b41e0a7739`.
- `AgarCylinderPhantom/Data/1o1_AgarCylinderPhantom_2Incs.mat`: SHA256 `db85fed3dc66973373a4e26a3ed33f9d0cc43d51b8367ff893a357487a5b1ddf`.

EIT182 reports both `currents_matrix` and `voltages_matrix` are shape `[79,16]`, float64. Use *all* elements and channels. Source labels aren't an independent measurement of material truth, operating conditions, units or measurement errors. No raw archives committed.

## Registered trial and stopping conditions

1. Stream bytes from exact HTTPS URL on standard free public GitHub runner using no credentials. Reject final non-Zenodo host, wrong compressed size/hash, unsafe archive paths, duplicate names, symlinks, encrypted entries and overlarge expansion. Verify the two selected raw-member SHA256 checksums. Read exact numeric finite `[79,16]` float64 HDF5 arrays using pinned numpy==2.3.5 and h5py==3.15.1.
2. Require exactly identical case current matrices via `np.array_equal`. If currents differ or measured voltage baseline is zero, the pairing fails closed; never claim a controlled difference. If voltage contrast is zero, record failure rather than sample another favorable case.
3. Under matched currents, ordinary difference `D=V_two_inclusions - V_no_inclusions`. Report complete-data `||D||2`, its RMS, its coordinate max, `||D||2/||V_no_inclusions||2` and every one of the 16 column RMS contrasts. No reconstruction, fitted model, selected channel or image.
4. Report a *hypothetical* sufficient per-coordinate absolute-error bound `epsilon_star=||D||2/(2*sqrt(1264))` for two separate additive-error acquisition vectors. Only independently validated per-reading error strictly less than epsilon_star under this error model would support that particular simple norm-based separation guarantee. No actual noise, repeatability or sensor calibration evidence is supplied.
5. One physical pair, one registered trial. Never retry until favorable or change thresholds post hoc. Execute adversarial synthetic unit tests and independent hosted replay, report observed resources and preserve failed logs. Actual model/host billing remains UNKNOWN.

**Pass tier:** real public archive bytes and source-bound *ordinary baseline* paired numerical contrast, conditional math only. **Not established:** physical reconstruction, new information operation, strong-complete-alternative advantage, causal successor, sensor error qualification, beneficiary acceptance, real commercial revenue, complete profit or $3B T365. Verdict always `HOLD_NO_DEPLOY_NO_BID`. Keep historical failures. No financial writes, physical actuation, outreach, paid model APIs, credentials or production deployment.
