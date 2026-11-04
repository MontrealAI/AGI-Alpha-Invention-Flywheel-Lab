"""Offline execution of the bounded observation-to-command contract."""
from .inputs import registration


def command(witness, hour, observed_fault=None):
    if not isinstance(hour,int) or not 0 <= hour < 24:
        raise ValueError('Hour outside registered horizon')
    r=registration()
    if hour < r['fault_reveal_hour']:
        if observed_fault is not None:
            return {'grid_mw':0.,'backup_mw':0.,'charge_mw':0.,'discharge_mw':0.,'work_units':0.,'completion_guaranteed':False,'status':'early unexpected event; disconnect; outside registered guarantee'}
        scenario='normal'
    elif observed_fault in r['scenarios']:
        scenario=observed_fault
    else:
        return {'grid_mw':0.,'backup_mw':0.,'charge_mw':0.,'discharge_mw':0.,'work_units':0.,'completion_guaranteed':False,'status':'unrecognized or missing observation; disconnect; no work guarantee'}
    p=witness['plans'][scenario]
    return {key+'_mw':float(p[key][hour]) for key in ('grid','backup','charge','discharge')} | {'work_units':float(witness['work'][hour]),'completion_guaranteed':True,'status':'registered modeled command'}


def replay(witness):
    r=registration();count=0
    for scenario in r['scenarios']:
        done=[0.,0.]
        for t in range(24):
            cmd=command(witness,t,None if t<8 else scenario)
            for key in ('grid','backup','charge','discharge'):
                if abs(cmd[key+'_mw']-witness['plans'][scenario][key][t])>1e-5:raise ValueError('Anticipatory command')
            done[t//12]+=cmd['work_units'];count+=1
        if any(abs(x-6*witness['it_capacity_mw'])>1e-5 for x in done):raise ValueError('Deadline missed in replay')
    unknown=command(witness,8,'unmodeled_simultaneous_failure')
    if unknown['grid_mw'] != 0 or unknown['completion_guaranteed']:raise ValueError('Fail-safe violated')
    return {'accepted':True,'commands_replayed':count,'unmodeled_event':'disconnects; no completed-work guarantee'}
