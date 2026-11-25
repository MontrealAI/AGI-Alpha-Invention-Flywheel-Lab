"""Verify bound research receipts and independently replay industrial decisions."""

import argparse
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from bridge.instruments import evaluate as evaluate_instrument
from evidence_control import compare
from evidence_truth import STUDY, evaluate, valid
from science_substrate import canonical, read_json


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def refusals(study):
    def rejected(name, data, reason):
        try:
            evaluate(data)
        except ValueError as error:
            valid(str(error)==reason, 'UNEXPECTED_REFUSAL:'+name)
        else:
            raise ValueError('UNACCEPTED_BOUNDARY:'+name)

    sample = deepcopy(study)
    sample['sources'].append(sample['sources'][0])
    rejected('duplicate-source',sample,'DUPLICATE_SOURCE')
    sample = deepcopy(study)
    sample['cases'][0]['as_of']='2026-02-30T23:59:59Z'
    try:
        evaluate(sample)
    except ValueError:
        pass
    else:
        raise ValueError('INVALID_UTC_DATE_ACCEPTED')
    sample = deepcopy(study)
    sample['cases'][0]['records'][0]['verified_by']='2000-01-01T00:00:00Z'
    rejected('lookahead-drift',sample,'UNBOUND_PRODUCT_DATE')
    sample = deepcopy(study)
    sample['sources'][0]['url']='http://example.invalid/source'
    rejected('unqualified-url',sample,'PUBLIC_SOURCE_URI')
    return 4


def lineage_contract(study):
    source=study['sources'][0]['id']
    when=study['sources'][0]['published_at']
    context={'subject':'control-subject','quantity':'exposure','unit':'second','basis':'elapsed'}
    first,second='observation:a','observation:b'
    a = {**context,'id':'physical-a','source':source,'lineage':[first],'parents':[],'interval':['1','1']}
    b = {**a,'id':'physical-b','lineage':[second]}
    aggregate = {**a,'id':'aggregate','lineage':[],'parents':[a['id'],b['id']]}
    case = {**context,'id':'lineage-control','kind':'measurement','as_of':when,'tolerance':'0',
            'origins':{first:'physical',second:'physical'},'records':[a,b,aggregate]}
    document = {**study,'cases':[case]}
    result = evaluate(document)['lineage-control']
    valid(result['verdict']=='PHYSICAL_AGREEMENT' and result['physical_pairs']==[['physical-a','physical-b']]
          and len(result['shared_pairs'])==2, 'AGGREGATE_ERASED_VALID_INDEPENDENCE')
    conflict = {**aggregate,'interval':['4','4']}
    actual = evaluate({**document,'cases':[{**case,'records':[a,b,conflict]}]})['lineage-control']
    valid(actual['verdict']=='AMBIGUOUS_CONFLICT' and len(actual['conflicts'])==2, 'CONFLICT_SUPPRESSED')
    dependent = {**b,'lineage':[first]}
    actual = evaluate({**document,'cases':[{**case,'records':[a,dependent]}]})['lineage-control']
    valid(actual['verdict']=='SHARED_UPSTREAM', 'REUSED_OBSERVATION_COUNTED_AS_INDEPENDENT')
    no_lineage = {**b,'lineage':[]}
    actual = evaluate({**document,'cases':[{**case,'records':[a,no_lineage,aggregate]}]})['lineage-control']
    valid(actual['verdict']=='INDEPENDENCE_UNESTABLISHED' and actual['lineage']['aggregate']==[],
          'UNKNOWN_LINEAGE_ADVANCED')
    circular = {**aggregate,'parents':['aggregate']}
    try:
        evaluate({**document,'cases':[{**case,'records':[a,b,circular]}]})
    except ValueError as error:
        valid(str(error)=='LINEAGE_CYCLE_OR_DEPTH','EXPECTED_CYCLE_REFUSAL')
    else:
        raise ValueError('CYCLE_ADMITTED')
    return 5


def harness_replay(study, instrument):
    source_times={row['id']:row['published_at'] for row in study['sources']}
    stage_roles={'public_offer':('manufacturer_offer','authorized_supplier_offer'),
                 'software_support':('first_party_release',),'machine_operation':('observed_machine_run',),
                 'fulfilled_order':('observed_fulfillment',)}
    records_checked, mismatches=0,[]
    for case in study['cases']:
        if case['kind']!='product_stage':
            continue
        for row in case['records']:
            identity=all(row['scope'].get(k)==v for k,v in case['scope'].items())
            source,observed,deadline=(int(datetime.fromisoformat(value).timestamp())
                                      for value in (source_times[row['source']],row['verified_by'],case['as_of']))
            query={'published':source,'observed':observed,'cutoff':deadline,'identity':identity,
                   'stage':case['stage'],'role':row['role']}
            actual=evaluate_instrument(instrument,query)['output']['eligible']
            if actual is not (source<=observed<=deadline and identity and row['role'] in stage_roles[case['stage']]):
                mismatches.append([case['id'],row['id']])
            records_checked+=1
    return {'rows':records_checked,'mismatches':mismatches}


