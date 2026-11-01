# Phase-one provenance and attribution

This is the original phase-one logical-class-mass experiment, not phase two and
not the repository's ordinary cooperative workflows or older RSD work. It retains
useful original code and compact negative evidence; it does not claim a breakthrough.

## Source chronology

`PROVENANCE.json` binds the immutable input archive and all 14 unchanged files
copied from it. The archive itself, upstream checkout, dependencies, raw traces,
shot archives, bytecode and repeated logs are deliberately not published.

- `kernel_initial_reconstructed.py` is explicitly a **post-run reconstruction** of
  the initial kernel, not contemporaneous source proof.
- `kernel.py` adds zero-syndrome singleton moves and reusable expansion.
- `diagnostic_repair_snapshot.py` matches the recorded prelaunch repair diagnostic
  SHA256 `ad5395875ae2ba33ca79e15a132ebe59630d96f05e1b02497307315a694a1856`.
  The repair used kernel SHA256
  `adfa0655d989f3b69ee373eed0c938004f3cf1e0da7e1fd23a777de12b617358` and diversifier
  SHA256 `0f8456960b8fab9957ee2f7c481d05b121806e110bfb9533dc017a9b49a5a28e`.
- `diagnostic.py` subsequently adds fallback/failure cross-tabs. The same-seed
  replay is verification, not another independent experiment.
- Five aggregate JSON records are unchanged. `default_sanity.json` retains only
  four compact selected syndrome witnesses, not a bulk shot dataset.
- README is edited solely for public packaging, clearer commands and removal of
  references to omitted duplicate logs. All eight Python files remain unchanged.

## Original interface failure (retained, not erased)

The initial attempt prepared a kernel (0.5943 seconds; 200000 pair attempts,
1024 moves, rank 426) and then failed in `MassKernel.syndrome` while indexing
`self.h[i]`: `IndexError: list index out of range`. Its path was
`diagnostic.py -> pool -> syndrome -> self.h[i]`. Public `decode_to_errors` returns
original flattened DEM indices whereas `decoder.errors` uses retained/merged
indices. Recompiling the normalized DEM with merging disabled repaired the index
contract. A dedicated unit test and exact oracle check this. Original failure-log
SHA256: `86c7b465b237938d1f07bfea1220accff414f5e8ba7734f4ec4b1416e52b51d5`.
Local absolute paths and the redundant raw traceback are not published.

## Dependencies, circuits and licensing

The executed registry package was **tesseract-decoder 0.1.1.dev20261021032048**.
The separately inspected upstream revision was
[838d4f64acc16b5c15adda01302a719400329d4b](https://github.com/quantumlib/tesseract-decoder/tree/838d4f64acc16b5c15adda01302a719400329d4b).
These are not asserted to be identical builds. The upstream project's LICENSE is
Apache-2.0. [Stim](https://github.com/quantumlib/stim) 1.16.0 identifies Apache-2.0;
[NumPy](https://numpy.org) 2.5.4 has a BSD-3-Clause base and bundled third-party
notices (installed metadata lists BSD-3-Clause, 0BSD, MIT, Zlib and CC0-1.0).
No upstream source, circuits, binaries or dependency distributions are vendored.
The original code uses public APIs and retains external scientific attribution in
README; no license for third-party material is replaced by this publication.
No new repository-wide or original-code license grant is inferred here.

`PROVENANCE.json` records the two exact public upstream circuit paths, their SHA256
and the derived undecomposed DEM SHA256. Fetch circuits only at the pinned revision.
The circuit family is [[72,12,6]], six-round Z memory under SI1000 noise; it is not
asserted byte-identical to the Nature-paper circuits. Original scientific context:
[Bravyi et al.](https://doi.org/10.1038/s41586-024-07107-7) and
[BivariateBicycleCodes](https://github.com/sbravyi/BivariateBicycleCodes).

Installed METADATA, RECORD and WHEEL fingerprints are supplied for the three
executed direct dependencies. These fingerprint installed distribution metadata,
**not wheel archive bytes**; original wheel archive hashes were not retained.
Version pins are not a cryptographic lock of every transitive dependency.
IonQ's noncommercial licensed code was not fetched, executed, adapted or distributed.

## Retained lesson

Tried bounded same-pool mass selection plus one parity-diversification repair →
zero decision differences; repair/replay pools had exactly one logical class →
observed candidate-search starvation, with 65/66 high-noise failures on fallback →
avoid interpreting one-class pools as a test of the broader class-mass hypothesis.
Any successor needs a genuinely different class-discovery construction and a
separate protocol, not further tuning of this negative phase. The official-default
4/4 validity check diagnoses the capped search; it is not logical accuracy evidence.

Preparation, unsuccessful capped searches and fallback shots remain included in
aggregate timings. Shared-host timing is not controlled tail-latency evidence.
Host/model/engineering monetary costs are unknown, not zero; no economic value,
customer demand, hardware performance or strongest-baseline advantage is established.
