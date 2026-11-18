# Scroll Prize research handoff

**Prepared November 18, 2026 for owner review. Current state: an identified sponsor and a locally verified result.**

## Technical inquiry

We built a CPU patch for the sparse fallback in the Reader V3 normalization work on PHerc0139. We compared it with LynnHenry’s histogram implementation. Across 24 prospectively sampled windows, summed median normalization CPU time fell from 208.27 to 92.82 ms. Two sparse windows accounted for most of the improvement. All output bytes matched both C++ controls and a separate NumPy implementation. The existing upstream patch already kept pace with the GPU on its reference machine.

Is there a representative reader installation where sparse preprocessing still delays completion? What whole-run improvement would justify maintaining the patch there? We can provide the source and a reproducible comparison that checks output TIFFs against the incumbent. [Offline tool](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/raw/a44aa8535e7899aa197d6e17f567e86547792536/docs/frontier-omega-ignition/continuation/beneficiary-pursuit/scroll-normalizer.zip) · [Measurements](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a44aa8535e7899aa197d6e17f567e86547792536/products/frontier-omega-ignition/invention/scroll_normalization/production_window/SCHEDULE_SAMPLE.md) · [Upstream issue](https://github.com/ScrollPrize/villa/issues/2522)

## Draft fields for the November programme

| Form field | Prepared response |
| --- | --- |
| Entrant name and email | The authorised MONTREAL.AI representative enters their own details privately. |
| Team description | MONTREAL.AI × QUÉBEC.AI. The team lead confirms the entrant, contributors and attribution before submission. |
| Discord identity | Optional. Use only the entrant’s actual handle. |
| Public contribution | [Download and trial instructions](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a44aa8535e7899aa197d6e17f567e86547792536/docs/frontier-omega-ignition/continuation/beneficiary-pursuit/REPORT.md) · [Source patch](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a44aa8535e7899aa197d6e17f567e86547792536/products/frontier-omega-ignition/invention/scroll_normalization/candidate.patch) · [24-window receiver evidence](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a44aa8535e7899aa197d6e17f567e86547792536/products/frontier-omega-ignition/invention/scroll_normalization/production_window/SCHEDULE_SAMPLE.md) · [Native CPU qualification](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a44aa8535e7899aa197d6e17f567e86547792536/products/frontier-omega-ignition/invention/scroll_reader/README.md) |

**Contribution text**

We worked on the PHerc0139 w054 surface volume at 9.362 µm. Sparse CT windows still trigger an expensive fallback in the exact histogram implementation proposed in ScrollPrize/villa #2521. Our patch reuses the histogram and reproduces the reference floating-point reduction order. It gives installations that are limited by this fallback a way to spend less CPU time feeding the existing ink model.

We registered a selection rule before acquiring full-resolution data, then tested 24 of the 2,116 previously unexamined positions on the 2,122-window schedule. Two nonconstant sparse windows normalized 11.93× and 12.60× faster. Including all 24 windows, summed median CPU time fell from 208.27 to 92.82 ms. The median individual ratio was 1.009×. The complete normalized outputs matched two C++ implementations, and a separate NumPy calculation verified 240,648,192 bytes. A downloadable offline checker reproduces the comparisons on a recipient’s own input.

The new capability is a faster output-preserving fallback in this implementation. We have not established improved papyrological readings, faster completion of a full scroll on beneficiary hardware, or community adoption. The paired full-workload trial below would establish whether the change helps a receiving team in practice. We credit the upstream histogram optimization and original Reader, dataset and checkpoint authors. [Strong comparator](https://github.com/ScrollPrize/villa/pull/2521) · [Data source and permissions](https://scrollprize.org/data_browser/PHerc0139)

## Recipient acceptance and payment

1. Ask the receiving team to specify its actual workload and minimum useful improvement before running the trial. Record the hardware, Reader revision, checkpoint, input volume, schedule, batch size and settings.
2. Run matched incumbent and candidate configurations in alternating order. Record all whole-run durations, input wait where instrumented, and complete forward/reverse TIFF hashes. Retain any mismatch, regression or decision to keep the incumbent.
3. If review supports practical usefulness, an authorised entrant may submit with confirmed attribution and licensing authority. The form requires a real contact, team identification and affirmative acceptance of the terms. A Progress Prize winner must make the method available under a permissive open-source license and supply payment information privately within the sponsor’s stated period. The best monthly submission has a published US$20,000 award. Review is discretionary.
4. Record the sponsor’s actual decision and any verified receipt of funds separately. The public award and CPU measurements are separate from any payable balance.

The next deadline published by the sponsor is November 30, 2026 at 11:59 p.m. Pacific. This draft has not been sent. [Official form](https://docs.google.com/forms/d/e/1FAIpQLSeB6MC_--4UCCEGc3zalX57-uE4puRcE_vJoYJCrEt4uYaaaw/viewform) · [Rules and terms](https://scrollprize.org/prizes#progress-prizes)
