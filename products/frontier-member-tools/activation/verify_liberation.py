"""Replay the packaged construction, covariance, transfer and regression results."""

import argparse
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import covariance_study
import independent_timing
from discovery_workbench import STUDY, open_result
from hydrology import integrate
from liberation import programs, receive, score
from science_substrate import canonical, read_json
from tempfile import TemporaryDirectory


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify_construction():
    raw=(STUDY/'CONFIRMATION.json').read_bytes()
    cases=read_json(STUDY/'CONFIRMATION.json')
    evidence=read_json(STUDY/'CONSTRUCTION.json')['conditions']
    observed={}
    for name,row in evidence.items():
        previous=row['held']
        old=row['construction']
        result=score(old['result'] if old['status']=='SEALED' else None,cases)
        require(previous['confirmation_sha256']==sha256(raw).hexdigest(),'CONFIRMATION_BINDING')
        require(result=={key:previous[key] for key in result},'LOCAL_COMPARISON_REPLAY')
        observed[name]=result['outcomes'].get('ACCEPT',0)
    require(len(cases)==42 and observed['manual']==42,'MANUAL_HELD_ACCEPTANCE')
    with TemporaryDirectory() as directory:
        path=Path(directory)
        response=STUDY/'RESPONSE.json'
        packet=STUDY/'PACKET.json'
        candidate=path/'candidate.json'
        receive(SimpleNamespace(packet=packet,response=response,output=candidate))
        require(read_json(candidate)==evidence['manual']['construction'],'MANUAL_REIMPORT_DRIFT')
        tampered=path/'changed.json'
        broken=read_json(response)
        tampered.write_bytes(canonical({**broken,'packet_sha256':'0'*64}))
        try:
            receive(SimpleNamespace(packet=packet,response=tampered,output=path/'rejected.json'))
        except ValueError as error:
            require(str(error)=='HANDOFF_BINDING','UNEXPECTED_HANDOFF_REFUSAL')
        else:
            raise ValueError('UNBOUND_RESPONSE_ADMITTED')
    for malformed in ('a.denominator','a if t else p','a**t','ceil(a,p)'):
        try:
            programs({**evidence['manual']['construction']['result'],'epoch':malformed})
        except ValueError:
            continue
        raise ValueError('UNSUPPORTED_EXPRESSION_ADMITTED')
    return observed


def verify(args):
    construction=verify_construction()
    published=read_json(STUDY/'COVARIANCE.json')
    covariance=open_result('covariance')
    require(covariance==published['study'] and covariance['confirmation_count']==106
            and covariance['calibration_count']==59 and covariance['observing_authority']=='ABSTAIN',
            'COVARIANCE_STUDY_DRIFT')
    provided=(args.elements,args.older,args.later)
    if any(provided):
        require(all(provided),'ALL_ORIGINAL_FILES_REQUIRED')
        args.sources=STUDY/'SOURCES.json'
        rebuilt=covariance_study.run(args)
        require(canonical(rebuilt)==canonical(published),'ORIGINAL_SOURCE_REPLAY')
    comparison=open_result('timing-audit')
    require(comparison['matched_epochs']==866 and comparison['top_five_checked']==0
            and comparison['operational_authority']=='ABSTAIN','INDEPENDENT_TIMING_SCOPE')
    extra=(args.independent,args.independent_elements)
    if any(extra):
        require(all(provided) and all(extra),'ALL_TIMING_AUDIT_FILES_REQUIRED')
        args.trial=STUDY/'COVARIANCE.json'
        require(canonical(independent_timing.audit(args))==canonical(comparison),'TIMING_AUDIT_REPLAY')
    flow=open_result('hydrology')
    require(flow['days']==28 and flow['daily_rate_sum']==[1075200,1],'FRESH_HYDROLOGY_CONTROL')
    transfer=read_json(STUDY/'HYDROLOGY.json')
    variations={
        'missing':{**transfer,'rows':transfer['rows'][1:]},
        'duplicate':{**transfer,'rows':[*transfer['rows'],transfer['rows'][0]]},
        'wrong_units':{**transfer,'unit':'m3/s'},
        'point_samples':{**transfer,'statistic':'instantaneous'},
    }
    estimated=deepcopy(transfer)
    estimated['rows'][0]['quality']='estimated'
    variations['estimated']=estimated
    refusals={key:integrate(value)['status'] for key,value in variations.items()}
    require(refusals=={'missing':'ABSTAIN_DAY_COVERAGE','duplicate':'ABSTAIN_DAY_COVERAGE',
                      'wrong_units':'ABSTAIN_UNITS_OR_BASIS','point_samples':'ABSTAIN_UNITS_OR_BASIS',
                      'estimated':'ABSTAIN_UNQUALIFIED_RECORD'},'SCIENTIFIC_TRANSFER_SCOPE')
    expect={
        'ephemeris':{'decision':'COVARIANCE_SENSITIVE','epoch':5817,'sigma_s':[175,267],'witness':'paper:T8:L98',
                     'target_limit_s':[110301,500]},
        'endpoint':{'load':256,'witnesses':['e045','e072']},
        'calibration':{'slack':[154525728350382,1892645562643243],'witness':['row-07','row-02']},
    }
    for name,result in expect.items():
        require(open_result(name)['result']==result,'PRIOR_WORKBENCH_REGRESSION:'+name)
    return {'construction_held_accepted':construction,'covariance_confirmed':covariance['confirmation_count'],
            'covariance_verdict':covariance['verdict'],'original_timings_rechecked':all(provided),
            'independent_timing_epochs':comparison['matched_epochs'],'independent_files_rechecked':all(extra),
            'hydrology':flow,'negative_hydrology_controls':refusals,'previous_tools':list(expect)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('elements','older','later','independent','independent-elements'):
        parser.add_argument('--'+name,type=Path)
    print(canonical(verify(parser.parse_args())).decode())
