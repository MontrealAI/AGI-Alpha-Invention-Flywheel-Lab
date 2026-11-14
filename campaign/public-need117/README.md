# Public Need 117 — conservative perception-methodology audit prototype

**Status:** independently counted local engineering demo, not a DFO proposal, customer delivery, supplier qualification, population inference, paid demand, or Blue Sky flagship. Constructed to investigate a *publicly expressed* methodological-audit need; no government or customer data was obtained.

The instrument takes a source-bound sample of **already labeled** binary perceptions, computes observed subgroup errors, explicit missing/abstained counts and Wilson intervals, and exports an offline accessible HTML table plus JSON. A separate reviewer independently re-counts the underlying CSV and rejects altered source, counts or invented commercial/population claims. A competent statistician with conventional Python/R and BI tools can do the same work; no algorithmic or commercial advantage over that incumbent is claimed.

## Run (Python standard library only)

From the repository root:

```sh
cd campaign/public-need117
python3 -m unittest -v test_interpret
python3 interpret.py --csv demo.csv --output /absolute/new/need117-output --role EXPOSED_DEMO --label-review UNVERIFIED --population-frame UNKNOWN
python3 verify.py --csv demo.csv --report /absolute/new/need117-output/RESULT.json
```

Use a **new absolute output directory** (must not already exist). The eight `SYN...` rows are intentionally synthetic. `RESULT.json` and `dashboard.html` are reproducible engineering artifacts; no buyers or real social-opinion observations are in the fixture. The label-review and heldout role flags are merely operator assertions. Population representativeness, causal effects, external validation and the actual buyer's acceptance **remain unknown**.

**Security/financial boundaries:** no network calls, external APIs, signing materials, billing, personal records, enterprise-account writes, contractor outreach, submissions or transactions. This prototype does not satisfy mandatory RFP criteria until the actual original RFP, valid supplier experience, data rights, independent labels, delivery costs, privacy obligations, maintenance, complete reporting and documented acceptance are reviewed.

The three public opportunity alternatives, strong incumbents, NO BID decision and source limitations are recorded in [PROTOCOL.md](PROTOCOL.md). This is intentionally not a pre-code preregistered study; prospective paid/commercial evidence has **not** occurred.
