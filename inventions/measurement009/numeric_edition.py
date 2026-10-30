import argparse
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time

SEMANTICS = 'canonical-json-finite-binary64-decimal-rational-v1'
CHANGE_LIMIT = Fraction(1, 2000000000000)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def _unique_pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY:' + key)
        result[key] = value
    return result

def adapt_corpus(raw_corpus_bytes):
    if type(raw_corpus_bytes) is not bytes:
        raise ValueError('EXACT_RAW_BYTES_REQUIRED')
    original = json.loads(raw_corpus_bytes, object_pairs_hook=_unique_pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('NONFINITE_JSON:' + value)))
    canonical(original)
    if original.get('schema') != 'agi-alpha/measurement-corpus009/v1' or original.get('numeric_semantics') != SEMANTICS:
        raise ValueError('CORPUS_NUMERICAL_CONTRACT')
    if 'numeric_edition' in original:
        raise ValueError('EDITION_ALREADY_ADAPTED')
    nodes, sources, times = original['nodes'], original['sources'], original['times_seconds']
    if any(type(values) is not list or not values or len(values) != len(set(values)) for values in (nodes,sources,times)):
        raise ValueError('COHORT_IDENTITIES')
    if len(nodes)*len(sources)*len(times) > 500000:
        raise ValueError('ADAPTER_COORDINATE_CAP')
    signal = original['signal']
    if type(signal) is not list or len(signal) != len(sources):
        raise ValueError('SOURCE_DIMENSION')
    if any(type(rows) is not list or len(rows) != len(times) for rows in signal):
        raise ValueError('TIME_DIMENSION')
    if any(type(row) is not list or len(row) != len(nodes) for rows in signal for row in rows):
        raise ValueError('SENSOR_DIMENSION')
    transformed, changes = [], []
    maximum_change = Fraction(0)
    minimum, maximum = None, None
    count = 0
    for i, rows in enumerate(signal):
        new_rows = []
        for t, row in enumerate(rows):
            new_row = []
            for k, value in enumerate(row):
                if type(value) not in (int,float) or (type(value) is float and not math.isfinite(value)):
                    raise ValueError('FINITE_NUMERIC_SIGNAL_REQUIRED')
                text = str(value)
                with localcontext() as context:
                    context.prec = max(64, len(text)+350)
                    rounded = Decimal(text).quantize(Decimal('0.000000000001'), rounding=ROUND_HALF_EVEN)
                new = float(rounded)
                if not math.isfinite(new):
                    raise ValueError('FINITE_ROUNDED_SIGNAL_REQUIRED')
                old_exact, new_exact = Fraction(text), Fraction(str(new))
                if new_exact != Fraction(rounded):
                    raise ValueError('CANONICAL_FLOAT_DOES_NOT_PRESERVE_ROUNDED_DECIMAL')
                change = abs(new_exact-old_exact)
                if change > CHANGE_LIMIT:
                    raise ValueError('REPRESENTATION_CHANGE_BOUND')
                if new_exact < 0 or new_exact > 100:
                    raise ValueError('TRANSFORMED_TRACE_PERCENT_RANGE')
                if change:
                    changes.append([i,t,k,text,str(new)])
                maximum_change = max(maximum_change,change)
                minimum = new_exact if minimum is None else min(minimum,new_exact)
                maximum = new_exact if maximum is None else max(maximum,new_exact)
                count += 1
                new_row.append(new)
            new_rows.append(new_row)
        transformed.append(new_rows)
    if count != len(nodes)*len(sources)*len(times):
        raise AssertionError('COORDINATE_DENOMINATOR_LOSS')
    adapter_sha = digest(Path(__file__).read_bytes())
    metadata = {
        'schema':'agi-alpha/uniform-decimal-edition009/v1',
        'edition':'uniform-half-even-12dp-v1',
        'raw_corpus_sha256':digest(raw_corpus_bytes),
        'raw_corpus_canonical_sha256':digest(canonical(original)),
        'adapter_sha256':adapter_sha,
        'decimal_places':12,
        'rounding':'ROUND_HALF_EVEN',
        'mapping':'same source/time/sensor indices; every coordinate transformed',
        'scope':'New finite numerical representation; no physical or simulator error bound; original qualification unchanged',
    }
    derived = {**original,'signal':transformed,'numeric_edition':metadata}
    body = canonical(derived)+b'\n'
    receipt = {
        'schema':'agi-alpha/numeric-edition-receipt009/v1',
        'raw_corpus_sha256':metadata['raw_corpus_sha256'],
        'raw_corpus_canonical_sha256':metadata['raw_corpus_canonical_sha256'],
        'derived_corpus_sha256':digest(body),
        'derived_corpus_canonical_sha256':digest(canonical(derived)),
        'adapter_sha256':adapter_sha,
        'decimal_places':12,
        'rounding':'ROUND_HALF_EVEN',
        'coordinate_count':count,
        'changed_count':len(changes),
        'maximum_representation_change_pp':str(maximum_change),
        'change_limit_pp':str(CHANGE_LIMIT),
        'cohort_unchanged':True,
        'transformed_range_pp':[str(minimum),str(maximum)],
        'changed_coordinates':changes,
        'source_simulator_error_bound':None,
        'physical_error_bound':None,
        'original_corpus_qualification':'Unchanged; raw Net3 admission failure remains preserved.',
        'scope':metadata['scope'],
    }
    return derived, receipt

