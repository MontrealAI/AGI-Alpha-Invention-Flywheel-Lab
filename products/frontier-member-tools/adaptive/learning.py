"""Train a portable timing regressor and compare complete monitoring decisions."""

from math import cos, exp, log, pi, sin
from statistics import fmean, median
from time import perf_counter_ns, process_time_ns

from pages import EVENTS, digest, validate

SCHEMA = 'frontier/completion-regressor-v1'
BASELINES = ('trailing-7','trailing-21','trailing-60','time-neighbors')
FEATURES = ('intercept','last-relative','recent-relative','long-relative','hour-sin','hour-cos',
            'recent-launches','push','schedule')


def quantile(values, quant):
    ordered = sorted(values)
    return ordered[(quant*(len(ordered)-1) + 99)//100]


def duration(row):
    return max(1, row['completed'] - row['created'])


def example(row, history):
    known = [x for x in history if x['event'] == row['event'] and x['completed'] is not None
             and x['completed'] < row['created']]
    recent = sorted(known, key=lambda x:(x['created'], x['number']), reverse=True)[:60]
    if len(recent) < 8:
        return None
    times = [duration(x) for x in recent]
    base = median(times[:21])
    hour = (row['created'] % 86400) / 86400

    def distance(prior):
        offset = abs(hour - (prior['created'] % 86400) / 86400)
        days = (row['created'] - prior['created']) / 86400
        return min(offset,1-offset) + min(days,120)/240

    neighbors = sorted(recent,key=distance)[:12]
    relative = lambda value: min(2, max(-2, log(value/base))) / 2
    x = (1, relative(times[0]), relative(median(times[:7])), relative(median(times)),
         sin(hour*2*pi), cos(hour*2*pi), min(10,sum(row['created']-old['created'] < 3600 for old in recent))/10,
         int(row['event']=='push'), int(row['event']=='schedule'))
    comparisons = dict(zip(BASELINES,(median(times[:7]),base,median(times),median(map(duration,neighbors)))))
    return {'id':row['id'],'number':row['number'],'event':row['event'],'base':base,'features':x,
            'alternatives':comparisons,'times':times,
            'actual': duration(row) if row['completed'] is not None else None}


def examples(records, prior=()):
    return [item for row in records if (item := example(validate(row), [*prior,*records])) is not None]


def train(cases):
    if len(cases) < 16 or any(c['actual'] is None for c in cases):
        raise ValueError('TRAINING_SAMPLE')
    start, cpu = perf_counter_ns(), process_time_ns()
    weights = [0.0] * len(FEATURES)
    outcomes = [(c['features'],log(c['actual']/c['base'])) for c in cases]
    for _ in range(360):
        gradient = [0.0] * len(weights)
        for features, target in outcomes:
            error = min(0.7,max(-0.7,sum(w*x for w,x in zip(weights,features))-target))
            for index, value in enumerate(features):
                gradient[index] += error*value
        for index, g in enumerate(gradient):
            weights[index] -= .08*(g/len(cases) + (.04*weights[index] if index else 0))
    model = {'schema':SCHEMA,'features':list(FEATURES),'init':[0]*len(FEATURES),
             'weights':[round(w,10) for w in weights],'epochs':360,'training_examples':len(cases),
             'training_ids_sha256':digest([c['id'] for c in cases]),'training_sha256':digest(cases)}
    resources = {'wall_ns':perf_counter_ns()-start,'cpu_ns':process_time_ns()-cpu,
                 'parameter_count':len(weights),'paid_inference':0}
    return model, resources


def estimate(model, item):
    base = item['base']
    if model is None:
        return round(base)
    if (model['schema'] != SCHEMA or model['features'] != list(FEATURES) or len(model['weights']) != len(FEATURES)
            or any(type(w) not in (int,float) or not -10 <= w <= 10 for w in model['weights'])):
        raise ValueError('MODEL_FORMAT')
    offset = sum(w*x for w,x in zip(model['weights'],item['features']))
    return max(1,round(base*exp(min(2,max(-2,offset)))))


def forecasts(cases, model):
    values = {'initial':lambda c:estimate(None,c),'trained':lambda c:estimate(model,c)}
    values.update({name:lambda c, name=name:round(c['alternatives'][name]) for name in BASELINES})
    report = {}
    for label, predict in values.items():
        started, cpu = perf_counter_ns(), process_time_ns()
        errors = [(c['event'],abs(predict(c)-c['actual'])) for c in cases]
        costs = {'wall_ns':perf_counter_ns()-started,'cpu_ns':process_time_ns()-cpu}
        by_event = {name:[value for event,value in errors if event==name] for name in EVENTS}
        row = [value for _,value in errors]
        report[label] = {'cases':len(row),'mae_seconds':round(fmean(row),4),'p90_seconds':quantile(row,90),
                         'by_event':{event:{'cases':len(values),'mae_seconds':round(fmean(values),4),
                                             'p90_seconds':quantile(values,90)}
                                     for event,values in by_event.items() if values}, 'measured_ns':costs}
    return report


def clock(cases, choose):
    readings = []
    start, cpu = perf_counter_ns(), process_time_ns()
    for item in cases:
        now, reads = 0, 1
        feature = (round(item['base']),quantile(item['times'],80),quantile(item['times'],95))
        while now < item['actual']:
            waiting = choose(now, *feature, reads, item['times'])
            if type(waiting) is not int or not 5 <= waiting <= 60 or reads >= 4096:
                raise ValueError('INVALID_MONITOR_POLICY')
            now += waiting
            reads += 1
        readings.append({'id':item['id'],'observed':item['actual'],'reads':reads,'delay':now-item['actual']})
    delays = [row['delay'] for row in readings]
    return {'cases':len(readings),'reads':sum(row['reads'] for row in readings),
            'p95_delay':quantile(delays,95),'max_delay':max(delays),
            'wall_ns':perf_counter_ns()-start,'cpu_ns':process_time_ns()-cpu,'details':readings}


def survival(elapsed, median_seconds, p80, p95, reads, times):
    waiting = [duration for duration in times if duration > elapsed]
    if not waiting:
        return 20
    minimum = max(1,len(waiting)//10)
    # Wait longer when the observed cohort rarely finished during that interval.
    near = sorted(waiting)[minimum-1]-elapsed
    return min(60,max(20,near))


def conventional(cases):
    return {'periodic-20':clock(cases,lambda *_:20),'empirical-survival':clock(cases,survival)}


def eligible(row):
    return row['p95_delay'] <= 20 and row['max_delay'] <= 60
