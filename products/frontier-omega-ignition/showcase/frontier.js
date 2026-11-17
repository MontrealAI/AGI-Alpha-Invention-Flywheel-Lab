(() => {
  "use strict";
  const record = JSON.parse(document.getElementById("public-record").textContent);
  const edition = record.receipt;
  const study = record.study;
  const cards = globalThis.IGNITION_OPPORTUNITIES;
  const text = {
    en: {
      skip:"Skip to the exhibition",opps:"Opportunities",evidence:"Evidence",kit:"The instrument",title:"Bring your ambition",title2:"to the frontier.",
      intro:"Can a reader trace a passage back to the exact page of a published paper? Explore five openings in scientific publishing, then inspect the reading instrument we built for MONTREAL.AI.",
      inspect:"Explore the Reading Room",folio:"Source atlas · Research edition",plateTitle:"Anatomy of a paper",plateDetail:"Five physical pages. Each mark follows an extracted line of type.",
      frontier:"The frontier · November 2026",fieldTitle:"What can a lab publish next?",fieldIntro:"Recent advances in parsing, transcription and evaluation open different paths. Select an opportunity to see the source, the strongest alternative and the test that could decide.",
      forge:"The forge · Recorded execution",proofTitle:"Follow the passage.",proofIntro:"The author supplies the reading order. The instrument searches the original PDF for each heading and paragraph and issues a page link only when one page matches. Inspect the actual output below.",
      total:"Author blocks examined",matchedLabel:"Unique page matches",openLabel:"Left unlinked",find:"Open a passage",statusFilter:"Show passages",chooseBlock:"Author block",viewPage:"Open the original PDF page ↗",savePdf:"Save the PDF ↓",tableKicker:"The forge · Table Desk",tableTitle:"From pixels to a usable table.",tableIntro:"This table spans two printed pages. A local NVIDIA Nemotron-3.5-Parse model read each crop. Its two outputs were assembled and checked cell by cell against the author’s table.",crop:"Printed page crop",csv:"Download the verified CSV ↓",tableReceipt:"Download the model receipt ↓",tableDetail:"The included Codex visual reader, Tesseract with supplied cell boundaries and direct export from the author’s HTML produced the same file. The conventional export is the simplest route when the source table is available.",
      compared:"Against conventional tools",boundary:"What remains to be proved",limit:"The annotated author edition in the kit retains tables, equations and lists. A direct Poppler implementation produced byte-identical complete editions on both papers. The experiment measures passage links. Screen-reader usability, labor savings, paid demand and a newly crossed economic threshold require separate evidence.",
      kitTitle:"Take the reading edition.",kitIntro:"Open the reader, follow a passage to the original PDF, and rebuild it from the author’s manuscript. The download includes both source files, the executable instrument, the independent study and its registered criteria.",
      download:"Download the offline kit",reproduce:"Reproduce the edition",prereq:"Extract the ZIP. Open annotated-author.html for the full paper or index.html for the passage reader. For a fresh build, run these commands with Python 3 and Poppler’s pdftotext installed.",archiveHash:"Inspect the ZIP’s SHA-256",
      other:"From the same laboratory",pair:"When is a second coding attempt worth its cost? On 40 held-out issues the selected pair resolved 18, versus 16 for the best selected single system. Two additional resolutions consumed 13,764,105 more recorded tokens.",
      openPair:"Open the Pairing Lab ↗",savePair:"Download the standalone exhibit ↗",invTitle:"Bring a mission.",invitation:"MONTREAL.AI develops FRONTIER Ω for its own research. Selected IGNITION engagements may be scoped during a limited window. An enquiry opens a discussion about the objective, rights and acceptance criteria.",
      footer:"Built in Montréal",top:"Back to top ↑",all:"All passages",matched:"Unique match",ambiguous:"Several candidate pages",missing:"No whole-page match",selected:"Selected for construction",investigate:"Research hypothesis",signal:"What changed",challenge:"Strong alternative",gate:"Decisive test",
      block:"Block",source:"Physical PDF page",noLink:"The instrument withheld a page link.",empty:"No passages in this category.",nav:"Exhibition",choices:"Research opportunities",comparison:(a,b,n,c,t)=>`Of ${n} registered blocks, independent inspection credited ${a} correct page links to Reading Room and ${b} to the conventional MuPDF concordance. Adverse controls passed: ${c} of ${t}. The author’s original HTML remains a complete reading option.`,
    },
    fr: {
      skip:"Aller à l’exposition",opps:"Possibilités",evidence:"Résultats",kit:"L’instrument",title:"Portez votre ambition",title2:"à la frontière.",
      intro:"Peut-on retrouver la page exacte d’un article à partir d’un passage? Explorez cinq pistes pour l’édition scientifique, puis examinez l’instrument de lecture que nous avons construit pour MONTREAL.AI.",
      inspect:"Explorer la salle de lecture",folio:"Atlas des sources · Édition de recherche",plateTitle:"Anatomie d’un article",plateDetail:"Cinq pages du PDF. Chaque trait situe une ligne de texte extraite.",
      frontier:"La frontière · Novembre 2026",fieldTitle:"Que pourra publier le laboratoire?",fieldIntro:"Les progrès en analyse de documents, en transcription et en évaluation ouvrent plusieurs pistes. Choisissez-en une pour examiner sa source, la meilleure solution de rechange et l’épreuve qui pourrait les départager.",
      forge:"La forge · Exécution consignée",proofTitle:"Remontez à la source.",proofIntro:"Le manuscrit fournit l’ordre de lecture. Pour chaque titre et paragraphe, l’instrument cherche le texte dans le PDF et ajoute un lien si une seule page correspond. Explorez les résultats de cette exécution.",
      total:"Blocs du manuscrit examinés",matchedLabel:"Correspondances uniques",openLabel:"Blocs sans lien",find:"Ouvrir un passage",statusFilter:"Afficher les passages",chooseBlock:"Bloc du manuscrit",viewPage:"Ouvrir la page du PDF original ↗",savePdf:"Enregistrer le PDF ↓",tableKicker:"La forge · Atelier des tableaux",tableTitle:"Des pixels à un tableau exploitable.",tableIntro:"Ce tableau s’étend sur deux pages imprimées. Le modèle NVIDIA Nemotron-3.5-Parse a lu chaque extrait sur une machine locale. Les deux résultats ont été assemblés, puis comparés cellule par cellule au tableau de l’auteur.",crop:"Extrait de la page imprimée",csv:"Télécharger le fichier CSV vérifié ↓",tableReceipt:"Télécharger le relevé du modèle ↓",tableDetail:"La lecture visuelle de Codex, Tesseract avec les limites des cellules fournies et l’export direct du HTML de l’auteur ont produit le même fichier. L’export direct est le moyen le plus simple lorsque le tableau source est disponible.",
      compared:"Comparaison avec les outils classiques",boundary:"Ce qui reste à établir",limit:"L’édition annotée fournie conserve tableaux, équations et listes. Sur les deux articles, la méthode directe avec Poppler a produit des éditions complètes identiques octet pour octet. L’essai porte sur les liens vers les pages. L’usage avec un lecteur d’écran, le temps économisé, la demande payante et la viabilité économique restent à mesurer.",
      kitTitle:"Emportez l’édition.",kitIntro:"Lisez le texte, retrouvez un passage dans le PDF original, puis recréez l’édition à partir du manuscrit. La trousse contient les deux sources, l’instrument exécutable, l’étude indépendante et ses critères enregistrés.",
      download:"Télécharger la trousse hors ligne",reproduce:"Reproduire l’édition",prereq:"Décompressez la trousse. Ouvrez annotated-author.html pour l’article complet ou index.html pour la lecture par passage. Pour reconstruire l’édition, exécutez ces commandes avec Python 3 et l’utilitaire pdftotext de Poppler.",archiveHash:"Examiner l’empreinte SHA-256 du ZIP",
      other:"Du même laboratoire",pair:"Quand faut-il tenter une deuxième correction? Sur 40 problèmes réservés à l’évaluation, la paire retenue en a résolu 18, contre 16 pour la meilleure configuration seule choisie à l’étalonnage. Ces deux réussites ont coûté 13 764 105 jetons supplémentaires.",
      openPair:"Ouvrir le Pairing Lab ↗",savePair:"Télécharger l’exposition autonome ↗",invTitle:"Confiez une ambition au laboratoire.",invitation:"MONTREAL.AI développe FRONTIER Ω pour ses propres recherches. Durant une période limitée, certains projets externes pourront faire l’objet d’une mission IGNITION. Une prise de contact ouvre la discussion sur l’objectif, les droits et les critères d’acceptation.",
      footer:"Conçu à Montréal",top:"Haut de page ↑",all:"Tous les passages",matched:"Correspondance unique",ambiguous:"Plusieurs pages possibles",missing:"Aucune page correspondante",selected:"Piste retenue",investigate:"Piste à étudier",signal:"Évolution",challenge:"Solution de rechange",gate:"Épreuve décisive",
      block:"Bloc",source:"Page du PDF original",noLink:"L’instrument a laissé ce passage sans lien.",empty:"Aucun passage dans cette catégorie.",nav:"Exposition",choices:"Pistes de recherche",comparison:(a,b,n,c,t)=>`La vérification indépendante a confirmé ${a} liens pour la salle de lecture et ${b} pour la concordance classique de MuPDF, sur ${n} blocs. Cas défavorables réussis : ${c} sur ${t}. Le HTML original reste une édition complète de l’article.`,
    },
  };
  const el = id => document.getElementById(id);
  const put = (id,value) => { el(id).textContent = value; };
  const node = (tag,value) => { const n = document.createElement(tag); n.textContent = value; return n; };
  const bytes = Uint8Array.from(atob(record.archive.bytes), ch => ch.charCodeAt(0));
  function resource(name,type) {
    const [offset,length] = record.archive.offsets[name];
    return URL.createObjectURL(new Blob([bytes.subarray(offset,offset+length)],{type}));
  }
  const pdf = resource("source.pdf","application/pdf");
  const crops = [1,2].map(n => resource("table/page-"+n+".png","image/png"));
  el("csv-download").href = resource("table/cycle-001.csv","text/csv;charset=utf-8");
  el("table-receipt").href = resource("table/nemotron/receipt.json","application/json");
  el("pdf-download").href = pdf;
  el("download").href = URL.createObjectURL(new Blob([bytes], {type:"application/zip"}));
  el("pair-link").href = location.pathname === "/exhibition" ? "/showcase" : "PAIRING_LAB.html";
  put("hash",record.archive.sha256);
  let locale = "en", selected = 0;
  const lang = () => text[locale];
  function selectCard(index) {
    selected = index;
    const card = cards[index], copy = card[locale];
    [...el("choices").children].forEach((b,i) => b.setAttribute("aria-pressed",String(i===index)));
    put("candidate-status",lang()[card.status]);
    put("candidate-title",copy.title);
    put("candidate-benefit",copy.benefit);
    el("candidate-detail").replaceChildren(...["signal","challenge","gate"].flatMap(k => [node("dt",lang()[k]),node("dd",copy[k])]));
    el("sources").replaceChildren(...card.sources.map(s => {
      const item = node("li","");
      const a = node("a",`${s.publisher} · ${s.title} · ${s.date} ↗`);
      a.href = s.url; a.rel = "noopener noreferrer"; a.target = "_blank"; item.append(a); return item;
    }));
  }
  function viewBlock() {
    const block = edition.blocks.find(b => b.index === Number(el("passage").value));
    el("pdf-download").hidden = !block || block.status !== "matched";
    el("source-page").hidden = true; el("source-page").removeAttribute("href");
    put("block-id",block ? `${lang().block} ${block.index} · ${lang()[block.status]}` : lang().empty);
    put("quotation",block ? block.text : "");
    put("witness","");
    if (!block) return;
    if (block.status === "matched") {
      put("witness",`${lang().source} ${block.page} / ${edition.page_count}`);
      el("source-page").href = pdf + "#page=" + block.page; el("source-page").hidden = false;
    } else {
      put("witness",lang().noLink + (block.candidate_pages.length ? " " + block.candidate_pages.join(", ") : ""));
    }
  }
  function filterBlocks(previous) {
    const status = el("filter").value;
    const rows = edition.blocks.filter(b => status === "all" || b.status === status);
    el("passage").replaceChildren(...rows.map(b => new Option(`${b.index} · ${b.text.slice(0,62)}`, String(b.index))));
    if (rows.some(b => String(b.index)===previous)) el("passage").value = previous;
    el("passage").disabled = rows.length === 0; viewBlock();
  }
  function viewCrop() {
    const i = Number(el("table-page").value) - 1;
    el("table-image").src = crops[i];
    el("table-image").height = i === 0 ? 501 : 294;
    el("table-image").alt = locale === "en" ? "Original text table from physical PDF page "+(i+1)
      : "Extrait du tableau de l’article, page "+(i+1)+" du PDF";
    put("table-caption",(locale === "en" ? "Source PDF, physical page " : "PDF original, page ")+(i+1));
    const desk = record.table, seconds = desk.seconds.toLocaleString(locale,{maximumFractionDigits:2});
    const elapsed = desk.page_seconds[i].toLocaleString(locale,{maximumFractionDigits:2});
    put("table-result",locale === "en" ? `Recorded on CPU · Page ${i+1} took ${elapsed} s. Across both pages, ${desk.cells} text cells matched. The complete run took ${seconds} s on ${desk.threads} threads, including validation and model loading.`
      : `Exécution consignée sur processeur · Page ${i+1} traitée en ${elapsed} s. Sur les deux pages, ${desk.cells} cellules de texte concordent. Le traitement complet a pris ${seconds} s sur ${desk.threads} fils d’exécution, vérification et chargement du modèle compris.`);
  }
  function verdict() {
    const accepted = study.verdicts.passage_acceptance;
    const missing = study.paper.candidate.counts.omitted || 0;
    if (locale === "fr") {
      return (accepted ? "L’édition satisfait aux critères enregistrés pour les passages."
        : "L’édition échoue aux critères enregistrés pour les passages.") +
        (missing ? ` Blocs du manuscrit omis : ${missing}.` : "");
    }
    return (accepted ? "The edition passed the registered passage criteria."
      : "The edition failed the registered passage criteria.") +
      (missing ? ` Omitted manuscript blocks: ${missing}.` : "");
  }
  function render() {
    const t = lang(), lastFilter = el("filter").value || "all", lastBlock = el("passage").value;
    document.documentElement.lang = locale;
    document.title = locale==="en" ? "FRONTIER Ω IGNITION · Reading Room" : "FRONTIER Ω IGNITION · Salle de lecture";
    for (const e of document.querySelectorAll("[data-t]")) e.textContent = t[e.dataset.t];
    const other = locale === "en" ? "fr" : "en";
    put("locale",other.toUpperCase()); el("locale").lang = other;
    el("locale").setAttribute("aria-label",other === "fr" ? "Français" : "English");
    document.querySelector("header nav").setAttribute("aria-label",t.nav);
    el("choices").setAttribute("aria-label",t.choices);
    el("choices").replaceChildren(...cards.map((card,index) => {
      const b = node("button",card[locale].title); b.type = "button"; b.addEventListener("click",() => selectCard(index)); return b;
    }));
    selectCard(selected);
    put("count-total",edition.summary.total); put("count-matched",edition.summary.matched);
    put("count-open",edition.summary.total-edition.summary.matched);
    el("filter").replaceChildren(...["all","matched","ambiguous","missing"].map(k => new Option(t[k],k)));
    el("filter").value = lastFilter; filterBlocks(lastBlock);
    viewCrop();
    put("verdict",verdict());
    put("comparison",t.comparison(study.paper.candidate.correct_links,study.paper.conventional.correct_links,
      study.paper.candidate.total,study.adverse.passed,study.adverse.total));
  }
  el("table-page").addEventListener("change",viewCrop);
  el("locale").addEventListener("click",() => { locale = locale === "en" ? "fr" : "en"; render(); });
  el("filter").addEventListener("change",() => filterBlocks(""));
  el("passage").addEventListener("change",viewBlock);
  render();
})();
