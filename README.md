# Frozen NASA numerical evidence archive

This data-only branch preserves 66,302,334 bytes of original and repaired numerical fields from campaign008. Do not merge its tree into the executable campaign. Source, protocols, negative outcomes and independent checks remain on campaign/overnight-civilization-008-20261030 and PR12. The separate archive keeps the executable source package within its existing resource envelope.

Four original registered-field files are stored whole. Two larger repaired-field files are split losslessly; their complete original SHA256 values and piece hashes are in NASA_ARRAY_PUBLICATION.json. Restore into a fresh directory with:

```sh
python3 assemble_nasa_fields008.py --root . --output /tmp/nasa-fields-RESTORED
```

This checks byte identity and preserves partial output on failure. It is not instrument runtime qualification, independent physical calibration, a technical win or commercial success. The ordinary zero-plane comparator still wins the frozen primary metric. All experiments are exposed development. Source data: NASA NTRS20240002767 (catalogue: public use permitted); source citation and actual acquisition identities remain in the campaign source package. No new software or data license grant is invented here.
