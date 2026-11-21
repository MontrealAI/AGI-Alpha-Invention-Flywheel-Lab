# CANADA-OPEN-NEED227 | Public requirements, not customers

**Status:** Independent research instrument. HOLD / NO BID / NO DEPLOY. Owns no financial source, operating account, or existing PR implementation. Original award-fetch HTTP 403 remains a failure.

## EN — What this delivers

A one-pass, read-only check of the Government of Canada's *currently open tender notices* CSV, independent of the failed FY2026–27 award-notice endpoint. Outputs an exact-byte SHA-256 receipt, whole-source denominators, a finite shortlist of future-dated software/data/automation titles with their source references, and every reason to abstain. A posted public tender means a buying institution advertised an opportunity; it does **not** establish a qualified contract, customer intent toward us, awarded work, payment, delivery benefit, available capital or profit.

The programme neither searches private material nor contacts purchasers, bids, deploys, collects money, creates accounts or installs credentials. No procurement face value may enter the native financial ledger. Strong alternatives remain the free government search, capable conventional procurement analysts, commercial monitoring products, complete incumbent suppliers and **no purchase**. Unknown market access and costs make commercial adoption a HOLD.

The preregistered fixed source, keyword list, bounds and stopping rule are in [PREREGISTRATION.md](PREREGISTRATION.md). The official data publisher's licence is the Open Government Licence – Canada, with attribution. The active source, checked at execution time rather than assumed accessible, is:

`https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv`

A fresh output directory is required; no signed account paths should ever be supplied:

```sh
python3 -B -m unittest -v tests.test_canada_open_need227
python3 -B tools/canada_open_need227.py observe --out /tmp/new-public-observation227
python3 -B tools/canada_open_need227.py verify --out /tmp/new-public-observation227
```

The hosted workflow runs the tests *before* its one official GET and preserves an exact-source witness or the original access failure for seven days. Do not repeat a failed GET to chase favorable results. Observation cannot establish an accepted complete outcome, inventor improvement, causal transfer, genuine collected revenue or US$3 billion trailing-365-day complete-cost profit. Any selected service requires actual public acceptance criteria, eligibility, rights, capacity, full costs, strong comparators and separate legitimate commercial authority before a deployment claim.

## FR — Ce qui est réellement établi

Cet instrument de recherche examine une seule fois le fichier officiel des appels d'offres fédéraux **ouverts**, sans recourir à une API payante ni à des données privées. Il produit une empreinte SHA-256 des octets, des dénominateurs complets et, si les données le permettent, une courte liste déterministe de besoins publiés. Une annonce gouvernementale **n'est pas** une commande obtenue par MONTREAL.AI, un paiement encaissé, une prestation acceptée ou un bénéfice réalisé.

Les alternatives comparées demeurent la recherche gratuite de CanadaBuys, l'analyse conventionnelle compétente, les fournisseurs déjà présents et l'abstention. Les coûts complets, l'admissibilité et la demande envers notre prestation restent inconnus. Aucune offre commerciale, soumission, dépense, transaction, mise en production, création de compte financier ou modification des obligations existantes n'est autorisée par ce protocole.

**Décision :** examen documentaire seulement, ou refus explicite si les données ne sont pas accessibles. Les échecs historiques demeurent des échecs. Une qualification technique n'est pas une preuve de rentabilité.
