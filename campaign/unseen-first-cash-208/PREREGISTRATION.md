# FIRSTCASH208 — independent public order-path verification (preimplementation freeze)

**Date:** 2026-11-21 UTC. **Source owner:** MONTREAL.AI, GitHub independent review. **Base:** draft PR #505 at exact `7f299640e9ad311b79b71850a9e0370aeb2984d9`; the previous FIRSTCASH207 dependent PR #506 is not edited. Financial/production owners, published release, live shop, accounts, journals, contracts, and private merchant data are excluded.

## Commercial dependency, not a flagship or an accepted sale

The already-owner-offered "FRONTIER Ω — THE UNSEEN ADVANTAGE" one-time research dossier has a named public order URL but **no independently observed outsider settlement**. Its official order-page availability and visible public product identity are unverified at this checkpoint. A source-backed specimen or attractive proof page cannot collect money if its link is unavailable or misdirected. The intended actual outcome is a verified outside buyer receiving and accepting a personalized 8–12-page dossier, funded through the *existing* merchant-controlled transaction; this preflight addresses only one prerequisite.

**Fixed URL:** `https://www.quebecartificialintelligence.com/shop/p/frontier-the-unseen-advantage`. The research script must never send credentials, cookies, form data, orders, payment requests or invented cart events. A noninteractive GET of one public URL is permitted; no referral tracker, crawl, bulk probing, outreach or account access. Do not retrieve, upload or persist customer information. Use a bounded byte cap and timeout. Record all attempted outcomes (including transport and policy errors) without retries for favorable observations.

## Prespecified three-way classification

- **PUBLIC_PRODUCT_VISIBLE:** direct public response is HTTP 200 on HTTPS with same registered host, HTML rather than error/CAPTCHA/access-block page, and a sufficiently specific anchored product identity `FRONTIER Ω` plus `UNSEEN ADVANTAGE`. Report any explicit price text as **observed unverified page text**, not as the charged amount. Public visibility is **not** checkout capability, settled payment or sales qualification.
- **PUBLIC_PRODUCT_NOT_CONFIRMED:** HTTP 200 but missing identity, parked/generic page, malformed HTML, application error, bot block, ambiguous canonical/redirect, or all other visually unconfirmed cases. This includes price-only fragments and a 200 generic home page.
- **INACCESSIBLE_FROM_RUNNER:** bounded network/DNS/TLS/HTTP failure, 404/410/5xx, rate limit, redirect off allowlist or timeout. This means **inaccessible from this runner**, not proof that a customer browser cannot access the page.

A missing or ambiguous price is `null`, not a price inferred from PR documentation or modeled economics. Explicit `2,995` page text is only a string, not proof of merchant terms, currency, successful order, merchant payout, tax or refund state. For all three statuses, `paying_customers=0`, `verified_collected_revenue=null`, `paid_checkout_verified=false`, `deployment_go=false`. No status can approve production or real commerce.

## Source-frozen acceptance before implementation

1. A standalone, dependency-free Python standard-library probe accepts exactly the registered URL and returns stable JSON without HTML, cookies, secrets, body snippets or customer data. Use a 20-second total request timeout, 512 KiB maximum body, at most 3 HTTPS redirects limited to the registered same host, and an explicit browser-like *read-only* user-agent.
2. An offline deterministic six-case suite covers valid product HTML; missing identity; a 200 generic error; 404; off-host redirect; and network exception. A seventh case covers unknown price in valid HTML. Mock transport; no network in unit tests. Both French/English wording can satisfy anchored product identity. No false checkout/merchant qualification.
3. A single hosted GitHub Actions standard public runner uses the repository mandatory 360-minute job window and first-step start marker. Run offline tests *before* one public read-only HTTP probe. Preserve JSON receipt, source SHA, UTC timestamp and byte/content digest. No automated reruns or looping.
4. Never edit owner PR #505, dependent #506, financial source/guards, branch protection, actual shop or any deployed system; do not merge automatically. Failure is durable and does not become success after changing a seed, test or interpretation.
5. **Decision:** If product visible, candidate official URL is worth owner/manual human checkout verification *when permitted*; do not make a transaction. If not confirmed/inaccessible, HOLD for buyer-path readiness, investigate with independent human browser evidence without inventing site outage. No payments can be claimed by this experiment.

**Cost and target:** GitHub included public Actions compute only; actual account-wide compute cost unknown. No added capital, orders, shipping, outreach or customer contact. US$3 billion trailing-365-day complete-cost profit remains unachieved. This is a commercial prerequisite for the existing first-dollar route, not a new profitable invention.
