"""Select and compose retained scientific operations for public research inputs."""

import argparse
import json
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
from pathlib import Path
from time import monotonic


ROOT = Path(__file__).resolve().parent
STUDY = ROOT / 'study/cascade'
MODEL = 'qwen3-4b-instruct-2507-q4_k_m'
PERMISSION = 'public-research/read'
EPHEMERIS_PROGRAM = '51d0e2d8788a67067462da5e6aa98e6f23a1f710f489512a2722823cb9b859ce'
OPERATIONS = {
    'check_tess': ('request', 'tess_pair', 'Two reductions of the same verified original FITS. Both use BJD_TDB.'),
    'compare_tess': ('tess_pair', 'decision', 'Check attributed midpoint agreement in seconds. This gives no observing authority.'),
    'check_ephemeris': ('request', 'ephemeris', 'Check the published element types, uncertainty fields, and BJD_TDB anchor.'),
    'compute_window': ('ephemeris', 'decision', 'Replay the retained exact arithmetic and return timing window classification.'),
    'check_oni': ('request', 'oni_series', 'Locate one dated season in the complete historical CPC ERSSTv5 series, in tenths of °C.'),
    'classify_oni': ('oni_series', 'decision', 'Classify the historical season using the five consecutive three-month means rule.'),
    'abstain': ('request', 'decision', 'Record a known missing source, incompatible basis, denied permission, or operational scope.'),
}
ROUTES = {
    'tess': ('check_tess', 'compare_tess'),
    'ephemeris': ('check_ephemeris', 'compute_window'),
    'oni': ('check_oni', 'classify_oni'),
}
BLOCKED = {'check_tess', 'compare_tess', 'compute_window', 'classify_oni'}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def stamp(value):
    return sha256(encode(value).encode()).hexdigest()


def decision(status, witness, value=None):
    return {'status':status, 'value':value, 'witness':witness}


def admissibility(job):
    if job.get('permission') != PERMISSION:
        return 'ABSTAIN_PERMISSION'
    kind = job.get('family')
    if type(kind) is not str or kind not in ROUTES or job.get('intent') != 'historical':
        return 'ABSTAIN_SCOPE'
    if job.get('basis') != {'oni':'ERSSTv5_ONI_TENTHS_C', 'ephemeris':'BJD_TDB', 'tess':'BJD_TDB'}[kind]:
        return 'ABSTAIN_BASIS'
    if type(job.get('witness')) is not str or not job['witness']:
        return 'ABSTAIN_SOURCE'
    return None


def number(value):
    if type(value) not in (str, float, int) or len(str(value))>36:
        raise ValueError('NUMBER')
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError('NUMBER') from error
    if not result.is_finite() or result.adjusted() not in range(-25, 15):
        raise ValueError('NUMBER')
    return result


def check_tess(job, evidence):
    pair = job.get('pair')
    witness = job['witness']
    if (type(pair) is not list or len(pair) != 2 or any(type(row) is not dict for row in pair)
            or [row.get('method') for row in pair] != ['primary','ordinary']
            or not all(row.get('source_sha256') == witness for row in pair)
            or len(witness) != 64 or witness.strip('abcdef0123456789')):
        return decision('ABSTAIN_SOURCE', witness)
    identifier = job.get('case_id')
    record = evidence['tess_records'].get(identifier) if type(identifier) is str else None
    if (record is None or any(encode(job.get(key)) != encode(record[key])
                             for key in ('pair','date_window_bjd_tdb','attribution_conflict'))):
        return decision('ABSTAIN_SOURCE', witness)
    if job.get('attribution_conflict') is True:
        return decision('ABSTAIN_ATTRIBUTION', witness)
    if any(row.get('verdict') != 'MEASURED' for row in pair):
        return decision('ABSTAIN_MEASUREMENT', witness)
    try:
        lower, upper = map(number, job['date_window_bjd_tdb'])
        measured = [(number(row['mid_bjd_tdb']), number(row['uncertainty_s'])) for row in pair]
    except (KeyError, ValueError, TypeError):
        return decision('ABSTAIN_MEASUREMENT', witness)
    if not all(lower < mid < upper and 0 < sigma <= 600 for mid, sigma in measured):
        return decision('ABSTAIN_MEASUREMENT', witness)
    return measured


