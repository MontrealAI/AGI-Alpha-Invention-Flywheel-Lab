# FRONTIER Ω IGNITION · Reading Room

Download [the standalone bilingual flagship](../../../docs/frontier-omega-ignition/continuation/FRONTIER_IGNITION.html) and open it in a browser. A full checkout also contains the [Pairing Lab](../../../docs/frontier-omega-ignition/continuation/PAIRING_LAB.html) next to it. The public exhibition is available at `/exhibition` in the running workbench. The Pairing Lab keeps its original `/showcase` route.

## Five minutes in English or French

| Time | English | Français |
|---|---|---|
| 0:00–0:35 | Start at the source atlas. The five sheets reproduce the line positions of Vincent Boucher’s public campaign paper. Ask the audience how they would verify a passage found in a different edition. | Présentez l’atlas. Les cinq feuilles reproduisent la position des lignes dans l’article public de Vincent Boucher. Comment vérifier un passage repéré dans une autre édition? |
| 0:35–1:20 | Open one or two opportunity cards. The sources document recent advances. For this paper the lab already has a stronger starting point for reading order: the author’s manuscript. | Ouvrez une ou deux pistes. Les sources documentent des progrès récents. Pour cet article, le manuscrit fournit déjà l’ordre de lecture. |
| 1:20–2:25 | Choose **Unique match** and a passage. Open the PDF page. Then show an unlinked block. The recorded instrument searches extracted text and withholds uncertain page links. | Choisissez **Correspondance unique**, puis un passage. Ouvrez la page du PDF. Montrez ensuite un bloc sans lien. L’instrument cherche le texte extrait et laisse les correspondances incertaines sans lien. |
| 2:25–3:30 | Read the registered verdict and conventional comparator aloud. The native author edition retains tables, equations and links. Discuss what a reader can already accomplish there. | Lisez le verdict enregistré et le résultat de la méthode classique. L’édition originale conserve tableaux, équations et liens. Que permet-elle déjà au lecteur? |
| 3:30–4:30 | Download the ZIP, extract it and open index.html. Open receipt.json to inspect a match and its source-file fingerprint. With Python and Poppler installed, repeat the command displayed in the exhibit. | Téléchargez la trousse, décompressez-la et ouvrez index.html. Consultez receipt.json pour examiner une correspondance et l’empreinte de sa source. Avec Python et Poppler, reproduisez l’édition. |
| 4:30–5:00 | End with the fresh test: readers locate citations on previously unseen papers using all three editions. Measure accuracy and time, including abstentions and assistance. At Table Desk, compare the actual table crop, the model’s accepted CSV and the direct author export. | Terminez par le prochain essai. Des lecteurs devront retrouver des citations dans de nouveaux articles avec les trois éditions. Mesurez la justesse et le temps, y compris les recherches infructueuses et l’aide requise. Dans l’atelier des tableaux, comparez l’extrait imprimé, le CSV issu du modèle et l’export direct du tableau de l’auteur. |

The exhibition uses only a registered PDF/HTML pair, the portable local producer and an independent adjudication. Source cards describe published advances. The browser presents recorded outputs, changes filters and opens or downloads local bytes. It runs no inference. The PDF remains in its original language when the interface switches languages. A PDF viewer may require entering the printed physical page number if it ignores a page fragment.

## Rebuild and inspect

From the product directory with Python 3, lxml, Poppler and the same pdftotext version recorded in the study:

```sh
python3 -B showcase/frontier.py --output ../../docs/frontier-omega-ignition/continuation/FRONTIER_IGNITION.html
node showcase/frontier_browser.cjs ../../docs/frontier-omega-ignition/continuation/FRONTIER_IGNITION.html
```

The browser check uses Playwright Core and Chromium as in the [Pairing Lab browser qualification](README.md). Optional arguments save desktop English and mobile French captures and exercise the real workbench boundary: `node showcase/frontier_browser.cjs EXHIBIT.html /tmp/exhibit-views http://127.0.0.1:8784/`. The separate [study guide](../reading_room_study/README.md) explains how to rebuild both candidate and conventional readers, inspect the visual page key and compare outcomes. For the earlier exhibit, use the [Pairing Lab presenter notes](PRESENT.md).

The offline kit includes the complete original author markup with verified page links in `annotated-author.html`, separately qualified in RR-02. Its direct Poppler comparator produced byte-identical output on both papers. Table Desk includes the two source crops, model outputs, receipts and exact CSV. Nemotron inference ran on the CPU before the exhibition. The browser opens those recorded bytes. Use the [Table Desk instructions](../table_desk/README.md) for the independent recipient.
