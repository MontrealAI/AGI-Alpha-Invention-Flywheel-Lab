# CONTINUITY Ω / CONTINUITÉ Ω — Language contract / Contrat de traduction

Research edition / Édition de recherche **1.1.1** · [English reading path](README.md) · [Parcours de lecture français](README.fr.md)

## English

### Same research, complete reading paths

The English and French editions express the same scientific and commercial claims, assumptions, observations, failures and limits. French is a complete reading edition, not an executive summary. The bilingual release adds access in another language; it does not report a new model experiment, field exercise, certification, commercial transaction or qualified prototype repair.

The release provides `CONTINUITY_OMEGA.pdf`, `CONTINUITY_OMEGA_FR.pdf` and one `CONTINUITY_OMEGA_SOURCE.zip` containing both complete manuscripts and their supporting material. The original 1.0.0 release keeps its own tag, notes and assets. Edition 1.1.1 has its own identities in `PUBLICATION.json`.

### What changes with language

The current main title is **CONTINUITY Ω** in English and **CONTINUITÉ Ω** in French, including the cover, running headers, body references, PDF metadata, citation metadata and current reading guides. Edition 1.1.1 corrects this title translation. Earlier releases 1.0.0 and 1.1.0, their records and assets remain unchanged. The current French cover series label and running footer read **INTELLIGENCE TRANSFORMATIONNELLE ∞**; authentic titles of cited source papers keep their originally published form.

Explanatory prose, headings, captions, diagram labels, table explanations and human-readable claim descriptions are translated. French uses professional French terminology and appropriate typography; for example, `1,900 units` becomes `1 900 unités` in prose and `US$650` becomes `650 $ US`. The quantities and currency remain the same. The claim register retains numeric literals without typographic regrouping so they remain directly comparable.

Official source titles, author names, product names, DOI strings and exact source URLs remain retrievable in their original form. Their role and limitations are explained in the reader's language. Keeping an official title does not leave its scientific significance unexplained or imply an endorsement. The four cited historical CONTINUITY prototype titles remain in their originally published English form in the French bibliography and source map; they identify earlier works, not the current French title. Stable filenames, URLs, release tags and schema identifiers such as `CONTINUITY_OMEGA_FR.pdf` and `continuity-omega` are not renamed.

### What remains immutable

Both languages share the same claim IDs, status tokens, source-map keys and values, source lists, commit and Git blob identities, SHA-256 strings, field names, mathematical variable names, equations, case identifiers, command-line options, filenames and raw outcome tokens. Machine JSON uses the same numeric values and Boolean literals. A translation must not turn `false` into `true`, a failed observation into a pass, a modeled amount into collected revenue, or a proposed service into an established one.

`CLAIMS.fr.json` translates `title`, `scope`, status-definition prose and each claim's `text`, `evidence` and `limits`. It has `language: "fr"`; the English register has `language: "en"`. Both retain the same edition and reviewed date. The French register intentionally preserves the exact shared `sources` map, including `manuscript: "CONTINUITY_OMEGA.tex"`, rather than redirecting an evidence anchor. The complete French manuscript is linked from the French reading path.

The recorded evidence JSON and executable source are not duplicated into language-dependent experimental records. [EVIDENCE.md](EVIDENCE.md) and [EVIDENCE.fr.md](EVIDENCE.fr.md) provide complete human explanations of their meaning. Raw software messages can remain in their original language; their field names and verdicts are explained in both guides. Code identifiers and commands remain executable exactly as documented.

### Invariants that must survive translation

