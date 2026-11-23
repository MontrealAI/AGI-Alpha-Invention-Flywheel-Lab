// Static member reading edition. Drawn from public sources and new proposed work.
export const brief001 = {
  "version": "1.1",
  "en": {
    "title": "Compile the decisions before calling the model",
    "edition": "Brief 001 · Version 1.1 · 23 November 2026",
    "sections": [
      {
        "heading": "What changed",
        "paragraphs": [
          "AnyS1 compiles decisions with known options out of written procedures. Its 4B pointer model handles routine choices and escalates uncertain ones. The preprint reports 75–91% lower episodic cost and 63–92% less model-call time against an uncompiled large-model agent. The result leaves open whether a competent rule-based workflow is already cheaper."
        ]
      },
      {
        "heading": "The overlooked move",
        "paragraphs": [
          "Use the same decision contract in two unrelated jobs. Each case declares permitted outcomes, the evidence that can support each outcome, and when to abstain. Apply ordinary rules first. A small local ranker can suggest which public source to check next in genuinely ambiguous cases. The independent verifier still decides what the record supports.",
          "For publication intake, separate a known invalid record from a valid candidate missing its versioned source. For equipment documentation, distinguish a documented compatibility route from a missing machine configuration. The two jobs share the contract. Each keeps its own rules and source index."
        ]
      },
      {
        "heading": "Smallest decisive test",
        "paragraphs": [
          "Work on temporary copies. Run the existing publication validator tests and replay the public ALPHA-1 technical cases using the inputs linked below. Freeze the two input versions. An independent reviewer then makes 24 new cases per workflow with expected outcomes and acceptable citations: eight straightforward, eight recoverable ambiguities and eight required holds. Hash the set before the comparison. Keep its answers hidden during development.",
          "Arm A uses the existing Python validator or SQLite rules, search of the same pinned materials, and competent review. Arm B adds a sparse ranker over source type, normalized identifiers and version. Fit it on separate development examples, freeze it before evaluation and keep its weights and abstention threshold fixed for the second workflow. Both arms can choose an allowed evidence lookup or a hold. The reviewer scores the cases in mixed order without arm labels.",
          "Record the decision, selected evidence, abstention, reviewer minutes, wall time, retries and completion for each case. Count failures and setup. Continue only if each job has zero material false accepts, matches the incumbent’s accepted outcomes and cuts median handling time by at least 25%. Compare total cost over 100 similar cases before making an adoption decision."
        ]
      },
      {
        "heading": "Budget, break-even and stop rule",
        "paragraphs": [
          "Cap the test at four builder hours, two reviewer hours and one CPU-hour. The test uses local tools and public inputs. No paid model calls are needed. Use actual labor rates when available and keep raw minutes too.",
          "Divide one-time labor by net labor saved per case, counting added review and maintenance. For scale, six setup hours and 30 seconds saved on 10% of cases yield a break-even of at least 7,200 cases before maintenance. At 100 cases, six setup hours require more than 216 seconds of net savings per case. These are planning examples. If the test cannot close the gap, keep the incumbent. Stop immediately if a draft passes with wrong evidence."
        ]
      },
      {
        "heading": "What we can retain",
        "paragraphs": [
          "Keep the typed decision contract, hashed examples and an independent scorer, even if the ranker loses. For a third workflow, measure time to an accepted result using the retained contract against a team implementing the same known method from its description under equal time and authority. The pilot exercises decision support only. The experiment and any economic benefit remain unmeasured."
        ]
      }
    ],
    "sources": [
      {
        "label": "AnyS1 preprint v1",
        "href": "https://arxiv.org/abs/2611.23751v1"
      },
      {
        "label": "Publication validator and test inputs",
        "href": "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/cf3860018083d299a78ee2c7643d61092e93933e/tests/test_research_site.py"
      },
      {
        "label": "ALPHA-1 public inputs and SQLite comparison",
        "href": "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/5cced81256c965797988cd682fb5f910fe72c981/products/frontier-omega-alpha/research/economic_alpha"
      }
    ]
  },
  "fr": {
    "title": "Compiler les décisions avant d’appeler le modèle",
    "edition": "Dossier 001 · Version 1.1 · 23 novembre 2026",
    "sections": [
      {
        "heading": "Ce qui a changé",
        "paragraphs": [
          "AnyS1 extrait de procédures écrites des décisions dont les options sont connues. Son modèle de 4 milliards de paramètres traite les choix courants et transmet les cas incertains au modèle principal. La prépublication rapporte des coûts par épisode réduits de 75 à 91 % et des délais d’appel réduits de 63 à 92 % face à un agent à grand modèle dont les procédures n’ont pas été compilées. Une méthode à base de règles bien conçue pourrait déjà coûter moins cher."
        ]
      },
      {
        "heading": "Le levier négligé",
        "paragraphs": [
          "Utiliser le même contrat de décision pour deux tâches distinctes. Chaque cas déclare les résultats autorisés, les preuves qui peuvent les appuyer et les conditions d’abstention. Appliquer d’abord les règles ordinaires. Dans les cas réellement ambigus, un petit outil de classement local peut suggérer la prochaine source publique à vérifier. Un évaluateur indépendant tranche sur les preuves.",
          "À l’entrée des publications, distinguer une fiche invalide d’une fiche plausible dont la source versionnée manque. Dans la documentation d’équipement, distinguer une compatibilité documentée d’une configuration inconnue. Les deux tâches partagent le contrat et chacune conserve ses règles et son index de sources."
        ]
      },
      {
        "heading": "Le plus petit essai décisif",
        "paragraphs": [
          "Travailler sur des copies temporaires. Lancer les tests du validateur de publication et rejouer les cas techniques publics d’ALPHA-1 à l’aide des entrées ci-dessous. Figer les deux versions. Un évaluateur indépendant prépare ensuite 24 cas inédits par processus, avec les résultats et les citations acceptables : huit cas directs, huit ambiguïtés résolubles et huit mises en attente obligatoires. Calculer l’empreinte du lot et garder les réponses masquées pendant le développement.",
          "La méthode A utilise le validateur Python ou les règles SQLite existantes, une recherche dans les mêmes sources figées et l’aide d’un réviseur compétent. La méthode B ajoute un classement parcimonieux selon le type de source, les identifiants normalisés et la version. Régler les poids et le seuil d’abstention sur d’autres exemples, puis les figer pour le deuxième processus. Les deux méthodes peuvent suggérer une recherche permise ou une mise en attente. Noter les cas en ordre mélangé sans afficher la méthode.",
          "Consigner la décision, la preuve retenue, les abstentions, les minutes d’examen, le temps écoulé, les reprises et le résultat. Compter les échecs et la préparation. Poursuivre si chaque processus affiche zéro acceptation erronée importante, conserve les résultats acceptés du témoin et réduit d’au moins 25 % le temps médian de traitement. Comparer le coût total sur 100 cas similaires avant de décider d’adopter la méthode."
        ]
      },
      {
        "heading": "Budget, seuil de rentabilité et arrêt",
        "paragraphs": [
          "Limiter l’essai à quatre heures de développement, deux heures d’examen indépendant et une heure de calcul CPU. Les outils locaux et les entrées publiques suffisent. Utiliser les coûts horaires réels dès qu’ils sont connus et conserver aussi les minutes brutes.",
          "Diviser le travail initial par le temps net économisé par cas, en intégrant la révision et l’entretien. À titre d’exemple, six heures de préparation et 30 secondes gagnées sur 10 % des cas donnent un seuil d’au moins 7 200 cas avant entretien. Sur seulement 100 cas, six heures de préparation exigent plus de 216 secondes de gain net par cas. Si l’écart subsiste, garder la méthode en place. Arrêter dès qu’une décision est acceptée à partir d’une preuve erronée."
        ]
      },
      {
        "heading": "Les acquis à conserver",
        "paragraphs": [
          "Garder le contrat typé, les exemples avec leur empreinte et le vérificateur indépendant, même si le classement perd. Pour un troisième processus, mesurer le délai jusqu’à l’acceptation en comparant le contrat conservé à une reconstruction de la même méthode à partir de sa description, à ressources et privilèges égaux. L’essai se limite à l’aide à la décision. Ses résultats et sa valeur économique restent à mesurer."
        ]
      }
    ],
    "sources": [
      {
        "label": "Prépublication AnyS1 v1",
        "href": "https://arxiv.org/abs/2611.23751v1"
      },
      {
        "label": "Validateur de publication et données d’essai",
        "href": "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/cf3860018083d299a78ee2c7643d61092e93933e/tests/test_research_site.py"
      },
      {
        "label": "Entrées publiques et comparaison SQLite d’ALPHA-1",
        "href": "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/5cced81256c965797988cd682fb5f910fe72c981/products/frontier-omega-alpha/research/economic_alpha"
      }
    ]
  }
};