def compare_tess(pair, witness):
    (first, error1), (second, error2) = pair
    with localcontext() as ctx:
        ctx.prec = 33
        seconds = abs(first-second)*86400
        # The methods share photometry. This is a conservative agreement screen, not an independent error estimate.
        limit = min(Decimal(600), max(Decimal(90), 3*(error1 + error2)))
        if seconds > limit:
            return decision('ABSTAIN_DISAGREEMENT', witness)
        return decision('CONCORDANT', witness, {'mid_bjd_tdb':format(first, '.6f')})


def run_plan(job, plan, evidence, *, withdrawn=False, oni_fixture=None):
    witness = job.get('witness')
    receipt = []
    reject = admissibility(job)
    family = job.get('family')
    route = ROUTES.get(family, ()) if type(family) is str else ()
    if (type(plan) not in (tuple, list) or not plan
            or tuple(plan) not in (('abstain',), route, route[:1])):
        return decision('ABSTAIN_PLAN', witness), receipt
    kind, value = 'request', job
    for operation in plan:
        if withdrawn and operation in BLOCKED:
            return decision('ABSTAIN_UNAVAILABLE', witness), receipt
        input_kind, output_kind, _ = OPERATIONS[operation]
        if kind != input_kind:
            return decision('ABSTAIN_PLAN', witness), receipt
        if reject and operation != 'abstain':
            return decision(reject, witness), receipt
        started = monotonic()
        if operation == 'abstain':
            value = decision(reject or 'ABSTAIN_UNJUSTIFIED', witness)
        elif operation == 'check_tess':
            value = check_tess(job, evidence)
        elif operation == 'compare_tess':
            value = compare_tess(value, witness)
        elif operation == 'check_ephemeris':
            from science_substrate import typed_fields
            case = job.get('input')
            if (type(case) is not dict or case.get('witness') != witness or case.get('basis') != job['basis']
                    or type(case.get('ephemeris')) is not dict or not case.get('anchor')):
                value = decision('ABSTAIN_SOURCE', witness)
            else:
                try:
                    value = decision('ABSTAIN_MISSING', witness) if any(x is None for x in typed_fields(case)) else case
                except (TypeError, ValueError, KeyError):
                    value = decision('ABSTAIN_SOURCE', witness)
        elif operation == 'compute_window':
            from liberation import programs, project
            from science_substrate import calculate
            try:
                artifact = evidence['ephemeris_program']
                if stamp(artifact) != EPHEMERIS_PROGRAM:
                    raise ValueError('UNQUALIFIED_EPHEMERIS_PROGRAM')
                computed = project(programs(artifact), value)
                if computed != calculate(value):
                    raise ValueError('EPHEMERIS_CONTROL_DISAGREEMENT')
                value = decision(computed['decision'], witness, {'epoch':computed['epoch'], 'sigma_s':computed['sigma_s']})
            except (ValueError, KeyError, ArithmeticError, TypeError, SyntaxError):
                value = decision('ABSTAIN_COMPUTATION', witness)
        elif operation == 'check_oni':
            from cascade_fresh_domain import SOURCE_SHA256
            month = job.get('middle_month')
            if type(month) is not str or witness != SOURCE_SHA256:
                value = decision('ABSTAIN_SOURCE', witness)
            else:
                value = month
        elif operation == 'classify_oni':
            from cascade_fresh_domain import qualify
            parameters = {'fixture':oni_fixture} if oni_fixture else {}
            try:
                finding = qualify(**parameters, middle_months=(value,))
                if finding['status']=='ABSTAIN_WINDOW':
                    value = decision('ABSTAIN_WINDOW', witness)
                else:
                    row, = finding['selected_seasons']
                    value = decision(row['classification'].upper(), witness,
                                     {'middle_month':row['middle_month'], 'anomaly_tenths_c':row['anomaly_tenths_c']})
            except (ValueError, KeyError, TypeError):
                value = decision('ABSTAIN_SOURCE', witness)
        receipt.append({'operation':operation,'input_kind':kind,'output_kind':output_kind,
                        'elapsed_ms':round(1000*(monotonic()-started),3)})
        if type(value) is dict and value.keys() == {'status', 'value', 'witness'}:
            return value, receipt
        kind = output_kind
    return decision('ABSTAIN_INCOMPLETE', witness), receipt