- The two historical suites contain **29** and **9** implementation tests; these counts do not measure customer outcomes or model-discovery performance.
- The 12 handoff CLI cases contain **3** passes and **9** refusals. The four recovery decisions are `[true, false, false, false]`, matched by the competent conventional control.
- The five separate probes preserve one positive control, three weaknesses and a previously disclosed coherent-reseal trust limit. Reproducing a weakness is not checker qualification.
- **1,900 units**, a **22-hour stipulated lead time** and **US$650 modeled contribution** remain synthetic case values. The distinct proposed target of **up to 20,000 units within 48 agreed business hours** remains unqualified.
- The separate historical **US$1,080 modeled loss** remains attributed to GENESIS Commitment 001.
- Hashes bind bytes. They do not establish completeness, authenticity of customer obligations, real reserved capacity, physical fulfillment or acceptance.
- A separately implemented checker and separately assigned AI review tasks do not become independent institutional certification or a comparison of two frontier models through translation.

### Build, verification and correction

`python3 build.py --language all` builds both manuscripts; `python3 build.py` has the same language default. `--language en` and `--language fr` select an individual manuscript. `python3 verify.py --check-build` checks both rebuilt language versions against their respective canonical texts. PDF bytes can differ between languages and TeX installations; their publication identities remain explicit. `check_translations.py --self-test` also rejects untranslated cover, running-header, body-macro and PDF-metadata titles, while retaining the existing mathematical and evidence checks. Current title QA is recorded in `PUBLICATION.json`; `evidence/QA.json` and `evidence/TRANSLATION_QA.json` remain historical records for editions 1.0.0 and 1.1.0.

If a material discrepancy is found, compare the two statements, their common claim ID and the cited source. Correct the affected reading paths and metadata through a reviewed edition. Do not silently select a more favorable language, rewrite historical evidence, or overwrite an earlier release. The translation is part of this research publication's quality process; it is not a certified legal translation.

## Français

### Une même recherche, des parcours de lecture complets

Les éditions anglaise et française expriment les mêmes affirmations scientifiques et commerciales, hypothèses, observations, échecs et limites. La version française est une édition de lecture complète, et non un résumé destiné à la direction. La publication bilingue donne accès au contenu dans une autre langue ; elle ne rapporte aucune nouvelle expérience de modèles, aucun exercice de terrain, aucune certification, aucune transaction commerciale et aucune qualification d’une correction du prototype.

La publication fournit `CONTINUITY_OMEGA.pdf`, `CONTINUITY_OMEGA_FR.pdf` et une archive `CONTINUITY_OMEGA_SOURCE.zip` contenant les deux manuscrits complets et les documents associés. La publication originale 1.0.0 conserve sa propre étiquette de version, ses notes et ses fichiers. L’édition 1.1.1 possède ses propres identités dans `PUBLICATION.json`.

### Ce qui change avec la langue

Le titre principal courant est **CONTINUITÉ Ω** en français et **CONTINUITY Ω** en anglais, y compris sur la couverture, dans les en-têtes, les mentions du texte, les métadonnées PDF, les métadonnées de citation et les guides de lecture courants. L’édition 1.1.1 corrige cette traduction du titre. Les publications antérieures 1.0.0 et 1.1.0, leurs relevés et leurs fichiers demeurent inchangés. Le libellé de série sur la couverture française courante et le pied de page indiquent **INTELLIGENCE TRANSFORMATIONNELLE ∞** ; les titres authentiques des articles sources cités conservent leur forme de publication d’origine.

Les explications, titres, légendes, libellés de schémas, descriptions de tableaux et descriptions d’affirmations destinées aux lecteurs sont traduits. Le français emploie une terminologie professionnelle et une typographie appropriée ; par exemple, `1,900 units` devient `1 900 unités` dans le texte courant, et `US$650` devient `650 $ US`. Les quantités et la devise restent identiques. Le registre des affirmations conserve les valeurs numériques littérales sans regroupement typographique pour permettre leur comparaison directe.

