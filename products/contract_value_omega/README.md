# CONTRACT VALUE Ω — MONTREAL.AI

## The private-enterprise contract-to-cash screening room

**A locally runnable product. Not a research paper, not an agent pitch and not a claim of recovered money.**

Contract Value Ω accepts five ordinary structured exports—**contract price ceilings, invoices, independently approved billable quantities, payment postings and applied supplier credits**—and produces an executive-grade review room, an exact line-level discrepancy CSV, separately organized supplier evidence dossiers and a cryptographically bound audit receipt.

**No accounts, no model API, no vendor contact, no data upload, no new spending, and no government-procurement workflow.** It runs with the Python standard library. The business target is a private company with material recurring outsourced IT, managed-services, professional-services or contracted-labour expenditure.

**First commercial wedge:** fixed-price monthly contract terms plus independently supported monthly units. Complex tiers, tax, markups, rate amendments and time-and-materials change orders require separate verification before they can enter the audit. The tool never guesses an entitlement from an invoice itself.

### Immediate trial — real executable product

From a checkout of [MONTREAL.AI / AGI ALPHA Invention Flywheel Lab](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab):

~~~bash
python3 -m products.contract_value_omega.run \
  --input products/contract_value_omega/demo \
  --output /tmp/contract-value-review
python3 -m products.contract_value_omega.verify \
  --input products/contract_value_omega/demo \
  --report /tmp/contract-value-review
~~~

