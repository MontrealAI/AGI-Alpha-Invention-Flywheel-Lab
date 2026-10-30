import argparse,hashlib,json
from fractions import Fraction
from pathlib import Path

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):
    raw=Path(path).read_bytes()
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('DUPLICATE_JSON_KEY')
            result[k]=v
        return result
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')));canonical(value);return value,raw
def q(value):
    if type(value) not in (float,int,str):raise ValueError('FINITE_NUMERIC_VALUE_REQUIRED')
    return Fraction(str(value))

def rounded(value):
    scaled=q(value)*10**12;lower=scaled.numerator//scaled.denominator;fraction=scaled-lower
    if fraction>Fraction(1,2) or (fraction==Fraction(1,2) and lower%2):lower+=1
    return Fraction(lower,10**12)

def check(raw_path,derived_path,receipt_path,adapter_source=None):
    raw,raw_bytes=read(raw_path);derived,derived_bytes=read(derived_path);receipt,receipt_bytes=read(receipt_path)
    if receipt.get('schema')!='agi-alpha/numeric-edition-receipt009/v1':raise ValueError('RECEIPT_SCHEMA')
    if raw.get('numeric_semantics')!='canonical-json-finite-binary64-decimal-rational-v1':raise ValueError('RAW_NUMERIC_MODEL')
    if set(derived)!=set(raw)|{'numeric_edition'} or 'numeric_edition' in raw:raise ValueError('ONE_NEW_EDITION_METADATA_ONLY')
    for name in raw:
        if name!='signal' and derived[name]!=raw[name]:raise ValueError('UNCHANGED_COHORT_OR_METADATA:'+name)
    raw_signal,new_signal=raw['signal'],derived['signal']
    if len(raw_signal)!=len(raw['sources']) or len(new_signal)!=len(raw_signal):raise ValueError('SOURCE_DIMENSION')
    changes=[];maximum=Fraction(0);minimum=None;largest=None;count=0
    for source,values in enumerate(raw_signal):
        if len(values)!=len(raw['times_seconds']) or len(new_signal[source])!=len(values):raise ValueError('TIME_DIMENSION')
        for t,row in enumerate(values):
            if len(row)!=len(raw['nodes']) or len(new_signal[source][t])!=len(row):raise ValueError('SENSOR_DIMENSION')
            for sensor,old in enumerate(row):
                new=new_signal[source][t][sensor];expected=rounded(old);actual=q(new);difference=abs(actual-q(old));count+=1
                if actual!=expected:raise ValueError('WRONG_UNIFORM_TRANSFORM:'+str((source,t,sensor)))
                if difference>Fraction(1,2*10**12):raise ValueError('REPRESENTATION_CHANGE_BOUND')
                if not 0<=actual<=100:raise ValueError('TRANSFORMED_PERCENT_RANGE')
                maximum=max(maximum,difference);minimum=actual if minimum is None else min(minimum,actual);largest=actual if largest is None else max(largest,actual)
                if actual!=q(old):changes.append([source,t,sensor,str(old),str(new)])
    metadata=derived['numeric_edition']
    if metadata.get('schema')!='agi-alpha/uniform-decimal-edition009/v1' or metadata.get('edition')!='uniform-half-even-12dp-v1':raise ValueError('EDITION_SCHEMA')
    if metadata.get('decimal_places')!=12 or metadata.get('rounding')!='ROUND_HALF_EVEN' or receipt.get('decimal_places')!=12 or receipt.get('rounding')!='ROUND_HALF_EVEN':raise ValueError('PRESPECIFIED_ROUNDING_RULE')
    identities={'raw_corpus_sha256':sha(raw_bytes),'raw_corpus_canonical_sha256':sha(canonical(raw)),'derived_corpus_sha256':sha(derived_bytes),'derived_corpus_canonical_sha256':sha(canonical(derived))}
    if any(receipt.get(k)!=v for k,v in identities.items()):raise ValueError('RECEIPT_CORPUS_BINDING')
    if any(metadata.get(k)!=identities[k] for k in ['raw_corpus_sha256','raw_corpus_canonical_sha256']):raise ValueError('EDITION_RAW_BINDING')
    adapter_source=Path(adapter_source) if adapter_source else Path(__file__).resolve().parents[2]/'inventions/measurement009/numeric_edition.py'
    adapter_raw=adapter_source.read_bytes();adapter_sha=sha(adapter_raw)
    if metadata.get('adapter_sha256')!=adapter_sha or receipt.get('adapter_sha256')!=adapter_sha:raise ValueError('ADAPTER_SOURCE_BINDING')
    if receipt.get('coordinate_count')!=count or receipt.get('changed_count')!=len(changes) or receipt.get('changed_coordinates')!=changes:raise ValueError('COMPLETE_CHANGED_COORDINATE_ACCOUNTING')
    if q(receipt.get('maximum_representation_change_pp'))!=maximum or q(receipt.get('change_limit_pp'))!=Fraction(1,2*10**12) or receipt.get('cohort_unchanged') is not True:raise ValueError('REPRESENTATION_BOUNDS_OR_COHORT_RECEIPT')
    if [q(v) for v in receipt.get('transformed_range_pp',[])]!=[minimum,largest]:raise ValueError('TRANSFORMED_RANGE_RECEIPT')
    for path,original in [(Path(raw_path),raw_bytes),(Path(derived_path),derived_bytes),(Path(receipt_path),receipt_bytes),(adapter_source,adapter_raw)]:
        if path.read_bytes()!=original:raise ValueError('INPUT_CHANGED_DURING_VERIFICATION')
    return {'schema':'agi-alpha/next009-independent-numeric-edition-check/v1','accepted':True,**identities,'adapter_sha256':adapter_sha,'checker_sha256':sha(Path(__file__).read_bytes()),'receipt_sha256':sha(receipt_bytes),'coordinate_count':count,'changed_count':len(changes),'maximum_representation_change_pp':str(maximum),'change_limit_pp':'1/2000000000000','transformed_range_pp':[str(minimum),str(largest)],'full_cohort_preserved':True,'scope':'Exact integer half-even recomputation of every coordinate, independent of adapter Decimal arithmetic. New finite numerical edition only; no physical calibration or simulator error bound; original raw-model qualification remains unchanged.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw-corpus',type=Path,required=True);p.add_argument('--derived-corpus',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--adapter-source',type=Path);a=p.parse_args();result=check(a.raw_corpus,a.derived_corpus,a.receipt,a.adapter_source)
    with a.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))