Les titres officiels des sources, noms d’auteurs, noms de produits, DOI et URL exactes restent accessibles dans leur forme originale. Leur rôle et leurs limites sont expliqués dans la langue de lecture. Le maintien d’un titre officiel ne dispense pas d’en expliquer la portée scientifique et ne signifie pas que son auteur approuve le projet. Les quatre titres historiques cités des prototypes CONTINUITY conservent leur forme anglaise publiée dans la bibliographie française et la filiation des sources : ils identifient des travaux antérieurs, et non le titre français courant. Les noms de fichiers, URL, étiquettes de publication et identifiants de schéma stables, comme `CONTINUITY_OMEGA_FR.pdf` et `continuity-omega`, ne sont pas renommés.

### Ce qui reste inchangé

Les deux langues partagent les mêmes identifiants d’affirmations, codes de statut, clés et valeurs de la table des sources, listes de sources, identifiants de commits et de blobs Git, empreintes SHA-256, noms de champs, variables mathématiques, équations, identifiants de cas, options de ligne de commande, noms de fichiers et codes bruts de résultat. Les fichiers JSON utilisent les mêmes valeurs numériques et les mêmes littéraux booléens. Une traduction ne doit pas transformer `false` en `true`, un échec observé en réussite, un montant modélisé en recette encaissée ou un service proposé en service établi.

`CLAIMS.fr.json` traduit `title`, `scope`, les descriptions des statuts et les champs `text`, `evidence` et `limits` de chaque affirmation. Il porte `language: "fr"` ; le registre anglais porte `language: "en"`. Les deux conservent la même édition et la même date de revue. Le registre français garde intentionnellement la table `sources` commune à l’identique, y compris `manuscript: "CONTINUITY_OMEGA.tex"`, sans rediriger un ancrage probant. Le parcours de lecture français donne accès au manuscrit français intégral.

Les fichiers JSON consignés et le code exécutable ne sont pas dupliqués en dossiers expérimentaux dépendant de la langue. [EVIDENCE.md](EVIDENCE.md) et [EVIDENCE.fr.md](EVIDENCE.fr.md) expliquent intégralement leur sens pour les lecteurs. Les messages bruts du logiciel peuvent rester dans leur langue d’origine ; leurs noms de champs et leurs verdicts sont expliqués dans les deux guides. Les identifiants de code et les commandes demeurent exécutables exactement comme ils sont documentés.

### Invariants à préserver dans la traduction

- Les deux suites historiques comprennent **29** et **9** tests d’implémentation ; ces nombres ne mesurent ni des résultats clients ni la performance de découverte des modèles.
- Les 12 cas du transfert en ligne de commande comprennent **3** validations et **9** refus. Les quatre décisions de reprise sont `[true, false, false, false]`, identiques à celles du comparateur classique compétent.
- Les cinq sondes distinctes conservent un témoin positif, trois faiblesses et une limite de confiance déjà déclarée concernant une réécriture cohérente avec nouvelle empreinte. Reproduire une faiblesse ne qualifie pas le vérificateur.
- Les **1 900 unités**, le **délai stipulé de 22 heures** et la **contribution modélisée de 650 $ US** restent des valeurs du scénario synthétique. La cible proposée distincte de **20 000 unités au plus dans un délai de 48 heures ouvrées convenues** reste à qualifier.
- La **perte modélisée historique de 1 080 $ US**, distincte, demeure attribuée à GENESIS Commitment 001.
- Les empreintes identifient des octets. Elles n’établissent ni l’exhaustivité, ni l’authenticité des obligations clients, ni une capacité réellement réservée, ni une exécution physique ou son acceptation.
- Un vérificateur implémenté séparément et des tâches de revue par IA attribuées distinctement ne deviennent pas, par traduction, une certification institutionnelle indépendante ou une comparaison entre deux modèles de pointe.

### Compilation, vérification et correction

