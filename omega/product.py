"""Native hypothetical products, actual software output and fictional session evidence.

No license grant, customer, session, payment or physical water qualification is
asserted. Prices, complete cost envelope and participant outcomes are authored
scenario assumptions. The download is an executable mathematical evaluation kit.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile

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
PROCESS_BUNDLE_PATHS = tuple(dict.fromkeys(BUNDLE_PATHS + (
    'omega/process.py', 'omega/process_verify.py', 'omega/PROCESS_HELP.json', 'omega/WORKFLOW.md',
    'commercial/__init__.py', 'commercial/ledger.py', 'commercial/native_engine.py',
    'experiments/__init__.py', 'experiments/commerce006.py')))
SOURCE_PATHS = PROCESS_BUNDLE_PATHS + ('omega/product.py',)
SCOPE = 'HYPOTHETICAL_SIMULATED_PRODUCT_NOT_ACTUAL_COMMERCE'
CHOICE_SCHEMA = 'omega/voluntary-choice/v1'


def _money(value, *, price=False):
    # The existing exact native engine admits prices of at least USD0.20.
    if type(value) is not int or value < (200_000 if price else 0):
        raise ValueError('EXACT_NONNEGATIVE_MICROUSD_OR_NATIVE_MINIMUM_PRICE_REQUIRED')
    return value


def _identifier(value):
    if type(value) is not str or not value.strip() or len(value) > 160:
        raise ValueError('BOUNDED_NONEMPTY_PRODUCT_ID_REQUIRED')
    return value


def _job_price(job):
    return _money(job.get('price', PRICE[job['product']]), price=True)


def _workflow(job):
    return job.get('workflow', 'water')


def _checker_hash(hashes, job):
    return hashes['omega/process_verify.py' if _workflow(job) == 'process' else 'omega/verify.py']


def _validate_rows(rows):
    if not isinstance(rows, dict) or not rows or any(type(k) is not str or not k or len(k) > 40 or type(v) is not int or v < 0 for k, v in rows.items()):
        raise ValueError('ITEMIZED_NONNEGATIVE_MICROUSD_COSTS_REQUIRED')


def validate_choice(choice, product, price):
    """Check a declared whole-bundle choice independently of the seller policy.

    This verifies arithmetic, quote binding and explicit scenario consent. It
    cannot turn authored buyer values into observed demand or real authority.
    """
    fields = {'schema', 'choice_id', 'offer_id', 'selected_id', 'selected_offer_ids',
              'consent', 'budget_microUSD', 'alternatives'}
    if type(choice) is not dict or set(choice) != fields or choice['schema'] != CHOICE_SCHEMA:
        raise ValueError('EXACT_BOUND_VOLUNTARY_CHOICE_REQUIRED')
    for key in ('choice_id', 'offer_id', 'selected_id'):
        _identifier(choice[key])
    if type(choice['consent']) is not bool:
        raise ValueError('EXPLICIT_BOUND_BUYER_CONSENT_REQUIRED')
    budget = _money(choice['budget_microUSD'])
    if type(choice['alternatives']) is not list or not 1 <= len(choice['alternatives']) <= 2048:
        raise ValueError('FINITE_COMPLETE_ALTERNATIVE_SET_REQUIRED')
    alternatives, quotes = {}, {}
    alt_fields = {'id', 'offers', 'value_before_fees_microUSD', 'adoption_operating_cost_microUSD',
                  'cash_operating_cost_microUSD', 'net_utility_microUSD'}
    for alternative in choice['alternatives']:
        if type(alternative) is not dict or set(alternative) != alt_fields:
            raise ValueError('EXACT_BUNDLE_ALTERNATIVE_REQUIRED')
        ident = _identifier(alternative['id'])
        if ident in alternatives or type(alternative['offers']) is not list:
            raise ValueError('UNIQUE_BUNDLE_ALTERNATIVES_REQUIRED')
        seen = set()
        for offer in alternative['offers']:
            if type(offer) is not dict or set(offer) != {'id', 'product', 'price_microUSD'}:
                raise ValueError('EXACT_BUNDLE_LINE_ITEM_REQUIRED')
            oid = _identifier(offer['id'])
            if oid in seen or offer['product'] not in PRICE:
                raise ValueError('UNIQUE_KNOWN_BUNDLE_LINE_ITEMS_REQUIRED')
            _money(offer['price_microUSD'])
            if oid in quotes and quotes[oid] != offer:
                raise ValueError('ALTERNATIVE_QUOTE_ID_REBOUND')
            quotes[oid] = offer
            seen.add(oid)
        value = _money(alternative['value_before_fees_microUSD'])
        adoption = _money(alternative['adoption_operating_cost_microUSD'])
        cash = _money(alternative['cash_operating_cost_microUSD'])
        total_price = sum(o['price_microUSD'] for o in alternative['offers'])
        if cash > adoption or type(alternative['net_utility_microUSD']) is not int or alternative['net_utility_microUSD'] != value - total_price - adoption:
            raise ValueError('COMPLETE_BUNDLE_NET_UTILITY_OR_CASH_COST_MISMATCH')
        alternatives[ident] = alternative
    zero = {'id':'no_purchase', 'offers':[], 'value_before_fees_microUSD':0,
            'adoption_operating_cost_microUSD':0, 'cash_operating_cost_microUSD':0,
            'net_utility_microUSD':0}
    if alternatives.get('no_purchase') != zero:
        raise ValueError('ZERO_COST_NO_PURCHASE_ALTERNATIVE_REQUIRED')
    selected = alternatives.get(choice['selected_id'])
    if selected is None:
        raise ValueError('SELECTED_BUNDLE_NOT_DECLARED')
    feasible = [a for a in alternatives.values() if sum(o['price_microUSD'] for o in a['offers']) + a['cash_operating_cost_microUSD'] <= budget]
    best = max(a['net_utility_microUSD'] for a in feasible)
    if selected not in feasible or selected['net_utility_microUSD'] != best or (best <= 0 and selected['id'] != 'no_purchase'):
        raise ValueError('VOLUNTARY_BUNDLE_MUST_MAXIMIZE_FEASIBLE_NET_UTILITY')
    ids = [o['id'] for o in selected['offers']]
    if type(choice['selected_offer_ids']) is not list or choice['selected_offer_ids'] != ids:
        raise ValueError('SELECTED_BUNDLE_ITEMS_CHANGED')
    expected = {'id':choice['offer_id'], 'product':product, 'price_microUSD':price}
    if expected not in selected['offers']:
        raise ValueError('PRODUCT_PRICE_OR_LINE_ITEM_NOT_BOUND_TO_SELECTED_BUNDLE')
    return selected


def _safe_output(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('ROOT_RELATIVE_PRODUCT_OUTPUT_REQUIRED')
    result = Path(root)/path
    if result.is_symlink() or any(p.is_symlink() for p in result.parents):
        raise ValueError('SYMLINK_PRODUCT_REFUSED')
    return result


def _write(path, value):
    raw = canonical(value) + b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('IMMUTABLE_PRODUCT_BYTES_CHANGED')
        return hashlib.sha256(raw).hexdigest()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name+'.pending-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return hashlib.sha256(raw).hexdigest()


def prepare_manifest(root, output, *, jobs=1, hypothetical_rights=False,
                     product='self_hosted', outcomes=None, costs=None,
                     claim_window_hours=720, residual_bps=100, session_ids=None,
                     prices=None, choices=None, water_requests=None,
                     process_requests=None, job_costs=None):
    """Freeze request, explicit modeled rights and outcomes before any sale.

    output must be a new directory beneath root. jobs may be an integer or a
    product-name list. Optional prices, complete choice receipts, requests and
    itemized costs are frozen per job. Defaults retain the original water kit.
    Outcomes and consent are authored simulation inputs, never market evidence.
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
    for name, values in [('prices', prices), ('choices', choices), ('water_requests', water_requests),
                         ('process_requests', process_requests), ('job_costs', job_costs)]:
        if values is not None and (type(values) is not list or len(values) != len(products)):
            raise ValueError('ONE_EXPLICIT_'+name.upper()+'_PER_JOB_REQUIRED')
    if session_ids is not None and (not isinstance(session_ids,list) or len(session_ids)!=len(products) or any((kind=='group_webinar' and (not isinstance(sid,str) or not sid or len(sid)>80)) or (kind!='group_webinar' and sid is not None) for kind,sid in zip(products,session_ids))):
        raise ValueError('ONE_EXPLICIT_SESSION_ID_PER_GROUP_SEAT_REQUIRED')
    outcomes = outcomes if outcomes is not None else [{} for _ in products]
    if type(outcomes) is not list or len(outcomes) != len(products):
        raise ValueError('ONE_SCENARIO_OUTCOME_PER_JOB_REQUIRED')
    root, output = Path(root).resolve(), Path(output).resolve()
    output.relative_to(root)
    hashes = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in SOURCE_PATHS}
    manifest = {'schema':SCHEMA, 'account_namespace':'adaptive012', 'scope':SCOPE,
                'native_engine':'exact-prospective-v2',
                'claim_window_hours':claim_window_hours, 'residual_bps':residual_bps,
                'hypothetical_rights':True, 'source_hashes':hashes, 'costs':costs,
                'cost_basis':'AUTHORED_COMPLETE_CASH_COST_SENSITIVITY_NOT_ACTUAL_BILL; acquisition external', 'jobs':[]}
    if choices is not None:
        manifest['choice_schema'] = CHOICE_SCHEMA
    pending = []
    group_index = 0
    for index, (kind, outcome) in enumerate(zip(products, outcomes)):
        if type(outcome) is not dict or set(outcome) - {'accepted', 'attended', 'completed', 'paid'} or any(type(v) is not bool for v in outcome.values()):
            raise ValueError('EXPLICIT_BOOLEAN_SIMULATED_OUTCOMES_REQUIRED')
        ident = 'omega-product-' + str(index)
        session = 'omega-session-' + str(group_index//500) if kind == 'group_webinar' else None
        if session_ids is not None:
            session = session_ids[index]
        group_index += kind == 'group_webinar'
        price = PRICE[kind] if prices is None else _money(prices[index], price=True)
        request = {'schema':'omega/product-order/v1', 'id':ident, 'product':kind,
                   'price':price, 'scope':SCOPE, 'hypothetical_rights':True,
                   'outcome':{'accepted':True, 'attended':True, 'completed':True, **outcome},
                   'session_id':session, 'founder_minutes':30 if kind == 'founder_private' else 0,
                   'water_request':strict_json((root/'omega/request.json').read_bytes()) if water_requests is None else water_requests[index]}
        job = {'id':ident, 'product':kind, 'session_id':session}
        if prices is not None:
            job['price'] = price
        if choices is not None:
            validate_choice(choices[index], kind, price)
            request['choice'] = json.loads(json.dumps(choices[index]))
        if job_costs is not None:
            _validate_rows(job_costs[index])
            request['job_costs'] = job['job_costs'] = json.loads(json.dumps(job_costs[index]))
        if process_requests is not None and process_requests[index] is not None:
            from omega.process_verify import inspect_request
            inspect_request(process_requests[index])
            request['workflow'] = job['workflow'] = 'process'
            request['process_request'] = process_requests[index]
        else:
            from omega.water import validate
            validate(request['water_request'])
        path = output/(ident+'.request.json')
        sha = hashlib.sha256(canonical(request) + b'\n').hexdigest()
        job.update({
            'input':str(path.relative_to(root)), 'input_sha256':sha,
            'output':str((output/(ident+'.delivery.json')).relative_to(root)),
            'artifact_sha256':digest({'request':sha, 'product':kind}),
            'receipt_sha256':digest({'checker':_checker_hash(hashes, job), 'adapter':hashes['omega/product.py'], 'request':sha})})
        manifest['jobs'].append(job)
        pending.append((path, request))
    _validate_choice_groups([(j, r) for j, (_, r) in zip(manifest['jobs'], pending)])
    output.mkdir(parents=True, exist_ok=False)
    for path, request in pending:
        _write(path, request)
    load_contracts(root, manifest)
    return manifest


def _validate_choice_groups(rows):
    groups = {}
    for job, request in rows:
        choice = request.get('choice')
        if choice is None:
            continue
        common = {key:value for key,value in choice.items() if key != 'offer_id'}
        group = groups.setdefault(choice['choice_id'], {'common':common, 'offers':[]})
        if group['common'] != common:
            raise ValueError('BUYER_BUNDLE_RECEIPTS_DISAGREE')
        group['offers'].append(choice['offer_id'])
    for group in groups.values():
        if sorted(group['offers']) != sorted(group['common']['selected_offer_ids']):
            raise ValueError('COMPLETE_SELECTED_BUYER_BUNDLE_REQUIRED_ONCE')


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
    outputs, requests = set(), []
    if 'choice_schema' in manifest and manifest['choice_schema'] != CHOICE_SCHEMA:
        raise ValueError('EXPLICIT_VOLUNTARY_CHOICE_SCHEMA_REQUIRED')
    for job in manifest['jobs']:
        request = read_bound(root, job['input'], job['input_sha256'])
        if job['product'] not in PRICE or job['id'] in result or request['id'] != job['id'] or request['product'] != job['product'] or request['price'] != _job_price(job) or request['hypothetical_rights'] is not True or request['scope'] != SCOPE or request['session_id'] != job['session_id']:
            raise ValueError('PRODUCT_REQUEST_BINDING_CHANGED')
        if request.get('schema') != 'omega/product-order/v1' or request.get('founder_minutes') != (30 if job['product'] == 'founder_private' else 0):
            raise ValueError('PRODUCT_REQUEST_SCOPE_CHANGED')
        outcome = request.get('outcome')
        if type(outcome) is not dict or not {'accepted', 'attended', 'completed'} <= set(outcome) or set(outcome)-{'accepted', 'attended', 'completed', 'paid'} or any(type(v) is not bool for v in outcome.values()):
            raise ValueError('EXPLICIT_BOOLEAN_SIMULATED_OUTCOMES_REQUIRED')
        workflow = _workflow(job)
        if workflow not in {'water', 'process'} or request.get('workflow', 'water') != workflow:
            raise ValueError('WORKFLOW_BINDING_CHANGED')
        if workflow == 'process':
            from omega.process_verify import inspect_request
            inspect_request(request['process_request'])
        else:
            from omega.water import validate
            validate(request['water_request'])
        if 'job_costs' in job or 'job_costs' in request:
            _validate_rows(job.get('job_costs'))
            if request.get('job_costs') != job['job_costs']:
                raise ValueError('JOB_COST_BINDING_CHANGED')
        if ('choice' in request) != ('choice_schema' in manifest):
            raise ValueError('COMPLETE_BOUND_VOLUNTARY_CHOICES_REQUIRED')
        if 'choice' in request:
            validate_choice(request['choice'], job['product'], request['price'])
        if job['artifact_sha256'] != digest({'request':job['input_sha256'], 'product':job['product']}) or job['receipt_sha256'] != digest({'checker':_checker_hash(manifest['source_hashes'], job), 'adapter':manifest['source_hashes']['omega/product.py'], 'request':job['input_sha256']}):
            raise ValueError('PRODUCT_CHECKER_BINDING_CHANGED')
        output = _safe_output(root, job['output'])
        if output in outputs or job['output'] == job['input']:
            raise ValueError('UNIQUE_PRODUCT_OUTPUT_REQUIRED')
        outputs.add(output)
        if (job['product'] == 'group_webinar' and (type(job['session_id']) is not str or not job['session_id'] or len(job['session_id']) > 80)) or (job['product'] != 'group_webinar' and job['session_id'] is not None):
            raise ValueError('ONE_EXPLICIT_SESSION_ID_PER_GROUP_SEAT_REQUIRED')
        if job['session_id'] is not None:
            sessions[job['session_id']] = sessions.get(job['session_id'], 0)+1
        result[job['id']] = {'job':job, 'artifact':{'unproduced_request':job['input_sha256']}, 'receipt':{'accepted':False}}
        requests.append((job, request))
    _validate_choice_groups(requests)
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
    if 'workflow' in request:
        artifact['workflow'] = request['workflow']
    if job['product'] == 'self_hosted':
        if _workflow(job) == 'process':
            from omega.process import construct
            from omega.process_verify import verify_policy
            policy = construct(request['process_request'])
            artifact['buyer_result'] = {'request_sha256':digest(request['process_request']),
                'model_api_calls':0, 'plan':policy,
                'certificate':verify_policy(request['process_request'], policy),
                'scope':'FINITE_MODEL_POLICY_NOT_PHYSICAL_OPERATION'}
        else:
            artifact['buyer_result'] = buyer(request['water_request'])
        paths = PROCESS_BUNDLE_PATHS if _workflow(job) == 'process' else BUNDLE_PATHS
        artifact['files'] = {p:(Path(root)/p).read_text() for p in paths}
    else:
        artifact['session_record'] = {'fictional':True, 'attendance':request['outcome']['attended'],
            'completed':request['outcome']['completed'],
            'curriculum':'Omega mathematical blueprint construction, independent checking and limitations',
            'physical_or_regulatory_authority':False}
    _write(_safe_output(root, job['output']), artifact)
    return artifact


def delivery(root, manifest, job_id):
    job, _ = _request(root, manifest, job_id)
    path = _safe_output(root, job['output'])
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
        and artifact.get('workflow', 'water') == _workflow(job)
        and all(request['outcome'][key] for key in ('accepted', 'attended', 'completed')))
    if job['product'] == 'self_hosted':
        files, result = artifact.get('files'), artifact.get('buyer_result')
        paths = PROCESS_BUNDLE_PATHS if _workflow(job) == 'process' else BUNDLE_PATHS
        accepted = accepted and isinstance(result, dict) and isinstance(files, dict) and set(files) == set(paths)
        if accepted:
            accepted = all(type(files[p]) is str and hashlib.sha256(files[p].encode()).hexdigest() == manifest['source_hashes'][p] for p in paths)
            workflow_request = request['process_request'] if _workflow(job) == 'process' else request['water_request']
            accepted = accepted and result.get('model_api_calls') == 0 and result.get('request_sha256') == digest(workflow_request)
            try:
                if _workflow(job) == 'process':
                    from omega.process_verify import verify_policy
                    checked = verify_policy(workflow_request, result['plan'])
                    accepted = accepted and checked['accepted'] is True
                else:
                    checked = verify(workflow_request, result['plan'])
                accepted = accepted and result.get('certificate') == checked
            except (ValueError, KeyError, TypeError):
                accepted = False
    else:
        expected = {'fictional':True, 'attendance':request['outcome']['attended'], 'completed':request['outcome']['completed'],
            'curriculum':'Omega mathematical blueprint construction, independent checking and limitations', 'physical_or_regulatory_authority':False}
        accepted = accepted and artifact.get('session_record') == expected and artifact.get('files') is None and artifact.get('buyer_result') is None
    return {'accepted':bool(accepted), 'decisive':True, 'scope':'SIMULATED', 'authority':job['receipt_sha256']}


