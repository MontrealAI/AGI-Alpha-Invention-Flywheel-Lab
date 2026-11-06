# CONTINUITY Ω / CONTINUITÉ Ω — Reading companion / Compagnon de lecture 1.0.1

**Release tag / Étiquette :** `continuity-omega-reading-v1.0.1`  
**Download / Téléchargement :** `CONTINUITY_OMEGA_BILINGUAL_COMPANION.zip`  
**Included paper / Article inclus :** immutable edition / édition immuable **1.1.1**

[Download the companion / Télécharger le compagnon](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/download/continuity-omega-reading-v1.0.1/CONTINUITY_OMEGA_BILINGUAL_COMPANION.zip) · [English reading guide](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/continuity-omega/OUTPUTS.md) · [Guide de lecture français](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/continuity-omega/OUTPUTS.fr.md) · [Paper release / Publication de l’article](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/continuity-omega-v1.1.1)

## English — CONTINUITY Ω

### A complete offline reading path in both languages

Edition **1.0.1** corrects the displayed French title to **CONTINUITÉ Ω**, including the guides, help and generated reports. The English title remains **CONTINUITY Ω**. Technical identifiers, paths, filenames and historical source records retain their original forms.

This separate companion brings the prototype’s English and French guides, a display-only passport reader, representative raw synthetic records, and the complete paper edition 1.1.1 into one archive. Open **`START_HERE.md`** after extraction. The nominal example and the overbooked refusal each have an English and a French report beside the original JSON records.

The companion preserves the six prototype source files, the original 29-test file and all paper files byte for byte. The earlier paper release `continuity-omega-v1.1.0` and companion release `continuity-omega-reading-v1.0.0` remain unchanged; this new companion includes the corrected paper edition 1.1.1. This reading release does not integrate the separately owned checker-hardening work or claim that the historical checker’s known weaknesses have been repaired.

### Run from the downloaded archive

From the extracted archive’s root, with **Python 3.10 or later**:

```bash
python3 -B scripts/package_continuity_reading.py --check .
python3 -B scripts/continuity_passport.py --in-dir examples/nominal --language en
python3 -B scripts/continuity_passport.py --in-dir examples/overbooked --language en
```

No package installation, network or API key is needed for these commands. The self-check verifies the complete file inventory against the included byte counts and hashes, checks the frozen source and paper identities, and executes **four presentations from the extracted code**: the two examples in both languages. It compares the rendered text exactly with the packaged reports. It does **not** run a new audit or replay the synthetic exercise.

The presenter reads saved records. Its exit code `0` means a supported report was rendered, including a recorded failure or refusal. Exit code `2` means presentation was refused. Neither a successful render nor an unchanged hash establishes current evidence validity, authentic source custody, checker correctness, live recovery, supplier availability, customer acceptance or commercial qualification. The documented historical counterexamples and source-authenticity limits still apply.

### Archive boundary and reproducibility

The explicit source inventory contains:

- Six unchanged files in `continuity_omega/`.
- `scripts/continuity_passport.py` and `scripts/package_continuity_reading.py`.
- `tests/test_continuity_omega.py` and `tests/test_continuity_passport.py`.
- The paired `README`, `QUICKSTART`, `REAL_PILOT` and `OUTPUTS` guides, plus these bilingual release notes, in `docs/continuity-omega/`.
- All 31 files listed in the paper’s immutable `PUBLICATION.json`, plus that manifest, under `docs/continuity-omega-paper/`.

The generated inventory contains `START_HERE.md`, `CHECKS.json`, `MANIFEST.json`, and the nominal and overbooked examples under `examples/`. Machine identifiers, filenames, raw JSON keys and verdict tokens retain their original forms. The legacy English-only `PASSPORT.md` is excluded; the new reports are explicitly named `PASSPORT.en.md` and `PASSPORT.fr.md`. Website pages, social artwork and unrelated repository components are outside this archive. Paper compilation retains its separately documented requirements; it is not required to read or check this companion.

Assembly runs the original 29 tests and the included presentation tests, exercises **all 12 synthetic cases**, and renders them in both languages (**24 presentations**). The native decisions are three synthetic passes and nine refusals. `CHECKS.json` keeps compact counts and content identities rather than bulky execution logs. The two representative cases retain their raw records and four complete readable reports.

The archive has a fixed file order, timestamp and permissions and uses uncompressed ZIP entries to avoid compression-library differences. Identical included source bytes produce identical archive bytes regardless of the build directory or current Git commit. Output must be a **new absolute directory outside the source tree**, with an existing parent. For example:

```bash
python3 -B scripts/package_continuity_reading.py --output /tmp/continuity-reading-001
```

`MANIFEST.json` covers every archive file except itself. The extracted check rejects missing files, additional paths, symbolic links and changed contents. These are local consistency checks; a manifest cannot authenticate its own origin. Keep the extracted archive unchanged for checking, and write any new demos or exported reports outside it.

## Français — CONTINUITÉ Ω

### Un parcours de lecture complet hors ligne dans les deux langues

L’édition **1.0.1** corrige le titre affiché en français pour utiliser **CONTINUITÉ Ω**, dans les guides, l’aide et les rapports générés. Le titre anglais demeure **CONTINUITY Ω**. Les identifiants techniques, chemins, noms de fichiers et enregistrements sources historiques conservent leur forme d’origine.

