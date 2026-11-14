# EIT108 — fewer recorded current-injection patterns for a real shape decision?

**Preregistered research; no sensor deployment, commercial acceptance or profit.** The [immutable protocol](PROTOCOL.md) was published at commit `8d973616313547cf716a3a02d700537f968b6601` **before implementation**, based on main `de9546ef9083f64a25186f1c5163e3a3a4eaeae5`. The proof is a comparison with a competent existing full-data classifier, *not* a claim of inventing shape classification.

## Why this is a useful hard test

EIT107 established a deterministic source mask on the **circle-only** recorded archive. That does not establish an actual sensor reference configuration, fewer physical injection operations, unseen specimens or a meaningful shape decision. Zenodo's independent 2023 v1 dataset also supplies `square_petg.csv` and `triangle_petg.csv`. The 2026 peer-reviewed SBrT shape-classification study already reports roughly **97%** test accuracy and a random forest competitive with the neural classifier. Any new result must confront that actual ordinary alternative, not a deliberately weak inverse. Original data and publication: [Zenodo v1](https://zenodo.org/records/7192883); [SBrT2026 DOI](https://doi.org/10.14209/sbrt.2026.1571299951).

## Run (one frozen attempt, no favorable reseeding)

```bash
python3 -m pip install --only-binary=:all: numpy==2.3.5 scikit-learn==1.7.2
python3 -B -m unittest tests.test_eit_sparse108 -v
python3 -O -B -m unittest tests.test_eit_sparse108 -v
python3 -B -m research.eit_sparse108.study > /tmp/EIT108_RESULT.json
```

The last command downloads and hashes the original three permitted public files once each (<=20 MB/source), groups the 16 complete pairs into **one archival measurement group**, and puts **all groups sharing a literal (r,phi) position** on one side of a deterministic 80/20 split. Four and eight fixed-pair random forests compete with full16 random forest and extra trees. Every missing electrode voltage is excluded, **never imputed as a synthetic measurement**. Report all three class recalls, confusion matrices, group units and full resource metadata. Predefined sparse screening is accuracy >=95%, within 2 percentage points of the better full-data conventional model, and every class recall >=90%. No test-output tuning. Every observed failure remains retained under the frozen contract.

The dataset is known publicly to everyone already and may use the **same physical apparatus and few physical objects** in many rows. These are held-out *recorded position strings*, **not genuinely independent held-out fabricated specimens**. The lower pattern count is an archived numerical measurement-policy contrast, not independently witnessed reduction in current-injection timing. Human visual shape recognition, professional measurement systems, buyer acceptance and complete costs remain unmeasured; even a passing sparse arm remains **HOLD / NO BID / NO DEPLOY**. No paid models, capital, account, buyer or real profit; no changes to owners' earlier EIT failures or financial account.

### Scope of live qualification

GitHub Actions runs source-matched synthetic adversarial tests in both ordinary and optimized Python, then the single frozen public-source attempt. If source grouping or source hashes disagree, the run **fails**; the original failed observation is not rewritten to make it pass. Main, signed queues, permissions, source owners, historical financial liabilities and releases are left untouched. The US$3 billion trailing-365-day complete-cost profit remains an **unqualified operating objective**, not a property of this scientific archive.