`python3 build.py --language all` compile les deux manuscrits ; `python3 build.py` utilise le même choix de langues par défaut. `--language en` et `--language fr` sélectionnent un seul manuscrit. `python3 verify.py --check-build` vérifie les deux versions recompilées par rapport à leurs textes canoniques respectifs. Les octets des PDF peuvent différer selon les langues et les installations de TeX ; les identités de publication restent explicites. `check_translations.py --self-test` rejette aussi les titres non traduits sur la couverture, dans les en-têtes, dans la macro du texte et dans les métadonnées PDF, en maintenant les contrôles des mathématiques et des éléments probants. Les contrôles actuels du titre figurent dans `PUBLICATION.json` ; `evidence/QA.json` et `evidence/TRANSLATION_QA.json` restent les relevés historiques des éditions 1.0.0 et 1.1.0.

Si une divergence importante apparaît, comparer les deux énoncés, leur identifiant d’affirmation commun et la source citée. Corriger les parcours de lecture et les métadonnées concernés dans une édition révisée. Ne pas retenir silencieusement la langue la plus favorable, réécrire les éléments historiques ou écraser une publication antérieure. La traduction fait partie du contrôle de qualité de cette publication de recherche ; elle ne constitue pas une traduction juridique certifiée.

## Glossary / Glossaire

| English term | Français | Shared meaning / Sens commun |
| --- | --- | --- |
| CONTINUITY Ω | CONTINUITÉ Ω | Main title of the same research in each language. / Titre principal de la même recherche dans chaque langue. |
| Keep the promise. | Tenir parole. | Preserve the authorized customer outcome. / Préserver le résultat autorisé attendu par le client. |
| Independently verified cyber resilience | Cyberrésilience vérifiée de manière indépendante | Research ambition; disclose the independence actually present. / Ambition de recherche ; préciser l’indépendance effectivement présente. |
| Business commitment | Engagement envers le client | Agreed quantity, quality, integrity, timing and acceptance. / Quantité, qualité, intégrité, délai et acceptation convenus. |
| Fallback | Solution de repli | A qualified alternative route to the same outcome. / Une autre voie qualifiée vers le même résultat. |
| Handoff / handoff package | Transfert / dossier de transfert | Portable obligations and permitted production information. / Obligations transférables et informations de production dont le partage est autorisé. |
| Recovery / restored snapshot | Reprise / instantané restauré | Recovery activity and its recorded state; neither automatically proves delivery. / Activité de reprise et état consigné ; aucun des deux ne prouve automatiquement la livraison. |
| Reconciliation | Rapprochement des données | Compare the scoped records and account for discrepancies. / Comparer les données du périmètre et traiter les divergences. |
| Replay | Réexécution | Recompute the recorded logic from the identified inputs. / Recalculer la logique consignée à partir des entrées identifiées. |
| Evidence / evidence boundary | Éléments probants / périmètre des éléments probants | What supports a claim and what remains outside it. / Ce qui étaye une affirmation et ce qui reste hors de sa portée. |
| Counterexample | Contre-exemple | A reproducible case defeating a specified claim. / Un cas reproductible qui réfute une affirmation précise. |
| Claim | Affirmation | A statement with its own evidence status and limits. / Un énoncé avec son propre statut probant et ses limites. |
| Continuity Passport | Passeport de continuité | A scoped, maintained evidence package; no accreditation implied. / Un dossier probant délimité et tenu à jour ; aucune accréditation implicite. |
| Complete cost | Coût complet | All relevant lifecycle costs and obligations, counted once. / Tous les coûts et obligations pertinents du cycle de vie, comptés une seule fois. |
| Modeled contribution | Contribution modélisée | An authored receipts-minus-costs quantity, not collected profit. / Une différence recettes-coûts construite pour le modèle, et non un profit encaissé. |
| Simultaneous activation | Activation simultanée | Multiple contingent commitments become due together. / Plusieurs engagements conditionnels deviennent exigibles ensemble. |
| Qualified reuse | Réutilisation qualifiée | Reuse with applicability, rights, cost and outcome checks. / Réutilisation après vérification de l’applicabilité, des droits, des coûts et du résultat. |
| Successor opportunity | Occasion suivante rendue possible | A distinct opportunity requiring a new enabling construction. / Une occasion distincte exigeant une nouvelle construction qui la rend possible. |
| Frontier model | Modèle de pointe | A capable model whose actual availability and performance require evidence. / Un modèle performant dont la disponibilité et les résultats effectifs doivent être établis. |

