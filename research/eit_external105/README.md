# EIT105 — independent physical-data acquisition-contract bridge (research-only)

**Current phase: source-contract preflight, no physical claim.** [Frozen protocol](PROTOCOL.md). New source differs from the repeatedly analyzed 21 FIPS EIT tank specimens. Public dataset: [Thönes, Krukewitt & Spors, Zenodo 7192883 v1](https://zenodo.org/records/7192883), CC BY 4.0. It contains physically measured 16-electrode phantom-tank voltage data (PETG geometry and ground-reference metadata); not our own physical measurements or an accepted product.

This branch only constructs the **missing independently acquired observation input** needed before another prospective Blue Sky interior-property test is intellectually defensible. The next experiment cannot claim that withholding E_01..E_16 voltages reduces injection operations; those are different units. Physically reduced acquisition requires a verified inject/measurement schedule, and source-comparable complete end-use quality must still be demonstrated against competent inverse/specialist/human-plus-software/no-test alternatives. Buyer need and complete costs remain unestablished.

## Reproduce

```sh
python3 -m unittest tests.test_eit_external105 -v
python3 -O -m unittest tests.test_eit_external105 -v
python3 -m research.eit_external105.preflight > /tmp/EIT105_PREFLIGHT.json
```

The last command retrieves only the two registered upstream files over HTTPS, verifies exact upstream file checksums and size ceilings, computes new SHA256 identifiers, and describes categories, injection pairs and group sizes without learning or predicting outcomes. Requires public network access and no credentials, purchases or external API subscription. It either succeeds with a compact receipt or **fails visibly and retains that failure**. GitHub workflow `eit-external105.yml` runs the same test on the exact PR head and retains the small JSON result, never the original CSV.

This phase does not operate the canonical business account, construct an electrical instrument, classify a specimen or add a physical acquisition. No human subjects, personal records, borrower data, customer outreach, real purchase, model API use or production deployment. Actual infrastructure and engineering monetary cost remain unknown.

**Verdict until independently qualified:** HOLD / NO BID / NO DEPLOY. Next: prospectively freeze measurement-unit holdouts, loss/abstention costs, strongest existing complete alternatives and a genuine decision/physical-acquisition budget only if the external source contract is actually verified. Do not merge a new scientific dataset probe into the nearly full enterprise release archive merely because its schema passes.
