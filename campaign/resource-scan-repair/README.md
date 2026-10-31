# Repaired resource sampling, not a new campaign result

Original public PR50/PR51 consequential007 failures were supervisor `FileNotFoundError` while statting transient SQLite journals, after 0.33/0.45 seconds, not CPU/storage exhaustion. Preserved downloaded artifact SHA256s: PR50 `bd56e3b34e2c252a450686fa52a7b45b77d6d1a979e4b2c598d52c5208cea84a`; PR51 `1503215af50efc1fca23f7cd6dcbc636caa063ed7a196d93c69a219a5936bd01`.

`resource006_v4` samples each entry once with lstat, counts regular-file and symlink bytes without following links, and skips only FileNotFoundError for an entry removed after enumeration. Other I/O errors still propagate. The same helper serves live monitoring and final receipt accounting. All CPU, wall, address-space, individual-file and aggregate-storage limits, process cleanup and conservative settlement rules remain unchanged. This remains sampled trusted-process monitoring, not an atomic filesystem snapshot, complete process accounting or a sandbox.

The v3 wrapper, original run_cycle007.py, original REPRODUCTION_FREEZE.json and published evidence remain byte-exact. The separate run_cycle007_repaired.py and REPAIRED_REPRODUCTION_FREEZE.json retain every original frozen entry and additionally bind the new driver/wrapper and old manifest. Current CI selects this explicitly repaired/exposed reproduction. The original historical release/archive path and paper-binding checks remain unchanged; no old paper is claimed to have exercised v4.

Local qualification: 12 deterministic/process/binding regressions pass, including missing-entry handling, symlink accounting, permission/EIO propagation, storage rejection, signal cleanup and frozen-source rejection. Both actually affected ASGI phases completed under unchanged 60 CPU-second/90 wall-second/128 MiB storage limits; see compact receipts. This is not the full hosted pipeline. Sole publisher must review source and execute public exact-head CI before merge qualification.

Reproduce focused tests: `python -m unittest discover -s tests -p 'test_resource006_v4*.py' -v`.
