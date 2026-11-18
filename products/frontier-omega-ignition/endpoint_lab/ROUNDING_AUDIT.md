# Display-precision sensitivity — optional Endpoint Lab review

**Source boundary:** dependent additive research work on PR #447 at `b10de326ae6dad744ba26aa76cd7e2ec613e09f4`. The original `decide.py`, its frozen report pack, original contract grammar, SQL comparison, recipient and public exhibition are unchanged.

## A procurement-relevant uncertainty

The official published tables print scalar values to finite decimal places. The existing decision answers the precise, defensible question *which of those displayed numbers meet this displayed-number requirement?* It must not be silently reinterpreted as a raw high-precision service-level guarantee. A printed latency of `100.0` ms could straddle a maximum of `100.0` ms; likewise a printed rate of `100.0` tokens/s can straddle a minimum of `100.0`. This supplementary, fail-conservative analysis models each positive decimal as **nearest-rounded to its last displayed place**, using a closed half-unit envelope, and asks which **already eligible** rows would meet the numerical limits at every point in that envelope.

This rounding convention is an **explicit conditional assumption**, not a proved MLCommons measurement policy or hidden raw measurement. Closed endpoints are conservative when half-step ties are unreported. It makes no inference about report independence, accuracy, real workload performance, capacity entitlement, prices, actual access or buyer demand. Failing the conservative test is *ambiguous under this assumed rounding model*, not proof the run actually failed its SLA.

## Executable recipient

From `products/frontier-omega-ignition`, with Python 3.11+ and no external packages:

```sh
python3 -B endpoint_lab/rounding_audit.py \
  --contract endpoint_study/contracts.json \
  --case interactive_gpt --output /tmp/endpoint-precision-new.json
python3 -B -m unittest discover -s endpoint_lab -p 'test*.py'
```

The output contains the full original source-locked decision, all display-supported but rounding-sensitive rows with explicit reasons, and the highest measured load qualifying conservatively. No interpolated loads, changed approval gates, new sources, remote queries or purchases. The exact original `REPORTS_SHA256` remains mandatory. The CLI uses exclusive file creation and does not overwrite previous receipts.

For the documented illustrative 500 ms P90 and 100 reported tokens/s/user GPT requirement, the published 140-concurrency point is comfortably inside both limits, so the conservative selected load remains 140. A deliberately borderline `100.0` vs `100.0` contract demonstrates why an exposed equality is not robust under the half-unit scenario.

A robust displayed-value result still **does not authorize physical deployment**. Re-measure the candidate and a strong existing alternative with actual traffic, current report status, complete infrastructure/service cost, quality checks and access rights before making a procurement or priced service decision. The direct official-table review and independent SQL are still competent alternatives; no improvement in their decision quality or cost is claimed.

## Prospective acceptance and authority

- Compare the literal source-locked answer with the new conditional conservative answer; never rewrite the original outcome.
- Test trailing-zero resolution, latency and both token-rate definitions, exact boundaries, clearly safe points, and lack of access/price evidence.
- Preserve every original endpoint exclusion and the unchanged evidence hash, and ensure the original supported load remains supported on the main illustrated contract.
- Run source-matched hosted endpoint/application and repository workflows; do not call this standalone research sidecar merged, released or financially operative until normal owner-controlled integration, publication and downloaded-byte qualification.
- No canonical financial account, private signing authority, historical study, market parameter or external transaction is touched. This cannot qualify native capital migration, buyer demand, earned reinvestment, causal model improvement or the $3B trailing-365-day complete-cost profit milestone.

**Next:** the PR #447 owner may review the sidecar on its exact base. A future product contract could offer a separate explicitly named rounding-conservative mode; do not silently change the published literal comparison or the frozen scientific study.