def conventional(job):
    return ('abstain',) if admissibility(job) else ROUTES[job['family']]


def complete_dependencies(job, selection):
    """Resolve required evidence checks for a compatible model-selected operation."""
    if type(selection) not in (list,tuple) or admissibility(job):
        return selection
    route = ROUTES[job['family']]
    if len(selection)==1 and selection[0] in route:
        return route
    if tuple(selection)==('abstain',) and job['family']=='tess':
        return route[:1]
    return selection


def visible_job(job):
    route_fields = ('id', 'family', 'basis', 'intent', 'permission')
    request = {name:job.get(name) for name in route_fields}
    if admissibility(job):
        return request
    details = {
        'tess':('witness','case_id','attribution_conflict','date_window_bjd_tdb','pair'),
        'ephemeris':('witness','input'),
        'oni':('witness','middle_month','ordered_window_tenths_c','requested_index'),
    }
    shown = {**request, **{name:job.get(name) for name in details[job['family']]}}
    if job['family']=='tess' and type(shown['pair']) is list:
        wanted = ('method','verdict','source_sha256','mid_bjd_tdb','uncertainty_s')
        shown['pair'] = [{key:row.get(key) for key in wanted} for row in shown['pair'] if type(row) is dict]
    if job['family']=='ephemeris' and type(shown['input']) is dict:
        case = shown['input']
        fields = ('t0_day','t0_sigma_day','period_day','period_sigma_day','duration_hour')
        shown['input'] = {key:case.get(key) for key in ('target','witness','basis','anchor')}
        shown['input']['ephemeris'] = {key:case['ephemeris'].get(key) for key in fields} if type(case.get('ephemeris')) is dict else None
    return shown


STEP_KEY = dict(zip('TtEeOoX', OPERATIONS, strict=True))
STATUS_KEY = dict(zip('CMADSBPYKLWN', (
    'CONCORDANT','ABSTAIN_MEASUREMENT','ABSTAIN_ATTRIBUTION','ABSTAIN_DISAGREEMENT',
    'ABSTAIN_SCOPE','ABSTAIN_BASIS','ABSTAIN_PERMISSION','WITHIN','COVARIANCE_SENSITIVE',
    'COLD','WARM','UNCOLORED'), strict=True))


def operator_job(job):
    shown = visible_job(job)
    base = {name: shown[name] for name in ('family','basis','intent','permission')}
    if admissibility(job):
        return base
    if job['family']=='tess':
        base['conflict'] = shown['attribution_conflict']
        base['band'] = shown['date_window_bjd_tdb']
        base['reductions'] = [[row['verdict'],row['source_sha256']==shown['witness'],row['mid_bjd_tdb'],row['uncertainty_s']]
                              for row in shown['pair']]
    elif job['family']=='ephemeris':
        case = shown['input']
        fields = ('t0_day','t0_sigma_day','period_day','period_sigma_day','duration_hour')
        base['elements'] = [case['anchor'],*[case['ephemeris'][name] for name in fields]]
    else:
        base['month'] = shown['middle_month']
        base['window'] = shown['ordered_window_tenths_c']
    return base


