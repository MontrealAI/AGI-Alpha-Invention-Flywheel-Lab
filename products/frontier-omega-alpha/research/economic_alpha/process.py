"""Apply the frozen selector to screening a separate installation and process."""

from .eligibility import REQUEST_FIELDS, assess, valid_temperature

PROCESS_FIELDS = REQUEST_FIELDS | {'claimed_installed', 'required_chamber_c', 'sheet', 'site_review'}
ELIGIBLE = {'existing-envelope', 'retrofit-candidate'}


def screen(request, protocol):
    if (not isinstance(request, dict) or set(request) != PROCESS_FIELDS
            or not valid_temperature(request['required_chamber_c'])
            or request['claimed_installed'] not in ('standard', 'retrofit', 'unknown')
            or request['site_review'] not in ('missing', 'approved-evidence')
            or not isinstance(request['sheet'], str) or len(request['sheet']) > 80):
        raise ValueError('Invalid process inquiry')
    fit = assess({key: request[key] for key in REQUEST_FIELDS}, protocol, protocol['after'])
    decision = fit['decision']
    chamber = None
    if decision in ELIGIBLE:
        chamber = protocol['catalog']['eligible'][fit['model']]['chamber_limit_c']
        if decision == 'retrofit-candidate' and request['claimed_installed'] != 'retrofit':
            decision = 'installed-configuration-unverified'
        elif request['claimed_installed'] == 'unknown':
            decision = 'installed-configuration-unverified'
        elif chamber is None:
            decision = 'need-chamber-evidence'
        elif request['required_chamber_c'] > chamber:
            decision = 'outside-chamber-envelope'
        elif request['sheet'] != protocol['catalog']['successor_sheet']:
            decision = 'accessory-evidence-required'
        elif request['site_review'] != 'approved-evidence':
            decision = 'site-evidence-required'
        else:
            decision = 'documented-process-envelope'
    return {'decision': decision, 'fit': fit, 'chamber_limit_c': chamber,
            'process_authority': False, 'accepted_delivery': False}
