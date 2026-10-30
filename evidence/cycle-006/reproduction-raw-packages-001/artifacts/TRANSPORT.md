The two original complete raw ZIPs exceed the GitHub connector's request limit. Their exact bytes are distributed as four and five indexed parts, each at most 6 MiB. The original per-file manifests and whole-ZIP identities remain unchanged. Original ZIPs remain intact locally and in the earlier local Git commit; they are not separately stored in the latest tree.

Reassemble into a new output path from the repository root:

```sh
python scripts/reassemble_evidence006.py --index evidence/cycle-006/reproduction-raw-packages-001/artifacts/connected-reproduction-001-parts/INDEX.json --output /tmp/connected-reproduction-001-complete-raw.zip --expected-sha256 cb9e8608a89318f29bc309e3f0dea024793e56dcefdedeb16e87a4fb69bd4054
python scripts/reassemble_evidence006.py --index evidence/cycle-006/reproduction-raw-packages-001/artifacts/connected-reproduction-002-parts/INDEX.json --output /tmp/connected-reproduction-002-complete-raw.zip --expected-sha256 2d4d4f6fb08a930a380828bd8dce6edb5175f103babc6f42b640fef7ba5bfe7d
```

The program checks every part and the complete ZIP, refuses overwrite, symlinks, nonregular inputs and out-of-budget indices, and never extracts or executes the archive. Its maximum whole size is 64 MiB, with bounded reads. Both complete archives were reconstructed and compared byte for byte with the untouched originals. `TRANSPORT_FINAL_QUALIFICATION.json` records the final source identity; the first qualified source and receipt are preserved separately.

After reassembly, use a standard ZIP reader in a new directory and verify each recovered path, byte count and SHA256 against `connected-reproduction-00N-MANIFEST.json`. Transport packaging changes no scientific or commercial verdict.