def model_prompt(jobs, arm):
    facts = ('Public historical research only. Require public-research/read. TESS and ephemeris require BJD_TDB. '
             'ONI requires ERSSTv5_ONI_TENTHS_C. Decline other scope, basis, or permission. '
             'TESS reductions are [verdict,hash verified,midpoint,sigma_seconds]. Decline target conflict, '
             'non-MEASURED rows, or sigma outside (0,600]. Compare midpoints in seconds within min(600,max(90,3*sum(sigmas))). '
             'For concordance use the first center, six decimals. Ephemeris elements are [a,t,u,p,v,d], '
             'a/t/u/p/v are in days, d is hours. n=ceil((a-t)/p); low=abs(u-abs(n)*v)*86400, high=(u+abs(n)*v)*86400, limit=d*300. '
             'WITHIN if high<=limit else COVARIANCE_SENSITIVE if low<=limit. Round interval outward to integer seconds. '
             'ONI uses nine ordered tenths Celsius values; the fifth is the requested month. WARM or COLD if it belongs '
             'to any five adjacent values >=5 or <=-5 respectively, otherwise UNCOLORED. Use the fifth anomaly.')
    if arm == 'direct':
        directive = ('Return a JSON object keyed by job ID. Values are brief strings. Start with the status letter '
                     'from ' + encode(STATUS_KEY) + '. For TESS concordance append |midpoint. For ephemeris append '
                     '|epoch|lower|upper. For ONI append |month|anomaly. For abstention use just the status letter. No tools.')
    elif arm == 'typed':
        directive = ('Return a JSON object keyed by job ID with ordered one- or two-letter programs. X alone records '
                     'the known scope denial. Registry maps letters to (input type, output type, purpose): ' + encode(
                         {code:OPERATIONS[operation] for code,operation in STEP_KEY.items()}))
    else:
        directive = ('Return a JSON object keyed by job ID with ordered one- or two-letter programs. X alone records '
                     'the known scope denial. Available operations: ' + ' '.join(
                         f'{code} takes {before} and yields {after}. {definition}'
                         for code,operation in STEP_KEY.items() for before,after,definition in (OPERATIONS[operation],)))
    return f'{facts}\n{directive}\nJobs: {encode({job["id"]:operator_job(job) for job in jobs})}'


def unpack(value, arm):
    if arm != 'direct':
        if len(value)>2 or any(code not in STEP_KEY for code in value):
            return []
        return [STEP_KEY[code] for code in value]
    letter, *payload = value.split('|')
    status = STATUS_KEY.get(letter)
    result = None
    try:
        if status == 'CONCORDANT':
            mid, = payload
            result = {'mid_bjd_tdb':mid}
        elif status in ('WITHIN','COVARIANCE_SENSITIVE'):
            epoch, low, high = map(int,payload)
            result = {'epoch':epoch,'sigma_s':[low,high]}
        elif status in ('WARM','COLD','UNCOLORED'):
            month, anomaly = payload
            result = {'middle_month':month,'anomaly_tenths_c':int(anomaly)}
        elif not status or payload:
            raise ValueError('DIRECT_OPERATOR_RESPONSE')
    except ValueError:
        return {'status':'ABSTAIN_RESPONSE','value_json':'null'}
    return {'status':status,'value_json':encode(result)}


def operator_batch(jobs, arm, options, workspace):
    from model_step import brief, object_schema, step

    properties = {job['id']:{'$ref':'#/$defs/answer'} for job in jobs}
    schema = {**object_schema(properties),'$defs':{'answer':brief(96 if arm=='direct' else 2)}}
    requested = options.tokens
    prompt = model_prompt(jobs,arm)
    start = monotonic()
    state = step(workspace, options.config, options.model, schema, prompt,
                 f'cascade-compact-{arm}', requested, attempts=1)
    response = state.get('result') or {}
    observations = []
    for event in state['events']:
        entry = {key:event[key] for key in ('status','diagnosis','usage','reason','reported_model','plan_sha256') if key in event}
        # Retain provider identity while omitting executor-local filenames from the public receipt.
        if type(entry.get('reported_model')) is str and '/' in entry['reported_model']:
            entry['reported_model'] = Path(entry['reported_model']).name
        observations.append(entry)
    return {'status':state['status'],'draft':{key:unpack(value,arm) for key,value in response.items()},
            'raw':response,'elapsed_s':round(monotonic()-start,3),
            'prompt_sha256':sha256(prompt.encode()).hexdigest(),'observations':observations}