def cost_rows(job, order_id, costs):
    rows = [('omega-order-cost:'+order_id+':'+kind, value) for kind,value in job.get('job_costs', costs[job['product']]).items()]
    if job['product'] == 'group_webinar':
        rows += [('omega-session-cost:'+job['session_id']+':'+kind, value) for kind,value in costs['group_session'].items()]
    return rows


def terms_for(manifest, order_id, product, hour, price=None):
    from commercial.terms_exact_v2 import prospective_terms
    price = _money(PRICE[product] if price is None else price, price=True)
    return prospective_terms(order_id, price, hour+manifest['claim_window_hours'], hour,
        residual=price*manifest['residual_bps']//10000,
        counterparty_obligations='Hypothetical buyer pays accepted product; complete declared support costs prepaid; all claims remain seller obligations; no enforceability established')


def require_costs(root, manifest, actions, order):
    task = json.loads(order['task'])
    job, request = _request(root, manifest, task['job_id'])
    paid = {a['args']['id']:a['args']['amount'] for a in actions if a['op']=='cost'
            and a['after']['expensePaid'] - a['before']['expensePaid'] == a['args']['amount']}
    if int(order['price']) != _job_price(job):
        raise ValueError('PRODUCT_PRICE_CHANGED')
    if request['outcome'].get('paid', True) is not True:
        raise ValueError('SCENARIO_NONPAYMENT_CANNOT_COLLECT')
    choice = request.get('choice')
    if choice is not None and choice['consent'] is not True:
        raise ValueError('BOUND_VOLUNTARY_BUYER_CONSENT_REQUIRED')
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
    expected = terms_for(manifest, order['id'], job['product'], offer['day'], _job_price(job))
    terms = [a['args']['terms'] for a in actions if a['op']=='register_terms' and a['args']['id']==offer['args'].get('terms_id')]
    if terms != [expected]:
        raise ValueError('EXACT_PRECOMMITTED_PRODUCT_TERMS_REQUIRED')
    if choice is not None and len(choice['selected_offer_ids']) > 1:
        # No line item may settle while a promised companion is missing or
        # rejected. Native events remain sequential, so this is a preparation
        # gate, not a claim of atomic multi-order settlement.
        for companion in manifest['jobs']:
            other = read_bound(root, companion['input'], companion['input_sha256'])
            if other.get('choice', {}).get('choice_id') != choice['choice_id']:
                continue
            if other['outcome'].get('paid', True) is not True:
                raise ValueError('WHOLE_BUYER_BUNDLE_NONPAYMENT')
            offers = [a for a in actions if a['op']=='offer' and a['args']['job_id']==companion['id']]
            if len(offers) != 1:
                raise ValueError('WHOLE_BUYER_BUNDLE_ORDERS_REQUIRED')
            oid = offers[0]['args']['id']
            if any(a['op']=='event' and a['args']['id']==oid
                   and a['args']['action'] in {'refund', 'cancel', 'late_reversal'} for a in actions):
                raise ValueError('WHOLE_BUYER_BUNDLE_HAS_TERMINAL_REFUND_OR_CANCELLATION')
            if not any(a['op']=='event' and a['args']['id']==oid and a['args']['action']=='fund' for a in actions):
                raise ValueError('WHOLE_BUYER_BUNDLE_FUNDING_REQUIRED')
            if any(paid.get(ident) != amount for ident, amount in cost_rows(companion, oid, manifest['costs'])):
                raise ValueError('WHOLE_BUYER_BUNDLE_COSTS_REQUIRED')
            if not check_delivery(root, manifest, companion['id'], delivery(root, manifest, companion['id']))['accepted']:
                raise ValueError('WHOLE_BUYER_BUNDLE_ACCEPTANCE_REQUIRED')


