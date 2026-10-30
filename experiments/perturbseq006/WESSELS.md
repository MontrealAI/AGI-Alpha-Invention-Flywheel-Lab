# Fresh Wessels raw-data access

The latest primary comparison is Miller et al., *Deep learning perturbation models can outperform baselines on calibrated metrics*, Nature Biotechnology,1October2026, https://doi.org/10.1038/s41587-026-03307-w . Its current author repository was inspected at `15361aec8392fb45a75c8c9da88ca5e6510fca97`. This does not prove that current main is byte-identical to the publication revision.

## Actual accessible input

The primary scPerturb record https://zenodo.org/records/13350497 lists `WesselsSatija2023.h5ad`,219,393,529bytes, MD5 `6897bfdcda928a678208fecf4eeb282e`, CC-BY4.0. The full downloaded input matched that exact MD5; independent SHA256 is `5da0485aed81b23bda57b4a7b4510a394682d54911416db89b4846ff6dd34732`. It remains outside Git because the public versioned source and bounded download command reproduce it.

`fetch_wessels.py --output NEW_PATH` downloads the complete file under a500MB transfer cap,180second download ceiling and exact size/digest checks. It inspects only metadata, never expression count values or combination outcomes. The optional runtime-route argument supplies existing service proxy/CA configuration when a credential-stripping supervisor otherwise removes routing; no target credential or disabled TLS verification is required. The route file is not evidence or a published deliverable.

```sh
/tmp/alpha-perturb006-env/bin/python experiments/perturbseq006/fetch_wessels.py --output /tmp/wessels006-NEW
```

The complete bounded command passed in87.597seconds wall and2.971waited-child CPU. Receipt/logs are under `evidence/cycle-006/wessels-access/raw-download-verified/`. The first route attempt failed before receiving data; it remains separately preserved and charged by the prospective ledger. No old reservation was erased.

## Changed applicability boundary

Native HDF5 metadata establishes30,707cells,21,052genes and90,716,135sparse nonzero entries. The187condition labels include28singles,158distinct canonical gene pairs and a424-cell control. Every pair constituent has a measured single condition. There are no reversed duplicates or self pairs.

The raw source explicitly says **THP-1, monocytes, CRISPR-cas13**. The author's dataset YAML description instead saysHEK293T. The paper reports157pairs after its preprocessing; this raw input has158. Neither label nor processed-cohort identity is silently inherited. The proposed separate pilot must preserve this boundary, fix its all-gene normalization/control-panel contract prospectively, and allow the verifier to partition AB outcomes before construction. It is not reproduction of the published processed benchmark.

The earlier Norman input uses K562 CRISPR activation. A fresh generative operator may remap and refit on the new data under checked units, control availability and normalization assumptions. Copying biological coefficients or already-published predictions would not establish inherited construction.

## Strong comparison and retained failure

The current primary paper reports PRESAGE outperforming additivity on15of18metrics under its Wessels processed benchmark. That is prior art, not an outcome measured here. The model wrapper is under the Genentech Non-Commercial Software License, separate from the core framework's MIT license. The license and notices are preserved; PRESAGE code/weights were not run, incorporated into a commercial service or represented as a qualified local comparator. Public scalar benchmark scores are not a substitute for an executable same-cohort baseline.

The author's2,160,011,462byte processed S3 HDF5 is range-accessible. An isolated deep-metadata callback probe through the RPE1-qualified range adapter exited139 with no result. The original empty output and source/receipt remain preserved. Its cause is unresolved; this is a scoped failed transfer, not a universal claim about remote HDF5. A fully verified local raw file removes that dependency for the new experiment. The ordinary bulk downloader and native HDF5 driver are the preferred available method here.

For any derived numeric data, attribute the scPerturb record (Peidli et al., *scPerturb: harmonized single-cell perturbation data*, Nature Methods, DOI10.1038/s41592-023-02144-y), the source `WesselsSatija2023` contribution, its CC-BY4.0 license, and all stated preprocessing changes. No newly collected cells, raw-to-published benchmark equivalence, predictive advantage, payments or commercial success have been established by this access qualification.
