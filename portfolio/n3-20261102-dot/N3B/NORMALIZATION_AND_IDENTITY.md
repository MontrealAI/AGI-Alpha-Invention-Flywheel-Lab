# Archived baseline identity

Primary source: NIST DOI10.18434/mds2-2950, `modified_pix2pix.zip`.

The archived `data/base_dataset.py`, lines 109–115, applies `ToTensor` followed by grayscale `Normalize((0.5,), (0.5,))`. Its SHA-256 is `881e5a682538fe55be883f9fa4e9cc5abc6576dfddb9623bd6bb3109d03c300f`; size 6,189 bytes. The exact source entry and archive provenance were inspected before baseline image values.

The archived `util/util.py`, function `tensor2im`, converts the tensor to float32 NumPy, computes `(x + 1) / 2 * 255`, and casts to uint8. The checker therefore accepts either the exact raw source mask or the exact single float32 roundtrip through these operations. It does not accept arbitrary per-pixel ±1 changes, alignment, rotation or permutation.

Source `models/test_model.py` binds `real` to input A and image paths to A's paths. `test.py` passes those paths to the visualizer. `util/visualizer.py` uses the input basename to save `<basename>_<label>.png`. Consequently `0000_real.png` must bind to `training_pairs/test/0000.png`'s left-hand mask, and `0000_fake.png` is its archived prediction. Repeated fiducial masks do not authorize reassigning predictions between source IDs.

All 300 same-ID input masks must match for each baseline. Any mismatch makes that saved-output comparator unqualified; mismatches remain reported. Save the actual decoded input and predicted arrays for independent replay without another download.

The source directory is named `test_200`. A later stored options file references larger masks and `latest`; it does not prove the exact historical test configuration. The comparison is to source-bound archived outputs, not a reproduced training run. No published prediction or test height has been accessed during model development.
