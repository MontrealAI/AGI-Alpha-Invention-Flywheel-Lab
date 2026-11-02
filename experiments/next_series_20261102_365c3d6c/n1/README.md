# N1: water provenance dependency

**Decision at source freeze: the supplement repairs a retrieval gap, but the public quality adapter remains unsupported. Fresh-date sampling has not started.** This finite dependency investigation is separate from N3 and does not reserve future physical investment.

## What changed

The public [supplement](https://static-content.springer.com/esm/art%3A10.1038%2Fs44221-024-00314-6/MediaObjects/44221_2024_314_MOESM1_ESM.pdf) was retrieved successfully: 1,634,588 bytes, SHA256 `97f37f427764ff8cee536aa22f4b340dfcd8382d6993e1ca9e32f055e2239f61`. The earlier W1 HTTP503 remains its historical retrieval outcome. It was never evidence that a supplement did not exist.

Two independently inspected pages now provide useful engineering context:

- **Table S1, PDF page 7 / printed page 19:** nine process states, including state 3 pre-fill with reversal and state 7 drain diluate with the product bypass on; sensor/actuator specifications; 100 ms PLC sampling. The outlet conductivity model is Sensorex TCS3020, with 2 s averaging. Its maximum stated range is not its installed calibration span.
- **Figure S2C, PDF page 8 / printed page 20:** process routing and multiple conductivity locations. Numbers 1 through 10 label valves. They do not identify the four numbered archive conductivity channels.

The source manifest retains these facts and their limits. A state diagram does not supply the archive state tag, a batch-release event, the installed sensor calibration, or the mapping from `conductivity1_DS` through `conductivity4_DS` to a physical stream. No channel was selected by low readings or favorable correlation.

## Constructed artifact and frozen controls

`adapter.py` emits a source tag, physical-stream identity, unit, temperature basis, calibration basis, clock interval, operating-state provenance and batch association. Missing evidence propagates `UNKNOWN` and `HOLD`. Quantity remains a separate unqualified counter observation. Unknown quality-qualified volume is `null`, not an assertion of zero physical production.

The public adapter is deliberately not admitted at this source version. It cannot accept physical water, even if a caller supplies favorable measurements or alleged release metadata. Admission would require independently supported sources, a genuine intended-use proxy contract and a new prospective registration.

`CONTRACT.json` freezes **28 authored implementation controls**: four unidentified public-channel cases, one completely specified synthetic positive control, and 23 targeted adverse controls. They cover wrong stream, units, temperature basis, reset, reversal, stale calibration, clock offset, missing release, batch-boundary gaps, mixing, nonfinite/missing data, premature release, recycle flow, measurement uncertainty, unknown tag, nonmonotone timestamps and empty/wrong-typed provenance. Independent static review identified the malformed-provenance gap before execution; the frozen suite includes six targeted checks. Each adverse case must produce its specific reason; an unrelated HOLD is insufficient. The synthetic positive control must pass at **model-only** scope, so an always-HOLD implementation cannot pass the suite.

The synthetic conductivity threshold and timing values are authored test inputs. They are neither a proposed water-quality standard nor a threshold selected from sensor outcomes. The complete model fixture may report model-qualified volume; every result retains `physical_admission: false`. Authored case frequencies estimate no physical error probability.

**At this freeze the suite is prepared and unexecuted.** After the coordinator publishes the source/preregistration receipt, run once from repository root with a new attempt-specific destination:

```sh
python3 experiments/next_series_20261102_365c3d6c/n1/challenge.py --output /absolute/new/n1-attempt-1.json
```

The runner records its source hashes, full denominator, every outcome, process CPU and wall time. It refuses to replace an existing result file. The independent verifier must check provenance and implementation separately. Shared-host procedural independence is not an external laboratory.

## Preserved W1 denominator

`ORIGINAL_W1.json` is a compact transcription from immutable predecessor `a5df603854f98cbd673204258c8d768e0c759975`, with SHA256 identities for the source reports, result and independent verification files. It does not change their acceptance rules.

| Original date | Observed counter increment, L | Original 1,000 L/day quantity result | Quality |
|---|---:|---|---|
| 2022-08-15 | 5,570 | Conditional pass with cyclic buffer | HOLD |
| 2022-09-15 | 1,060 | Conditional pass with cyclic buffer | HOLD |
| 2022-10-15 | 360 | Insufficient | HOLD |
| 2022-12-15 | 2,660 | Conditional pass with cyclic buffer | HOLD |
| 2023-01-15 | 0 | Insufficient; cause unresolved | HOLD |
| 2023-02-15 | Missing | Abstain; three-byte file retained | HOLD |
| 2023-03-15 | 0 | Insufficient; cause unresolved | HOLD |

These are historical W1 inputs, not N1 fresh observations. The coordinator separately reproduced W1's eight unit tests and 48 independent LP comparisons; this N1 source freeze claims no new physical quantity qualification. Initial fill, terminal stock, spills, recycle distinctions and subhour uncertainty retain their original scope.

## Finite retrieval and stopping rule

The completed source-discovery phase is explicitly exploratory: publisher/DOI routes, direct supplementary bytes, public Figshare metadata, manufacturer documentation and bounded exact author/code searches. Its actual transport outcomes are recorded in `SOURCE_MANIFEST.json`. No daily sensor CSV was downloaded for N1.

The newly located [2026 MIT thesis](https://dspace.mit.edu/entities/publication/bec7ff50-942f-44af-aa01-46868098c735) has been inspected only at metadata level. Its full text is **uninspected**, so this result is not a claim that every public source lacks a tag dictionary. A namesake public account is not evidence of the authors' source repository. The present finite dependency investigation stops without exhausting the thesis route; this limit remains visible.

Fresh-date selection is **NOT STARTED: prerequisite stop**. There is no selected fresh denominator, no new-date quality/volume chart and no replacement of missing or zero-output days. The metadata-only future selection rule in the contract is a prospective specification requiring a new admitted adapter and frozen proxy before any measurements are retrieved.

The observations most likely to change this stop are: an authoritative numbered-channel/stream/units dictionary; installed calibration and temperature-compensation records; archive clock/state semantics; authenticated batch identity, mixing and release transitions; and a source-supported one-pass product-counter conversion. A source-grounded non-potable proxy also needs its own intended-use envelope and coverage/uncertainty contract. Conductivity does not establish excluded contaminants or potability.

## Economics and retained lesson

No native account, sale, physical output or financial trajectory ran in this dependency stage. Included research and execution still consume resources; complete model/tool/host costs, specialist reconstruction time and later plant economics remain unknown. A conventional specialist receives the same public sources and may use the same reconstruction and stock tools. No labor-saving or technical-superiority claim is made.

**Tried → outcome → lesson → next:** retrieve the missing process supplement → state definitions and instrument specifications recovered, archive identity/calibration/release links unresolved → retain provenance-preserving failure propagation and the stock constructor, with separate quality and quantity → inspect the named missing source/instrument only when its expected decision impact warrants another finite stage; otherwise redirect investment.

Primary data credit: **Bessette, Pratt and Winter**, [Figshare dataset DOI](https://doi.org/10.6084/m9.figshare.24991158), CC BY 4.0. The published FCCC controller is prior art, not an AGI ALPHA invention. The source PDFs and bulk archive are linked, not redistributed here.
