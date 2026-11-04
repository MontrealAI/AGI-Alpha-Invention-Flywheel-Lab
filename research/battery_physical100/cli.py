"""Offline first-100-cycle screening; no network and no equipment control."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .measurement import extract
from .prognosis import CUTOFF,PRIMARY,interval_decision,predict,prefix_features


def screen(input_file,group,model,method=PRIMARY,protocol_confirmed=False):
    if not protocol_confirmed:
        return {'status':'CONTINUE_TESTING','reason':'Confirm matched 1C/35C laboratory protocol before screening','group':group}
    bank=json.loads(Path(model).read_text())
    info=bank.get('groups',{}).get(group)
    if info is None:
        return {'status':'CONTINUE_TESTING','reason':'Unsupported cell model group','group':group}
    try:
        measurement=extract(input_file,info['rated_capacity_ah'],CUTOFF)
        prefix=prefix_features(measurement)
        predictions=predict(prefix,group,bank,method)
    except (ValueError,KeyError) as error:
        return {'status':'CONTINUE_TESTING','reason':str(error),'group':group}
    return {'status':'RESEARCH_SCREEN_ONLY','method':method,'group':group,'observed_through_cycle':CUTOFF,
            'reference_capacity_ah':prefix['reference_capacity_ah'],'accepted_prefix_cycles':len(prefix['curve']),
            'data_quality_flags':measurement.flags,'endpoints':interval_decision(predictions,bank['widths'].get(method,{})),
            'limits':['Same-model 1C/35C laboratory protocol only; temperature is not present in this file and requires confirmation.',
                      'Intervals are calibrated residual ranges from nine cells, not field-risk guarantees.',
                      'Screening does not certify safety, warranty, fitness for use or permission to stop required testing.'],
            'unavailable_endpoints':[str(t) for t in (500,1000) if str(t) not in predictions],
            'model_identity':bank.get('model_identity')}


def readable(report):
    lines=['Battery laboratory screening',f"Status: {report['status']}",f"Cell model: {report['group']}"]
    if 'reason' in report:lines.append('Reason: '+report['reason'])
    for endpoint,e in report.get('endpoints',{}).items():
        interval=f" [{100*e['lower']:.2f}%, {100*e['upper']:.2f}%]" if 'lower' in e else ''
        lines.append(f"Cycle {endpoint}: {100*e['prediction']:.2f}% retention{interval}; {e['decision']}")
    lines.extend(report.get('limits',[]))
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',help='BDF CSV, full history or prefix ending at100cycles')
    p.add_argument('--group',required=True)
    p.add_argument('--model',required=True)
    p.add_argument('--method',default=PRIMARY)
    p.add_argument('--json-output')
    p.add_argument('--confirm-matched-lab-protocol',action='store_true',help='Confirm cell model, 1C/35C and publisher cycling/RPT schedule match')
    args=p.parse_args();report=screen(args.input,args.group,args.model,args.method,args.confirm_matched_lab_protocol)
    print(readable(report),end='')
    if args.json_output:Path(args.json_output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main()