Ce compagnon distinct réunit les guides du prototype en français et en anglais, un lecteur de passeport limité à la présentation, des données synthétiques brutes représentatives et l’édition complète 1.1.1 de l’article dans une seule archive. Après extraction, ouvrez **`START_HERE.md`**. L’exemple nominal et le refus pour capacité déjà réservée disposent chacun d’un rapport français et d’un rapport anglais, à côté des fichiers JSON d’origine.

Le compagnon conserve, octet par octet, les six fichiers sources du prototype, le fichier des 29 tests originaux et tous les fichiers de l’article. Les publications antérieures de l’article `continuity-omega-v1.1.0` et du compagnon `continuity-omega-reading-v1.0.0` demeurent inchangées ; ce nouveau compagnon inclut l’édition corrigée 1.1.1 de l’article. Cette publication de lecture n’intègre pas les travaux de renforcement du vérificateur qui relèvent d’une initiative distincte et ne prétend pas corriger les faiblesses connues du vérificateur historique.

### Exécuter le lecteur depuis l’archive téléchargée

À la racine de l’archive extraite, avec **Python 3.10 ou une version ultérieure** :

```bash
python3 -B scripts/package_continuity_reading.py --check .
python3 -B scripts/continuity_passport.py --in-dir examples/nominal --language fr
python3 -B scripts/continuity_passport.py --in-dir examples/overbooked --language fr
```

Ces commandes ne nécessitent ni installation de paquets, ni réseau, ni clé d’API. Le contrôle autonome compare l’inventaire complet aux tailles en octets et aux empreintes incluses, vérifie les identités figées des sources et de l’article, puis exécute **quatre présentations avec le code extrait** : les deux exemples dans les deux langues. Il compare exactement les textes produits aux rapports inclus. Il ne relance **aucun audit** et ne réexécute pas l’exercice synthétique.

Le présentateur lit les données enregistrées. Son code de sortie `0` signifie qu’un rapport pris en charge a été présenté, y compris un échec ou un refus consigné. Le code `2` signifie que la présentation a été refusée. Ni une présentation réussie ni une empreinte inchangée n’établit la validité actuelle des preuves, l’authenticité de leur conservation, la correction du vérificateur, une reprise réelle, la disponibilité d’un fournisseur, l’acceptation par un client ou une qualification commerciale. Les contre-exemples historiques documentés et les limites d’authenticité des sources demeurent applicables.

### Périmètre de l’archive et reproductibilité

La liste explicite des sources comprend :

- Les six fichiers inchangés de `continuity_omega/`.
- `scripts/continuity_passport.py` et `scripts/package_continuity_reading.py`.
- `tests/test_continuity_omega.py` et `tests/test_continuity_passport.py`.
- Les guides `README`, `QUICKSTART`, `REAL_PILOT` et `OUTPUTS` dans les deux langues, ainsi que les présentes notes bilingues, dans `docs/continuity-omega/`.
- Les 31 fichiers énumérés dans le manifeste immuable `PUBLICATION.json` de l’article, ainsi que ce manifeste, sous `docs/continuity-omega-paper/`.

Le contenu généré comprend `START_HERE.md`, `CHECKS.json`, `MANIFEST.json`, ainsi que les exemples nominal et de capacité déjà réservée sous `examples/`. Les identifiants machine, noms de fichiers, clés JSON brutes et verdicts techniques conservent leur forme d’origine. L’ancien `PASSPORT.md` unilingue anglais est exclu ; les nouveaux rapports portent les noms explicites `PASSPORT.en.md` et `PASSPORT.fr.md`. Les pages du site, les visuels sociaux et les autres composants du dépôt ne font pas partie de cette archive. La compilation de l’article conserve ses exigences documentées séparément ; elle n’est pas nécessaire pour lire ou contrôler ce compagnon.

L’assemblage exécute les 29 tests originaux et les tests de présentation inclus, exerce **les 12 cas synthétiques** et les présente dans les deux langues (**24 présentations**). Les décisions d’origine comprennent trois réussites synthétiques et neuf refus. `CHECKS.json` conserve des décomptes et des identités de contenu compacts, sans journaux d’exécution volumineux. Les deux cas représentatifs conservent leurs données brutes et leurs quatre rapports lisibles complets.

L’archive utilise un ordre des fichiers, un horodatage et des permissions fixes, ainsi que des entrées ZIP non compressées afin d’éviter les différences entre bibliothèques de compression. Des sources incluses identiques produisent des archives identiques, quels que soient le répertoire d’assemblage et le commit Git courant. La sortie doit être un **nouveau répertoire absolu à l’extérieur des sources**, dont le parent existe. Par exemple :

```bash
python3 -B scripts/package_continuity_reading.py --output /tmp/continuity-reading-001
```

`MANIFEST.json` couvre tous les fichiers de l’archive sauf lui-même. Le contrôle après extraction refuse les fichiers absents, les chemins supplémentaires, les liens symboliques et les contenus modifiés. Ces contrôles établissent une cohérence locale ; un manifeste ne peut pas authentifier sa propre origine. Conservez l’archive extraite intacte pour la contrôler et enregistrez toute nouvelle démonstration ou tout rapport exporté à l’extérieur.