def audit_order(root, manifest, job_id):
    """Public quote/request binding, without private account or signing data."""
    job, request = _request(root, manifest, job_id)
    choice = request.get('choice')
    selected = validate_choice(choice, job['product'], request['price']) if choice is not None else None
    return {'job_id':job_id, 'product':job['product'], 'workflow':_workflow(job),
            'price_microUSD':request['price'], 'request_sha256':job['input_sha256'],
            'choice_sha256':digest(choice) if choice is not None else None,
            'choice_id':choice['choice_id'] if choice is not None else None,
            'selected_id':selected['id'] if selected is not None else None,
            'selected_offer_ids':choice['selected_offer_ids'] if choice is not None else None,
            'bound_simulated_consent':choice['consent'] if choice is not None else None,
            'buyer_net_utility_microUSD':selected['net_utility_microUSD'] if selected is not None else None,
            'scope':SCOPE, 'observed_customer_demand':False}


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
    job, request = _request(root, manifest, job_id)
    if session_id is not None and session_id != job['session_id']:
        raise ValueError('PRECOMMITTED_SESSION_REQUIRED')
    if len(request.get('choice', {}).get('selected_offer_ids', [])) > 1:
        raise ValueError('COMPLETE_SELECTED_BUNDLE_REQUIRES_FULFILL_BUNDLE')
    result = _fulfill_group(account, root, manifest, [(job, request, order_id, buyer)], hour, consent)
    if result['status'] == 'released':
        result['artifact_sha256'] = digest(delivery(root, manifest, job_id))
    return result


