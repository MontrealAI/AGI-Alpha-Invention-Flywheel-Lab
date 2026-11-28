// Public derivatives of dated primary sources. Operation descriptors contain
// public model identifiers only and never authorize inference or execution.
export const currentOpportunities = [
  {
    id: 'bonsai-local-deployment',
    date: '2026-11-24',
    sourceURL: 'https://prismml.com/news/prismml-launches-ternary-bonsai-2-5-27b',
    resources: ['https://huggingface.co/prism-ml/Ternary-Bonsai-2.5-27B-GGUF'],
    match: {
      en: ['local AI', 'private inference', 'on-device coding', 'open weights', 'local coding assistant', 'coding assistant', 'run locally', 'local model', 'local workstation', 'machine capacity', 'GGUF', 'Bonsai'],
      fr: ['IA locale', 'inférence locale', 'poids ouverts', 'assistant de programmation local', 'assistant de programmation', 'exécution locale', 'modèle local', 'poste de travail', 'capacité de la machine', 'GGUF', 'Bonsai'],
    },
    en: {
      title: 'Choose a model for private coding',
      change: 'PrismML released the Apache 2.0 Bonsai 2.5 27B model. The developer reports stronger coding and tool-use benchmark results than its previous compressed model.',
      benefit: 'Compare two real weight files and save their exact versions, hashes, licenses and download sizes before deciding what to evaluate locally.',
      limit: 'The inventory checks publisher metadata and download sizes. Runtime memory, output quality and a benefit on your work still require a local comparison.',
      ambition: 'Prepare a reproducible local coding assistant and compare the available Bonsai GGUF files before downloading weights.',
      action: 'Compare model files',
    },
    fr: {
      title: 'Choisir un modèle pour programmer en privé',
      change: 'PrismML a publié le modèle Bonsai 2.5 27B sous licence Apache 2.0. Le développeur rapporte de meilleurs résultats en programmation et en utilisation d’outils que pour son modèle compressé précédent.',
      benefit: 'Comparer deux fichiers de poids et conserver leurs versions exactes, leurs empreintes, leur licence et leur taille avant de choisir quoi évaluer localement.',
      limit: 'L’inventaire vérifie les métadonnées de l’éditeur et la taille des téléchargements. La mémoire utilisée, la qualité et le gain sur vos propres tâches restent à mesurer localement.',
      ambition: 'Préparer un assistant de programmation local et reproductible, puis comparer les fichiers GGUF de Bonsai avant de télécharger les poids.',
      action: 'Comparer les fichiers du modèle',
    },
    operation: {
      kind: 'huggingface-model-inventory',
      repo: 'prism-ml/Ternary-Bonsai-2.5-27B-GGUF',
      filename: 'Ternary-Bonsai-2.5-27B-PTQ1_0.gguf',
      comparisonFilename: 'Ternary-Bonsai-2.5-27B-Q2_0.gguf',
    },
  },
  {
    id: 'soma-private-document-extraction',
    date: '2026-11-25',
    sourceURL: 'https://www.amini.ai/blog-post/introducing-soma-1x-lite-a-2b-model-for-document-intelligence',
    resources: ['https://huggingface.co/AminiTech/Soma-1X-lite-GGUF'],
    match: {
      en: ['scanned documents', 'scanned pages', 'extract text', 'extract tables', 'document extraction', 'optical character recognition', 'visual extraction', 'supplier specifications', 'supplier specs', 'OCR', 'Soma'],
      fr: ['documents numérisés', 'pages numérisées', 'extraire le texte', 'extraire des tableaux', 'extraction de documents', 'reconnaissance de caractères', 'extraction visuelle', 'fiches fournisseurs', 'spécifications des fournisseurs', 'OCR', 'Soma'],
    },
    en: {
      title: 'Prepare private extraction from scanned documents',
      change: 'Amini released the Apache 2.0 Soma-1X Lite document model. Its local GGUF workflow is designed to preserve text and layout, with a separate vision encoder.',
      benefit: 'Get a pinned manifest for the weights, vision encoder and prompts before bringing any documents into a local evaluation.',
      limit: 'The operation checks the file list. Extraction accuracy and the review effort for your documents still require a comparison with conventional OCR.',
      ambition: 'Prepare a reproducible local workflow for extracting text and tables from scanned documents without sharing the documents externally.',
      action: 'Get the required file list',
    },
    fr: {
      title: 'Préparer l’extraction locale de documents numérisés',
      change: 'Amini a publié son modèle documentaire Soma-1X Lite sous licence Apache 2.0. Le mode local au format GGUF vise à préserver le texte et la mise en page et exige un encodeur visuel distinct.',
      benefit: 'Obtenir une liste versionnée des poids, de l’encodeur visuel et des instructions nécessaires avant d’utiliser les documents pour un essai local.',
      limit: 'Cette opération vérifie la liste des fichiers. La précision d’extraction et l’effort de révision sur vos documents restent à comparer à la reconnaissance de caractères classique.',
      ambition: 'Préparer un processus local et reproductible pour extraire le texte et les tableaux de documents numérisés sans les transmettre à un service externe.',
      action: 'Relever les fichiers nécessaires',
    },
    operation: {
      kind: 'huggingface-model-inventory',
      repo: 'AminiTech/Soma-1X-lite-GGUF',
      filename: 'Soma-1X-lite-Q8_0.gguf',
      requiredFilenames: ['mmproj-Soma-1X-lite-F16.gguf', 'system_prompt.txt', 'user_prompt.txt'],
    },
  },
];
