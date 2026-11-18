# FRONTIER Ω IGNITION · simulated beneficiary decision

**Reference decision: keep the incumbent. Simulated receipts: US$0.** This exercise was run separately from the operating mission. We did not contact a maintainer or perform an authenticated financial operation.

## Replay of the mission

| Stage | What happened |
| --- | --- |
| Sense and select · observed | The engineering team supplied evidence for three opportunities. The ranked worker rejected a contested routine repair, selected a cheap test of Google’s quantum competition objective, then advanced to the scroll reader when the scored quantum resources tied. |
| Invent and verify · observed | The team developed a faster sparse normalization fallback and used the worker to build, compare and export it. In 24 prospectively sampled real windows, CPU time summed over per-window medians fell from 208.27 to 92.82 ms. Two windows accounted for 98.73% of the saving. Two C++ controls and a separate NumPy calculation agreed on every output byte. |
| Deliver · simulated | A maintainer receives the ZIP, reproduces its controls and asks what changes for a complete reader on their machine. The example maintainer values a 3% whole-run reduction with identical TIFFs. That threshold and response are invented scenario inputs. |
| Test the buyer’s outcome · simulated | Start with LynnHenry’s measured 41.2 seconds per w054 reader run, including 3.7 seconds of GPU input wait. Assume one quarter of that wait can benefit from the component gain, no new overhead and identical full-reader TIFFs. Projected wall time is 40.69 seconds, a 1.24% improvement. |
| Capture · simulated | The reference maintainer retains the existing implementation. There is no accepted offer, paid deployment, prize submission or award in this scenario. No positive demand or award probability is assumed. |
| Learn and repeat | Keep the reusable patch and full comparison method. Ask a future recipient to measure worker-ready times, GPU batch starts and complete-pipeline output and elapsed time. Reopen the commercial hypothesis when those measurements show meaningful exposed cost, scarce capacity or a valued turnaround constraint. |

The two sparse cases were schedule indices 22 and 30. They could both affect the first 32-patch batch if loader ordering preserves the analyzed schedule. The sample covers one scroll surface. Cache state, batching and overlap may hide a speedup or make it cross a discrete queueing threshold.

## Sensitivity of the full reader

The exposed share is the assumed fraction of the measured 3.7-second wait to which a 55.43% component reduction transfers proportionally. The model holds everything else constant. Actual queues and overlap can behave nonlinearly. The upstream contributor measured an RTX 3080 and compared three complete runs. Their separate loader-throughput experiment used a different scroll surface and is excluded from this calculation.

| Assumed exposed share | Modeled whole-run time | Reduction | Modeled value at 10,000 runs and US$1 per genuinely avoidable machine-hour |
| ---: | ---: | ---: | ---: |
| 0% | 41.20 s | 0.00% | $0.00 |
| 25% | 40.69 s | 1.24% | $1.42 |
| 50% | 40.17 s | 2.49% | $2.85 |
| 100% | 39.15 s | 4.98% | $5.70 |

For a 3% target, this model requires 60.3% of the observed input wait to benefit before accounting for new overhead. The 100% row can justify a paired beneficiary trial under the hypothetical threshold. Adoption and an award are independent decisions. With an assumed 0.25 seconds of new overhead and all component savings hidden, the modeled run instead takes 41.45 seconds. On fixed-cost hardware, a shorter job can save zero cash. At the reference assumptions, an illustrative $250 adoption cost requires about 1.76 million runs to recover from avoidable machine time alone.

## Value capture

The organizer’s November programme offers a discretionary US$20,000 best monthly submission. Winning requires sponsor selection and appropriate licensing. The organizer favors practical adoption. A prize is a one-time award, with no evidenced probability for this contribution. Neither sustained product demand nor repeatable sales follows from winning.

All figures in the sensitivity table are conditional calculations. The measured sources are the [upstream full-reader trial](https://github.com/ScrollPrize/villa/pull/2521), the [24-case comparison](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a44aa8535e7899aa197d6e17f567e86547792536/products/frontier-omega-ignition/invention/scroll_normalization/production_window/SCHEDULE_SAMPLE.md) and the [organizer’s criteria](https://scrollprize.org/prizes#progress-prizes). [Unsent draft of the actual form fields](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/92cc5cf39c891e38aad7c01ccc0069c24be5f743/docs/frontier-omega-ignition/continuation/beneficiary-pursuit/SCROLL_PRIZE_DRAFT.md)

## Reproduce the simulation

From the repository root on this evidence branch, use Python 3 and the measured sample included in the checkout.

```sh
simulation=docs/frontier-omega-ignition/continuation/beneficiary-pursuit/simulation
sample=products/frontier-omega-ignition/invention/scroll_normalization/production_window/sample
python -IB "$simulation/simulate_commercial_route.py" "$sample"
python -IB "$simulation/simulate_commercial_route.py" "$sample" --exposed-share 0.75 --hourly-value 3 --runs 5000 --overhead-seconds 0.1
```

[Saved base case and sensitivity results](reference-scenarios.json)

### Conditional paid-pilot rehearsal

A separate fictional customer agrees to a $250 pilot, reports acceptance and delivery of the real offline checker, and supplies a simulated payment record. In a disposable journal the actual release-candidate program advanced through six stages. A mocked provider returned $250 gross, an assumed $8 fee and $242 available before labor, taxes or support. Those are invented fixture amounts. This demonstrates the software behavior conditional on a sale; it gives no evidence that Scroll Prize or any private customer would buy. The check contacted no provider and used no live account or real credentials. The separate no-award branch records $0. [Isolated receipt](hypothetical_pilot_receipt.json) · [Reproducer](simulate_private_pilot.py)