def _bundle_rows(root, manifest, job_ids, order_id_prefix, buyer):
    if type(job_ids) is not list or not job_ids or len(job_ids) != len(set(job_ids)):
        raise ValueError('UNIQUE_COMPLETE_BUNDLE_JOB_IDS_REQUIRED')
    _identifier(order_id_prefix)
    _identifier(buyer)
    rows = []
    choices = []
    # Preserve the manifest's numerical construction order. Lexicographical
    # sorting would put omega-product-10 before omega-product-9 and would change
    # the registered economic/event sequence across a two-item bundle.
    ordered_ids = [job['id'] for job in manifest['jobs'] if job['id'] in job_ids]
    if len(ordered_ids) != len(job_ids):
        raise ValueError('KNOWN_BUNDLE_JOB_IDS_REQUIRED')
    for job_id in ordered_ids:
        job, request = _request(root, manifest, job_id)
        oid = _identifier(order_id_prefix+':'+job_id)
        bid = _identifier(buyer+'/'+job_id)
        rows.append((job, request, oid, bid))
        choices.append(request.get('choice'))
    if any(choice is not None for choice in choices):
        if any(choice is None for choice in choices) or len({choice['choice_id'] for choice in choices}) != 1:
            raise ValueError('ONE_BOUND_BUYER_CHOICE_PER_BUNDLE_REQUIRED')
        if sorted(choice['offer_id'] for choice in choices) != sorted(choices[0]['selected_offer_ids']):
            raise ValueError('COMPLETE_SELECTED_BUYER_BUNDLE_REQUIRED_ONCE')
    return rows


