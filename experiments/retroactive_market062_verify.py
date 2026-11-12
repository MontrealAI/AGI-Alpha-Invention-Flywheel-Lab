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
