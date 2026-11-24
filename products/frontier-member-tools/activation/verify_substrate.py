"""Verify the source-bound science workbench and its distributed evidence."""

import argparse
from collections import Counter
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from science_reference import verified
from science_substrate import calculate, canonical, fingerprint, problem, read_json, review, source_records
from science_workbench import LABS, replay


ROOT = Path(__file__).resolve().parent
STUDY = ROOT/'study/substrate'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def verify_sources(paths, surveys):
    total = 0
    for source, path in paths.items():
        if path is None:
            continue
        with path.open('rb') as handle:
            raw = handle.read(2_000_001)
        require(len(raw)<=2_000_000, 'PUBLIC_SOURCE_SIZE')
        rows = source_records(raw, source)
        for recorded in surveys:
            if recorded['source'] != source:
                continue
            anchor = recorded['anchor_bjd_tdb']
            require(review(raw, source, anchor)==recorded, 'SOURCE_SURVEY_REPLAY')
            for target, witness, values in rows:
                case = problem(target, witness, 'BJD_TDB', anchor, values)
                require(verified(case)==calculate(case), 'SOURCE_INDEPENDENT_REPLAY')
                total += 1
    return total


def launch(*arguments, check=True):
    return subprocess.run((sys.executable, str(ROOT/'substrate_study.py'), *map(str, arguments)),
                          cwd=ROOT, capture_output=True, check=check)


def verify_handoff(run_native):
    packet_path = STUDY/'MANUAL-PACKET.json'
    response_path = STUDY/'MANUAL-RESPONSE.json'
    packet = read_json(packet_path)
    packet_hash = packet.pop('packet_sha256')
    require(packet_hash==fingerprint(packet) and packet['development_sha256']==digest(STUDY/'DEVELOPMENT.json'),
            'MANUAL_PACKET_BINDING')
    with TemporaryDirectory() as directory:
        scratch = Path(directory)
        candidate = scratch/'candidate.json'
        launch('import','--packet',packet_path,'--response',response_path,'--output',candidate)
        require(digest(candidate)==digest(STUDY/'manual-candidate.json'), 'MANUAL_CANDIDATE_IDENTITY')
        tampered = scratch/'tampered.json'
        response = read_json(response_path)
        tampered.write_bytes(canonical({**response,'packet_sha256':'0'*64}))
        refused = launch('import','--packet',packet_path,'--response',tampered,'--output',scratch/'bad.json',check=False)
        require(refused.returncode!=0 and b'HANDOFF_BINDING' in refused.stderr
                and not (scratch/'bad.json').exists(), 'ALTERED_HANDOFF_ACCEPTED')
        if not run_native:
            return {'packet_sha256':packet_hash,'native_accepted':None, 'tampered_binding_refused':True}
        trial = launch('evaluate','--candidate',candidate,'--confirmation',STUDY/'CONFIRMATION.json','--arm','direct')
        trial_path = scratch/'trial.json'
        trial_path.write_bytes(trial.stdout)
        result = read_json(trial_path)
        require(result['outcomes']=={'ACCEPT':28} and result['unsupported_decisions']==0,'MANUAL_CONFIRMATION')
        return {'packet_sha256':packet_hash,'native_accepted':28,'tampered_binding_refused':True}


def verify(args):
    binding = read_json(STUDY/'BINDINGS.json')
    for member in ('REGISTRATION','DEVELOPMENT','CONFIRMATION','SURVEYS'):
        require(digest(STUDY/(member+'.json'))==binding[member.lower()+'_sha256'], 'EVIDENCE_DIGEST_'+member)
    development, confirmed = [read_json(STUDY/(name+'.json')) for name in ('DEVELOPMENT','CONFIRMATION')]
    require(len(development)==4 and Counter(item['origin'] for item in confirmed)==binding['confirmation_counts'],
            'CASE_PARTITIONS')
    require(len({item['input']['target'] for item in development+confirmed})==len(development+confirmed),
            'CASE_ID_OVERLAP')
    for item in development+confirmed:
        require(calculate(item['input'])==verified(item['input'])==item['expected'],'DUAL_REFERENCE_REPLAY')
    surveys = read_json(STUDY/'SURVEYS.json')
    require(len(surveys)==4 and all(sum(row['decisions'].values())==row['rows']==binding['rows'][row['source']]
            for row in surveys), 'CENSUS_SCOPE')
    replayed = {name:replay(name,read_json(ROOT/lab['file']))['result'] for name,lab in LABS.items()}
    require(replayed['ephemeris']=={
        'decision':'COVARIANCE_SENSITIVE','epoch':5817,'sigma_s':[175,267],'target_limit_s':[110301,500],
        'witness':'paper:T8:L98'}, 'EPHEMERIS_WITNESS')
    require(replayed['endpoint']=={'load':256,'witnesses':['e045','e072']}, 'ENDPOINT_REGRESSION')
    require(replayed['calibration']=={'slack':[154525728350382,1892645562643243],
        'witness':['row-07','row-02']}, 'CALIBRATION_REGRESSION')
    handoff = verify_handoff(args.native)
    return {'checked_cases':len(development)+len(confirmed),'sample':replayed['ephemeris'],
            'endpoint':replayed['endpoint'],'calibration':replayed['calibration'], 'manual_handoff':handoff,
            'reported_source_checks':sum(row['rows'] for row in surveys),
            'reexecuted_source_checks':verify_sources({'paper':args.paper,'archive':args.archive},surveys)}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', action='store_true',help='also exercise the manual candidate in the isolated Linux worker')
    parser.add_argument('--paper', type=Path, help='original pinned publication table')
    parser.add_argument('--archive', type=Path, help='original pinned JSON database snapshot')
    started = perf_counter_ns()
    result = verify(parser.parse_args())
    print(canonical({**result, 'work_ns':perf_counter_ns()-started}).decode())
