# Public metadata acquisition history

The initial source `9e75094f6eac8844deec666f8818da0897e2925b`, workflow run41485941964, job125416186702 returned HTTP200 with JSON `{"error":400}` from the first Mendeley URL. The first parser incorrectly treated syntactically valid JSON as a successful catalog and stopped trying alternatives. The workflow completed, but **no file catalog or measurements were acquired**. Its response SHA256 was `067b54b10f9034fdaa6ee1ea34518b5d7369f4b5a8d813f0fcc6890fa201826e`.

The next source rejects remote error bodies, empty/malformed catalogs and unnamed entries, and checks the root-folder query before the other public endpoints. Regression checks include the actual returned error shape. This corrects an acquisition implementation defect; it neither changes scientific thresholds nor establishes physical data availability. No original result or workflow history was overwritten.
