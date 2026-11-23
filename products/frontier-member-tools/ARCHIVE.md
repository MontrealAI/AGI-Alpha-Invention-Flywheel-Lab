# NOAA Archive Point 1.0.0

Retrieve the archived NOAA GFS 24-hour forecast of 2 m air temperature at an exact native 0.25° grid cell in the retained packing format. The 384 KiB experimental response limit covers the index and field prefix. The result is a historic **model forecast**, reported in kelvin.

## Run (qualified Linux, Python 3.12, curl and OpenSSL)

```sh
python3 archive-verify.py
python3 archive-query.py --day 2024-01-18 --cycle 00 --latitude 46.75 --longitude -71.25 > point.json
python3 archive-verify.py point.json
```

The first command verifies the frozen Ed25519 receipt and scores offline. It checks six registered ecCodes full-field comparisons. The query requires anonymous, read-only access to the official NOAA source. It retrieves immutable archive bytes over HTTPS and records the requested range, content digests, ETags, times and bytes. For the Québec-area sample the retained accepted value is **257.85171875 K** within a tolerance of 1e-10 K. The last command verifies the returned grid index, value, body accounting and origin-byte digests against the independently decoded, signed reference. A result outside those six historical cases requires a fresh reference and remains unverified by this receipt.

Select a supported UTC date and cycle, then specify a coordinate on the exact grid. Off-grid positions, missing records, unsupported GRIB packing and unavailable source ranges abstain. The manifest identifies the immutable original experiment. The networkless audit only tests the existing evidence. Successful live retrieval depends on the public archive and connectivity. Compare against NCAR's existing point service first if it can serve the required historical point. In the experiment, NCAR returned all six values after one retry using much less data. The direct query used 49.8% fewer response-body bytes than the complete indexed-field route. Complete costs and productive superiority remain unproven.

## Sources and use

The author-approved public download contains first-party query and audit code plus the signed comparison. NOAA archive bytes are obtained from the original public provider and are not bundled. ecCodes is an independent reference used in the retained experiment. Neither ecCodes nor credentials are needed to run the shipped query or offline audit. The manifest records the source pin and permitted distribution scope. Nearby use requires equal format, rights and reference validation. A useful query is not a weather observation, operating recommendation or realized economic gain.

## Français

L’outil interroge l’archive NOAA GFS pour une température de l’air à 2 m, à une coordonnée exacte de la grille de 0,25°. Il retourne une **prévision historique** en kelvins. La limite expérimentale de 384 Kio couvre l’index et le préfixe du champ. Le premier appel vérifie hors ligne le reçu Ed25519 et les six comparaisons contre ecCodes. Le deuxième requiert un accès anonyme à l’archive NOAA. Le troisième compare l’extraction aux valeurs et aux empreintes du reçu signé. Pour le point près de Québec, la valeur attendue est de **257,85171875 K**. NCAR a obtenu les six valeurs avec beaucoup moins de données après une relance. Les coûts complets demeurent inconnus.
