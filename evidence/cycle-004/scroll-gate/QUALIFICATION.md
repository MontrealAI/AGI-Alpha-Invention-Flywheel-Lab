# Independent data and baseline qualification

Role: separate verifier; read-only source and metadata audit on 2026-10-29 before 20:17:53 UTC. No candidate code or candidate outputs inspected, no truth pixels opened, no model executed by this verifier. Shared host and previously published benchmark outcomes are not a physical isolation or a fresh blinded corpus.

## Qualified physical reference, with a registration reservation

The strongest located tiny real fixture is PHerc0343P segment `20250511003658`, an opened fragment with two lines of physically photographed ink. Author Domenico Russo states that the Vesuvius Challenge team made the 1050nm infrared photograph, registered it to the 2.2um front-surface render, and traced the letters on that photograph. The author transfers that reference onto the 8.64um/116keV CT surface volume. This is independently observed ink at origin, unlike the many benchmarks whose reference is a finer-scan model map. It tests an exposed fragment, not newly read text inside an unopened scroll.

Pinned source: `DomRusso2/ir-truth-9um@7e96b969d3a1407504db4826543136573bda78b8` (README blob a7d7ff8879b1246d3ca13b54cf9712934927b106; carry_labels.py blob 475bb2148a2f32fb0d20b7451a1e088282744190; score_map.py blob 2e333242344d203e8a9df99e8bd565e9d0ed59e5).

The exact CT URL is `https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/PHerc0343P/segments/20250511003658-tifxyz/surface-volumes/8.64um-1.2m-116keV-volume-20250521134555.zarr`.

Anonymous `.zattrs` and `0/.zarray` were successfully fetched. Metadata confirms uint8 ZYX shape [31,3440,2060], chunks [31,128,128], no compression, isotropic 8.64um sampling, and source CT identifier `SCROLLS_TA_HEL_4.320um_1.0m_116keV_binmean_2_PHerc0343P_TA_0001_masked.zarr`. Full logical array is 219,678,400 bytes; a padded chunk is 507,904 bytes. A crop aligned to a few 128px chunks avoids a full corpus download. Surface volumes are already rendered geometry-conditioned CT, not raw whole-scroll CT.

Truth files in the pinned commit: truth_ink.png 25,880 bytes, truth_noink.png 77,314 bytes, valid.png 31,617 bytes; Git blob IDs are preserved in sources/IR_FILE_METADATA.json. These are not SHA256 hashes, and pixels have not been downloaded/inspected in this qualification.

Registration is not independently certified here. The saved pose has `numeric_pass:false` and `shift_on_edge:true`, despite README claims of a second registration route. It records scale .246, rotation 2deg, row offset 0, column offset -21, silhouette IoU .8837287, CT-texture NCC .5012294; 100px-shift NCC controls .1762015 and .0862410. The README claims letter-level error 10–80um and strokes 350–580um wide, and expressly disclaims stroke-edge precision. The meaning of the failed numeric flag is not explained by the released scripts. Do not silently call it PASS, or call the whole fixture invalid merely from the unexplained flag. A candidate result must disclose this reservation or independently confirm registration from non-ink geometry/texture before a precise physical claim.

## Executable incumbent and leakage

`inksweep/inkbench@b391e2f94dc5564f9c7abe939f6f4030c15652ac` specifies the camera-truth scorer and already implements exact canvas-map label transfer versus plain-resize controls. This mapping corrects a known ~7.4px/70um offset for 2.4um-to-9.4um canvases. Reimplementing that correction is not a new invention. The IR registration pose is a separate route, not an automatic application of the canvas-map identity.

Published source training configurations include the exact IR segment for Reader v2, Reader V3 and d9v4C. Hecate training membership is UNKNOWN. The IR paper author reports v8-in never trained on this fragment; benchmark catalog only has partial per-scroll disclosure for v8-in. Preserve the distinct strength of these statements. A local Hecate improvement on this fixture cannot establish unseen-scroll generalization. Existing Reader V3, v8-in, Hecate and their published maps are stronger comparisons than a mean-intensity or resized teacher pseudo-baseline. The published whole-fragment comparisons already demonstrate real ink detection, so a positive detector alone is not a previously unavailable capability.

The local upstream Hecate source and metadata identify HF revision `9cb86e500e944b11a06a7020403cde5dffb5bcb2`, 9.6um geometry [16,64,64], ordinary 2D attention projection and an existing 3D-logit path. Joint depth/ink claims must compare to those complete paths and equally resourced depth-sweep/aggregation alternatives. Hecate is not merely a 2D unrelated weak incumbent. Actual 8.64um CT must be resampled consistently to the trained 9.6um grid; the official CLI rejects >2% spacing mismatch. Correct depth order, central-plane selection, intensity normalization/divisor255, native-canvas backmapping, support mask, padding, overlap and uint8 score quantization are part of a fair complete baseline.

Full inkbench requires Linux/final CPython3.14 and an NVIDIA GPU for all readers. Its scoring runs on CPU; all-reader input/cache allocation is ~30GB plus ~55GB prediction maps. This host's CPU-only runtime cannot be declared qualified for the full benchmark simply because packages import. A tiny fixed CT crop may be constructible, but requires a timed real-forward smoke test and a projected runtime before freezing. Published maps can supply an incumbent on the same crop; they do not constitute a newly executed baseline.

## Frozen-outcome constraints for later confirmation

Before truth exposure, pin source bytes, crop coordinates selected without ink outcomes, resampling/depth conventions, candidate, strongest executable baseline, budget, effect criterion, and terminal outcome. A crop containing no ink/clean class is not an AUC test; any truth-based crop selection is development exposure. A tiny crop cannot inherit the whole-fragment random-placement p-value: 250px minimum shifts and 80% mask retention may be impossible. No new statistical claim should be manufactured from correlated pixels. A diagnostic comparison with matched pixels and a spatially disjoint confirmation is stronger; small-sample reservations remain.

The upstream masks are positive letters eroded 2px; clean class is valid photographed papyrus >=12px from letters and brighter than the median IR intensity; valid support is fragment mask eroded10px intersected with the central CT layer. Unknown/untraced faint ink is not assigned negative truth. Upstream quantizes maps using their 0.1/99.9 percentiles over the fragment and tie-aware AUC. Applying this normalization independently to a crop changes the protocol and must be declared. The released scorer's 2,000 translations are a within-fragment alignment test, not a method-ranking or unseen-scroll significance test.

## Terms and demand boundary

The scoring code is MIT. Source data and maps follow Vesuvius Challenge terms; the official data portal `https://scrollprize.org/data` currently specifies CC BY-NC4.0 unless asset-specific terms differ. This is a public research fixture; neither its availability nor a challenge prize establishes a buyer invoice or permission for commercial reuse. No new terms accepted, account created, spending, outreach or remote mutation performed.

Verdict: REAL_PHYSICAL_REFERENCE_CONDITIONAL_ON_REGISTRATION; TINY_CPU_EXECUTION_NOT_YET_TIMED; STRONG_EXISTING_DETECTORS_PRESENT; GENERALIZATION_NOT_ESTABLISHED. This qualification is not a candidate result.