def _group_status(account, rows):
    """Read native orders and native journal entries; no parallel balances."""
    ledger = account.export()['ledger']
    orders = {order['id']:order for order in ledger['orders']}
    ids = {row[2] for row in rows}
    collections = sum(int(entry['amount']) * (1 if entry['kind']=='collections' else -1)
                      for entry in ledger['journal'] if entry['order_id'] in ids and entry['kind'] in {'collections', 'reversal_paid'})
    items = [{'job_id':job['id'], 'order_id':oid, 'state':orders.get(oid, {}).get('state', 'not_offered')}
             for job, request, oid, bid in rows]
    states = {item['state'] for item in items}
    complete = states == {'released'}
    settled = all(item['state'] in {'released', 'cancelled', 'refunded', 'breached'}
                  and int(orders.get(item['order_id'], {}).get('refund_due', 0)) == 0
                  and int(orders.get(item['order_id'], {}).get('compensation_due', 0)) == 0 for item in items)
    return {'status':'released' if complete else 'incomplete', 'complete':complete, 'settled':settled,
            'collected':collections, 'items':items, 'scope':SCOPE,
            'settlement_scope':'PREPARE_ALL_THEN_SEQUENTIAL_RELEASE; INTERRUPTION_REQUIRES_RECOVERY_NOT_DISTRIBUTED_ATOMICITY'}


