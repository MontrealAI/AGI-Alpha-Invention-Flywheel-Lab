"""Inspect A0067's step protocol only, before freezing other-cell analysis."""
import csv
import hashlib
import io
import json
import urllib.request
from collections import defaultdict

from .probe import URL, EXPECTED_BYTES, EXPECTED_SHA256


def main():
    with urllib.request.urlopen(URL, timeout=120) as response:
        raw = response.read(EXPECTED_BYTES + 1)
    assert len(raw) == EXPECTED_BYTES and hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256
    rows = list(csv.DictReader(io.StringIO(raw.decode())))
    groups = defaultdict(list)
    for r in rows:
        groups[(int(r['Cycle Count / 1']), int(r['Step Index / 1']))].append(r)
    by_step = defaultdict(list)
    selected = []
    for (cycle, step), rs in sorted(groups.items()):
        iv = [float(r['Current / A']) for r in rs]
        vv = [float(r['Voltage / V']) for r in rs]
        tv = [float(r['Test Time / s']) for r in rs]
        qv = [float(r['Step Capacity / Ah']) for r in rs]
        if min(iv) < -0.1:
            qmax = max(qv)
            integral = sum(-0.5*(iv[j]+iv[j-1])*(tv[j]-tv[j-1])/3600 for j in range(1,len(rs)))
            entry = dict(cycle=cycle,step=step,rows=len(rs),imax=max(iv),imin=min(iv),vmax=max(vv),vmin=min(vv),qmax=qmax,qfirst=qv[0],qlast=qv[-1],integral=integral,duration=tv[-1]-tv[0])
            by_step[step].append(entry)
            if cycle in [0,1,2,3,4,5,10,20,50,99,100,101,200,499,500,501,999,1000,1001]:
                selected.append(entry)
    summary = {step:dict(cycles=len(es),first_cycle=min(e['cycle'] for e in es),last_cycle=max(e['cycle'] for e in es),qmin=min(e['qmax'] for e in es),qmax=max(e['qmax'] for e in es),max_integral_error=max(abs(e['integral']-(e['qlast']-e['qfirst'])) for e in es),imin=min(e['imin'] for e in es),imax=max(e['imax'] for e in es),vmin=min(e['vmin'] for e in es),vmax=max(e['vmax'] for e in es)) for step,es in sorted(by_step.items())}
    print('DEVELOPMENT_DISCHARGE_STEPS='+json.dumps(summary,sort_keys=True))
    print('DEVELOPMENT_SELECTED_CYCLES='+json.dumps(selected,sort_keys=True))
    print('DEVELOPMENT_ANOMALIES='+json.dumps(dict(voltage_over_5_rows=sum(float(r['Voltage / V'])>5 for r in rows),time_decreases=sum(float(b['Test Time / s'])<float(a['Test Time / s']) for a,b in zip(rows,rows[1:])),cycle_decreases=sum(int(b['Cycle Count / 1'])<int(a['Cycle Count / 1']) for a,b in zip(rows,rows[1:])))))


if __name__ == '__main__':
    main()
