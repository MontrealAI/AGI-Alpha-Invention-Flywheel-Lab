"""Native hypothetical products, actual software output and fictional session evidence.

No license grant, customer, session, payment or physical water qualification is
asserted. Prices, complete cost envelope and participant outcomes are authored
scenario assumptions. The download is an executable mathematical evaluation kit.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from commercial.ledger import canonical, digest, read_bound, strict_json

SCHEMA = 'omega/native-product/v1'
MICRO = 1_000_000
PRICE = {'self_hosted': 299*MICRO, 'group_webinar': 99*MICRO, 'founder_private': 20_000*MICRO}
COSTS = {
    'self_hosted': {'acquisition':8, 'compute':3, 'verification':4, 'support':10, 'maintenance':5, 'payment_friction':3},
    'group_webinar': {'acquisition':5, 'support':2, 'payment_friction':1},
    'founder_private': {'acquisition':100, 'preparation':250, 'founder_time':1000, 'support':150, 'payment_friction':200},
}
SESSION_COSTS = {'preparation':120, 'founder_delivery':1000, 'platform':20, 'support':60}
# Authored sensitivities, not measured salaries/bills. Cash-paid services only;
# unpaid owner time belongs in the policy's noncash opportunity-cost account.
# Defaults: compute 0.1h*$30, verification 0.1h*$40, support 0.25h*$40,
# maintenance 0.125h*$40; founder service 0.5h*$2000; preparation 1h*$250.
# Card friction is an illustrative 2.9%+$0.30, not a processor contract.
DEFAULT_COSTS = {p:{k:v*MICRO for k,v in rows.items() if k not in {'acquisition', 'payment_friction'}} for p,rows in COSTS.items()}
DEFAULT_COSTS['self_hosted']['payment_friction'] = 8_970_000
DEFAULT_COSTS['group_webinar']['payment_friction'] = 3_170_000
DEFAULT_COSTS['founder_private']['payment_friction'] = 580_300_000
DEFAULT_COSTS['group_session'] = {k:v*MICRO for k,v in SESSION_COSTS.items()}


def validate_costs(costs):
    if not isinstance(costs, dict) or set(costs) != {*PRICE, 'group_session'}:
        raise ValueError('COMPLETE_PRODUCT_COST_ENVELOPES_REQUIRED')
    for rows in costs.values():
        if not isinstance(rows, dict) or not rows or any(not isinstance(k,str) or not k or len(k)>40 or type(v) is not int or v<0 for k,v in rows.items()):
            raise ValueError('ITEMIZED_NONNEGATIVE_MICROUSD_COSTS_REQUIRED')

BUNDLE_PATHS = ('omega/__main__.py', 'omega/README.md', 'omega/__init__.py', 'omega/water.py', 'omega/verify.py', 'omega/runner.py',
                'omega/request.json', 'omega/requirements.txt',
                'mechanism_harness/__init__.py', 'mechanism_harness/core.py',
                'mechanism_harness/evidence.py', 'mechanism_harness/experiment.py')
SOURCE_PATHS = BUNDLE_PATHS + ('omega/product.py',)
SCOPE = 'HYPOTHETICAL_SIMULATED_PRODUCT_NOT_ACTUAL_COMMERCE'


def _write(path, value):
    raw = canonical(value) + b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('IMMUTABLE_PRODUCT_BYTES_CHANGED')
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def prepare_manifest(root, output, *, jobs=1, hypothetical_rights=False,
                     product='self_hosted', outcomes=None, costs=None,
                     claim_window_hours=720, residual_bps=100, session_ids=None):
    """Freeze request, explicit modeled rights and outcomes before any sale.

    output must be a new directory beneath root. jobs may be an integer or a
    product-name list. Outcomes are scenario assumptions, never inferred consent.
    """
    if hypothetical_rights is not True:
        raise ValueError('EXPLICIT_HYPOTHETICAL_DISTRIBUTION_RIGHTS_REQUIRED')
    if type(claim_window_hours) is not int or claim_window_hours < 1 or type(residual_bps) is not int or not 0 <= residual_bps <= 10000:
        raise ValueError('EXPLICIT_CLAIM_WINDOW_AND_RESIDUAL_REQUIRED')
    costs = json.loads(json.dumps(DEFAULT_COSTS if costs is None else costs))
    validate_costs(costs)
    products = [product]*jobs if type(jobs) is int and jobs > 0 else jobs
    if not isinstance(products, list) or not products or any(p not in PRICE for p in products):
        raise ValueError('DECLARED_PRODUCTS_REQUIRED')
    if session_ids is not None and (not isinstance(session_ids,list) or len(session_ids)!=len(products) or any((kind=='group_webinar' and (not isinstance(sid,str) or not sid or len(sid)>80)) or (kind!='group_webinar' and sid is not None) for kind,sid in zip(products,session_ids))):
        raise ValueError('ONE_EXPLICIT_SESSION_ID_PER_GROUP_SEAT_REQUIRED')
    outcomes = outcomes if outcomes is not None else [{} for _ in products]
    if len(outcomes) != len(products):
        raise ValueError('ONE_SCENARIO_OUTCOME_PER_JOB_REQUIRED')
    root, output = Path(root).resolve(), Path(output).resolve()
    output.relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    hashes = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in SOURCE_PATHS}
    manifest = {'schema':SCHEMA, 'account_namespace':'adaptive012', 'scope':SCOPE,
                'native_engine':'exact-prospective-v2',
                'claim_window_hours':claim_window_hours, 'residual_bps':residual_bps,
                'hypothetical_rights':True, 'source_hashes':hashes, 'costs':costs,
                'cost_basis':'AUTHORED_COMPLETE_CASH_COST_SENSITIVITY_NOT_ACTUAL_BILL; acquisition external', 'jobs':[]}
    group_index = 0
    for index, (kind, outcome) in enumerate(zip(products, outcomes)):
        if set(outcome) - {'accepted', 'attended', 'completed'} or any(type(v) is not bool for v in outcome.values()):
            raise ValueError('EXPLICIT_BOOLEAN_SIMULATED_OUTCOMES_REQUIRED')
        ident = 'omega-product-' + str(index)
        session = 'omega-session-' + str(group_index//500) if kind == 'group_webinar' else None
        if session_ids is not None:
            session = session_ids[index]
        group_index += kind == 'group_webinar'
        request = {'schema':'omega/product-order/v1', 'id':ident, 'product':kind,
                   'price':PRICE[kind], 'scope':SCOPE, 'hypothetical_rights':True,
                   'outcome':{'accepted':True, 'attended':True, 'completed':True, **outcome},
                   'session_id':session, 'founder_minutes':30 if kind == 'founder_private' else 0,
                   'water_request':strict_json((root/'omega/request.json').read_bytes())}
        path = output/(ident+'.request.json')
        sha = _write(path, request)
        manifest['jobs'].append({'id':ident, 'product':kind, 'session_id':session,
            'input':str(path.relative_to(root)), 'input_sha256':sha,
            'output':str((output/(ident+'.delivery.json')).relative_to(root)),
            'artifact_sha256':digest({'request':sha, 'product':kind}),
            'receipt_sha256':digest({'checker':hashes['omega/verify.py'], 'adapter':hashes['omega/product.py'], 'request':sha})})
    load_contracts(root, manifest)
    return manifest


def load_contracts(root, manifest):
    if manifest.get('schema') != SCHEMA or manifest.get('scope') != SCOPE or manifest.get('hypothetical_rights') is not True:
        raise ValueError('HYPOTHETICAL_PRODUCT_AUTHORITY_REQUIRED')
    if manifest.get('native_engine') != 'exact-prospective-v2' or type(manifest.get('claim_window_hours')) is not int or manifest['claim_window_hours'] < 1 or type(manifest.get('residual_bps')) is not int or not 0 <= manifest['residual_bps'] <= 10000:
        raise ValueError('PROSPECTIVE_PRODUCT_TERMS_REQUIRED')
    validate_costs(manifest['costs'])
    if set(manifest['source_hashes']) != set(SOURCE_PATHS):
        raise ValueError('COMPLETE_PRODUCT_SOURCE_BINDING_REQUIRED')
    for path, expected in manifest['source_hashes'].items():
        candidate = Path(root)/path
        if candidate.is_symlink() or any(p.is_symlink() for p in candidate.parents) or hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
            raise ValueError('PRODUCT_SOURCE_CHANGED')
    result = {}
    sessions = {}
    for job in manifest['jobs']:
        request = read_bound(root, job['input'], job['input_sha256'])
        if job['id'] in result or request['id'] != job['id'] or request['product'] != job['product'] or request['price'] != PRICE[job['product']] or request['hypothetical_rights'] is not True or request['scope'] != SCOPE or request['session_id'] != job['session_id']:
            raise ValueError('PRODUCT_REQUEST_BINDING_CHANGED')
        if job['artifact_sha256'] != digest({'request':job['input_sha256'], 'product':job['product']}) or job['receipt_sha256'] != digest({'checker':manifest['source_hashes']['omega/verify.py'], 'adapter':manifest['source_hashes']['omega/product.py'], 'request':job['input_sha256']}):
            raise ValueError('PRODUCT_CHECKER_BINDING_CHANGED')
        if job['session_id'] is not None:
            sessions[job['session_id']] = sessions.get(job['session_id'], 0)+1
        result[job['id']] = {'job':job, 'artifact':{'unproduced_request':job['input_sha256']}, 'receipt':{'accepted':False}}
    if any(n > 500 for n in sessions.values()):
        raise ValueError('WEBINAR_SESSION_CAPACITY_EXCEEDED')
    return result


def _request(root, manifest, job_id):
    job = load_contracts(root, manifest)[job_id]['job']
    return job, read_bound(root, job['input'], job['input_sha256'])


def produce(root, manifest, job_id):
    """Produce actual software output, or explicitly fictional session records."""
    from omega.runner import buyer
    job, request = _request(root, manifest, job_id)
    artifact = {'schema':'omega/product-delivery/v1', 'scope':SCOPE, 'request_sha256':job['input_sha256'],
                'product':job['product'], 'outcome':request['outcome'], 'session_id':job['session_id'],
                'founder_minutes':request['founder_minutes'], 'source_sha256':digest(manifest['source_hashes']),
                'buyer_result':None, 'files':None}
    if job['product'] == 'self_hosted':
        artifact['buyer_result'] = buyer(request['water_request'])
        artifact['files'] = {p:(Path(root)/p).read_text() for p in BUNDLE_PATHS}
    else:
        artifact['session_record'] = {'fictional':True, 'attendance':request['outcome']['attended'],
            'completed':request['outcome']['completed'],
            'curriculum':'Omega mathematical blueprint construction, independent checking and limitations',
            'physical_or_regulatory_authority':False}
    _write(Path(root)/job['output'], artifact)
    return artifact


def delivery(root, manifest, job_id):
    job, _ = _request(root, manifest, job_id)
    path = Path(root)/job['output']
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('SYMLINK_PRODUCT_REFUSED')
    return strict_json(path.read_bytes())


def check_delivery(root, manifest, job_id, artifact):
    """Independent acceptance never invokes buyer or constructor."""
    from omega.verify import verify
    job, request = _request(root, manifest, job_id)
    accepted = (artifact == delivery(root, manifest, job_id)
        and artifact.get('schema') == 'omega/product-delivery/v1'
        and artifact.get('scope') == SCOPE and artifact.get('request_sha256') == job['input_sha256']
        and artifact.get('source_sha256') == digest(manifest['source_hashes'])
        and artifact.get('product') == job['product'] and artifact.get('outcome') == request['outcome']
        and artifact.get('session_id') == job['session_id'] and artifact.get('founder_minutes') == request['founder_minutes']
        and all(request['outcome'].values()))
    if job['product'] == 'self_hosted':
        files, result = artifact.get('files'), artifact.get('buyer_result')
        accepted = accepted and isinstance(files, dict) and set(files) == set(BUNDLE_PATHS)
        if accepted:
            accepted = all(hashlib.sha256(files[p].encode()).hexdigest() == manifest['source_hashes'][p] for p in BUNDLE_PATHS)
            accepted = accepted and result.get('model_api_calls') == 0 and result.get('request_sha256') == digest(request['water_request'])
            checked = verify(request['water_request'], result['plan'])
            accepted = accepted and result.get('certificate') == checked
    else:
        expected = {'fictional':True, 'attendance':request['outcome']['attended'], 'completed':request['outcome']['completed'],
            'curriculum':'Omega mathematical blueprint construction, independent checking and limitations', 'physical_or_regulatory_authority':False}
        accepted = accepted and artifact.get('session_record') == expected and artifact.get('files') is None and artifact.get('buyer_result') is None
    return {'accepted':bool(accepted), 'decisive':True, 'scope':'SIMULATED', 'authority':job['receipt_sha256']}


def cost_rows(job, order_id, costs):
    rows = [('omega-order-cost:'+order_id+':'+kind, value) for kind,value in costs[job['product']].items()]
    if job['product'] == 'group_webinar':
        rows += [('omega-session-cost:'+job['session_id']+':'+kind, value) for kind,value in costs['group_session'].items()]
    return rows


def terms_for(manifest, order_id, product, hour):
    from commercial.terms_exact_v2 import prospective_terms
    price = PRICE[product]
    return prospective_terms(order_id, price, hour+manifest['claim_window_hours'], hour,
        residual=price*manifest['residual_bps']//10000,
        counterparty_obligations='Hypothetical buyer pays accepted product; complete declared support costs prepaid; all claims remain seller obligations; no enforceability established')


def require_costs(root, manifest, actions, order):
    task = json.loads(order['task'])
    job, _ = _request(root, manifest, task['job_id'])
    paid = {a['args']['id']:a['args']['amount'] for a in actions if a['op']=='cost'
            and a['after']['expensePaid'] - a['before']['expensePaid'] == a['args']['amount']}
    if order['price'] != PRICE[job['product']] and int(order['price']) != PRICE[job['product']]:
        raise ValueError('PRODUCT_PRICE_CHANGED')
    if any(paid.get(ident) != amount for ident,amount in cost_rows(job, order['id'], manifest['costs'])):
        raise ValueError('COMPLETE_PRODUCT_COSTS_BEFORE_ACCEPTANCE_REQUIRED')
    matching = [a for a in actions if a['op']=='offer' and a['args']['job_id']==job['id']]
    if len(matching) != 1:
        raise ValueError('ONE_ORDER_PER_PRODUCT_JOB_REQUIRED')
    offer = matching[0]
    if job['product']=='group_webinar':
        session_cost_ids = {'omega-session-cost:'+job['session_id']+':'+kind for kind in manifest['costs']['group_session']}
        if any(a['day']!=offer['day'] for a in actions if a['op']=='cost' and a['args']['id'] in session_cost_ids):
            raise ValueError('SESSION_SEATS_MUST_SHARE_REGISTERED_SESSION_HOUR')
    expected = terms_for(manifest, order['id'], job['product'], offer['day'])
    terms = [a['args']['terms'] for a in actions if a['op']=='register_terms' and a['args']['id']==offer['args'].get('terms_id')]
    if terms != [expected]:
        raise ValueError('EXACT_PRECOMMITTED_PRODUCT_TERMS_REQUIRED')


def rebind_prepared(root, manifest, actions, jobs):
    offers = {a['args']['id']:a['args']['job_id'] for a in actions if a['op']=='offer'}
    for action in actions:
        if action['op']=='event' and action['args']['action']=='prepare':
            job_id = offers[action['args']['id']]
            artifact = delivery(root, manifest, job_id)
            if digest(artifact) != action['args']['artifact_sha256'] or not check_delivery(root, manifest, job_id, artifact)['accepted']:
                raise ValueError('PRODUCT_PREPARED_BYTES_OR_ACCEPTANCE_CHANGED')


def fulfill(account, root, manifest, job_id, *, order_id, buyer, hour,
            consent=True, session_id=None):
    """Native modeled order. Refusal costs nothing; failure refunds, costs remain."""
    if type(consent) is not bool:
        raise ValueError('EXPLICIT_SIMULATED_BUYER_CONSENT_REQUIRED')
    job, _ = _request(root, manifest, job_id)
    if session_id is not None and session_id != job['session_id']:
        raise ValueError('PRECOMMITTED_SESSION_REQUIRED')
    if not consent:
        return {'status':'declined', 'collected':0, 'scope':SCOPE}
    # Reentry uses identical native identifiers, hours and bytes; no new money.
    existing = {a['args']['id'] for a in account.export()['ledger']['actions'] if a['op']=='cost'}
    for ident, amount in cost_rows(job, order_id, manifest['costs']):
        if ident not in existing:
            account.cost(ident, amount, hour)
    price = PRICE[job['product']]
    account.execute('register_terms', {'id':order_id+':terms', 'terms':terms_for(manifest,order_id,job['product'],hour)}, hour)
    account.execute('wallet', {'buyer':buyer, 'amount':price}, hour)
    account.execute('offer', {'id':order_id, 'buyer':buyer, 'price':price, 'job_id':job_id, 'deadline':hour+24, 'terms_id':order_id+':terms'}, hour)
    def event(action, **extra):
        return account.execute('event', {'id':order_id, 'action':action, 'event_id':order_id+':'+action, **extra}, hour)
    event('consent'); event('fund')
    artifact = produce(root, manifest, job_id)
    accepted = check_delivery(root, manifest, job_id, artifact)['accepted']
    if not accepted:
        event('refund')
        return {'status':'refunded', 'collected':0, 'scope':SCOPE}
    event('prepare', artifact_sha256=digest(artifact)); event('release')
    return {'status':'released', 'collected':price, 'artifact_sha256':digest(artifact), 'scope':SCOPE}


def replay(record, *, root, manifest):
    from connected_enterprise.finance import audit_journal
    checked = audit_journal(record, root=root, manifest=manifest)
    return {'accepted':checked['accepted'], 'native_audit':checked,
            'summary':record['ledger']['summary'], 'scope':SCOPE}


def example(output, *, root=None):
    """Fresh isolated public replay example, never a top-up or live transaction."""
    import shutil
    from connected_enterprise.finance import JournalAccount, source_paths_for_manifest
    from experiments.commerce006 import PINS
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output/'source'
    for path in sorted(set(source_paths_for_manifest({'schema':SCHEMA})) | set(PINS)):
        destination = source/path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root/path, destination)
    manifest = prepare_manifest(source, source/'products', jobs=list(PRICE), hypothetical_rights=True)
    _write(output/'manifest.json', manifest)
    with JournalAccount(source, manifest, output/'account.sqlite', opening=100_000*MICRO,
                        working=0, contract='omega-product-example:'+digest(manifest)) as account:
        outcomes = [fulfill(account, source, manifest, job['id'], order_id='example-'+job['id'],
                    buyer='synthetic-'+job['id'], hour=0) for job in manifest['jobs']]
        record = account.export()
        checked = replay(record, root=source, manifest=manifest)
    _write(output/'native-public-export.json', record)
    _write(output/'result.json', {'outcomes':outcomes, **checked})
    return checked


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['example', 'audit'])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.operation == 'example':
        result = example(args.output)
    else:
        directory = Path(args.output)
        result = replay(strict_json((directory/'native-public-export.json').read_bytes()),
                        root=directory/'source', manifest=strict_json((directory/'manifest.json').read_bytes()))
    print(json.dumps(result, sort_keys=True))