## Publication inventory / Inventaire de la publication

| Material / Document | English / Anglais | Français | Relationship / Relation |
| --- | --- | --- | --- |
| Complete paper / Article intégral | `CONTINUITY_OMEGA.pdf` | `CONTINUITY_OMEGA_FR.pdf` | Complete parallel manuscripts. / Manuscrits complets parallèles. |
| Editable source / Source modifiable | `CONTINUITY_OMEGA.tex` | `CONTINUITY_OMEGA_FR.tex` | Same mathematics, evidence and source anchors. / Mêmes mathématiques, éléments probants et ancrages de sources. |
| Browser reader / Lecteur web | [English](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega.html) | [Français](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-fr.html) | Same authored interactive illustration and limits. / Même illustration interactive construite et mêmes limites. |
| Media galleries / Galeries multimédias | [English gallery](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-media.html) | [Galerie française](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-media-fr.html) | Four conceptual illustrations, user-controlled play/stop and complete transcripts. / Quatre illustrations conceptuelles, commandes de lecture et d’arrêt et transcriptions complètes. |
| Ascent / Ascension | [GIF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-ascent-en.gif) · [Still preview](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-ascent-en-poster.png) | [GIF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-ascent-fr.gif) · [Aperçu fixe](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-ascent-fr-poster.png) | Original English illustration and localized French adaptation; no operational result asserted. / Illustration anglaise d’origine et adaptation française localisée ; aucun résultat opérationnel revendiqué. |
| Reveal / Révélation | [GIF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-reveal-en.gif) · [Still preview](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-reveal-en-poster.png) | [GIF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-reveal-fr.gif) · [Aperçu fixe](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-reveal-fr-poster.png) | Original English illustration and localized French adaptation; no operational result asserted. / Illustration anglaise d’origine et adaptation française localisée ; aucun résultat opérationnel revendiqué. |
| Journey / Parcours | [GIF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-journey-en.gif) · [Still preview](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-journey-en-poster.png) | [GIF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-journey-fr.gif) · [Aperçu fixe](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-journey-fr-poster.png) | Original English illustration and localized French adaptation; no operational result asserted. / Illustration anglaise d’origine et adaptation française localisée ; aucun résultat opérationnel revendiqué. |
| In motion / En mouvement | [GIF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-motion-en.gif) · [Still preview](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-motion-en-poster.png) | [GIF](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-motion-fr.gif) · [Aperçu fixe](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-motion-fr-poster.png) | Original English illustration and localized French adaptation; no operational result asserted. / Illustration anglaise d’origine et adaptation française localisée ; aucun résultat opérationnel revendiqué. |
| Social cards / Visuels de partage | [PNG](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-social.png) · [SVG](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-card.svg) | [PNG](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-fr-social.png) · [SVG](https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/continuity-omega-fr-card.svg) | Language-specific research visuals with the same scope. / Visuels de recherche propres à chaque langue, de même portée. |
| Entry guide / Guide d’entrée | [README.md](README.md) | [README.fr.md](README.fr.md) | Complete guides. / Guides complets. |
| Review / Revue | [REVIEW.md](REVIEW.md) | [REVIEW.fr.md](REVIEW.fr.md) | Same challenges and corrections. / Mêmes objections et corrections. |
| Source lineage / Filiation des sources | [SOURCE_MAP.md](SOURCE_MAP.md) | [SOURCE_MAP.fr.md](SOURCE_MAP.fr.md) | Same references and page anchors. / Mêmes références et pages sources. |
| Evidence guide / Guide probant | [EVIDENCE.md](EVIDENCE.md) | [EVIDENCE.fr.md](EVIDENCE.fr.md) | Human explanation of shared records. / Explication des fichiers communs pour les lecteurs. |
| Claim register / Registre d’affirmations | [CLAIMS.json](CLAIMS.json) | [CLAIMS.fr.json](CLAIMS.fr.json) | Same 22 claim IDs, statuses, source anchors and measurements. / Mêmes 22 identifiants, statuts, ancrages de sources et mesures. |
| Citation metadata / Métadonnées de citation | [CITATION.cff](CITATION.cff) | [CITATION.fr.cff](CITATION.fr.cff) | Language-specific reading edition, shared research provenance. / Édition de lecture propre à chaque langue, même provenance scientifique. |
| Prototype guide / Guide du prototype | [README.md](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/continuity-omega-v1.1.1/docs/continuity-omega/README.md) | [README.fr.md](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/continuity-omega-v1.1.1/docs/continuity-omega/README.fr.md) | Full current guide with the same qualification note. / Guide courant complet avec la même note de portée. |
| Prototype quick start / Démarrage rapide | [QUICKSTART.md](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/continuity-omega-v1.1.1/docs/continuity-omega/QUICKSTART.md) | [QUICKSTART.fr.md](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/continuity-omega-v1.1.1/docs/continuity-omega/QUICKSTART.fr.md) | Same commands and synthetic-only scope. / Mêmes commandes et portée limitée au synthétique. |
| Proposed pilot / Pilote proposé | [REAL_PILOT.md](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/continuity-omega-v1.1.1/docs/continuity-omega/REAL_PILOT.md) | [REAL_PILOT.fr.md](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/continuity-omega-v1.1.1/docs/continuity-omega/REAL_PILOT.fr.md) | Same proposed obligations and acceptance gates. / Mêmes obligations proposées et conditions d’acceptation. |
| Release body / Notes de publication | [RELEASE_NOTES.md](RELEASE_NOTES.md) | [RELEASE_NOTES.md](RELEASE_NOTES.md) | Complete EN and FR sections in one file. / Sections EN et FR complètes dans un seul fichier. |
| Language contract / Contrat de traduction | This file. | Ce fichier. | Complete bilingual contract, glossary and inventory. / Contrat, glossaire et inventaire bilingues complets. |
| Evidence JSON, manifest and code / JSON probants, manifeste et code | Shared immutable records and executable identifiers. | Fichiers immuables et identifiants exécutables communs. | Explained in both evidence guides; no translated experimental record. / Expliqués dans les deux guides probants ; aucun dossier expérimental traduit distinct. |

