# Source-bound perturbation-data qualification

This is a bounded data/runtime qualification path, not an invention advantage or a qualified PSGRN benchmark. The cycle pivoted to the independently published Norman combination means before reading RPE1 expression outcomes or streaming the full RPE1 file.

## Executing interfaces

`range_hdf5.RangeFile` supplies bounded read-only HTTPS byte ranges to h5py. It refuses a full HTTP200 response, wrong range, wrong length, unbounded read, out-of-file seek or an exhausted byte budget. It honors the runtime's proxy/CA configuration while disabling implicit target authentication from `.netrc`. TLS verification stays enabled. This is a trusted data acquisition adapter, not the generated-program sandbox.

`qualify.py` checks both exact upstream Git revisions before imports, exercises the actual PSGRN `main_app.py --help` entrypoint, inspects actual remote HDF5 metadata through `RangeFile`, and verifies the paper XLSX identity before inspecting its header only. It never emits AB/error outcome values to the constructor. The separate verifier owns combination-level protection and outcome release.

```sh
python -m venv --system-site-packages /tmp/alpha-perturb006-env
/tmp/alpha-perturb006-env/bin/pip install -r requirements-perturb006.txt
git clone https://github.com/GuanLab/PSGRN.git /tmp/psgrn006
git -C /tmp/psgrn006 checkout --detach 74aa640f7c472b23a69811f6795bb17678efd344
git clone https://github.com/const-ae/linear_perturbation_prediction-Paper.git /tmp/linear006
git -C /tmp/linear006 checkout --detach bfa6eeea2bd145a1af2ec0127a2e808cc38456a9
/tmp/alpha-perturb006-env/bin/python experiments/perturbseq006/qualify.py --output /tmp/perturb006-NEW --psgrn-source /tmp/psgrn006 --linear-source /tmp/linear006
/tmp/alpha-perturb006-env/bin/python -m unittest discover -s experiments/perturbseq006 -p 'test*.py' -v
```

This isolated environment is not the original full PSGRN environment. The pinned README requests Python3.10; its environment.yml instead pins Python3.8. The qualification used Python3.12 with versions recorded in the report. Main_app still refuses at missing `slingpy`; no intact full PSGRN inference or causal benchmark was run. The correct documented custom entrypoint is `src/main.py`; `src/main_fast.py` does not exist at the pinned revision.

## What the access check established

The 8,700,873,216-byte RPE1 mirror has a contiguous dense float32 matrix of 247,914 cells by 8,749 genes. Strict ranged metadata reads retrieved 8,178,176 bytes. Full file SHA256 and byte equivalence to original Figshare input35775606 remain unknown.

Pinned preprocessing first normalizes over the complete matrix, then retains genes represented by more than100 intervention cells. Metadata admits651 genes before the unexecuted strong-effect filter, implying423,150 directed pairs, not the76,535,252 raw-column pairs. There are11,485 non-targeting controls. Exact default normalization requires the global median full-X row total; an arbitrary cell/gene truncation or existing UMI metadata is not a certified substitute. The reader removes a local whole-file storage assumption but does not establish a missing scientific capability. Ordinary h5py/file-object composition supplies this capability.

## Norman source-panel identity and limits

The paper repository's `source_data/suppl-qqplot.xlsx` is10,905,627 bytes, SHA256 `1b652c352d4dabdd20324d7fd74d331898fa22c51cf6fa28ff65aa1322a6c78f`, Git blob `f35c9efe3bf0f917068b2aaf2c2236b593c06e2c`. Its124,000 data rows represent124 combination conditions and1,000 readouts. This data owner inspected the header only, not AB/error values.

The exact analysis source defines the panel by control expression rank, not by combination-effect magnitude: lines103-109 of `notebooks/double_perturbation_analysis.Rmd`. Lines391-405 construct A/B/AB/control ground-truth means and select seed1/rank<=1000; line545 exports the XLSX. The upstream MIT notices are retained alongside the source snapshot.

These are published condition means with no cell-level or biological-replicate uncertainty in the file. They do not establish whole-transcriptome performance, clinical utility or exact equivalence to another processed Norman input. Shared singles/controls and correlated readouts prevent treating the124,000 rows as independent experimental tasks. The original paper's held-out test assignments are not reconstructed from this export. A separately identified pilot must freeze its own combination split and strong controls before outcomes are exposed.

The recorded exact paper Figshare ZIP44477939 and Harvard6154020 routes returned403. These are access failures, not evidence that inference methods fail. The successful source-panel route is a licensed, hash-bound alternative for a narrowly declared pilot.

## Preserved failures and costs

`evidence/cycle-006/psgrn/qualified-interface/` preserves the first adapter's TLS failure. The repair honors the existing CA bundle; it does not disable certificate verification. `qualified-interface-r2/` records the successful actual adapter execution,10.620 seconds wall,0.1645 self CPU and1.5369 child CPU. Setup, Git transfer, installation and implementation inference costs are not fully metered and remain unknown. `initial-range-probe.json`, `intervention-metadata-probe.json`, and all403/entrypoint receipts remain separate original evidence. Five negative/bounded reader tests passed. No paid model call, buyer participation, earnings or funded successor follows from these checks.
