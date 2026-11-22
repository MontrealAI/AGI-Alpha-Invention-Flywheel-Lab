# Physical interior-observatory dependency 082 — preregistered experiment

The commercial possibility is a non-invasive, lower-cost interior-condition observatory: a qualified instrument could enable checking a hidden hazardous or valuable condition in equipment that cannot economically be opened. That productive activity requires an observed decision, a calibrated uncertainty contract, capable complete alternatives, physical requalification, buyers, and funding. This experiment **does not** provide those. It measures one much narrower dependency on a real published physical tank: whether only four of the 79 KIT4 excitation columns preserve the *metal-only versus plastic-only inclusion* distinction when inclusion count changes.

## Evidence source and experimental design

Registration was published at [035c2fc0ba2e2189e93eb4a4f57bb0b6a8664316](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/035c2fc0ba2e2189e93eb4a4f57bb0b6a8664316), **before** candidate implementation or the hosted scientific run. Source: Hauptmann and colleagues, [Zenodo 1203914](https://doi.org/10.5281/zenodo.1203914), 2017, physical tank with 16 electrodes, 79 current injection patterns and 16 adjacent-electrode voltages per pattern. The official [FIPS catalogue](https://fips.fi/open-datasets/eit-datasets/2d-electrical-impedance-tomography-dataset/) identifies CC BY 4.0. Archive MD5 is pinned to `ad9f03325cafc9aae8c0149927de8e06`. Its exact SHA256 will be measured, not invented.

The registered development set has plastic cases 1.1, 2.1, 2.2 and metallic-only 1.2–1.4, 2.3–2.6. The frozen heldout set is plastic 3.1–3.3, metal-only 3.4–3.6. Inclusion labels come from [the paper's figures 3–5](https://arxiv.org/abs/1704.01178). All inputs were observed long before this run; the heldout cases are **algorithmically hidden from fitting**, not scientifically fresh physical validation. This is one finite split, not a repeatedly optimized benchmark.

For equal-volume observations compare a standard Fisher-separation design, a competent greedy leave-one-out classification design, and a proposed count-robust design. All three select four of the same 79 injection columns using exactly the same development voltages and training labels. The proposed score maximizes the poorer of the two observed inclusion-count class separations after within-class normalization. A full 79-pattern nearest-centroid control and no-deploy are additional complete options. The four-pattern arms use exactly 64 voltage readings against 1,264 for the full-observation arm. No physical instrument was built; retrospective pattern selection **does not** prove such acquisition hardware could run accurately or cheaply.

Prediction uses the same train-scaled nearest-centroid classifier in each observed arm. Balanced accuracy counts abstentions as errors. No heldout voltage, label, post hoc fitted parameter, cash or future result is available when deciding patterns. A provisional sparse dependency requires at least 5/6 heldout correct and at least one more correct than the best competent equal-budget control. Even that is **not** Blue Sky admission; a strong ordinary full-system solution, physical repeated measurements and a complete economically valued decision could negate a new-observation claim.

## Reproduce on downloaded physical measurements

On Python 3.12 with NumPy 2.3.5 and SciPy 1.17.0, run from the repository root:

```sh
python -m unittest discover -s experiments/interior_eit082 -p 'test_run.py' -v
curl -fLsS 'https://zenodo.org/records/1203914/files/data_mat_files.zip?download=1' -o /tmp/eit082-source.zip
echo 'ad9f03325cafc9aae8c0149927de8e06  /tmp/eit082-source.zip' | md5sum --check -
python experiments/interior_eit082/run.py run --archive /tmp/eit082-source.zip --output /tmp/EIT082_RESULT.json
python experiments/interior_eit082/run.py audit --archive /tmp/eit082-source.zip --receipt /tmp/EIT082_RESULT.json
```

The dedicated [interior-eit-physical082 GitHub Actions workflow](../../.github/workflows/interior-eit-physical082.yml) runs those stages and publishes only a compact scientific result, not original data or private authority. If the source checksum, required case, pattern, output or invariant fails, the run must **remain failed**. This first iteration is unqualified until the actual exact-head hosted job and artifact are checked. Historical trials are never overwritten to obtain a desired outcome.

## Commercial and invention acceptance remain separate

The source is publicly accessible and physically measured, but it does **not** establish calibration outside its tank, a hidden-property confidence interval, medically or industrially acceptable accuracy, repeatability, a deployed sensor, buyer intent, supplier assent, current canonical available money, financing, external sales or US$3 billion trailing-365-day complete-cost profit. The 2017 EIT inverse solvers, conventional sensor designs, competent human-plus-software tomography, self-service and no purchase remain strong alternatives. Actual source processing CPU is recorded as process telemetry; equipment, engineering, independent lab validation, customer support, tax, acquisition, financing and host/model bills remain UNKNOWN.

No `JournalAccount` or `Account` is created, read with authority, reset or mutated. This experiment is nonconflicting with Omega water, Enterprise078 and the original native-capital integration owner. A negative physical result is useful: do not reclassify the observation as enabling, and move to a different experiment class or physical measurement if the same boundary voltages cannot answer the required condition. Do not deploy, buy sensors, use paid model APIs, contact customers or presume contracts.

**Tried → outcome:** pending the public physical-data run. **Next decision:** evaluate the registered comparison, retain each result, and either qualify a concrete physical information dependency for further validation or reject the path without another unregistered favorable sample.
