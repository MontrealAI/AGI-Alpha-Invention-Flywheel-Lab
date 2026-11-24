"""Exercise distributed isolation and independently replay both research generations."""

from pathlib import Path

from activate import read
from packets import allowed
from pages import canonical
from phase import close, predict
from table_program import Program, Refused
from verify_activation import LIVE_CASE, LIVE_CATALOGUE, verify
from pages import digest


def portable(value):
    if isinstance(value,dict):
        return {k:portable(v) for k,v in value.items() if not k.endswith('_ns')}
    if isinstance(value,list):
        return [portable(x) for x in value]
    return value


def controls():
    body='def choose(n, r):\n  for i in range(n):\n    if v(i, 0) < 2:\n      continue\n    return i\n  return -1'
    rows=[(0,0,0,0,0,0),(3,50,0,0,0,0)]
    if Program(body,2)(rows,1)!=1:
        raise ValueError('LOOP_REPLAY')
    invalid=[('def choose(n, r):\n  return outside()',2),
             ('def choose(n, r):\n  return v(n,0)',2),
             ('def choose(n, r):\n  while n:\n    return 0',2),(body,1)]
    for source,revision in invalid:
        try:
            Program(source,revision)(rows,1)
        except Refused:
            pass
        else:
            raise ValueError('ISOLATION_DENIAL')
    heavy='def choose(n, r):\n  total=0\n  for i in range(n):\n    for j in range(n):\n'+(
        '      total=total+1\n'*18)+'  return total'
    try:
        Program(heavy)(rows*24,1)
    except Refused as issue:
        if str(issue)!='TRAP_OR_FUEL':
            raise ValueError('FUEL_CONTROL_DID_NOT_EXECUTE') from issue
    else:
        raise ValueError('FUEL_DENIAL')
    if allowed({'kind':'direct','url':'https://example.org/unknown'}):
        raise ValueError('ORIGIN_DENIAL')
    return {'row_loop':True,'denied':len(invalid)+2}


def phase_controls(root):
    state={'predictions':[{'observed_at':30},{'observed_at':60}]}
    close(state,{'completed':55})
    if [item['actual'] for item in state['predictions']]!=[25,None]:
        raise ValueError('PHASE_CENSOR')
    history=read(root/'phase-history.json')['history']
    events=read(root/'phase-events.json')
    edge=max(r['completed'] for r in events)+30
    fixture={'event':'push','created':edge,'number':9999}
    scored=predict(edge+5,fixture,{},history,events)
    altered=history+[{'run':{'event':'push','completed':edge+1},'jobs':{}}]*20
    if not scored or predict(edge+5,fixture,{},altered,events)!=scored:
        raise ValueError('PHASE_TIME_BOUNDARY')
    out={'historical_runs':len(history),'censored':True,'future_excluded':True}
    prospective=root/'phase-pr.json'
    if prospective.is_file():
        observation=read(prospective)
        terminal=observation['terminal']
        if (observation['state']!='COMPLETE' or terminal['id']!=observation['binding']['run'] or
                observation['binding']['history']!=digest(history) or observation['binding']['events']!=digest(events)):
            raise ValueError('PHASE_EXPERIMENT_BINDING')
        rebuilt={'predictions':[]}
        used=set()
        for poll in observation['polls']:
            if 'jobs' not in poll:
                continue
            label=predict(poll['seen'],terminal,poll['jobs'],history,events)
            if label and label['phase'] not in used:
                rebuilt['predictions'].append(label)
                used.add(label['phase'])
        close(rebuilt,terminal)
        if rebuilt['predictions']!=observation['predictions']:
            raise ValueError('PROSPECTIVE_PHASE_DRIFT')
        out.update(prospective_run=terminal['id'],admissible_predictions=sum(x['admissible'] for x in rebuilt['predictions']))
    return out


def replay(root):
    catalogue=read(root/'corpus/catalogue.json')
    if digest(catalogue)!=LIVE_CATALOGUE or digest(read(root/'live-case.json'))!=LIVE_CASE:
        raise ValueError('PORTABLE_LIVE_BINDING')
    results={key:verify(root/'corpus',read(root/f'{key}-run.json')) for key in ('initial','followup')}
    if portable(results)!=portable(read(root/'verification.json')):
        raise ValueError('ACTIVATION_REPLAY_DRIFT')
    return {'studies':{name:{'objective':r['objective'],'exact':r['primary']['exact'],
                    'cases':r['primary']['cases'],'fresh':{arm:x['exact'] for arm,x in r['fresh'].items()}}
                       for name,r in results.items()},'controls':controls(),'historical_phases':phase_controls(root)}


if __name__=='__main__':
    print(canonical(replay(Path(__file__).resolve().parent/'study')).decode())