def save(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value)+b'\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-corpus',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compile-plan',action='store_true')
    args = parser.parse_args()
    output = args.output; output.mkdir(parents=True,exist_ok=False)
    start, own = time.monotonic(), time.process_time()
    raw = args.raw_corpus.read_bytes()
    (output/'raw_corpus.json').write_bytes(raw)
    derived, receipt = adapt_corpus(raw)
    save(output/'corpus.json',derived)
    save(output/'NUMERIC_RECEIPT.json',receipt)
    plans = {}
    if args.compile_plan:
        from . import compiler
        expected_compiler = '98892085340baf1b58762e46bc83d46b5290c7b3198171782b407e9c0a783c0d'
        actual_compiler = digest(Path(compiler.__file__).read_bytes())
        if actual_compiler != expected_compiler:
            raise ValueError('FROZEN_PRIMARY_COMPILER_CHANGED')
        for name, algorithm in [('generated_plan','milp'),('ordinary_greedy_plan','greedy'),('ordinary_exact_plan','milp')]:
            plan = compiler.compile_plan(derived,noise_bound_pp='1',max_sensor_erasures=1,algorithm=algorithm)
            save(output/(name+'.json'),plan)
            plans[name] = {'status':plan['status'],'sensors':plan['sensors'],'solver':plan['solver']}
    result = {
        'schema':'agi-alpha/numeric-edition-construction009/v1',
        'network':derived['network'],
        'edition':derived['numeric_edition']['edition'],
        'source_raw_sha256':receipt['raw_corpus_sha256'],
        'derived_canonical_sha256':receipt['derived_corpus_canonical_sha256'],
        'coordinate_count':receipt['coordinate_count'],'changed_count':receipt['changed_count'],
        'maximum_representation_change_pp':receipt['maximum_representation_change_pp'],
        'plans':plans,
        'wall_seconds':time.monotonic()-start,'process_cpu_seconds':time.process_time()-own,
        'complete_monetary_cost':None,
        'scope':receipt['scope'],
        'files':{p.name:{'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()},
    }
    if args.raw_corpus.read_bytes() != raw:
        raise ValueError('ORIGINAL_CORPUS_CHANGED')
    save(output/'RESULT.json',result)
    print(json.dumps({key:result[key] for key in ['network','coordinate_count','changed_count','maximum_representation_change_pp','process_cpu_seconds']}))

if __name__ == '__main__':
    main()
