// Public, authored research cards. Qualification results come from the separate receipt.
globalThis.IGNITION_OPPORTUNITIES = [
  {
    id: "reading-editions",
    status: "selected",
    sources: [
      {
        date: "2026-10-21",
        publisher: "NVIDIA",
        title: "Nemotron 3.5 Parse",
        url: "https://huggingface.co/blog/nvidia/nemotron-retriever-world-class-agentic-retrieval",
      },
      {
        date: "2026-11-12",
        publisher: "Doulcet et al.",
        title: "ParseBench-2",
        url: "https://arxiv.org/abs/2611.17400",
      },
    ],
    en: {
      title: "Research reading editions",
      benefit: "Follow the author’s manuscript in reading order. Link each passage to its uniquely matching PDF page and flag unresolved matches.",
      signal: "NVIDIA released a parser that locates and orders text. ParseBench-2 shows how a high extraction score can conceal a changed fact.",
      challenge: "The author’s HTML may already give readers the complete text in the right order.",
      gate: "Compare the edition with author sources and ordinary PDF extraction. Measure errors, reader effort and the pages that need review.",
    },
    fr: {
      title: "Éditions de lecture scientifique",
      benefit: "Lire le manuscrit dans l’ordre des auteurs. Relier chaque passage à la page PDF où il apparaît de façon unique et signaler les cas à vérifier.",
      signal: "NVIDIA a publié un modèle qui situe et ordonne le texte. ParseBench-2 montre qu’un bon score d’extraction peut masquer une erreur de fond.",
      challenge: "La version HTML des auteurs offre parfois déjà le texte intégral dans le bon ordre.",
      gate: "Comparer l’édition aux sources des auteurs et à une extraction PDF classique. Mesurer les erreurs, l’effort de lecture et les pages à réviser.",
    },
  },
  {
    id: "figure-data",
    status: "investigate",
    sources: [
      {
        date: "2026-10-14",
        publisher: "Datalab",
        title: "Chandra 2.5",
        url: "https://www.datalab.to/blog/chandra-2-5",
      },
    ],
    en: {
      title: "Recover the data behind a figure",
      benefit: "Turn a published chart into reusable data, with units and an explicit distinction between printed and estimated values.",
      signal: "Chandra 2.5 returns chart panels as tables and marks values estimated from an axis.",
      challenge: "The original data file may be available. A specialist can digitize the plot when it is the only surviving source.",
      gate: "Blind-test unseen plots with known source data. Check units, series identity and numerical error against expert digitization.",
    },
    fr: {
      title: "Retrouver les données d’une figure",
      benefit: "Tirer d’un graphique des données réutilisables, avec leurs unités et une distinction claire entre valeurs imprimées et estimées.",
      signal: "Chandra 2.5 restitue chaque volet d’un graphique sous forme de tableau et signale les valeurs estimées à partir d’un axe.",
      challenge: "Le fichier de données d’origine peut être disponible. Si seul le graphique subsiste, un spécialiste peut en relever les valeurs.",
      gate: "Tester à l’aveugle des graphiques inédits dont les données sont connues. Comparer les unités, les séries et les écarts numériques au relevé d’un spécialiste.",
    },
  },
  {
    id: "experiment-replay",
    status: "investigate",
    sources: [
      {
        date: "2026-11-05",
        publisher: "Wang et al.",
        title: "ReproBridge",
        url: "https://arxiv.org/abs/2611.08452",
      },
    ],
    en: {
      title: "Replay a published experiment",
      benefit: "Give another lab the code, configuration and commands it needs to regenerate a reported result.",
      signal: "ReproBridge tested whether storing recovered execution procedures helped a fresh agent reproduce experiments.",
      challenge: "An author-maintained environment and run script may already reproduce the result in one command.",
      gate: "Give each route a clean environment. Count preparation and failed runs, then compare regenerated results with an independent reference.",
    },
    fr: {
      title: "Rejouer une expérience publiée",
      benefit: "Fournir à un autre laboratoire le code, la configuration et les commandes nécessaires pour reproduire un résultat.",
      signal: "L’équipe de ReproBridge a testé si un nouvel agent reproduisait mieux les expériences lorsqu’il disposait des procédures reconstituées.",
      challenge: "L’environnement et le script fournis par les auteurs permettent parfois déjà de reproduire le résultat en une commande.",
      gate: "Donner à chaque méthode un environnement vierge. Comptabiliser la préparation et les échecs, puis comparer les résultats à une référence indépendante.",
    },
  },
  {
    id: "bilingual-seminars",
    status: "investigate",
    sources: [
      {
        date: "2026-10-28",
        publisher: "NVIDIA",
        title: "Nemotron 3.5 Transcribe",
        url: "https://huggingface.co/blog/nvidia/nemotron-transcribe-granary",
      },
    ],
    en: {
      title: "Bilingual seminar editions",
      benefit: "Let a reader search a research talk in French or English, identify the speaker and listen to the original passage.",
      signal: "NVIDIA released an open-weight model combining multilingual transcription, translation and speaker attribution.",
      challenge: "A direct transcription system and a bilingual editor can already prepare searchable proceedings.",
      gate: "Use a consented recording with language changes. Check scientific names, speaker turns and timing against an independent bilingual transcript.",
    },
    fr: {
      title: "Éditions bilingues de séminaires",
      benefit: "Retrouver en français ou en anglais un passage d’une conférence, identifier la personne qui parle et réécouter l’extrait.",
      signal: "NVIDIA a publié les poids d’un modèle qui réunit transcription multilingue, traduction et attribution de la parole.",
      challenge: "Un logiciel de transcription et une révision bilingue permettent déjà de publier des actes consultables.",
      gate: "Avec le consentement des participants, tester un enregistrement où les langues alternent. Vérifier les noms scientifiques, les tours de parole et le minutage à partir d’une transcription bilingue indépendante.",
    },
  },
  {
    id: "claim-audit",
    status: "investigate",
    sources: [
      {
        date: "2026-11-12",
        publisher: "Zubeldia et al.",
        title: "Auditing AI peer reviewers",
        url: "https://arxiv.org/abs/2611.17052",
      },
    ],
    en: {
      title: "Audit scientific claims",
      benefit: "Show an editor the passage or calculation behind a disputed claim before publishing a correction.",
      signal: "A study of AI reviewers tested citation retrieval and numerical checks on altered and clean papers. The gain from retrieving citations varied by field.",
      challenge: "An expert with conventional tools or a directly prompted frontier model may resolve the same discrepancy.",
      gate: "Mix clean and deliberately altered claims in a blinded review. Measure missed errors, false alarms and time to justify each finding.",
    },
    fr: {
      title: "Vérifier les affirmations scientifiques",
      benefit: "Montrer à la rédaction le passage ou le calcul qui permet de trancher une question avant de publier un correctif.",
      signal: "Une étude a testé la recherche de références et la vérification numérique sur des articles intacts ou modifiés. L’apport de la recherche de références variait selon le domaine.",
      challenge: "Une personne experte munie d’outils classiques ou un modèle avancé interrogé directement peut déjà résoudre le désaccord.",
      gate: "Faire examiner à l’aveugle des affirmations intactes et modifiées. Mesurer les erreurs manquées, les fausses alertes et le temps nécessaire pour justifier chaque constat.",
    },
  },
];
