"""Register one new experiment from exact, attributed MLCommons measurements."""

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from route_environment import independent


SOURCE = '522542e525e96556285560e65e4443c85cc7b709'
ORIGINAL = 'products/frontier-omega-alpha/research/possibility_observatory/endpoint_study/observations.json'
UPSTREAM = 'ce3226048090ba13e5d2369b582126f8440ba3485926f91ed81396fe15acada0'
CONTRACT = '''One input is a single already scoped workload. Each row is
[evidence_id, system_id, actually tested concurrency, least supported throughput in millitokens/s/user,
conservative P90 time to first token in microseconds, verified bool]. rate_min and latency_max use those same
integer units. Require verified=true, both metrics present, rate >= rate_min and latency <= latency_max.
Select the highest-load qualifying row per distinct system, breaking exact load ties by ascending evidence ID.
Take the system_count best such rows, ordered by descending load then ascending evidence ID.
Output exactly {"load": minimum load of the selected rows, "witnesses": [selected evidence IDs in that order]}.
If fewer distinct systems qualify, output {"load": null, "witnesses": []}. Study numerical screening only.
Do not extrapolate to other loads, assume deployability, mix workloads or treat matching IDs as measurements.'''

G4 = ('GPT-OSS 120B', 'perf')
KIMI = ('kimi-k3', 'agentic_combined')
QWEN = ('Qwen3.6 35B-A3B', 'agentic_coding')
FLASH = ('deepseek-v4_1-flash', 'mlperf_agentic_inference_dataset')
R1 = ('DeepSeek-R1', 'dsr1-perf')
SCOPES = (G4, KIMI, QWEN, FLASH, R1)
WEIGHTS = {
    'qwen3-4b-instruct-2507-q4_k_m': '2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e',
    'qwen3-8b-q4-k-m': 'd98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785',
}


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n').encode()


def save(path, value):
    raw = encoded(value)
    with path.open('xb') as output:
        output.write(raw)
    return sha256(raw).hexdigest()


def scaled(value, round_to):
    return int((Decimal(value)*1000).to_integral_value(rounding=round_to)) if value is not None else None


def rows(data):
    groups = {scope: [] for scope in SCOPES}
    origin = {}
    names = {name: 's%02d' % i for i, name in enumerate(sorted({r['system'] for r in data}),1)}
    for i, record in enumerate(sorted(data, key=lambda item: item['id']),1):
        facts = record['facts']
        scope = facts['model'], facts['dataset']
        if scope not in groups:
            continue
        evidence = 'e%03d' % i
        published = record['published']
        verified = bool(published and published <= '2026-11-23' and facts['submission']=='official'
                        and facts['run']=='valid-online')
        groups[scope].append([evidence, names[record['system']], record['load'],
                             scaled(record['metric'],ROUND_FLOOR), scaled(record['upper_metric'],ROUND_CEILING),verified])
        origin[evidence] = {'source_id': record['id'], 'system': record['system'], 'published': published, 'scope': scope}
    return groups, origin


def case(case_id, data, requirements):
    count, rate, latency = requirements
    problem = {'rate_min':rate,'latency_max':latency,'system_count':count,'rows':data}
    return {'id':case_id,'input':problem,'expected':independent(problem)}


def compact_scenario(data):
    """Keep a few real worked examples, covering multiple systems and misses."""
    systems = {}
    for row in data:
        systems.setdefault(row[1], []).append(row)
    sample = []
    for group in sorted(systems.values(),key=lambda rows:(not any(row[-1] for row in rows),rows[0][1])):
        good = sorted((row for row in group if row[-1] and row[3] is not None and row[4] is not None),
                      key=lambda row: (row[4],-row[2],row[0]))
        if good:
            sample.extend(good[:1]+(good[-1:] if len(good)>1 else []))
    return sample[:8]


def create(root):
    root.mkdir(parents=True,exist_ok=False)
    raw = subprocess.check_output(['git','cat-file','blob', f'{SOURCE}:{ORIGINAL}'])
    data = json.loads(raw)
    if data['source_sha256'] != UPSTREAM or len(data['rows']) != 365:
        raise ValueError('PINNED_SOURCE')
    groups, origin = rows(data['rows'])
    dev = [case('examples-a',compact_scenario(groups[QWEN]),(2,100_000,450_000)),
           case('examples-b',compact_scenario(groups[G4]),(2,100_000,500_000))]
    hold = [case('deployment-%02d'%i,groups[scope],rules) for i,(scope,rules) in enumerate((
        (G4,(1,100_000,500_000)),(G4,(2,100_000,500_000)),
        (R1,(1,110_000,500_000)),(R1,(2,70_000,1_200_000)),
        (QWEN,(2,90_000,390_000)),(QWEN,(3,55_000,470_000)),(QWEN,(3,205_000,120_000)),
        (KIMI,(2,45_000,3_500_000)),(KIMI,(4,10_000,17_000_000)),(KIMI,(3,69_500,500_000)),
        (FLASH,(2,110_000,480_000)),(FLASH,(3,71_000,1_400_000)),
    ),1)]
    dev_digest = save(root/'development.json',dev)
    held_digest = save(root/'confirmation.json',hold)
    provenance = {'upstream':data['source'],'upstream_sha256': UPSTREAM,'raw_sha256':sha256(raw).hexdigest(),
                  'source_commit':SOURCE,'source_path':ORIGINAL,'rows':len(data['rows']),
                  'scope_ids': {case['id']:origin[case['input']['rows'][0][0]]['scope'] for case in dev+hold},
                  'evidence':origin,'rights':'Public benchmark facts, attributed to MLCommons and the relevant submitters.'}
    save(root/'provenance.json',provenance)
    save(root/'trial.json',hold[4]['input'])
    save(root/'registration.json',{'schema':'frontier/amplification-registration-v1',
                                  'objective':'Adapt the Endpoint Lab to a distinct-system evidence contract',
                                  'contract':CONTRACT,'development_sha256':dev_digest,'confirmation_sha256':held_digest,
                                  'boundaries':'Single administrative host. Confirmation absent from constructor input directory.',
                                  'materiality':'An amplified arm must beat both same-model controls by >=2 of 12 with zero '
                                      'additional false-positive witness plans. A single exemplar can warrant follow-up only.',
                                  'case_selection':'Six workload families are not assumed; five fixed model/workload groups. '
                                      'Twelve authored contract queries over underlying actual public benchmark measurements.',
                                  'release_acceptance':'All 12 independently matched and no new authority. Operational adoption abstains.',
                                  'design_tokens':850,'design_attempts':2,'weights':WEIGHTS,
                                  'comparisons': {key:{'arms':['direct','harness','amplified'],
                                                       'attempts':2,'request_tokens':850} for key in WEIGHTS},
                                  'execution_order':{'qwen3-8b-q4-k-m':['design','harness','amplified','direct'],
                                      'qwen3-4b-instruct-2507-q4_k_m':['amplified','direct','harness']}})


if __name__ == '__main__':
    create(Path(sys.argv[1]))