def check_bambu(path, witness):
    valid(digest(path)==witness['source_sha256'],'BAMBU_RULE_SOURCE')
    content=read_json(path)
    models={model:sorted(value) for model,value in content['printer_models'].items()}
    valid(content['version']==witness['rules_version'] and models==witness['models'],'BAMBU_RULES_REPLAY')
    return len(models)


def verify(folder, bambu_rules=None):
    report=read_json(folder/'FACTORY.json')
    for name,want in report['bindings']['inputs'].items():
        valid(Path(name).name==name and digest(folder/name)==want,'FACTORY_INPUT_BINDING:'+name)
    code=Path(__file__).resolve().parent
    for name,want in report['bindings']['code'].items():
        valid(Path(name).name==name and digest(code/name)==want,'FACTORY_CODE_BINDING:'+name)
    study=read_json(folder/'EVIDENCE.json')
    results=evaluate(study)
    valid(results==report['results'],'FACTORY_OUTCOME_REPLAY')
    projected={item['id']:item for item in compare(study)}
    valid(projected=={item['id']:results[item['id']] for item in study['cases'] if item['kind']=='product_stage'},
          'INDEPENDENT_SQL_COMPARISON')
    valid(projected==report['industry_control'],'FROZEN_CONTROL_REPLAY')
    historical=report['summary']['industry']
    valid({name:record['verdict'] for name,record in historical.items()}=={
        'prusa_offer':'DOCUMENTED_BY_CUTOFF','bambu_software':'DOCUMENTED_BY_CUTOFF','bambu_machine':'ABSTAIN_UNESTABLISHED'},
        'INDUSTRIAL_RELEASE_SCOPE')
    bound_sources={row['id']:row['url'] for row in study['sources']}
    for name,summary in historical.items():
        verified=projected[name]
        valid(summary=={'verdict':verified['verdict'],'first_verified_by':verified['first_verified_by'],
                        'source_url':bound_sources.get(verified['source'])},'PUBLISHED_PRODUCT_PROJECTION')
    valid(all(not record['onset_established'] and not record['continuity_established']
              for record in projected.values()),'UNSUPPORTED_PRODUCT_PROMOTION')
    working=report['harness']['instrument']
    check=harness_replay(study,working)
    valid(check==report['harness']['execution'] and check['mismatches']==[],'HARNESS_INSTRUMENT_REPLAY')
    transit=read_json(folder/'TRANSIT.json')
    valid(transit['summary']==report['summary']['transit'] and transit['forecast_authority']=='ABSTAIN'
          and report['summary']['transit']['forecast_verdict']=='ABSTAIN',
          'FORECAST_SCOPE')
    ground=results[report['raw_ground_reconciliation']]
    valid(ground['verdict']=='PHYSICAL_AGREEMENT' and ground['physical_pairs']==[['ground-only-lcogt','joint-tess']],
          'GROUND_RECONCILIATION')
    valid(results['dawn-release-revision']['verdict']=='SHARED_UPSTREAM'
          and 'SUPERSEDED_RELEASE' in results['dawn-release-revision']['excluded'].values()
          and results['fiona-local-pressure-instruments']['verdict']=='INSUFFICIENT_RECORDS'
          and not results['fiona-local-pressure-instruments']['physical_pairs'], 'NATIVE_SOURCE_REVISIONS')
    valid(all(entry['admission'] in ('HISTORICAL_PUBLIC_REPLAY','EXPERIMENTAL') for entry in report['registry'].values()),
          'AUTHORITY_PROMOTION')
    denial=refusals(study)+lineage_contract(study)
    return {'industry_cases':len(projected),'positive_industry_cases':sum(
        row['verdict']=='DOCUMENTED_BY_CUTOFF' for row in projected.values()),'independent_sql_agreement':len(projected),
        'measurement_cases':len(results)-len(projected),'scope_and_lineage_controls':denial,
        'harness':check,'transit':report['summary']['transit'],'hurricane':report['summary']['hurricane'],
        'raw_slicer_rule_models_replayed':check_bambu(bambu_rules,report['bambu_rule_witness']) if bambu_rules else 0,
        'promotion_authority':'PUBLIC_HISTORICAL_EVIDENCE'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study-directory',type=Path,default=STUDY)
    parser.add_argument('--bambu-rules',type=Path,help='Replay an original checksum-matching source rules file')
    args=parser.parse_args()
    print(canonical(verify(args.study_directory,args.bambu_rules)).decode())
