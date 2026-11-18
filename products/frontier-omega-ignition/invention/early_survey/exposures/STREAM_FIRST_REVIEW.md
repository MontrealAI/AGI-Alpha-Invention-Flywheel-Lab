# Independent reference-stream precedence review — 18 November 2026

**Frozen owner source:** PR #451 `ffd8a0ebf1000173ca2446b9475be128463d6c17`; portable original source blob `eb02cfed39cac262b3ff1ee41ae07ef66ce7d5b6`. This is a dependent, synthetic test and prospective correction only. The original archived receipts, science measurements and beneficiary conclusions stay unchanged.

## Scientific rule and defect hypothesis (registered before modifying implementation)

The original public ZTF notice requests the **first eligible subsequent measurement in the same detector/reference-processing stream** (matching band, field/readout/reference image and registered time). In `invention/early_survey/exposures/verify.py`, the ALeRCE projection currently orders *every* detection with the same band in the window before comparing the first one against the qualified packet. A distinct reference-processing stream of the same object and band, arriving earlier, could therefore cause `ambiguous or missing first alternative-broker witness`, even though the registered same-reference first witness remains valid. Such a hypothetical extra detection is **not** evidence the public archive contains one.

Freeze two deterministic offline controls before repair:
1. **Different-reference earlier candidate.** Duplicate the published g-band projection row in memory only; give the duplicate a unique candidate ID, an earlier October 27 MJD inside the original window, and another reference ID. Leave both original ZTF Avro packets, the pinned acquisition index, original source files and every published receipt unchanged. The public eligible g/r outcomes must remain byte-for-byte identical to the registered final `RESULT.json`; a different reference must not preempt the same-reference candidate.
2. **Same-reference earlier candidate.** Repeat with the original g reference ID. Without its separately source-qualified original packet, the receiver must continue failing closed on ambiguity, not silently skip it or accept the later packet as first.

The one-line candidate correction is to restrict the ALeRCE first-candidate precedence list to the original notice's immutable `rfid` before sorting and validating the packet, preserving all original packet, geometry, timestamp and calibration checks. The test replaces only the in-memory broker projection returned by `inputs`, not an authoritative downloaded source or an archive index; therefore it establishes only controlled software behavior and cannot prove that such an alternative stream exists or that archive access is complete.

## Publication and integration boundary

Run unchanged published-source tests plus the new adversarial tests on the **exact dependent head**. A full CI result is reported separately; a focused success does not turn any failing workflow into a pass. PR #451's original owner keeps the integration, release and production decisions. No native financial source, account, credential, queue, liability or historical allocation is in scope. No paid model calls, outreach, physical observing or real transaction.
