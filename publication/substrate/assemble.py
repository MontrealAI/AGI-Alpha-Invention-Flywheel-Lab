"""Project pinned scientific sources into constructor and evaluator files."""

import argparse
from hashlib import sha256
from pathlib import Path

from science_reference import verified
from science_substrate import canonical, calculate, problem, read_json, review, source_records


def emit(path, value):
    path.write_bytes(canonical(value)+b'\n')


def scoped_case(row, anchor):
    target, witness, values = row
    return problem(target,witness,'BJD_TDB',anchor,values)


def held(rows, anchor, forbidden, source):
    result=[]
    ordered=sorted(rows,key=lambda row:sha256((source+row[0]).encode()).digest())
    for decision in ('WITHIN','EXCEEDS','COVARIANCE_SENSITIVE'):
        chosen=[]
        for row in ordered:
            if row[0] in forbidden:
                continue
            case=scoped_case(row,anchor)
            expected=verified(case)
            if expected['decision'] == decision:
                chosen.append({'input':case,'expected':expected,'origin':source})
                forbidden.add(row[0])
                if len(chosen)==4:
                    break
        if len(chosen)!=4:
            raise ValueError('CONFIRMATION_DENOMINATOR')
        result.extend(chosen)
    return result


def main():
    parse=argparse.ArgumentParser(description=__doc__)
    for name in ('registration','paper','archive','output'):
        parse.add_argument('--'+name,type=Path,required=True)
    a=parse.parse_args()
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    constructor=a.output/'constructor'
    evaluation=a.output/'evaluation'
    constructor.mkdir(mode=0o700)
    evaluation.mkdir(mode=0o700)
    reg=read_json(a.registration)
    papers=a.paper.read_bytes()
    archived=a.archive.read_bytes()
    rows=source_records(papers,'paper')
    archives=source_records(archived,'archive')
    anchor=reg['horizons_bjd_tdb'][0]
    by_name={row[0]:row for row in rows}
    chosen=[by_name[n] for n in ('55Cnce','GJ1252b','HAT-P-13b')]
    dev=[scoped_case(row,anchor) for row in chosen]
    dev.append(problem('fixture-missing','fixture:missing','BJD_TDB',anchor,['2459554.20747','0.0001','0.73654635',None,'1.55757']))
    fixtures=[
        problem('fixture-scale','fixture:wrong-basis','JD_UTC',anchor,['2459544','0','1.1','0','1']),
        problem('fixture-boundary','fixture:positive-boundary','BJD_TDB','2000001',['2000000','0.002','1','0.0005','0.72']),
        problem('fixture-signed','fixture:negative-epoch','BJD_TDB','1999997.9',['2000000','0.001','1','0.0005','0.56']),
        problem('fixture-zero','fixture:zero-errors','BJD_TDB','2000000',['2000000','0','1','0','1']),
    ]
    forbidden={row[0] for row in chosen}
    native=held(rows,anchor,forbidden,'paper')
    fresh=held(archives,reg['horizons_bjd_tdb'][1],forbidden,'archive')
    tests=native+fresh+[{'input':case,'expected':verified(case),'origin':'boundary fixture'} for case in fixtures]
    if any(calculate(row['input'])!=row['expected'] for row in tests):
        raise ValueError('SEPARATE_REFERENCE_CONFIRMATION')
    emit(constructor/'DEVELOPMENT.json',[{'input':case,'expected':verified(case)} for case in dev])
    emit(evaluation/'CONFIRMATION.json',tests)
    reconciliation=[]
    for raw, collection in ((papers,'paper'),(archived,'archive')):
        items = source_records(raw,collection)
        for horizon in reg['horizons_bjd_tdb']:
            for row in items:
                case=scoped_case(row,horizon)
                if calculate(case)!=verified(case):
                    raise ValueError('CENSUS_REFERENCE_DISAGREEMENT')
            reconciliation.append(review(raw,collection,horizon))
    emit(evaluation/'SURVEYS.json',reconciliation)
    emit(a.output/'BINDINGS.json',{
        'registration_sha256':sha256(a.registration.read_bytes()).hexdigest(),
        'development_sha256':sha256((constructor/'DEVELOPMENT.json').read_bytes()).hexdigest(),
        'confirmation_sha256':sha256((evaluation/'CONFIRMATION.json').read_bytes()).hexdigest(),
        'surveys_sha256':sha256((evaluation/'SURVEYS.json').read_bytes()).hexdigest(),
        'rows':{'paper':len(rows),'archive':len(archives)},'confirmation_counts':{'paper':12,'archive':12,'boundary fixture':4}})


if __name__=='__main__':
    main()
