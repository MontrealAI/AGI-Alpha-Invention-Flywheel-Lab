"""Prepare a bilingual, private reading packet from a verified research run."""


def member_packet(plan, report):
    count = sum(len(stage['theorems']) for stage in report['stages'])
    cases = sum(len(stage['cases']) for stage in report['stages'])
    bytes_used = sum(file['bytes'] for stage in report['stages'] for file in stage['files'].values())
    fr_bytes = f'{bytes_used:,}'.replace(',', ' ')
    bylines = [
        {'en': 'MIT verification files', 'fr': 'Dossier de vérification du MIT', 'url': plan['sources']['mit-rh']['url']},
        {'en': 'Lean and Mathlib community verification', 'fr': 'Vérification par les communautés Lean et Mathlib',
         'url': plan['sources']['lean-rh']['url']}
    ]
    records = [
        (
            'radar', 'Formal proof receipts become available', 'De nouveaux rapports de vérification formelle',
            ['The Lean and Mathlib communities certified the statement and proof of the Riemann Hypothesis on 21 November 2026.',
             'Public logs report statement matching and allowed axioms. The cited receipts were unavailable at the registered 15 November comparison date.'],
            ['Les communautés Lean et Mathlib ont certifié l’énoncé et la preuve de l’hypothèse de Riemann le 21 novembre 2026.',
             'Les journaux publics documentent la concordance des énoncés et les axiomes utilisés. Ces pièces n’étaient pas disponibles à la date de comparaison du 15 novembre.'],
        ),
        (
            'opportunity', 'Screen large formal dependencies', 'Présélectionner des dépendances formelles volumineuses',
            ['A research team can screen a named formal dependency before committing resources to a full build. The initial comparison used direct receipt inspection.',
             'A full kernel replay remains a different acceptance task. Beneficiary adoption, integration cost and willingness to pay are open.'],
            ['Une équipe peut vérifier les pièces disponibles pour une dépendance formelle précise avant d’engager des ressources dans une compilation intégrale. L’inspection directe des rapports a servi de comparaison.',
             'La vérification intégrale par le noyau répond à un autre besoin. L’adoption, le coût d’intégration et la volonté de payer restent à établir.'],
        ),
        (
            'experiment', 'Two receipt cohorts', 'Deux ensembles de pièces justificatives',
            [f'The experiment used {bytes_used:,} bytes of pinned statements and logs for {count} declarations. '
             f'The reusable parser and independent reference agreed with the registered outcomes on {cases} cases.'],
            [f'L’essai a analysé {fr_bytes} octets d’énoncés et de journaux identifiés par empreinte pour {count} déclarations. '
             f'L’analyse réutilisable et le contrôle indépendant ont concordé avec les résultats attendus dans les {cases} cas.'],
        ),
        (
            'verification', 'What was actually checked', 'Ce qui a été vérifié',
            ['The reference verifier re-read the external logs, tested both checker exits and matched statements and axioms against the registered criteria.',
             'The replay did not run Lean or verify the mathematical proofs independently. Altered input bytes fail the source check.'],
            ['Le vérificateur de référence a relu les journaux externes, contrôlé la fin d’exécution des deux vérificateurs et comparé les énoncés et axiomes aux critères du protocole.',
             'La reproduction n’a pas exécuté Lean ni revérifié les preuves mathématiques. Toute modification des données d’entrée invalide le contrôle de provenance.'],
        ),
        (
            'compounding', 'Retained receipt parser', 'Analyseur de pièces justificatives conservé',
            ['The second run loaded the retained profile from disk for the Robin and Lagarias arithmetic criteria. Both approaches agreed.',
             'This demonstrates reuse across two sets. A causal improvement in invention speed or cost remains unproven.'],
            ['Le deuxième essai a relu le profil conservé sur disque pour les critères arithmétiques de Robin et de Lagarias. Les deux approches ont concordé.',
             'L’analyseur a servi sur deux ensembles. Aucun gain causal de vitesse ou de coût d’invention n’est établi.'],
        ),
        (
            'archive', 'Replay identity and provenance', 'Identité de l’essai et provenance',
            [f"Protocol SHA-256 {report['protocol_sha256']}.",
             f"Retained parser SHA-256 {report['retained_profile_sha256']}.",
             'The protocol records source URLs, lengths and SHA-256 digests for each input.'],
            [f"Empreinte SHA-256 du protocole {report['protocol_sha256']}.",
             f"Empreinte SHA-256 de l’analyseur conservé {report['retained_profile_sha256']}.",
             'Le protocole indique l’URL, la taille et l’empreinte SHA-256 de chaque donnée source.'],
        ),
    ]
    return {
        section: {'section': section, 'en': {'title': en, 'paragraphs': en_text},
                  'fr': {'title': fr, 'paragraphs': fr_text}, 'sources': bylines}
        for section, en, fr, en_text, fr_text in records
    }