Open **/tmp/contract-value-review/index.html** in a browser. View **review.csv**, **summary.json**, **audit.json**, **SHA256SUMS.json** and the seller-specific files in **supplier_packets/**. Output is created at a **new path only**; input files are never edited. Python 3.11+ recommended, no third-party packages needed.

The included dataset is **100% fictional/synthetic**: ten invoice lines, two fictional vendors, fake contracts and intentionally inserted discrepancies. Its candidate amounts are **test oracles, not real money owed**. Never use those amounts in marketing as recovered funds.

**Simpler macOS/Linux launch:** `bash products/contract_value_omega/start.sh` reproduces the synthetic example and automatically checks its source-bound output. For buyer-owned files, run `bash products/contract_value_omega/start.sh /absolute/path/to/five-CSVs /absolute/path/to/new-output`. The second output path must not already exist. The downloadable standalone ZIP contains all required source and the synthetic demo; no system-wide installation or paid service is required.

**Executive sales assets:** [Private-company buyer proposal](BUYER_PROPOSAL.md) · [Pricing, competitor comparison and demand gates](COMMERCIAL.md) · [Software licence](LICENSE). The CAD $25,000 and CAD $120,000 offers are *hypotheses*, not sales.

**Enterprise-scale synthetic QA:** `python3 -m products.contract_value_omega.stress --lines 25000` generates a completely fictional 25,000-line, 20-supplier case with 250 planted rate anomalies, incomplete payment evidence and applied credits. The engine and its separate reconciler must agree on the **CAD 2,375** net **synthetic** review amount, split into CAD 2,000 on fully paid sample invoices and CAD 375 on incomplete-payment samples, with **zero recovered cash**. This is a capacity and financial-integrity test, not real buyer value, external demand or a peer benchmark.

### Use on authorized private-customer data

Prepare a directory containing exactly five named input CSVs. Copy the headers from the demo, maintaining the exact meaning below. Exports remain on the buyer's infrastructure unless a separate, legitimate disclosure arrangement is made.

| CSV | Required meaning | Why it matters |
| --- | --- | --- |
| **contracts.csv** | Supplier ID, service code, currency, inclusive term dates, maximum fixed unit price, *signed document/page reference* | A valid price ceiling requires buyer confirmation of the actual executed contract and amendments |
| **invoices.csv** | Buyer-unique invoice and line IDs, supplier's document number, invoice date, service month, service code, integer quantity, pre-tax unit rate and pre-tax extended amount, source reference | Computes exact billed amount and can identify exact repeated supplier documents |
| **usage.csv** | Supplier, service, month and currency, independently approved **maximum billable quantity**, original evidence reference | Proves quantity limits; missing usage causes **no invented quantity overcharge** |
| **payments.csv** | Unique payment ID, matched buyer invoice ID, amount, currency and bank/AP posting reference | Classifies paid-versus-not-confirmed exposure; incomplete ledgers are disclosed |
| **credits.csv** | Unique supplier credit memo, matched invoice **line ID**, credited amount, currency and original memo reference | Deducts already applied credits and prevents counting the same amount again |

Rules are deliberately strict. Every invoice line must have nonnegative integer quantity, a 0–2-decimal-place unit price, a line extension exactly equal to quantity × price, and a three-letter uppercase currency. No FX conversions, taxes, fees, negative adjustment lines, price tiers or "estimated" invoice amounts are silently assumed.

**Quantity interpretation matters.** The buyer must supply billable units already validated against contract terms and independent delivery or authorization data. The engine allocates that period's billable quota chronologically to nonduplicate invoice lines; this is an **allocation convention**, not a finding of which specific invoice is legally erroneous. Supplier review must resolve allocation and billing-period boundaries before any demand.

**Duplicate interpretation matters.** Only **exact whole-document repetitions** sharing supplier invoice number, currency and matching full line-item contents are flagged. Two identical charges for different legitimate services or multiple instalments do not automatically qualify.

**The engine neither reads nor interprets PDFs.** A procurement controller or authorized operator must extract source-bound contract terms into the CSV and verify amendments. An LLM may assist with preparing data if permitted, but it must not be trusted as the source of pricing rights.

### Buyer output: what can actually be used

- **Executive review room:** attractive, local, offline HTML with currency-specific totals, invoice-level evidence and explicit review gates.
- **Exact findings CSV:** line IDs, traceable source rows and document references, expected amount, candidate discrepancy, credits and payment state.
- **Supplier packets:** draft **buyer-side evidence dossiers**, never auto-sent claim letters or allegations.
- **Reconciliation certificate:** source and output SHA-256 manifest, explicit claim scope, and a second pass that independently checks line arithmetic, payment evidence, totals and report integrity.
- **Adversarial acceptance tests:** reject altered inputs, modified reports, overcredited lines, duplicate payment IDs, unsupported amounts and HTML injection; preserve unknown terms as evidence gaps.

### The only financially defensible claim

**Potential review amount ≠ justified refund ≠ supplier admission ≠ issued credit ≠ collected cash ≠ MONTREAL.AI revenue.**

The program fixes realized recoveries to **zero**; buyer-approved settlements and actual cash must be recorded outside this initial software boundary and reconciled by the customer. Source rows are **screening evidence**, not proof that executed contract interpretation, service delivery, payment records or legal remedies are correct.

If a buyer has partial payments, tax-inclusive invoice totals, different legal entities, contract amendments, tiered discounts, currencies or shared entitlements, arrange a scoped data mapping and verification first. Do not adjust acceptance thresholds after seeing a favorable result.

### Private-sector high-ticket commercial offer (hypothesis, not sales)

**Recommended productized service:** a buyer-approved, source-bound review of one large outsourced-IT or professional-services supplier, with controlled evidence preparation, independent validation, supplier-review-ready dossiers and recurring control recommendations.

- **Paid diagnostic hypothesis: CAD 25,000** for a defined sample of supplier contracts and pre-tax invoice lines, subject to actual scope.
- **Enterprise assurance hypothesis: CAD 120,000 per year** for a multi-supplier recurring assurance programme with defined service and support obligations.
- **Optional success fee** negotiated only on independently confirmed **cash/credited amounts actually recovered**, explicitly excluding existing recoveries and double counting. Performance fees and audit rights require a written customer agreement.

These are **market-test offers**, not prices accepted by customers, an indication that a company will pay them, or a prediction of profit. No customer engagement, deposits, receivables, revenue or cash has been obtained. Avoid government procurement completely.

The [commercial positioning and demand test](COMMERCIAL.md) defines the initial buyer, comparison with capable competitors, proposed acceptance and full-cost profit accounting.

### Privacy and safe operation

No telemetry, cloud processing, outbound call or stored credentials. The software writes **unencrypted** files to the specified output folder; use customer-controlled disk encryption, access permissions, backups and retention. Public GitHub PRs must contain **only the synthetic demo and code**, never customer contracts or ledger exports. Do not submit customer documents to models or external services without explicit authorization. Supplier contact and contract enforcement remain with authorized people.

### Scientific and institutional boundary

This is a **commercial implementation lane**, not a GOAL GENESIS Ω scientific breakthrough, a globally novel algorithm, or proof that MONTREAL.AI leads the AI frontier. Competent market incumbents include **PRGX, apexanalytix and established accounting/recovery-audit practices**. The product can win commercially only if an actual private buyer finds the complete outcome more attractive after accuracy, price, time, risk and full costs.

The software's strongest current asset is **local control + source-grounded review artifacts + rapid, inspectable adoption without deep ERP integration**. That is a testable commercial wedge, not an automatic moat.

**Licence:** The product software and the synthetic fixtures are available under [Apache License 2.0](LICENSE) with the [brand and service boundary](NOTICE). An external company may run the software locally, including commercially, under that licence; purchasing professional audit/recovery services is optional and separately contracted. **The software licence does not grant any MONTREAL.AI trademark rights or imply a certified audit.** No representation of professional accounting certification is made.
