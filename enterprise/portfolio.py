"""Admit executed contracts from an extensible historical candidate universe."""
import hashlib
import json
from .services import load_jobs


def admitted_portfolio(root, manifest):
    root = __import__('pathlib').Path(root)
    raw = (root/'portfolio_scale/universe.json').read_bytes()
    universe = json.loads(raw)
    jobs = universe['jobs']
    if len({j['id'] for j in jobs}) != len(jobs):
        raise ValueError('UNIQUE_CANDIDATE_IDS_REQUIRED')
    actual = load_jobs(root, manifest)
    links = {'reconciliation': {'candidate_id': 'enterprise011__invoice_payment_reconciliation', 'family': 'finance_backoffice', 'source': 'New specialized contract; does not authorize bank access or signoff'},
             'kpi_variance': {'candidate_id': 'business_intelligence__kpi_variance_report', 'family': 'business_intelligence', 'source': 'Existing candidate specialized to exact supplied metric arithmetic'},
             'evidence_matrix': {'candidate_id': 'proposals_rfp__product_capability_matrix', 'family': 'proposals_rfp', 'source': 'Existing candidate specialized to supplied facts; missing/conflicting evidence disclosed'}}
    admitted = []
    for service, link in links.items():
        packets = [v for v in actual.values() if v['job']['service_id'] == service]
        if not packets:
            raise ValueError('ACTUAL_CONTRACT_ACCEPTANCE_REQUIRED')
        admitted.append({'service_id': service, **link, 'accepted_packets': len(packets), 'acceptance': manifest['acceptance_contracts'][service],
                         'autonomous_deliverability': 'EXECUTED_DETERMINISTIC_TOOL', 'recurring_need': 'HYPOTHESIS_TESTED_IN_MARKET_SCENARIOS',
                         'buyer_value': 'Source reconciliation, exact metric changes, or supported proposal facts; no inferred market demand',
                         'human_advantage': 'Conditional itemized cost/speed comparison only', 'acquisition': 'Simulated finite customer channel',
                         'permission': 'Synthetic USD source packets only; no private data, regulated decision or outreach',
                         'working_capital': 'Native protected exchange with separate opening seed/reserves', 'expansion': 'Recurring cross-service context; tested by controlled bundle/allocation arms'})
    return {'schema': 'agi-alpha/enterprise011-admission/v1', 'registry_sha256': hashlib.sha256(raw).hexdigest(),
            'historical_candidates': len(jobs), 'historical_families': len({j['family'] for j in jobs}),
            'unexecuted_candidates_stay_unverified': True, 'risk_approval_grants': False, 'admitted': admitted,
            'selection': 'Three complete source-bound outcome contracts with executable independent acceptance and synthetic permission; broader ranking/pricing remains a planning screen. Service count is no commercial conclusion.',
            'catalogue_limit': None, 'observed_customers': 0}
