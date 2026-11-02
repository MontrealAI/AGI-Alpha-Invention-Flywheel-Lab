"""Registered finite technical probes and matched established-method controls."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time
import numpy as np
from .kernel import Infeasible,solve
from .verify import digest,verify


def candidate_probes():
    # These intentionally tiny probes test one stated prerequisite, not markets.
    measurement=np.array([[1,1]],dtype=float)
    manufacturing_paths={'milling_only':{'milled'},'heat_only':{'heat-treated'},'joined_process':{'milled','heat-treated'}}
    return [
      {'candidate':'pooled-flexibility-contract','kind':'exact-dispatch-probe','test':'100 kWh derated event; four individually 40 kWh profiles; frozen full dispatch follows','status':'EXECUTE_REGISTERED_DISPATCH'},
      {'candidate':'retrospective-measurement-identifiability','kind':'inverse-prerequisite-probe','unknowns':2,'independent_measurements':int(np.linalg.matrix_rank(measurement)),'indistinguishable_vectors':[[1,0],[0,1]],'same_observation':True,'status':'HOLD_UNIDENTIFIABLE_WITHOUT_NEW_OBSERVATION','limitation':'Toy rank test does not evaluate ESA products or prove impossibility of historical measurement.'},
      {'candidate':'complementary-manufacturing-process','kind':'finite-interface-feasibility-probe','required':['heat-treated','milled'],'single_provider_feasible':any({'milled','heat-treated'}<=v for k,v in manufacturing_paths.items() if k!='joined_process'),'joined_process_feasible':{'milled','heat-treated'}<=manufacturing_paths['joined_process'],'status':'FEASIBLE_EXISTING_COORDINATION','limitation':'Set interface test has no machine qualification, tolerances, traceability or price evidence; active industrial-network owner preserved.'}
    ]


def run(output):
    root=Path(__file__).resolve().parents[1]
    registration=json.loads((root/'flexibility063/REGISTRATION.json').read_text())
    profiles=json.loads((root/'flexibility063/profiles.json').read_text())
    output=Path(output).resolve()
    if output.exists(): raise ValueError('NEW_TECHNICAL_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    report={'schema':'flexibility063/technical-experiment/v1','source_files_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('flexibility063/kernel.py','flexibility063/verify.py','flexibility063/experiment.py')},'registration_sha256':digest(registration),'profiles_sha256':digest(profiles),'scope':'SYNTHETIC_COMPUTATIONAL_EVIDENCE_NOT_PHYSICAL_OPERATION','candidate_probes':candidate_probes(),'profiles':[],'direct_frontier_ai':'NOT_EXECUTED_NO_SEPARATELY_BILLABLE_API_AUTHORITY','actual_model_host_billing':'UNKNOWN','algorithmic_superiority':'NOT_ESTABLISHED','physical_or_new_industry_enablement':'NOT_ESTABLISHED'}
    for request in profiles:
        row={'id':request['id'],'request_sha256':digest(request),'controls':{}}
        for mode in ('individual','conventional','pooled'):
            cpu=resource.getrusage(resource.RUSAGE_SELF);started=time.monotonic()
            try:
                artifact=solve(request,mode)
                acceptance=verify(request,artifact)
                (output/(request['id']+'-'+mode+'.json')).write_text(json.dumps(artifact,indent=2)+'\n')
                result={'feasible':acceptance['accepted'],'receipt':acceptance,'participant_payment_microUSD':sum(artifact['payments_microUSD'].values()),'artifact_sha256':digest(artifact)}
            except Infeasible as error:
                result={'feasible':False,'reason':str(error)}
            after=resource.getrusage(resource.RUSAGE_SELF)
            result.update(wall_seconds=time.monotonic()-started,cpu_seconds=after.ru_utime+after.ru_stime-cpu.ru_utime-cpu.ru_stime)
            row['controls'][mode]=result
        row['ordinary_tie']=row['controls']['conventional'].get('participant_payment_microUSD')==row['controls']['pooled'].get('participant_payment_microUSD')
        report['profiles'].append(row)
    successor=profiles[-1]
    fresh=solve(successor,'conventional');inherited=solve(successor,'pooled')
    report['successor']={'fresh_request_id':successor['id'],'equal_resource_ordinary_may_rebuild':True,'ordinary_accepted':verify(successor,fresh)['accepted'],'inherited_accepted':verify(successor,inherited)['accepted'],'payment_delta_microUSD':sum(fresh['payments_microUSD'].values())-sum(inherited['payments_microUSD'].values()),'retained_advantage':'NOT_ESTABLISHED','construction_cost_treatment':'Native economics reports construction; neither arm is credited a proprietary algorithm.'}
    (output/'TECHNICAL.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();report=run(args.output)
    print(json.dumps({'output':str(args.output),'profiles':len(report['profiles']),'ordinary_ties':sum(r['ordinary_tie'] for r in report['profiles']),'successor':report['successor']},sort_keys=True))


if __name__=='__main__':main()
