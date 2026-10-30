# Rebuild the commercial010 paper

Run from the repository root with Python3 and pdflatex (TeXLive with lmodern, microtype, booktabs, longtable, fvextra, xurl and hyperref). The builder requires actual source-bound campaign/v2 results, policy and cohort inputs; it does not generate placeholder results.

```sh
python scripts/build_commercial010_paper.py --results campaign/commercial-010/RESULT.json --policy campaign/commercial-010/POLICY.json --manifest campaign/commercial-010/service/executed-002/manifest.json --output docs/commercial010
```

`REPORT.md` is the native GitHub-readable browser edition. `index.html` is a self-contained portable HTML edition; GitHub's HTML source preview is not a rendered web publication. `paper.tex` is the LaTeX source and `paper.pdf` the compiled edition. All three text editions derive from the same narrative/data nodes.

`SOURCE_MANIFEST.json` binds the exact source/evidence and generated output bytes. Rebuilding intentionally replaces these publication derivatives, while frozen operating inputs remain unchanged. `BUILD.json` records the toolchain, compilation and warnings. After a final build, render and visually inspect every PDF page, then write `PDF_QA.json` bound to its exact SHA256. Run the independent paper check before publishing. No paper build or visual check constitutes fresh commercial confirmation.
