# QUÉBEC.AI publication and delivery checklist

## Current observed state

The existing shop is https://www.quebecartificialintelligence.com/shop. Its administration route presented a Squarespace login page in the available browser. No authenticated editing session or connected Squarespace capability was available. Therefore **no actual draft product, uploaded delivery archive, checkout test or product publication is recorded**. Prepared files and copy are not storefront deployment.

The intended price is CAD $299, one-time. Do not change currency, taxes, billing plans, subscriptions or merchant settings to force publication. No real test payment is authorized.

## Release gate

- [ ] Freeze the exact source revision and resolve release-blocking findings.
- [ ] Run the independent acceptance matrix and retain actual failures/unknowns.
- [ ] Verify source-bound archive inventory and whole-archive SHA-256.
- [ ] Download the published archive into a clean folder and exercise the actual application, export/reopen and documented launch path.
- [ ] Reconcile every listing claim with executed evidence, including provider live-test status and actual platform coverage.
- [ ] Confirm the version-specific entitlement and supported customer contact route.

Do not turn the current research ambitions into present-tense feature claims. Do not charge for a fully qualified edition while this gate remains incomplete.

## Draft configuration after authorized account access

1. In the existing shop, create a **Download** product and keep it in draft.
2. Paste the product name and exact English/French copy from `listing.md`. Use `listing.json` as the field map.
3. Set the regular price to **299.00** only after confirming the store's currency is **CAD**. Leave sale pricing disabled.
4. Upload the exact verified ZIP named in the release receipt. Its ASCII filename avoids download-name problems. Keep a permanent original copy outside Squarespace.
5. Add screenshots captured from the actual released application with synthetic data only. Show the mission, experiment result and evidence view; do not use a generated mockup as a screenshot or hide a meaningful limitation.
6. Verify seller/contact details, existing privacy and refund policies, tax display and checkout disclosures. Confirm their actual values; do not invent a blanket no-refund policy or promise support that is not provided.
7. Test delivery with Squarespace's supported non-charging test-order route only if the merchant can do so without disrupting the active shop. Do not silently enable a store-wide mode that affects live sales. Record whether this route is available; otherwise leave checkout qualification incomplete.
8. Open the delivered archive, verify its whole-archive hash against the approved release, and complete the customer workflow from that downloaded copy. A preview screenshot is insufficient.
9. Publish only when release qualification and the required merchant disclosures are complete. Record product URL, version, public release identity, archive digest, delivery-test result and publication time.

## Delivery constraints verified from Squarespace

Squarespace Download products take one file under 300 MB, so the release uses one ZIP. The platform provides order download links; its guide describes an initial 24-hour expiry and replacement-link behavior. Replacing or deleting an uploaded product file can affect expired-link renewal. Keep versioned source archives and test the actual customer route.

Source checked 2026-11-09: [Squarespace Download products](https://support.squarespace.com/hc/en-us/articles/206540787-Download-products). The guide's visible update was October 26, 2026. No store configuration or account-wide entitlement is inferred from that public documentation.

## Customer acceptance from the actual download

- [ ] ZIP expands successfully; all manifest hashes match.
- [ ] START-HERE.html leads directly to the local application.
- [ ] Demonstration runs without an API key or developer environment.
- [ ] French and English instructions remain coherent and accessible.
- [ ] Manual mission, model-response import and comparison work.
- [ ] Experiment results and verification limitations are understandable.
- [ ] Project export, reopen and dossier export work without data loss.
- [ ] Model connections are accurately labeled; no untested provider claim appears.
- [ ] Purchase receipt, product version and downloaded archive agree.

## Publication receipt

Record only observed values in a separate release receipt. Unperformed steps remain `NOT TESTED` or `BLOCKED`, never `PASSED`. Current product URL: **not created**. Current checkout/delivery result: **not tested**. Current publication state: **not deployed**.
