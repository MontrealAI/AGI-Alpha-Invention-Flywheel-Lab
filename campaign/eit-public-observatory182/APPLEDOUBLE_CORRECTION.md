# EIT182 second-phase prospective format correction — AppleDouble metadata is not a measurement

**Only after the original trials failed**, in immutable run order:

- #44444829767: GitHub rejected new YAML syntax; **FAILED, no jobs**, repaired prospectively.
- #44445008075: 20/20 offline controls pass, but physical ingestion **FAILED** at “file signature not found.”
- #44445204158: 20/20 offline controls pass; physical ingestion **FAILED** more precisely:
  `NON_HDF5_MATLAB_MEMBER:__MACOSX/AgarCylinderPhantom/Data/._1o0_AgarCylinderPhantom_NoInc.mat:prefix=00051607000200004d6163204f532058`.
  The member’s `__MACOSX/` directory, `._` basename and AppleDouble magic (`00051607`) identify **macOS Finder metadata**, not experimental MATLAB electrode data. The actual archive was still checked against the original declared size and MD5 before it reached this error. Never relabel the failed runs successful.

## Exactly limited correction, before next executed trial

Still inspect every ZIP entry for unsafe paths, symlinks, duplicates, size expansion and encryption; **do not** waive its archive-integrity gate. Exclude from the *physical measurement case inventory only* all AppleDouble OS metadata entries where the first path component equals `__MACOSX` or the basename starts with `._`. Count and report all excluded members, and preserve their ZIP path names in the public summary if safe. Do not skip any other genuine `Data/*.mat` case, irrespective of shape, outcome, file name, apparent strength or measured voltage.

Under unchanged source and size/checksum, parse **all remaining** predeclared HDF5 cases exactly as registered; maintain the same minimum-two-case threshold and all source/cost/physical/nondeployment distinctions. If another member fails, report it with its exact name and failure rather than tuning or selecting favorable data. The prospective correction is strictly format hygiene on public source packaging; it proves no scientific or economic advantage. No changed financial source, signing, account, constraints or PR40 ownership. `HOLD / NO DEPLOY / NO BID`.
