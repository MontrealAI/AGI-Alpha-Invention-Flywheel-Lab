"""Audited physical discharge episodes, with a strict observation cutoff."""
from __future__ import annotations
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median

FIELDS = ['Test Time / s', 'Voltage / V', 'Current / A', 'Cycle Count / 1',
          'Step Index / 1', 'Step Capacity / Ah']

@dataclass
class Measurement:
    cycles: dict
    flags: list
    observed_rows: int
    cutoff: int

def read_prefix(path: str | Path, cutoff: int):
    """Stop at the first row after cutoff; future voltages/Q never affect features."""
    previous_time = previous_cycle = -1
    with open(path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
            raise ValueError('Required BDF physical quantities missing')
        for line, row in enumerate(reader, 2):
            cycle = float(row['Cycle Count / 1'])
            if not math.isfinite(cycle) or cycle < 0 or not cycle.is_integer():
                raise ValueError(f'Invalid cycle counter on line {line}')
            if cycle > cutoff:
                break
            vals = [float(row[x]) for x in FIELDS]
            if not all(math.isfinite(x) for x in vals):
                raise ValueError(f'Nonfinite observed measurement on line {line}')
            t,v,i,c,s,q = vals
            if t < previous_time or c < previous_cycle or t < 0 or s < 0 or not s.is_integer():
                raise ValueError(f'Chronology or step error on line {line}')
            previous_time, previous_cycle = t,c
            yield (t,v,i,int(c),int(s),q)

def episodes(rows):
    """Contiguous executions, never concatenate repeated step IDs."""
    batch=[]
    key=None
    for row in rows:
        newkey = row[3:5]
        if key is not None and newkey != key:
            yield batch
            batch=[]
        key=newkey
        batch.append(row)
    if batch:
        yield batch

def inspect_episode(ep, nominal):
    t=[x[0] for x in ep]; v=[x[1] for x in ep]; i=[x[2] for x in ep]; q=[x[5] for x in ep]
    # Full approximately 1C discharge, not small pulses or charge/rest steps.
    if min(i) > -0.5*nominal or q[-1]-q[0] < 0.2*nominal:
        return None
    errors=[]
    if len(ep)<3: errors.append('too_few_discharge_samples')
    if q[0]>0.005*nominal: errors.append('nonzero_initial_step_capacity')
    duration=t[-1]-t[0]
    near_1c=sum(t[k]-t[k-1] for k in range(1,len(ep)) if 0.85<=-(i[k]+i[k-1])/(2*nominal)<=1.15)
    if duration<=0 or near_1c/duration<0.98: errors.append('unsupported_discharge_rate')
    if any(x>0.05*nominal for x in i): errors.append('mixed_charge_discharge_episode')
    if any(x<2.5 or x>4.6 for x in v): errors.append('invalid_discharge_voltage')
    if any(b<a-0.0002 for a,b in zip(q,q[1:])): errors.append('capacity_reset_within_episode')
    if any(x<0 for x in q): errors.append('negative_step_capacity')
    if any(b-a>180 for a,b in zip(t,t[1:])): errors.append('discharge_sampling_gap')
    if v[0]<4.0 or v[-1]>3.5: errors.append('incomplete_voltage_span')
    if max(q)>1.3*nominal: errors.append('implausible_capacity')
    integ=sum(-(i[k-1]+i[k])*0.5*(t[k]-t[k-1])/3600 for k in range(1,len(ep)))
    delta=q[-1]-q[0]
    disagreement=abs(integ-delta)
    if disagreement>max(0.005*nominal,0.01*abs(delta)): errors.append('current_capacity_disagreement')
    return dict(cycle=ep[0][3],step=ep[0][4],capacity_ah=q[-1],integral_delta_ah=integ,
                reported_delta_ah=delta,disagreement_ah=disagreement,
                first_capacity_ah=q[0],last_voltage_v=v[-1],first_voltage_v=v[0],
                rows=len(ep),near_1c_fraction=near_1c/duration if duration>0 else 0,errors=errors,curve=[(x[1],x[5]) for x in ep])

def extract(path, nominal, cutoff=100):
    rows=list(read_prefix(path, cutoff))
    flags=[]; cand=defaultdict(list)
    for ep in episodes(rows):
        e=inspect_episode(ep,nominal)
        if e is not None: cand[e['cycle']].append(e)
        elif any(r[1]<2.5 or r[1]>4.6 for r in ep):
            flags.append({'cycle':ep[0][3],'step':ep[0][4],'flag':'non_discharge_voltage_anomaly'})
    cycles={}
    for c in sorted(set(r[3] for r in rows)):
        es=cand.get(c,[])
        if len(es)!=1:
            flags.append({'cycle':c,'flag':'missing_or_multiple_primary_discharge','count':len(es)})
        elif es[0]['errors']:
            flags.append({'cycle':c,'flag':'invalid_primary_discharge','errors':es[0]['errors']})
        else:
            cycles[c]=es[0]
    return Measurement(cycles,flags,len(rows),cutoff)

def window_capacity(measurement,start,end,required_fraction=0.8):
    values=[measurement.cycles[c]['capacity_ah'] for c in range(start,end+1) if c in measurement.cycles]
    required=math.ceil((end-start+1)*required_fraction)
    if len(values)<required:
        raise ValueError(f'Insufficient accepted cycles in [{start},{end}]: {len(values)}/{required}')
    return median(values)

def retained_curve(measurement,reference):
    return {c:e['capacity_ah']/reference for c,e in measurement.cycles.items()}
