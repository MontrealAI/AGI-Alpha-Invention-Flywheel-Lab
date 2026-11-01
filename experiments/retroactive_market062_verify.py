"""Independent source-row verifier; does not import the producer.

Content hashes do not establish physical calibration or lawful data use.
"""
import hashlib,json

def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def check_measurement(question,sources,result):
    if result.get('schema')!='agi-alpha/historical-sensor062/v1' or result.get('question')!=question:
        raise ValueError('DIFFERENT_QUESTION_OR_SCHEMA')
    names=[question['left'],question['right']]
    if result.get('source_names')!=names or any(result['source_sha256'].get(k)!=sha(sources[k]) for k in names):
        raise ValueError('SOURCE_BYTES_NOT_BOUND')
    if result.get('source_scope')!='SYNTHETIC_NOT_PHYSICAL_GROUND_TRUTH':
        raise ValueError('PHYSICAL_TRUTH_CLAIM_FORBIDDEN')
    observations=[]
    for moment in question['times']:
        matching=[[item for item in sources[name] if item['time']==moment] for name in names]
        if any(len(records)!=1 for records in matching):
            observations.append({'time':moment,'status':'UNKNOWN','source_ids':[]});continue
        a,b=matching[0][0],matching[1][0]
        if any(type(item['value']) not in (int,float) for item in (a,b)):
            observations.append({'time':moment,'status':'UNKNOWN','source_ids':[]});continue
        left_pass=a['value']>=question['left_min']
        right_pass=(b['value']>=question['right_min']) if 'right_min' in question else (b['value']<=question['right_max'])
        observations.append({'time':moment,'status':'EVENT' if left_pass and right_pass else 'NO_EVENT',
                             'source_ids':[a['id'],b['id']]})
    if result.get('measurements')!=observations:raise ValueError('DERIVED_SERIES_CONTRADICTS_SOURCE')
    if result.get('event_count')!=sum(x['status']=='EVENT' for x in observations):raise ValueError('EVENT_COUNT_TAMPERED')
    if result.get('unknown_count')!=sum(x['status']=='UNKNOWN' for x in observations):raise ValueError('UNKNOWN_COUNT_TAMPERED')
    return True


def check_native_claim_binding(arm, exported, reported, measurements, protocol):
    """Cross-check public sales and earned expansion against an already audited native export."""
    if arm not in ('direct', 'shared', 'cheap_rival'):
        raise ValueError('UNKNOWN_NATIVE_COMPARISON_ARM')
    tape = exported.get('ledger', {})
    if tape.get('config', {}).get('contract') != 'market062-' + arm:
        raise ValueError('NATIVE_COMPARISON_ARM_IDENTITY_MISMATCH')
    buyers = ('A', 'B', 'C') if arm == 'shared' else ('A', 'B') if arm == 'direct' else ()
    orders = tape.get('orders', [])
    sales = reported.get('sales')
    if not isinstance(orders, list) or not isinstance(sales, list) or len(orders) != len(buyers) or len(sales) != len(buyers):
        raise ValueError('NATIVE_SALE_DENOMINATOR_MISMATCH')
    order_index = {o.get('id'): o for o in orders if isinstance(o, dict)}
    sale_index = {s.get('id'): s for s in sales if isinstance(s, dict)}
    ids = {'market062-' + buyer for buyer in buyers}
    if set(order_index) != ids or set(sale_index) != ids:
        raise ValueError('NATIVE_SALE_IDENTITY_MISMATCH')
    for buyer in buyers:
        ident = 'market062-' + buyer
        native, claim = order_index[ident], sale_index[ident]
        requirements = {
            'native_state': (native.get('state'), 'released'),
            'native_buyer': (native.get('buyer'), buyer),
            'native_price': (native.get('price'), str(protocol['quote_microUSD'])),
            'reported_state': (claim.get('status'), 'ACCEPTED_AND_COLLECTED'),
            'reported_collection': (claim.get('native_collection_microUSD'), protocol['quote_microUSD']),
            'reported_artifact': (claim.get('artifact'), measurements[buyer])}
        for field, (actual, expected) in requirements.items():
            if actual != expected:
                raise ValueError('NATIVE_SALE_REPORT_NOT_SUPPORTED_BY_LEDGER:' + field)
    expected_choice = 'NO_BID' if arm == 'cheap_rival' else 'SHARED_CONTRACT'
    if reported.get('decision', {}).get('choice') != expected_choice:
        raise ValueError('NATIVE_VOLUNTARY_CHOICE_REPORT_MISMATCH')
    if arm != 'shared':
        if reported.get('earned_receipt') is not None:
            raise ValueError('UNFUNDED_ARM_CLAIMS_EARNED_EXPANSION')
        return True
    journal = exported.get('connected_journal', {})
    entries = journal.get('entries', []) if isinstance(journal, dict) else []
    matching = [e for e in entries if isinstance(e, dict) and e.get('key') == 'spend:third-sensor-adapter']
    if len(matching) != 1:
        raise ValueError('NATIVE_ADAPTER_EXPENSE_MISSING_OR_DUPLICATED')
    entry = matching[0]
    expected_request = {'operation': 'spend', 'id': 'third-sensor-adapter',
        'kind': 'new_archival_signal_instrument',
        'amount': protocol['earned_only_successor_adapter_microUSD'], 'day': 3,
        'work': {'source_measurement': ['A', 'B'], 'new_domain': 'leakage-anomaly',
                 'new_archives': ['flow', 'pressure'], 'expected_successor': 'C'},
        'expected_net': 834 * 1_000_000, 'allow_seed': False}
    receipt = reported.get('earned_receipt')
    if (entry.get('status') != 'COMPLETE' or entry.get('funding') != 'EARNED' or
            entry.get('request') != expected_request or not isinstance(receipt, dict) or
            receipt != entry.get('receipt') or receipt.get('funding') != 'EARNED' or
            receipt.get('amount') != expected_request['amount']):
        raise ValueError('NATIVE_EARNED_ADAPTER_RECEIPT_UNBOUND')
    plan_id = receipt.get('plan_id')
    reserves = [a for a in tape.get('actions', []) if isinstance(a, dict) and
                a.get('op') == 'reserve' and a.get('args', {}).get('id') == plan_id]
    if len(reserves) != 1 or not isinstance(reported.get('after_two'), dict):
        raise ValueError('NATIVE_EARNINGS_PREFIX_NOT_BOUND')
    before = reserves[0].get('before', {})
    for field in ('cash', 'profit', 'collections', 'expenses', 'available', 'unrestrictedEarned'):
        if reported['after_two'].get(field) != before.get(field):
            raise ValueError('NATIVE_EARNINGS_PREFIX_NOT_BOUND')
    return True
