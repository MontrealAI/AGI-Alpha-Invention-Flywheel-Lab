"""Create the frozen compact-construction confirmation from public source bytes."""

import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

from science_reference import verified
from science_substrate import calculate, canonical, problem, read_json, source_records


def confirmation(paper,exclude):
    ends=('2464236.5','2466070.5')
    classes=('WITHIN','EXCEEDS','COVARIANCE_SENSITIVE')
    groups=defaultdict(list)
    for target,witness,values in source_records(paper,'paper'):
        if target in exclude:
            continue
        draw=int(sha256(('liberation-case-v1:'+target).encode()).hexdigest(),16)
        anchor=ends[draw%2]
        case=problem(target,witness,'BJD_TDB',anchor,values)
        result=verified(case)
        if result['decision'] in classes:
            groups[(anchor,result['decision'])].append((draw,case,result))
    measured=[{'input':case,'expected':result,'origin':'paper'}
              for key in [(a,c) for a in ends for c in classes]
              for _,case,result in sorted(groups[key])[:6]]
    if len(measured)!=36:
        raise ValueError('FROZEN_COHORT_SMALL')
    typical=['2400000.0','0.001','0.51','0.000004','1.4']
    boundaries=[
        ('earlier','BJD_TDB','2399981.7',typical),
        ('at-epoch','BJD_TDB','2400000.0',typical),
        ('rounding','BJD_TDB','2400040.25',['2400000','0','0.50','0.0000037','0.89']),
        ('threshold','BJD_TDB','2400000',['2400000','0.0025','1','0','0.72']),
        ('wrong-basis','JD_UTC','2400000',typical),
        ('unknown','BJD_TDB','2400000',[*typical[:3],None,typical[4]]),
    ]
    for name,basis,anchor,values in boundaries:
        case=problem(name,'liberation:fixture:'+name,basis,anchor,values)
        measured.append({'input':case,'expected':verified(case),'origin':'boundary'})
    if any(calculate(row['input'])!=row['expected'] for row in measured):
        raise ValueError('INDEPENDENT_REFERENCE_DISAGREES')
    return measured


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper',type=Path,required=True)
    parser.add_argument('--exclude',type=Path,nargs='+',required=True)
    args=parser.parse_args()
    omitted={row['input']['target'] for file in args.exclude for row in read_json(file)}
    print(canonical(confirmation(args.paper.read_bytes(),omitted)).decode())
