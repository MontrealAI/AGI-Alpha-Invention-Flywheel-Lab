"""Use the consolidated offline scientific workbench and its observed research evidence."""

import argparse
from pathlib import Path

import covariance_study
import hydrology
from science_substrate import canonical, read_json
from science_workbench import LABS, replay


ROOT = Path(__file__).resolve().parent
STUDY = ROOT/'study/liberation'


def open_result(name, source=None):
    if name in LABS:
        path=source or ROOT/LABS[name]['file']
        return replay(name,read_json(path))
    if name=='hydrology':
        return hydrology.integrate(read_json(source)) if source else hydrology.verify_report(read_json(STUDY/'HYDROLOGY.json'))
    if name=='covariance':
        return covariance_study.assess(read_json(source or STUDY/'COVARIANCE.json')['cases'])
    if name=='timing-audit':
        return read_json(source or STUDY/'INDEPENDENT-TIMING.json')
    if name=='construction':
        cases=read_json(source or STUDY/'CONSTRUCTION.json')['conditions']
        return {name:{'status':row['construction']['status'],'score':row['held']['outcomes']} for name,row in cases.items()}
    return {**LABS,'covariance':{'scope':'Historical calibration and temporal contrast from 165 public transit targets'},
            'timing-audit':{'scope':'Cross-reduction evidence on the same historical TESS observations'},
            'hydrology':{'scope':'Source-bound integration of complete measured discharge intervals'},
            'construction':{'scope':'Held execution of bounded scientific expressions'}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool',choices=('list',*LABS,'covariance','timing-audit','hydrology','construction'))
    parser.add_argument('input',type=Path,nargs='?')
    options=parser.parse_args()
    print(canonical(open_result(options.tool,options.input)).decode())