def bundle_status(account, root, manifest, job_ids, *, order_id_prefix, buyer):
    """A partially released bundle is visibly incomplete, with actual collections."""
    return _group_status(account, _bundle_rows(root, manifest, job_ids, order_id_prefix, buyer))


def fulfill_bundle(account, root, manifest, job_ids, *, order_id_prefix, buyer, hour,
                   consent=True):
    """Recoverably prepare a complete voluntary bundle before any collection.

    The native journal owns all money and event identity. Per-item synthetic
    wallets represent one receipt-bound total buyer budget; they are not new
    customer demand. All outputs must pass independent acceptance before any
    release. An interruption propagates and is resumed using identical IDs.
    A definitive failure compensates every item, including a native reversal
    (and its retained breach consequences) if release had already occurred.
    """
    return _fulfill_group(account, root, manifest,
                          _bundle_rows(root, manifest, job_ids, order_id_prefix, buyer), hour, consent)


def _fulfill_group(account, root, manifest, rows, hour, consent):
    if type(consent) is not bool:
        raise ValueError('EXPLICIT_SIMULATED_BUYER_CONSENT_REQUIRED')
    if type(hour) is not int or hour < 0:
        raise ValueError('EXPLICIT_NONNEGATIVE_PRODUCT_HOUR_REQUIRED')
    if not consent or any(request.get('choice', {}).get('consent', True) is not True for job, request, oid, bid in rows):
        result = _group_status(account, rows)
        result.update(status='declined', reason='NEW_ACTION_DECLINED_EXISTING_NATIVE_STATE_RETAINED')
        return result
    for job, request, oid, bid in rows:
        _identifier(oid+':late_reversal')
        _identifier(bid)
    ledger = account.export()['ledger']
    actions = ledger['actions']
    orders = {order['id']:order for order in ledger['orders']}
    existing_costs = {a['args']['id']:a for a in actions if a['op']=='cost'}
    planned_costs = {}
    for job, request, oid, bid in rows:
        for ident, amount in cost_rows(job, oid, manifest['costs']):
            if ident in planned_costs and planned_costs[ident] != amount:
                raise ValueError('BUNDLE_COST_ID_REBOUND')
            planned_costs[ident] = amount
            if ident in existing_costs:
                action = existing_costs[ident]
                if action['args']['amount'] != amount or action['after']['expensePaid'] - action['before']['expensePaid'] != amount:
                    raise ValueError('COMPLETE_PRODUCT_COSTS_BEFORE_ACCEPTANCE_REQUIRED')
    paying = all(request['outcome'].get('paid', True) for job, request, oid, bid in rows)
    missing_cost = sum(amount for ident, amount in planned_costs.items() if ident not in existing_costs)
    # Each price backs native funded custody. The additional USD0.20 per new
    # item is a conservative campaign liquidity buffer for prospective tail
    # exposure; it is not an invented native expense or extra collection.
    funding = sum(_job_price(job)+200_000 for job, request, oid, bid in rows
                  if oid not in orders or orders[oid]['state'] == 'offered') if paying else 0
    if missing_cost + funding > ledger['summary']['available']:
        return {'status':'deferred', 'complete':False, 'collected':_group_status(account, rows)['collected'],
                'reason':'PRESENT_UNRESTRICTED_NATIVE_CASH_INSUFFICIENT',
                'required_microUSD':missing_cost+funding, 'available_microUSD':ledger['summary']['available'], 'scope':SCOPE}

    def event(oid, action, **extra):
        return account.execute('event', {'id':oid, 'action':action, 'event_id':oid+':'+action, **extra}, hour)

    def compensate(status, reason=None):
        current = {order['id']:order for order in account.export()['ledger']['orders']}
        for job, request, oid, bid in rows:
            state = current.get(oid, {}).get('state')
            if state == 'released':
                event(oid, 'late_reversal')
            elif state in {'funded', 'verified', 'custody-lost', 'refund-due'}:
                event(oid, 'refund')
            elif state == 'offered':
                event(oid, 'cancel')
            elif state == 'breached' and int(current[oid]['refund_due']) > 0:
                event(oid, 'refund')
        result = _group_status(account, rows)
        result.update(status=status)
        if reason is not None:
            result['reason'] = reason
        return result

    # An interrupted compensation is an existing obligation, not a new sale.
    if any(orders.get(oid, {}).get('state') in {'cancelled', 'refunded', 'breached', 'refund-due'} for job, request, oid, bid in rows):
        return compensate('unpaid' if not paying else 'refunded', 'RECOVER_EXISTING_TERMINAL_BUNDLE')
    for ident, amount in planned_costs.items():
        if ident not in existing_costs:
            account.cost(ident, amount, hour)
    for job, request, oid, bid in rows:
        price = _job_price(job)
        account.execute('register_terms', {'id':oid+':terms', 'terms':terms_for(manifest,oid,job['product'],hour,price)}, hour)
        account.execute('wallet', {'buyer':bid, 'amount':price if paying else 0}, hour)
        account.execute('offer', {'id':oid, 'buyer':bid, 'price':price, 'job_id':job['id'],
                                 'deadline':hour+min(24, manifest['claim_window_hours']-1), 'terms_id':oid+':terms'}, hour)
        event(oid, 'consent')
        if paying:
            event(oid, 'fund')
    if not paying:
        return compensate('unpaid', 'DECLARED_BUYER_NONPAYMENT_NO_FUNDED_CUSTODY_OR_COLLECTION')
    try:
        artifacts = [(job, oid, produce(root, manifest, job['id'])) for job, request, oid, bid in rows]
        if not all(check_delivery(root, manifest, job['id'], artifact)['accepted'] for job, oid, artifact in artifacts):
            return compensate('refunded', 'WHOLE_BUNDLE_INDEPENDENT_ACCEPTANCE_FAILED')
        for job, oid, artifact in artifacts:
            event(oid, 'prepare', artifact_sha256=digest(artifact))
        for job, oid, artifact in artifacts:
            event(oid, 'release')
    except (ValueError, RuntimeError, OSError) as error:
        # Simulated interruptions must remain pending and resume through the
        # existing journal. They do not prove a definitive delivery failure.
        if isinstance(error, InterruptedError):
            raise
        if str(error) == 'IMMUTABLE_PRODUCT_BYTES_CHANGED':
            raise
        return compensate('refunded', type(error).__name__+':'+str(error)[:200])
    return _group_status(account, rows)


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
