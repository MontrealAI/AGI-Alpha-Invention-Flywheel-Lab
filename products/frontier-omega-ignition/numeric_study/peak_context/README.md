# Can published supernova peaks corroborate a change alert?

The six printed Type Ia rows in Ma et al. contain five extinction-corrected absolute r-band peaks. Each belongs to a different supernova. **The table supplies zero same-object pairs from which to recover a brightness change.** A user can inspect all six source rows and the qualifiers that govern their interpretation. [Checked CSV](peaks.csv) · [Original result and per-cell discrepancies](observation.json) · [Prior registration](REGISTRATION.md)

| Extraction on the pinned edition | Exact quantities / 36 | IDs / 6 | Source conditions / 3 | Observed route time |
| --- | ---: | ---: | ---: | ---: |
| Structured author HTML | 36 | 6 | 3 | 0.0104 s |
| Conventional PDF, words and physical cell boundaries | 36 | 6 | 3 | 0.0398 s |
| Historical Table Desk reference reader, unchanged | 24 | 6 | 2 | 0.0383 s |

The first two routes produced identical CSV bytes. The PDF prints the data as Table A.1, on rotated physical page 16. The versioned HTML calls it Table 6, Appendix A. Both identify the printed subset, the correction applied to the r-band peak and the authors' two sources of host-extinction estimates. The source forms share authorship. This comparison tests recovery of the published measurements and their scope.

For SN 2016coj, the r-band peak is **−19.0 ± 0.2 mag** and the reported host colour excess is **≲0.020 mag**. The extraction preserves the distinction between that approximate bound, an equality and no reported measurement. The unchanged reader emitted the visible ± or ≲ alongside its hidden TeX spelling in twelve cells. It recovered six blank entries, both declination signs and the two field-level footnotes. Its exported table omitted the caption's six-entry restriction. The independent scorer withheld that delivery. The initial extraction required no post-scoring correction.

Each CSV row carries the source identifier, peak absolute r magnitude and its quoted uncertainty, Galactic r extinction in magnitudes, host E(B−V) in magnitudes, signed declination in degrees:minutes:seconds, dimensionless redshift and distance with uncertainty in Mpc. Empty fields mean the printed cell is blank. The six blank numerical cells comprise one peak and five host colour excesses. The extinction note links some estimates to the paper's listed photometry references and others to sodium absorption where high-resolution spectra were available. Uncertainty fields retain exactly the displayed digits.

The alert experiment uses positive ZTF difference-image measurements relative to survey reference images. A meaningful independent physical confirmation requires epoch-matched observations, consistent photometric definitions and suitable reference/calibration information. The published peaks are contextual information for this decision. The observed same-object pair upper bound checks that conclusion even before considering cross-survey calibration. [ZTF explanatory supplement](https://irsa.ipac.caltech.edu/data/ZTF/docs/ztf_explanatory_supplement.pdf)

## Reproduce

In the IGNITION product directory with Python 3.11 or later, replay the frozen comparison and run sign, precision, missingness, inequality, note-loss and source-substitution checks.

```sh
python3 -B numeric_study/peak_context/study.py
python3 -B -m unittest discover -s numeric_study/peak_context -v
```

For a fresh native extraction, supply the two versioned originals. The observed runtime used PyMuPDF 1.26.6 and lxml 6.1.1. Each route reopens its own source bytes. The script rejects a changed input, independently re-derives both projections and checks the exact frozen outcome. Give `--output` a new directory to save a fresh receipt with its own timings. If the arXiv presentation wrapper changes, the historical HTML checksum signals a different input. A new observation can then be registered without changing this one.

```sh
curl -fLsS https://arxiv.org/pdf/2504.04393v1 -o /tmp/ma25-v1.pdf
curl -fLsS https://arxiv.org/html/2504.04393v1 -o /tmp/ma25-v1.html
python3 -B numeric_study/peak_context/study.py --pdf /tmp/ma25-v1.pdf --html /tmp/ma25-v1.html
```

The cached inputs occupy 2,206,891 PDF bytes and 363,177 HTML bytes. The three single-run intervals include reading, identity checks and extraction. PyMuPDF and lxml had already been imported. Comparison and CSV encoding took a further 0.0010 s. The PDF geometry and HTML projection were prepared for this publication. Original acquisition, geometry registration, engineering, scientific review, delivery and maintenance costs remain unmetered. The observations do not rank end-to-end costs. This study used public-source material and incurred no purchase. It measured no acceptance by a field operator, human reader performance or revenue.

Numerical facts are attributed to Xiaoran Ma et al., *Supernovae at Distances < 40 Mpc: I. Catalogues and fractions of Supernovae in a Complete Sample* (2025). The author edition was submitted 6 April 2025. The publisher and the tested author edition are separately identifiable. [Versioned author edition](https://arxiv.org/abs/2504.04393v1) · [Journal article](https://doi.org/10.1051/0004-6361/202452684)

## Résultat en français

Les six lignes imprimées présentent cinq magnitudes absolues au maximum en bande r, corrigées de l’extinction. Chaque valeur correspond à une supernova différente. Le tableau fournit donc **zéro paire de mesures du même objet** permettant d’établir une variation temporelle. L’extraction du PDF et l’export HTML retrouvent les 36 champs numériques, les six identifiants et les trois conditions. Le lecteur historique restitue 24 champs et deux conditions. Il duplique la notation de onze incertitudes et d’une borne approximative. Les six cases vides restent vides dans le fichier livré.
