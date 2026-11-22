"""Stage bilingual records consumable by the existing approved encrypted publisher."""

from .intake import LEGACY_RECORD, RECORD, digest

STATUS = {
    'source-insufficient': ('Investigating', 'En cours d’examen'),
    'detected': ('Detected', 'Détecté'),
    'experiment-prepared': ('Experiment prepared', 'Expérience préparée'),
    'technically-verified': ('Technically verified', 'Vérifié techniquement'),
    'falsified': ('Registered comparison failed', 'Comparaison enregistrée non concluante'),
}


def packet(record, ledger):
    active = next((row for row in reversed(ledger['entries'])
                   if row['scope'] == record['scope'] and row['version'] == record['change']['current']), None)
    if (record['schema'] not in (RECORD, LEGACY_RECORD) or record['classification'] != 'public-evidence' or not active
            or active['id'] != record['finding_id'] or active['digest'] != digest(record) or active['phase'] != record['status']
            or record['reception']['authenticated_by'] != 'github-rest'
            or record['status'] not in STATUS or record['production_authority'] is not False):
        raise ValueError('Use a reviewed GitHub-origin receipt and its exact approved ledger entry')
    en_status, fr_status = STATUS[record['status']]
    change = record['change']
    version = f"{change['prior']} → {change['current']}"
    source_links = [{'en': 'Primary evidence ' + source['id'], 'fr': 'Source primaire ' + source['id'],
                     'url': source['url']} for source in record['source_evidence']]
    count = record['evaluation']['independence']['distinct_groups']
    plan = record['evaluation']['id']
    observed = record['observed_at']
    asset = record['asset']['verified_identity']
    records = (
        ('radar', 'Frontier observation', 'Observation à la frontière',
         [f'{en_status}. {version}. Observed {observed}.'],
         [f'{fr_status}. {version}. Observé le {observed}.']),
        ('opportunity', 'Opportunity review', 'Examen de l’occasion',
         ['The registered comparison holds the required outcome, inputs and authorization fixed.',
          'Any unavailable rights, beneficiary evidence or source facts remain open.'],
         ['La comparaison garde le résultat recherché, les données et les autorisations constants.',
          'Les droits, la preuve du bénéficiaire ou les faits manquants restent à établir.']),
        ('experiment', 'Registered experiment', 'Expérience enregistrée',
         [f'Registered test {plan}.' if plan else 'An independently reproducible test still needs review.'],
         [f'Essai enregistré {plan}.' if plan else 'Un essai reproductible reste à faire approuver.']),
        ('verification', 'What is supported', 'Ce que les pièces établissent',
         [f'{en_status}. The upstream group count is {count}. It does not certify scientific independence.',
          'Economic validation and collected payment remain unproven.'],
         [f'{fr_status}. Le nombre de groupes sources est de {count}. Ce nombre ne certifie pas l’indépendance scientifique.',
          'La validation économique et l’encaissement demeurent à établir.']),
        ('compounding', 'Retained method', 'Méthode conservée',
         [f'Qualified retained asset SHA-256 {asset}.' if asset else 'A retained capability has yet to qualify.',
          'A causal improvement on a different successor remains unproven.'],
         [f'Actif conservé et qualifié, SHA-256 {asset}.' if asset else 'Une capacité réutilisable reste à qualifier.',
          'Le gain causal sur un successeur distinct reste à établir.']),
        ('archive', 'Intake and review identity', 'Identité de la réception et de la revue',
         [f"Finding {record['finding_id']}.", 'GitHub verified the PR author and reviewed commit. Task authorship is operator-declared.'],
         [f"Observation {record['finding_id']}.", 'GitHub a vérifié l’auteur de la demande et le commit approuvé. L’origine de la tâche est déclarée par l’opérateur.']),
    )
    return {section: {'section': section, 'en': {'title': en, 'paragraphs': en_body},
                      'fr': {'title': fr, 'paragraphs': fr_body}, 'sources': source_links}
            for section, en, fr, en_body, fr_body in records}
