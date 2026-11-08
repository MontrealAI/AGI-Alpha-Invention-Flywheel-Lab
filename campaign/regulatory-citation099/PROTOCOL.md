# Regulatory offline replay099 — preregistered file-descriptor custody check
Date: 2026-11-08. Parent: draft PR #301 exact head `01726e7a56636085cf394fed2362ea8a5e83caf9`, stacked on unmerged PR #300, never main. This additive nonfinancial follow-up belongs to the current independent research qualification and does not change external source pins, claims, native finance, original signer, permissions, historical failures or external commerce.

## Specific bug hypothesis
`research/regulatory_portable_audit098._read_regular` checks `Path.lstat()` and subsequently calls `Path.open()`: another writer could replace the final path with a symlink or FIFO between the check and the open. The resulting file descriptor might not refer to the checked regular file. The existing synthetic symlink guard is therefore only pre-open and not atomic. This is a defense-in-depth claim under adversarial filesystem mutation, not a claim that the approved trusted POSIX exclusive-writer model was breached or that past evidence was forged.

## Before-change fixed adversarial cases
F0: unchanged regular synthetic byte input passes read and full offline packet replay; original 44 citation/offline methods remain unchanged.
F1: an ordinary final-component symlink and a symlink substituted **immediately before** the OS open must both fail closed without reading its target, regardless of whether target content looks valid.
F2: a FIFO substituted before open must be rejected without a blocking read.
F3: final-component path replaced **after obtaining a descriptor** must fail identity consistency rather than issuing accepted output based on a different final pathname. Nonhostile unchanged path passes.
F4: oversized/empty/irregular content still rejects and valid bounded content remains unchanged; no raw private or public HTML published.
F5: no weakening hardcoded source hashes, packet comparator, existing output refusal, no HTTP calls inside offline replay, no new broad visibility/issuer/semantic/commercial claim.

## Fix and stop
Open the final component with POSIX no-follow, nonblocking, close-on-exec flags; verify `fstat` regularity and before/after named-path identity on the same open descriptor while reading at most the registered upper bound. A filename race beyond the final check or hostile mutable parent path still lies outside this small claim; no broad hostile-directory guarantee. Write deterministic adversarial tests first, retain actual failing baseline, then prospectively fix without weakening tests. Run fixed targeted GitHub Actions on exact SHA and preserve failures. Stop after this finite boundary (one baseline and one prospective repair; a deterministic correctness defect may be investigated with a separately recorded amendment). No merge/release/deploy without independent full qualifications and source-owner safe boundary. No real buyers, finance, API keys, spending, paid tools, outreach, contracts, production, source redistribution or government certification.