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
    # A valid account proves what was charged, not that all authored service,
    # acquisition, independent checking, failed-quote and tax costs were paid.
    # Bind every required modeled cost to the original frozen protocol.
    required_costs = {}
    if arm == 'cheap_rival':
        required_costs['cheap-rival-prospecting'] = protocol['no_bid_search_microUSD']
    else:
        if arm == 'shared':
            for name, amount in protocol['fixed_shared'].items():
                required_costs['shared-' + name] = amount
        else:
            for name in ('failed_search', 'support_and_maintenance'):
                required_costs['direct-' + name] = protocol['fixed_shared'][name]
        for buyer in buyers:
            for name, amount in protocol['per_order'].items():
                required_costs['market062-' + buyer + '-' + name] = amount
            if arm == 'direct':
                required_costs['market062-' + buyer + '-bespoke-source-setup'] = protocol['fixed_per_independent_buyer']
        if arm == 'shared':
            required_costs['first-stage-profit-tax'] = protocol['stage1_tax_microUSD']
            required_costs['second-stage-profit-tax'] = protocol['stage2_tax_microUSD']
    costs = {}
    for action in tape.get('actions', []):
        if not isinstance(action, dict) or action.get('op') != 'cost':
            continue
        args = action.get('args', {})
        if not isinstance(args, dict) or args.get('id') in costs:
            raise ValueError('NATIVE_COMPLETE_COST_SCHEDULE_MISMATCH')
        costs[args.get('id')] = args.get('amount')
    if costs != required_costs:
        raise ValueError('NATIVE_COMPLETE_COST_SCHEDULE_MISMATCH')
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
        # Audit of a valid native order alone cannot establish WHICH accepted
        # service was offered to this buyer. Tie its source-bound offer action
        # to the exact independently checked historical measurement job.
        offers = [action for action in tape.get('actions', [])
                  if isinstance(action, dict) and action.get('op') == 'offer'
                  and isinstance(action.get('args'), dict)
                  and action['args'].get('id') == ident]
        if (len(offers) != 1 or offers[0]['args'].get('buyer') != buyer
                or offers[0]['args'].get('job_id') != 'evidence_matrix-market062-' + buyer):
            raise ValueError('NATIVE_OFFER_DELIVERABLE_IDENTITY_MISMATCH')
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
    # An earned-funded expense is not a predecessor of the successor merely
    # because both occur in one valid account. Verify native event ordering:
    # the adapter must be finished before the C instrument is offered.
    actions = tape.get('actions', [])
    finished = [i for i, action in enumerate(actions) if isinstance(action, dict)
                and action.get('op') == 'finish'
                and isinstance(action.get('args'), dict)
                and action['args'].get('id') == plan_id]
    successor_offers = [i for i, action in enumerate(actions) if isinstance(action, dict)
                        and action.get('op') == 'offer'
                        and isinstance(action.get('args'), dict)
                        and action['args'].get('id') == 'market062-C']
    if len(finished) != 1 or len(successor_offers) != 1 or successor_offers[0] <= finished[0]:
        raise ValueError('EARNED_ADAPTER_NOT_BEFORE_SUCCESSOR_OFFER')
    before = reserves[0].get('before', {})
    for field in ('cash', 'profit', 'collections', 'expenses', 'available', 'unrestrictedEarned'):
        if reported['after_two'].get(field) != before.get(field):
            raise ValueError('NATIVE_EARNINGS_PREFIX_NOT_BOUND')
    return True


def check_public_economic_claims(report, protocol):
    """Derive economic flags from audited arm summaries; keep real-world nonclaims fixed."""
    arms = report.get('arms')
    if not isinstance(arms, dict) or set(arms) != {'direct', 'shared', 'cheap_rival'}:
        raise ValueError('PUBLIC_ECONOMIC_ARM_INVENTORY_MISMATCH')
    shared, direct, rival = (arms[name] for name in ('shared', 'direct', 'cheap_rival'))
    expected = {
        'shared_positive': shared['summary']['profit'] > 0,
        'matched_direct_negative': direct['summary']['profit'] < 0,
        'earned_funded': shared['earned_receipt']['funding'] == 'EARNED',
        'cheap_rival_no_bid': rival['decision']['choice'] == 'NO_BID',
        'actual_revenue_microUSD': 0,
        'real_demand_observed': False,
        'complete_actual_host_cost_known': False,
        'recursive_or_market_novelty_proven': False,
        'successor_output_preconstructed_for_native_registration': True,
        'causal_necessity_of_adapter_not_proven': True,
        'ordinary_pooled_rival_excluded': False}
    if report.get('conclusions') != expected:
        raise ValueError('PUBLIC_ECONOMIC_SCOPE_OR_CLAIM_TAMPERED')
    fixed = sum(protocol['fixed_shared'].values())
    per = sum(protocol['per_order'].values())
    sensitivity = {
        'ten_percent_fixed_cost_overrun_stage1_profit_microUSD':
            int(2*protocol['quote_microUSD'] - fixed*110//100 -
                2*per - protocol['stage1_tax_microUSD']),
        'first_stage_profit_hurdle_microUSD': protocol['earned_only_successor_adapter_microUSD']}
    if report.get('sensitivity') != sensitivity:
        raise ValueError('PUBLIC_ECONOMIC_SENSITIVITY_TAMPERED')
    return True
