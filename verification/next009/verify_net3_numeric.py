import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time
from verification.next009 import verify, numeric_edition_checker

EXPECTED = {
    "checker_sha256": "08bd61de297e491115c48d0a6eca482dc1c40f42966daf646e4cd2737cf68a76",
    "plan_sha256": "c182c3452dfef907f43b293953c1336826b6d38428d1b369d73bf7abd61d58f5",
    "corpus_raw_sha256": "28e760c2b9270e2309a098d74b8ac13c4fa4372b3edecc38e6412d5d760534cd",
    "corpus_canonical_sha256": "2b539b2350ab274612454d4530cf897e8edf52d86b02e3f9f7c6c9b266cf1aff",
    "primary_protocol_sha256": "5e80370c23a9486489334a9b7e17cd2f612d5db5dab77bd2e546313aa7282351",
    "network_sha256": "ea3e825c4fef0b5cba47fb06301bc85253f18b6364dc96c44d9fb492c40faa52",
    "original_raw_corpus_sha256": "8d67223f938b73889c1e80905a90861f72926d9a9e2a8233f37cc7fa2c5e545f",
    "numeric_receipt_sha256": "8d3f9134d5c720c252b11c96d6283a80a0cdf941ce806abc0a83ecf09afe7c1c",
    "adapter_source_sha256": "34a847e1944b3bed8bcc69221b94ac7d24f8b19f04a029c893afd8926775a13e",
    "numeric_checker_sha256": "2a8cec4a863e6102d3a3c1b610e193f2156c2000225cfd44a9f284c9ec74ac64"
}

SCOPE = {
    'schema': 'agi-alpha/net3-numeric-edition-driver-scope009/v1',
    'exposure': 'EXPOSED_DEVELOPMENT_DERIVED_NUMERICAL_EDITION',
    'fixed_dimensions': {'sources': 92, 'sensors': 92, 'times': 24, 'source_pairs': 4186},
    'sensor_chunk_width': 46,
    'primary_requirement_subset_checked': ['all-pair feasibility after every allowed sensor erasure', 'all-sensor uncalibrated ambiguity witness'],
    'primary_requirements_not_repeated': ['independently exhaustive global minimum', 'protected runtime confirmation'],
    'source_rule': 'Use unchanged frozen verifier arithmetic only; do not import candidate arithmetic.',
    'cap_rule': 'Each corpus_values call receives exactly two sources and at most 46 sensors; the original 48-object cap is preserved.',
    'composition_justification': 'The allowed nuisance and error set factors by sensor. Each sensor has its own constant offset and reference error; shared reference error across times stays within that sensor check. There is no cross-sensor constraint and no probabilistic independence assumption. Thus the complete pair-channel vector is exactly the concatenation of disjoint checked sensor slices.',
    'role': 'Executed by the original builder using separately authored frozen verifier arithmetic plus this new builder-authored composition driver. Shared host and session; procedural replay, not external independence.',
    'optimality': 'HiGHS cardinality 25 remains solver-reported; this driver certifies feasibility only.',
    'claim_alpha_spent': 0,
    'edition_rule': 'Uniform half-even 12-place numerical edition, independently checked at every coordinate before feasibility. Original raw Net3 failure and identities remain unchanged.',
    'driver_ancestry_sha256': '80b96c6f5b35ab539baa207cca9ab252d4b66733c2286f5ab694d9b3cd4438eb',
}

def save(path, value):
    with path.open('xb') as stream:
        stream.write(verify.canonical(value)+b'\n')

def slice_pair(corpus, a, b, begin, end):
    return {
        **corpus,
        'sources': [corpus['sources'][a], corpus['sources'][b]],
        'nodes': corpus['nodes'][begin:end],
        'signal': [[row[begin:end] for row in corpus['signal'][source]] for source in (a,b)],
    }