The browser readers, media galleries and image assets, and prototype guides belong to the repository beside the paper folder. The source ZIP contains the paper folder and its complete bilingual materials; those adjacent web and prototype resources remain accessible through the links above. The animation galleries distinguish conceptual illustrations from operational evidence, provide complete transcripts and keep animation stopped until the reader chooses to play it.

Les lecteurs web, les galeries multimédias et leurs images, ainsi que les guides du prototype, se trouvent dans le dépôt, à côté du dossier de l’article. L’archive source contient le dossier de l’article et ses documents bilingues complets ; les ressources web et les guides du prototype adjacents restent accessibles par les liens ci-dessus. Les galeries distinguent les illustrations conceptuelles des éléments probants opérationnels, fournissent des transcriptions complètes et maintiennent les animations à l’arrêt jusqu’à ce que le lecteur choisisse de les lancer.

The public source references keep their pinned SHAs. The separately owned PR 279 hardening candidate is cited as the origin of counterexample leads; its implementation is not translated into, merged with, or qualified by this bilingual publication.

Les références aux sources publiques conservent leurs SHA figés. La proposition de renforcement de la PR 279, gérée séparément, est citée comme origine des pistes de contre-exemples ; son implémentation n’est ni incorporée par traduction, ni fusionnée, ni qualifiée par cette publication bilingue.
