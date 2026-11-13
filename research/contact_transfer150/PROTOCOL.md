# Contact-transfer metrology 150 — pre-code registered discrimination

**Registration date:** 2026-11-13 UTC. **Base:** 240e8d7f3497294636a5afc1d65253692f38e2e4. **Owner:** independent Blue Sky offline scientific instrument research; not the original native-account or physical-device owner. No physical actuation, purchases, data collection, customer claims, account access, merge, or deployment.

## Decisive dependency

The existing [Blue Sky 064 fixed mixed-geometry registration](../../campaign/blue-sky-064/friction-probe/MIXED_REGISTRATION.json) requires an **increase in static-hold/dynamic-slide ratio of at least 0.05** from two indentations (0.01 and 0.10 mm). The earlier nominal calculation reports 0.17212125749, but original independent coefficient-interval test can fail and transfer of isolated contact calibration to a mixed physical surface is unverified. Blue Sky 101 investigates a conditional geometry-only no-go. More nominal geometry search is not the appropriate next physical step.

**Construct:** a *measurement-uncertainty contract*, not a synthetic-success certificate. On four strictly positive, two-load force measurements (static and dynamic at each load), compute conservative exact/decimal ratio intervals from explicit nonnegative absolute force-error bounds; certify the inequality only within that declared error model. Reject missing provenance declaration, malformed/duplicate JSON keys, NaN, infinity, nonpositive dynamic lower bound, missing values, missing units, negative bounds, ambiguous ordering, or unsafe paths. This tool cannot certify that measurement error bounds were actually validated, that force observations were physical, or that the material performed as modeled.

## Frozen finite acceptance and comparison

- Standard-library-only Python 3.12; input JSON limited to 64 KiB, two states with distinct predeclared indentations (0.01, 0.10 mm), nonnegative errors smaller than nominal force, explicit force unit N, velocity 0.1 mm/s, source declaration and per-record trace provenance.
- Floor/ceiling of ratio at each indentation use (Fs−es)/(Fd+ed), (Fs+es)/(Fd−ed); lower bound for increase uses high-load lower ratio minus low-load upper ratio; upper bound is converse. Reject if all 4 force errors were not declared.
- Threshold fixed at 0.05. Output verdict CERTIFIABLE_WITHIN_DECLARED_NUMERIC_BOUNDS only if the lower bound >= 0.05; otherwise HOLD. Neither verdict equals physical qualification or acceptance of a customer outcome.
- Demo only: replay the published **source-model** nominal predicted force magnitudes, not acquired sensor measurements. For a hypothetical uniform independently bounded relative force-error fraction eps, calculate precision boundary by deterministic bisection within 0..0.1. Precommitted expected boundary ~0.0280, pass at eps=0.02, fail at eps=0.04. This tells an experimenter how tight a justified error envelope would need to be *if the nominal force model were realized*; it does not validate future actual uncertainty.
- Include 12+ adversarial regressions (inclusive threshold, zero error, nonfinite/negative/zero dynamic, duplicate keys, wrong units/velocity, equal or reversed loads, missing provenance, non-observed demonstration label, monotonic uncertainty widening, hash-binding/tampered source and no physical-claim escalation).
- Compare four options with no commercial promotion: (a) no additional measurement/geometry-only (conditional no-go unresolved), (b) paired mixed-surface force measurement and validated uncertainty (instrument proposed, no data), (c) complete conventional passive/active mechanical route (still feasible), (d) NO BID/NO DEPLOY.
- No holdout reseeding or new third-party measurements. Total results are a deterministic single preregistered calculation; preserve negative inputs. Finite bounded size/time. No inferred device cost, buyer, supplier, annualized profit, or discovery-process gain.

## Stop and fail regions

The campaign stops after the registered source-model preflight, adversarial regressions, and one source-matched hosted qualification. Missing real measurements, physically traceable error envelopes, multiple velocity/load validation, independent mixed-surface transfer and a beneficiary-specific complete-alternative comparison keep the physical/product/commerce verdict HOLD. All historical interval failures remain unchanged. Do not turn the synthetic example into a demand/profit observation. This new independent branch does not modify any native financial source or account.
