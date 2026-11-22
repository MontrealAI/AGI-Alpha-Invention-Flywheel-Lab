"""Retain a small, read-only fit checker for the registered OEM retrofit."""

from datetime import date

REQUEST_FIELDS = frozenset({'model', 'nozzle_requirement_c', 'use'})


def valid_temperature(value):
    return type(value) is int and 0 <= value <= 1000


def check_request(request):
    if (not isinstance(request, dict) or set(request) != REQUEST_FIELDS
            or not isinstance(request['model'], str) or len(request['model']) > 150
            or not valid_temperature(request['nozzle_requirement_c'])
            or request['use'] not in ('non_safety_critical', 'safety_critical', 'regulated', 'unknown')):
        raise ValueError('Invalid or incomplete registered inquiry')


def assess(request, protocol, observed_on):
    check_request(request)
    label = ' '.join(request['model'].casefold().split())
    catalog = protocol['catalog']
    model = next((key for key, item in catalog['eligible'].items() if label in item['labels']), None)
    need = request['nozzle_requirement_c']
    limit = None
    sources = []
    part = None
    if request['use'] != 'non_safety_critical':
        decision = 'external-review-required'
    elif label.removeprefix('prusa ') in catalog['explicit_exclusions']:
        decision, sources = 'unsupported-configuration', ['upgrade']
    elif model is None:
        decision = 'need-model-evidence'
    else:
        active_upgrade = date.fromisoformat(observed_on) >= date.fromisoformat(protocol['after'])
        limit = catalog['retrofit_nozzle_c'] if active_upgrade else catalog['standard_nozzle_c']
        sources = ['stock', 'release', 'upgrade'] if active_upgrade else ['stock']
        if need <= catalog['standard_nozzle_c']:
            decision = 'existing-envelope'
        elif need <= limit and active_upgrade:
            decision, part = 'retrofit-candidate', protocol['sku']
        else:
            decision = 'no-documented-path'
    return {'decision': decision, 'model': model, 'part': part, 'nozzle_limit_c': limit,
            'required_nozzle_c': need, 'source_ids': sources, 'fulfillment_authority': False}
