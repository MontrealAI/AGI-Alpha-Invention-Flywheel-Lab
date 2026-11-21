# OPEN-DEMAND211 — public procurement evidence, not presumed buyers

An independent, additive market-evidence experiment for MONTREAL.AI's Blue Sky mandate. It creates an executable read-only observer over the **UK Find a Tender** official public OCDS API. The UK government publishes notice data under the Open Government Licence v3.0; attribution appears in the receipt. [Government source and API description](https://www.gov.uk/government/publications/open-contracting).

It competes with **existing free official procurement search**, competent analysts and no purchase. It does **not** establish an economic advantage or a customer. This is separate from FIRSTCASH206–210 and protected native-finance PR40. All remain independent; no account/queue/cash changes.

## Run

From this branch's exact source:

    python3 -B -m unittest -v tests.test_open_demand211
    python3 -B tools/open_demand211.py fetch --out /tmp/open-demand211-new
    python3 -B tools/open_demand211.py verify --out /tmp/open-demand211-new

Live fetch makes **one** public HTTPS read of \`https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?limit=2\`, no credentials/cookies/redirect/retries, 15s, maximum 512 KiB. Source bytes stay in SOURCE.json locally and, if available, in the short-lived CI artifact for offline independent byte replay. RELEASE, checkout, customer data and private accounts untouched.

## Conservative results

Each notice includes source IDs, published buyer/title, declared stage, explicit active status, timestamped future deadline, declared value if present and refusal reasons. Only a record meeting **all** requirements is marked \`REVIEW_ELIGIBILITY_ONLY\`. Overall operation remains \`HOLD_NO_BID_NO_DEPLOY\`. Unknown costs remain unknown; GBP notice values do not become awarded work, revenue, commitments, bids, payment, opportunity advantage or spendable funds.

**Four distinct choices:** current C$2,995 company-decision dossier; source-bound public-tender observation; hypothetical recurring notice-intelligence capability; NO DEPLOY. The first two face strong free/human-plus-software alternatives, and none have observed profit. Only authentic voluntary buyer payments, independent accepted output, full costs and repeat results could establish commercial fit.

Source freeze: \`8cd41b11dc0fe8dd64b0ab7000fc7296b4b77ce7\` registered before implementation. Historical release outcomes, failures, P0 finance custody and $3B T365 objective remain unchanged.