def batches(jobs):
    return [jobs[start:start+13] for start in range(0,len(jobs),13)]


def small_operator(jobs, arm, options):
    observed = [operator_batch(group,arm,options,options.workspace/arm/str(number))
                for number,group in enumerate(batches(jobs),1)]
    return {'status':'SEALED' if all(row['status']=='SEALED' for row in observed) else 'PARTIAL',
            'draft':{key:value for row in observed for key,value in row['draft'].items()},
            'elapsed_s':round(sum(row['elapsed_s'] for row in observed),3), 'batches':observed}


def accepted(actual, expected):
    return actual['status'] == expected['status'] and encode(actual['value']) == encode(expected['value'])


def evaluate(document, arm, draft=None, oni_fixture=None):
    from bridge.instruments import strict_portable_json

    tally = 0
    rows = []
    expected = document['expected']
    for job in document['jobs']:
        name = job['id']
        calls = []
        if arm == 'direct':
            choice = (draft or {}).get(name, {})
            try:
                result = decision(choice['status'], job['witness'], strict_portable_json(choice['value_json']))
            except (KeyError, ValueError, TypeError):
                result = decision('ABSTAIN_RESPONSE', job['witness'])
        else:
            plan = conventional(job) if arm in ('conventional','strong-reviewed') else (draft or {}).get(name)
            if arm.startswith('completed-'):
                plan = complete_dependencies(job,plan)
            result,calls = run_plan(job,plan,document,withdrawn=arm in ('withdrawn','completed-withdrawn'),oni_fixture=oni_fixture)
        passed = accepted(result, expected[name])
        tally += passed
        item = {'id':name,'accepted':passed,'result':result,'calls':calls}
        if arm != 'direct':
            item['route_correct'] = type(plan) in (list,tuple) and tuple(plan)==conventional(job)
        rows.append(item)
    return {'accepted':tally,'jobs':len(rows),'rows':rows}


def trial_for(arm):
    return 'typed' if arm in ('withdrawn','completed-withdrawn') else arm.removeprefix('completed-')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('registry','replay','operator'))
    parser.add_argument('--study', type=Path, default=STUDY/'RESULTS.json')
    parser.add_argument('--oni',type=Path,default=STUDY/'FRESH-DOMAIN.json')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--workspace',type=Path)
    parser.add_argument('--model',default=MODEL)
    parser.add_argument('--tokens',type=int,default=1400)
    parser.add_argument('--arm',choices=('direct','ordinary','typed'),default='typed')
    opts = parser.parse_args()
    if opts.action == 'registry':
        output = {'operations':OPERATIONS,'permission':PERMISSION,'deployment':'local read-only research',
                  'qualification':'Activation 1.3 ephemeris guard; Activation 1.4 TESS extraction and NOAA CPC reproduction',
                  'dependencies':'Python and packaged public source evidence. Raw TESS rerun additionally needs NumPy, SciPy, CFITSIO.',
                  'costs':'No inference required for deterministic replay. See typed/ordinary receipts for actual measured inference.'}
    else:
        document = json.loads(opts.study.read_bytes())['composition']
        if opts.action == 'operator':
            if not opts.config or not opts.workspace:
                parser.error('operator requires --config and --workspace')
            observation = small_operator(document['jobs'],opts.arm,opts)
            output = {'observation':observation,'score':evaluate(document,opts.arm,observation['draft'],opts.oni),
                      'with_dependencies':evaluate(document,'completed-'+opts.arm,observation['draft'],opts.oni)
                      if opts.arm!='direct' else None}
        else:
            output = {arm:evaluate(document,arm,document.get('trials',{}).get(trial_for(arm),{}).get('draft'),opts.oni)
                      for arm in ('conventional','direct','ordinary','typed','withdrawn',
                                  'completed-typed','completed-ordinary','completed-withdrawn')}
    print(encode(output))


if __name__ == '__main__':
    main()
