# ALPHA-1 · Manufacturer archive follow-up / Fiche fabricant archivée

On 29 September 2026 at 19:26:30 UTC, the Internet Archive captured Prusa's US product listing for the HT Hotend. The page showed the 400 °C specification, a cart button, a two-week order preparation estimate and these supported configurations: CORE One, CORE One+, CORE One+ (Gen 2), CORE One L and CORE One L+. The same page excluded the two named INDX arrangements. This is primary documentary evidence that the upgrade was offered with the compatibility used in the original replay before 21 October. [Archived storefront](https://web.archive.org/web/20260929192630/https://www.prusa3d.com/product/ht-hotend-upgrade-for-core-one-and-core-one-l/)

The result supports the earlier correction. The October before-and-after comparison mixed a catalog assumption with the date of a later announcement. The [separate replay](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/abc79ae1c30bb8cac7b10422159d0325196f1d23) reproduced all 42 technical decisions. With the documented catalog carried into both October dates, **0/24** compatibility decisions change, compared with **7/24** in the original scenario. The earlier observation and the present-day product listing are distinct evidence. The file records an offer, and neither it nor the numerical replay establishes fulfillment, daily stock or incremental economic benefit.

### Reproduce

```sh
python3 scripts/verify_frontier_alpha1_oem_archive.py --check
```

The program confirms the capture date, bounds the response size, checks the SHA-256 of decoded HTML and reads the product fields without running page scripts. The archived byte stream can also be supplied with `--snapshot`. Only the extracted [receipt](frontier-alpha-1-oem-archive.json) is saved in Git. The live listing is a separate source and can change.

## Français

Le 29 septembre 2026 à 15 h 26 min 30 s, heure de Montréal, Internet Archive a capturé la fiche américaine de la boutique Prusa. On y trouve la limite de 400 °C, les cinq configurations compatibles de l’étude, un bouton de commande et un délai de préparation de deux semaines. Deux configurations INDX sont exclues. Cette fiche confirme que la mise à niveau était proposée avant l’annonce du 21 octobre.

Les **42 décisions techniques** de l’étude sont reproductibles. En appliquant le catalogue documenté aux deux journées d’octobre, **0 cas sur 24** change, contre **7 sur 24** dans le scénario initial. La fiche ne documente ni la livraison, ni le stock de chaque jour, ni un avantage économique.
