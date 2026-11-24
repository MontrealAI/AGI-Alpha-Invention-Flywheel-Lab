"""Recompute the cascade qualification from portable evidence and optional originals."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
from math import isfinite, sqrt
from pathlib import Path
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import ZipFile

from cascade import STUDY, batches, conventional, encode, evaluate, model_prompt, run_plan, trial_for, unpack
from cascade_fresh_domain import qualify
from science_substrate import read_json


ARMS = ('direct','ordinary','typed','conventional','withdrawn','completed-typed','completed-ordinary','completed-withdrawn')
DAYS_SECONDS = Decimal(86400)


def require(condition, code):
    if not condition:
        raise ValueError(code)


def unique(rows):
    result = {row['id']:row for row in rows}
    require(len(rows)==len(result),'DUPLICATE_EVENT')
    return result


def event_error(row, source, reference):
    require(row['source_sha256']==source['sha256'],'FITS_WITNESS')
    verdict = row['verdict']
    y, s = row['mid_bjd_tdb'], row['uncertainty_s']
    sigma = float(Decimal(reference['catalogue_uncertainty_days'])*DAYS_SECONDS)
    threshold = min(720,max(90,3*sigma))
    if verdict != 'MEASURED':
        require(verdict.startswith('ABSTAIN') and y is None and s is None,'EXTRACTION_STATUS')
        return {'verdict':verdict,'signed_error_s':None,'threshold_s':round(threshold,6),
                'catalogue_agreement':False,'covered_90':None}
    require(type(y) in (float,int) and type(s) in (float,int) and isfinite(y) and isfinite(s) and s>0
            and source['search_start_bjd_tdb'] < y < source['search_stop_bjd_tdb'], 'EXTRACTION_NUMBERS')
    err = float((Decimal(str(y))-Decimal(reference['catalogue_mid_bjd_tdb']))*DAYS_SECONDS)
    return {'verdict':verdict,'signed_error_s':round(err,6), 'threshold_s':round(threshold,6),
            'catalogue_agreement':s<=600 and abs(err)<=threshold,'covered_90':abs(err)<=1.644853627*sqrt(s*s+sigma*sigma)}


def attribute(cases, case):
    return any(other['sha256']==case['sha256'] and other['target']!=case['target']
               and other['utc_identifier_date']==case['utc_identifier_date'] for other in cases)


def study(cases, references, primary, ordinary):
    require(set(unique(cases))==set(references)==set(primary)==set(ordinary),'EXTRACTION_COHORT')
    rows = []
    for case in cases:
        ident = case['id']
        p,o = primary[ident],ordinary[ident]
        a,b = (event_error(row,case,references[ident]) for row in (p,o))
        conflict = attribute(cases,case)
        delta = None
        both = False
        if a['verdict']==b['verdict']=='MEASURED':
            delta = abs(p['mid_bjd_tdb']-o['mid_bjd_tdb'])*86400
            limit = min(600,max(90,3*(p['uncertainty_s']+o['uncertainty_s'])))
            both = a['catalogue_agreement'] and b['catalogue_agreement'] and delta<=limit and not conflict
        rows.append({'id':ident,'cohort':case['cohort'],'primary':a,'ordinary':b,'attribution_conflict':conflict,
                     'method_separation_s':None if delta is None else round(delta,6),'confirmed':both})
    held = [row for row in rows if row['cohort']=='held']
    development = [row for row in rows if row['cohort']=='development']
    require(len(held)+len(development)==len(rows),'EXTRACTION_COHORT_STATUS')
    results = {'held':len(held),'development':len(development),'held_confirmed':sum(row['confirmed'] for row in held),
               'development_confirmed':sum(row['confirmed'] for row in development),
               'products':len({row['sha256'] for row in cases})}
    for method in ('primary','ordinary'):
        results[method+'_agrees'] = sum(row[method]['catalogue_agreement'] for row in held)
        results[method+'_development_agrees'] = sum(row[method]['catalogue_agreement'] for row in development)
        results[method+'_held_verdicts'] = dict(Counter(row[method]['verdict'] for row in held))
        results[method+'_held_covered_90'] = sum(row[method]['covered_90'] is True for row in held)
        errors = [abs(row[method]['signed_error_s']) for row in held if row[method]['signed_error_s'] is not None]
        results[method+'_held_measured_median_error_s'] = None if not errors else median(errors)
    return results, rows


def independently_expected_tess(source, reference, p, o, conflict):
    status = 'ABSTAIN_ATTRIBUTION' if conflict else 'ABSTAIN_MEASUREMENT'
    row_check = [event_error(row,source,reference) for row in (p,o)]
    if conflict or any(not row['catalogue_agreement'] for row in row_check):
        return {'status':status,'value':None}
    absolute_s = abs(p['mid_bjd_tdb']-o['mid_bjd_tdb'])*86400
    if absolute_s>min(600,max(90,3*(p['uncertainty_s']+o['uncertainty_s']))):
        return {'status':'ABSTAIN_DISAGREEMENT','value':None}
    return {'status':'CONCORDANT','value':{'mid_bjd_tdb':str(Decimal(str(p['mid_bjd_tdb'])).quantize(
        Decimal('.000001'), rounding=ROUND_HALF_EVEN))}}


def score_forecasts(forecasts, references, cases):
    rows = unique(forecasts['events'])
    require(rows.keys()=={row['id'] for row in cases if row['cohort']=='held'},'FORECAST_COHORT')
    summary = {}
    for name in ('released_marginals','weighted_linear','ttv'):
        halfwidths, errors = [], []
        for identifier, row in rows.items():
            forecast = row[name]
            if forecast is None:
                continue
            y = Decimal(references[identifier]['catalogue_mid_bjd_tdb'])
            delta = float((Decimal(str(forecast['mid_bjd_tdb']))-y)*DAYS_SECONDS)
            halfwidths.append(forecast['nominal_90_halfwidth_s'])
            errors.append(delta)
        summary[name] = {'issued':len(errors),'held':len(rows),
                         'covered':sum(abs(e)<=w for e,w in zip(errors,halfwidths,strict=True)),
                         'median_absolute_error_s':round(median(map(abs,errors)),3) if errors else None,
                         'median_window_s':round(2*median(halfwidths),3) if halfwidths else None}
    return summary


def source_timings(path, evidence, cases, references):
    expected = evidence['bindings']['label_archive_sha256']
    require(path.stat().st_size == 983058 and sha256(path.read_bytes()).hexdigest()==expected,'TIMING_ARCHIVE_HASH')
    with ZipFile(path) as archive:
        for case in cases:
            label = references[case['id']]
            name = f'by_planet/{case["target"]}.txt'
            sheet, index = label['witness'].rsplit(':L',1)
            require(sheet==name,'TIMING_ARCHIVE_WITNESS')
            rows = list(csv.reader(archive.read(name).decode().splitlines(), delimiter='\t'))
            require(tuple(value.strip() for value in rows[0])==('Tmid (BJD_TDB)','Tmid unc.','source','ID'),
                    'TIMING_ARCHIVE_COLUMNS')
            require(list(map(str.strip,rows[int(index)-1]))==[label['catalogue_mid_bjd_tdb'],
                    label['catalogue_uncertainty_days'],'space',case['id']], 'TIMING_ARCHIVE_ROW')


def replay_originals(path, cases, primary, ordinary):
    root = Path(__file__).resolve().parent
    manifest = []
    for case in cases:
        name = urlsplit(case['fits_uri']).query.rsplit('/',1)[-1]
        require(name.endswith('_lc.fits') and Path(name).name==name, 'FITS_RESOURCE_NAME')
        file = path/name
        require(file.stat().st_size==case['bytes'] and sha256(file.read_bytes()).hexdigest()==case['sha256'],
                'FITS_RESOURCE_DIGEST')
        manifest.append({**case,'fits':str(file.resolve())})
    with TemporaryDirectory() as temporary:
        folder = Path(temporary)
        inputs, output = folder/'input.json', folder/'ordinary.json'
        inputs.write_text(encode({'events':manifest}))
        first = subprocess.run([sys.executable,str(root/'transit_cascade.py'),str(inputs)],
                               capture_output=True,check=True,text=True)
        subprocess.run([sys.executable,str(root/'transit_ordinary.py'),'--inputs',str(inputs),'--output',str(output)],
                       capture_output=True,check=True,text=True)
        import json
        a,b = unique(json.loads(first.stdout)['events']), unique(read_json(output)['events'])
        for observed,wanted in ((a,primary),(b,ordinary)):
            require(observed.keys()==wanted.keys(),'RAW_FITS_EVENT_IDS')
            for name, row in observed.items():
                pinned = wanted[name]
                require(row['verdict']==pinned['verdict'] and row['source_sha256']==pinned['source_sha256'], 'RAW_FITS_VERDICT')
                if row['verdict']=='MEASURED':
                    require(abs(row['mid_bjd_tdb']-pinned['mid_bjd_tdb'])*86400<1
                            and abs(row['uncertainty_s']-pinned['uncertainty_s'])<2,'RAW_FITS_REPLAY_NUMBERS')
    return len(manifest)


def verify(args):
    root = args.study.parent
    evidence = read_json(args.study)
    witnesses = {}
    for method in ('primary','ordinary'):
        receipt = root/(method.upper()+'.json')
        require(sha256(receipt.read_bytes()).hexdigest()==evidence['bindings'][method+'_receipt_sha256'],'REDUCER_RECEIPT')
        script = Path(__file__).with_name('transit_'+('cascade' if method=='primary' else 'ordinary')+'.py')
        require(sha256(script.read_bytes()).hexdigest()==evidence['bindings'][method+'_script_sha256'],'REDUCER_SOURCE')
        witnesses[method] = unique(read_json(receipt)['events'])
    cases = evidence['tess']['cases']
    sources, references = unique(cases), unique(evidence['tess']['references'])
    if args.labels_zip:
        source_timings(args.labels_zip,evidence,cases,references)
    findings, scores = study(cases,references,**witnesses)
    require(evidence['summary']['tess']==findings and evidence['tess']['scores']==scores,'TESS_SCORE_REPLAY')
    forecast = root/'TTV.json'
    require(sha256(forecast.read_bytes()).hexdigest()==evidence['bindings']['ttv_receipt_sha256'], 'FORECAST_RECEIPT')
    forecast_input = read_json(forecast)
    require(sha256((root/'TTV-INPUT.json').read_bytes()).hexdigest()==forecast_input['sha256']['manifest'], 'FORECAST_INPUT')
    script = Path(__file__).with_name('ttv_diagnostic.py')
    require(sha256(script.read_bytes()).hexdigest()==forecast_input['sha256']['script'],'FORECAST_SCRIPT')
    prediction = score_forecasts(forecast_input,references,cases)
    require(prediction==evidence['forecast'],'FORECAST_REPLAY')
    overlap = read_json(root/'POST-REVEAL.json')
    overlap_registration = read_json(root/'POST-REVEAL-INPUT.json')
    require(overlap['fits_sha256']==overlap_registration['product_sha256']
            and overlap['fits_sha256'] in {row['sha256'] for row in cases}
            and overlap['reducer_sha256']==evidence['bindings']['primary_script_sha256']
            and overlap_registration['primary_output_sha256']==evidence['bindings']['primary_receipt_sha256'],
            'POST_REVEAL_WITNESS')
    raw = replay_originals(args.fits_dir,cases,**witnesses) if args.fits_dir else 0
    fixture = root/'FRESH-DOMAIN.json'
    fresh = qualify(fixture,source_html=args.oni_html)
    require(fresh['status']=='QUALIFIED_HISTORICAL_REPLAY' and fresh['operational_decision']=='ABSTAIN_SCOPE',
            'NOAA_REPLAY')
    stratum = evidence['composition']
    for job in stratum['jobs']:
        if job['family']=='tess' and job['permission']=='public-research/read' and job['basis']=='BJD_TDB':
            case = sources[job['case_id']]
            p,o = (witnesses[name][case['id']] for name in ('primary','ordinary'))
            fields = ('verdict','mid_bjd_tdb','uncertainty_s','source_sha256')
            asserted = [{'method':method, **{key:record[key] for key in fields}}
                        for method,record in (('primary',p),('ordinary',o))]
            pair = {'pair':asserted,'date_window_bjd_tdb':[case['search_start_bjd_tdb'],case['search_stop_bjd_tdb']],
                    'attribution_conflict':attribute(cases,case)}
            require(stratum['tess_records'][case['id']]==pair and all(job[key]==value for key,value in pair.items()),
                    'COMPOSED_REDUCER_BINDING')
            require(stratum['expected'][job['id']]==independently_expected_tess(case,references[case['id']],p,o,
                     attribute(cases,case)),'COMPOSED_EXTERNAL_TESS_SCORER')
    compared = {'jobs':len(stratum['jobs'])}
    for arm in ARMS:
        trial_arm = trial_for(arm)
        trial = stratum['trials'].get(trial_arm,{})
        outcome = evaluate(stratum,arm,trial.get('draft'),fixture)
        compared[arm] = outcome['accepted']
        for row in outcome['rows']:
            row['calls'] = [{key:value for key,value in call.items() if key!='elapsed_ms'} for call in row['calls']]
        require(outcome==stratum['outcomes'][arm], 'COMPOSITION_REPLAY:'+arm)
        if trial:
            groups = batches(stratum['jobs'])
            for group, receipt in zip(groups,trial['batches'],strict=True):
                require(receipt['prompt_sha256']==sha256(model_prompt(group,trial_arm).encode()).hexdigest(),
                        'MODEL_PROMPT_BINDING:'+arm)
                require(receipt['draft']=={key:unpack(value,trial_arm) for key,value in receipt['raw'].items()},
                        'MODEL_RESPONSE_BINDING:'+arm)
            require(trial['draft']=={key:value for receipt in trial['batches'] for key,value in receipt['draft'].items()},
                    'MODEL_DRAFT_BINDING:'+arm)
    require(compared==evidence['summary']['composition'],'COMPOSITION_SCORE_REPLAY')
    job = stratum['jobs'][0]
    for plan in (('abstain','compute_window'),('classify_oni','check_tess'),('check_tess','compute_window')):
        decision,calls = run_plan(job,plan,stratum,oni_fixture=fixture)
        require(decision['status']=='ABSTAIN_PLAN' and not calls, 'ROUTE_ADMISSION')
    denied = {**job,'permission':'withheld','pair':'PRIVATE_VALUE_MARKER'}
    require('PRIVATE_VALUE_MARKER' not in model_prompt([denied],'typed'),'MODEL_PERMISSION_BOUNDARY')
    decision,calls = run_plan(denied,conventional(job),stratum,oni_fixture=fixture)
    require(decision['status']=='ABSTAIN_PERMISSION' and not calls,'TOOL_PERMISSION_BOUNDARY')
    return {'tess':findings,'forecast':prediction,'composition':compared,'raw_tess_events_replayed':raw,
            'raw_catalogue_rows_replayed':len(cases) if args.labels_zip else 0,
            'historical_oni_seasons':fresh['seasons_compared'],'oni_source':fresh['source_verification'],
            'independent_authority':'HISTORICAL_PUBLIC_REPLAY','observing_decision':'ABSTAIN'}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=STUDY/'RESULTS.json')
    parser.add_argument('--fits-dir',type=Path)
    parser.add_argument('--oni-html',type=Path)
    parser.add_argument('--labels-zip',type=Path)
    print(encode(verify(parser.parse_args())))