def evaluate(corpus_path, plan_path, protocol_path, output, raw_corpus_path, numeric_receipt_path, adapter_source_path):
    started, own = time.monotonic(), time.process_time()
    corpus, corpus_raw = verify.read(corpus_path)
    plan, plan_raw = verify.read(plan_path)
    protocol, protocol_raw = verify.read(protocol_path)
    checker_path = Path(verify.__file__)
    driver_path = Path(__file__)
    checker_raw, driver_raw = checker_path.read_bytes(), driver_path.read_bytes()
    numeric_checker_path = Path(numeric_edition_checker.__file__)
    numeric_checker_raw = numeric_checker_path.read_bytes()
    original_raw = raw_corpus_path.read_bytes()
    numeric_receipt_raw = numeric_receipt_path.read_bytes()
    adapter_raw = adapter_source_path.read_bytes()
    observed = {
        'checker_sha256': verify.sha(checker_raw),
        'plan_sha256': verify.sha(plan_raw),
        'corpus_raw_sha256': verify.sha(corpus_raw),
        'corpus_canonical_sha256': verify.sha(verify.canonical(corpus)),
        'primary_protocol_sha256': verify.sha(protocol_raw),
        'network_sha256': corpus.get('network_sha256'),
        'original_raw_corpus_sha256': verify.sha(original_raw),
        'numeric_receipt_sha256': verify.sha(numeric_receipt_raw),
        'adapter_source_sha256': verify.sha(adapter_raw),
        'numeric_checker_sha256': verify.sha(numeric_checker_raw),
    }
    if observed != EXPECTED:
        raise ValueError('REGISTERED_NET3_NUMERIC_EDITION_IDENTITIES_CHANGED')
    numeric_check = numeric_edition_checker.check(raw_corpus_path,corpus_path,numeric_receipt_path,adapter_source_path)
    if numeric_check.get('accepted') is not True or numeric_check.get('coordinate_count') != 203136:
        raise ValueError('FULL_NUMERIC_TRANSFORM_NOT_QUALIFIED')
    if corpus.get('network') != 'Net3' or len(corpus['sources']) != 92 or len(corpus['nodes']) != 92:
        raise ValueError('EXACT_NET3_COHORT_REQUIRED')
    if corpus['sources'] != corpus['nodes'] or corpus['times_seconds'] != list(range(0,86400,3600)):
        raise ValueError('COHORT_OR_TIME_DENOMINATOR_CHANGED')
    if len(set(corpus['sources'])) != 92 or any(type(s) is not str or not s for s in corpus['sources']):
        raise ValueError('COMPLETE_UNIQUE_SOURCE_IDENTITIES_REQUIRED')
    if len(corpus['signal']) != 92 or any(len(rows) != 24 or any(len(row) != 92 for row in rows) for rows in corpus['signal']):
        raise ValueError('COMPLETE_SIGNAL_CUBE_REQUIRED')
    if protocol.get('scope') != verify.SCOPE or protocol.get('noise_bound_pp') != '1' or protocol.get('max_sensor_erasures') != 1:
        raise ValueError('REUSED_REQUIREMENTS_CHANGED')
    if plan.get('schema') != 'agi-alpha/observation-plan009/v1' or plan.get('operator') != 'known-zero-reference':
        raise ValueError('PLAN_TYPE')
    if plan.get('corpus_sha256') != observed['corpus_canonical_sha256'] or plan.get('network_sha256') != observed['network_sha256']:
        raise ValueError('PLAN_SOURCE_BINDING')
    if plan.get('numeric_semantics') != corpus.get('numeric_semantics') or plan.get('noise_bound_pp') != '1' or plan.get('max_sensor_erasures') != 1:
        raise ValueError('PLAN_MODEL_MISMATCH')
    expected_ast = {'op':'subtract','left':{'op':'read','sensor':'$sensor','time':'$time'},'right':{'op':'zero_reference','sensor':'$sensor'}}
    if plan.get('generated_expression',{}).get('ast') != expected_ast:
        raise ValueError('GENERATED_EXPRESSION_MISMATCH')
    if plan.get('nuisance') != 'arbitrary-per-sensor-offset-constant-across-reference-and-trace':
        raise ValueError('NUISANCE_SCOPE_MISMATCH')
    nodes, sources = corpus['nodes'], corpus['sources']
    selected_names = plan.get('sensors')
    if type(selected_names) is not list or len(selected_names) != 25 or len(set(selected_names)) != 25 or any(s not in nodes for s in selected_names):
        raise ValueError('REGISTERED_25_SENSOR_PLAN_REQUIRED')
    selected = tuple(nodes.index(s) for s in selected_names)
    noise = verify.exact(protocol['noise_bound_pp'])
    output.mkdir(parents=True, exist_ok=False)
    save(output/'DRIVER_SCOPE.json', SCOPE)
    save(output/'NUMERIC_TRANSFORM_CHECK.json',numeric_check)
    save(output/'SOURCE_BINDINGS.json', {**observed, 'driver_sha256': verify.sha(driver_raw), 'expected': EXPECTED})
    channels, coverage = [], []
    original_pairs = list(itertools.combinations(range(92),2))
    for a,b in original_pairs:
        calibrated, uncalibrated, sensor_indices = [], [], []
        for begin in (0,46):
            end = begin+46
            small = slice_pair(corpus,a,b,begin,end)
            values = verify.corpus_values(small)
            checked = verify.pair_channels(values,noise)
            if len(checked) != 1 or checked[0]['a'] != 0 or checked[0]['b'] != 1:
                raise AssertionError('CHECKER_PAIR_INDEX_COMPOSITION')
            pair = checked[0]
            if len(pair['calibrated']) != 46 or len(pair['uncalibrated']) != 46:
                raise AssertionError('CHECKER_SENSOR_DIMENSION_COMPOSITION')
            if any(type(v) is not bool for v in pair['calibrated']+pair['uncalibrated']):
                raise AssertionError('CHECKER_BOOLEAN_CHANNEL_TYPE')
            calibrated.extend(pair['calibrated']); uncalibrated.extend(pair['uncalibrated'])
            sensor_indices.extend(range(begin,end))
        if sensor_indices != list(range(92)):
            raise AssertionError('SENSOR_CHANNEL_COVERAGE_LOSS')
        channels.append({'a':a,'b':b,'calibrated':calibrated,'uncalibrated':uncalibrated})
        coverage.append([a,b])
    if coverage != [list(pair) for pair in original_pairs] or len(channels) != 4186:
        raise AssertionError('SOURCE_PAIR_DENOMINATOR_LOSS')
    save(output/'ALL_PAIR_CHANNELS.json', {'sources':sources,'nodes':nodes,'pairs':channels})
    checks = verify.outage_checks(selected,channels,sources,1)
    expected_erasures = [[], *[[s] for s in selected]]
    if [row['erased_indices'] for row in checks] != expected_erasures or len(checks) != 26:
        raise AssertionError('OUTAGE_DENOMINATOR_LOSS')
    save(output/'ALL_OUTAGE_CHECKS.json', {'all_pairs_denominator':4186,'outage_states':26,'pair_outage_obligations':4186*26,'checks':checks})
    unresolved = [pair for pair in channels if not any(pair['uncalibrated'])]
    if not unresolved:
        raise AssertionError('NO_FULL_SENSOR_CAUSAL_WITNESS')
    first = unresolved[0]
    assembled = []
    for begin in (0,46):
        small = slice_pair(corpus,first['a'],first['b'],begin,begin+46)
        values = verify.corpus_values(small)
        witness = verify.ambiguity_witness(values,{'a':0,'b':1},noise,small['nodes'],small['sources'])
        if witness['sources'] != [sources[first['a']],sources[first['b']]] or not witness['checked_equal']:
            raise AssertionError('WITNESS_TRUTH_IDENTITY_CHANGED')
        assembled.extend(witness['witness'])
    if [record['sensor'] for record in assembled] != nodes:
        raise AssertionError('WITNESS_SENSOR_DENOMINATOR_LOSS')
    full_witness = {'sources':[sources[first['a']],sources[first['b']]],'all_sensor_count':92,'all_timestamps':24,
        'witness':assembled,'checked_equal':True,'scope':'One coherent pair of source truths, each with a full 92-sensor offset/noise vector. Frozen checker verifies identical observations within allowed errors at every original sensor and time. Per-sensor composition does not assert probabilistic independence.'}
    save(output/'UNCALIBRATED_ALL_SENSOR_WITNESS.json',full_witness)
    for path, raw in [(corpus_path,corpus_raw),(plan_path,plan_raw),(protocol_path,protocol_raw),(checker_path,checker_raw),(driver_path,driver_raw),(numeric_checker_path,numeric_checker_raw),(raw_corpus_path,original_raw),(numeric_receipt_path,numeric_receipt_raw),(adapter_source_path,adapter_raw)]:
        if path.read_bytes() != raw:
            raise ValueError('SOURCE_BYTES_CHANGED_DURING_REPLAY')
    feasible = all(row['passed'] for row in checks)
    report = {
        'schema':'agi-alpha/net3-numeric-edition-feasibility009/v1',
        'exposure':SCOPE['exposure'],
        'numeric_edition':corpus['numeric_edition'],
        'numeric_transform_check':numeric_check,
        'original_raw_net3_qualification':'UNCHANGED; original frozen range-admission failure remains preserved.',
        'feasibility_accepted':feasible,
        'full_primary_protocol_qualification':'NOT_ESTABLISHED_BY_THIS_DRIVER; exhaustive global minimum and protected runtime confirmation are not rerun.',
        'bindings':{**observed,'driver_sha256':verify.sha(driver_raw)},
        'dimensions':{'sources':92,'sensors':92,'times':24,'pairs':4186,'outage_states':26,'pair_outage_obligations':4186*26},
        'composition':{'sensor_chunks':[[0,46],[46,92]],'exact_source_pair_coverage':True,'exact_sensor_coverage_per_pair':True,'original_frozen_verifier_cap_preserved':48,'all_sample_times_included':True},
        'candidate_sensors':selected_names,
        'all_pairs_after_each_erasure':checks,
        'uncalibrated_all_sensor_ambiguous_pairs':[[sources[p['a']],sources[p['b']]] for p in unresolved],
        'first_two_truth_witness':full_witness['sources'],
        'global_minimum':{'independently_certified':False,'status':'SOLVER_REPORTED_ONLY','source_plan_solver_report':plan['solver'],'exhaustive_subsets_evaluated':0},
        'independence':SCOPE['role'],
        'claim_alpha_spent':0,
        'scope':'Exact finite-corpus observation-plan feasibility and causal ambiguity replay. No field measurement, novelty superiority, independent global optimum, protected confirmation, or commercial validation.',
        'wall_seconds':time.monotonic()-started,'process_cpu_seconds':time.process_time()-own,
        'complete_monetary_cost':None,
        'files':{path.name:{'sha256':verify.sha(path.read_bytes()),'bytes':path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file()},
    }
    save(output/'NET3_NUMERIC_FEASIBILITY.json',report)
    print(json.dumps({'feasibility_accepted':feasible,'pairs':4186,'outage_states':26,'witness':full_witness['sources'],'process_cpu_seconds':report['process_cpu_seconds']}))
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('corpus','plan','protocol','output','raw-corpus','numeric-receipt','adapter-source'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    result=evaluate(args.corpus,args.plan,args.protocol,args.output,args.raw_corpus,args.numeric_receipt,args.adapter_source)
    raise SystemExit(0 if result['feasibility_accepted'] else 1)
