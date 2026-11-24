"""Create public-input development and independent confirmation cohorts."""

import argparse
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import random
import secrets
from zipfile import ZipFile

ORIGIN = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/'
BASE = '162ac807c6a7302fa8b4fd6fa1a03ff786fd1f41'
MODEL = 'qwen3-8b-q4-k-m'
WEIGHTS = 'd98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785'
SMALL_MODEL = 'qwen3-4b-instruct-2507-q4_k_m'
SMALL_WEIGHTS = '2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e'
RUNTIME = '909eef25cd53e6601c8a07c866d8dbb2983e74177088d55182137a8fb8255d62'

MISSIONS = {
    'editions': {
        'id':'editions',
        'goal':'Find the effective public evidence edition per Atlas subject so a member never acts on a superseded assertion.',
        'contract':('Each case has one cutoff. Eligible editions have verified=1, held=0 and stamp <= cutoff. '
                    'Return at most one row per subject, honoring the latest eligible stamp. Break a timestamp tie '
                    'using larger revision; break any remaining tie using lexicographically smaller edition. '
                    'Omit subjects without a qualifying edition. A negative decision is still a decision.'),
        'tables':{'editions':{'subject':'TEXT','edition':'TEXT','stamp':'TEXT','revision':'INTEGER','verified':'INTEGER',
                             'held':'INTEGER','decision':'TEXT'}, 'cutoff':{'stamp':'TEXT'}},
        'output':'subject, edition, decision (in that column order)',
    },
    'endpoint': {
        'id':'endpoint',
        'goal':'Make a defensible capacity selection from measured endpoint results for each contracted workload.',
        'contract':('Per workload, use only published trials on or before its cutoff, with rate >= its floor '
                    'and lag <= its ceiling. Fields can be NULL and an incomplete trial is ineligible. Select the '
                    'highest tested load. If two qualifying trials tie on load, prefer lower lag, then smaller '
                    'trial ID lexicographically. Omit workloads without a qualifying trial.'),
        'tables':{'trial':{'workload':'TEXT','id':'TEXT','load':'INTEGER','rate':'INTEGER','lag':'INTEGER','stamp':'TEXT'},
                  'limits':{'workload':'TEXT','floor':'INTEGER','ceiling':'INTEGER','cutoff':'TEXT'}},
        'output':'workload, id, load (in that column order)',
    },
    'impact': {
        'id':'impact',
        'goal':'Identify which qualification artifacts must be rechecked when an input changes in the Foundry release.',
        'contract':('One edge links a prerequisite input to a downstream check or deliverable. Include known '
                    'changed items themselves and every known item reachable downstream. Cycles, duplicated links, '
                    'several initial changes and orphaned edges can exist. Never traverse an edge through an unknown '
                    'item. Return each affected known name exactly once. No changed items means empty output.'),
        'tables':{'node':{'name':'TEXT'}, 'edge':{'input':'TEXT','downstream':'TEXT'}, 'changed':{'name':'TEXT'}},
        'output':'name (one column)',
    },
}

# Strong conventional implementations exercise the same endpoint contract.
BASELINES = {
    'editions': '''WITH ranked AS (
        SELECT e.*, row_number() OVER (PARTITION BY subject ORDER BY e.stamp DESC,revision DESC,edition ASC) AS pos
        FROM editions AS e CROSS JOIN cutoff AS c WHERE verified=1 AND held=0 AND e.stamp<=c.stamp)
        SELECT subject,edition,decision FROM ranked WHERE pos=1''',
    'endpoint': '''WITH ranked AS (
        SELECT t.*, row_number() OVER (PARTITION BY t.workload ORDER BY load DESC,lag,id) AS pos
        FROM trial AS t JOIN limits AS l ON t.workload=l.workload
        WHERE rate>=floor AND lag<=ceiling AND stamp<=cutoff AND load IS NOT NULL)
        SELECT workload,id,load FROM ranked WHERE pos=1''',
    'impact': '''WITH RECURSIVE affected(name) AS (
        SELECT node.name FROM node JOIN changed USING (name) UNION
        SELECT e.downstream FROM affected AS a JOIN edge AS e ON a.name=e.input
        JOIN node AS n ON n.name=e.downstream)
        SELECT name FROM affected''',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def save(file, value):
    with file.open('xb') as handle:
        handle.write(canonical(value) + b'\n')


def expected(name, data):
    if name == 'editions':
        last = {}
        for row in data['editions']:
            if row['verified'] == 1 and row['held'] == 0 and row['stamp'] <= data['cutoff'][0]['stamp']:
                subject = row['subject']
                candidate = (row['stamp'], row['revision'])
                current = last.get(subject)
                if (current is None or candidate > (current['stamp'],current['revision']) or
                        (candidate == (current['stamp'],current['revision']) and row['edition'] < current['edition'])):
                    last[subject] = row
        return [[subject, row['edition'],row['decision']] for subject,row in sorted(last.items())]
    if name == 'endpoint':
        results = []
        for limit in data['limits']:
            rows = [r for r in data['trial'] if r['workload'] == limit['workload'] and
                    None not in (r['stamp'],r['rate'],r['lag'],r['load']) and r['stamp'] <= limit['cutoff'] and
                    r['rate'] >= limit['floor'] and r['lag'] <= limit['ceiling']]
            if rows:
                pick = min(rows, key=lambda r:(-r['load'],r['lag'],r['id']))
                results.append([pick['workload'],pick['id'],pick['load']])
        return sorted(results)
    nodes = {r['name'] for r in data['node']}
    found = {r['name'] for r in data['changed']} & nodes
    while True:
        reach = found | {e['downstream'] for e in data['edge'] if e['input'] in found and e['downstream'] in nodes}
        if found == reach:
            return [[x] for x in sorted(found)]
        found = reach


def case(name, ident, family, data):
    return {'id':ident,'family':family,'input':data,'expected':expected(name, data)}


def graph(nodes, edges, starts):
    return {'node':[{'name':n} for n in nodes], 'edge':[{'input':a,'downstream':b} for a,b in edges],
            'changed':[{'name':n} for n in starts]}


def control(name, rng, suffix):
    first, second = f'a{suffix}', f'b{suffix}'
    load, rate, lag = rng.randint(12,50), rng.randint(30,99), rng.randint(200,650)
    if name == 'editions':
        def row(subject, edition, stamp=3, revision=1, verified=1, held=0, decision='use'):
            return {'subject':subject,'edition':edition,'stamp':f'2026-11-{stamp:02d}', 'revision':revision,
                    'verified':verified,'held':held,'decision':decision}
        variants = [
            ('basic',[row(first,'p')]),
            ('order',[row(first,'p'),row(first,'q',2,revision=9),row(second,'n')]),
            ('ties',[row(first,'q'),row(first,'n'),row(first,'p',revision=0)]),
            ('excluded',[row(first,'p'),row(first,'q',4,held=1),row(second,'v',verified=0)]),
            ('cutoff',[row(first,'p'),row(first,'q',22),row(second,'n',verified=0)]),
            ('negative',[row(first,'a'),row(first,'b',revision=3,decision='withdraw')]),
            ('empty',[]),
            ('multiple',[row(first,'x'),row(first,'y',4),row(second,'q'),row(second,'u',17,held=1)]),
        ]
        return [case(name, f'{suffix}-{i}', family, {'editions':rows,'cutoff':[{'stamp':'2026-11-17'}]})
                for i,(family,rows) in enumerate(variants)]
    if name == 'endpoint':
        def row(workload, ident, n=load, r=rate, l=lag, date='2026-11-10'):
            return {'workload':workload,'id':ident,'load':n,'rate':r,'lag':l,'stamp':date}
        limits = [{'workload':group,'floor':rate,'ceiling':lag,'cutoff':'2026-11-12'} for group in (first,second)]
        variants = [
            ('basic',[row(first,'p')]),
            ('ties',[row(first,'q'),row(first,'n'),row(first,'p',l=lag-1)]),
            ('cutoff',[row(first,'p'),row(first,'q',load+1,date='2026-11-13')]),
            ('missing',[row(first,'p',r=None),row(second,'q',n=None)]),
            ('bounds',[row(first,'p'),row(first,'q',load+1,r=rate-1),row(second,'v',l=lag+1)]),
            ('multiple',[row(first,'x'),row(second,'y'),row('uncontracted','v')]),
            ('empty',[]),
            ('rank',[row(first,'p',n=load+2,l=lag-1),row(first,'q',n=load+1,l=lag-2),row(second,'a',date=None)]),
        ]
        return [case(name,f'{suffix}-{i}',family,{'trial':rows,'limits':limits}) for i,(family,rows) in enumerate(variants)]
    names = [first, second, f'c{suffix}',f'd{suffix}',f'e{suffix}']
    a,b,c,d,e = names
    variants = [
        ('basic',[(a,b)], [a]), ('chain',[(a,b),(b,c),(c,d)], [a]),
        ('cycle',[(a,b),(b,c),(c,a),(c,d)], [b]), ('multiple',[(a,b),(b,c),(d,e)], [d,a]),
        ('orphan',[(a,'unknown'),('unknown',b),('lost',a)], [a,'lost']),
        ('duplicate',[(a,b),(a,b),(a,c),(b,d),(c,d)], [a]), ('empty',[(a,b)], []),
        ('orientation',[(a,b),(c,b),(b,d)], [b]),
    ]
    return [case(name,f'{suffix}-{i}',family,graph(names,edges,starts)) for i,(family,edges,starts) in enumerate(variants)]


def source_inputs(public):
    release = json.loads((public/'atlas-release.json').read_bytes())
    assert release['source_commit'] == BASE, 'Expected the pinned deployment receipt.'
    member = (public/'member-value.json').read_bytes()
    endpoint = (public/'endpoint-evidence-screen-1.0.0.zip').read_bytes()
    assert sha256(member).hexdigest() == release['member_value_sha256']
    assert sha256(endpoint).hexdigest() == release['public_capability_sha256']['endpoint-evidence-screen-1.0.0.zip']
    briefs = json.loads(member)['briefs']
    edition = {'editions':[{'subject':r['id'],'edition':r['review_sha256'][:16], 'stamp':r['updated_at'],
                            'revision':1,'verified':1,'held':0,'decision':r['verdict']} for r in briefs],
               'cutoff':[{'stamp':release['checked_at']}]}
    with ZipFile(public/'endpoint-evidence-screen-1.0.0.zip') as zipfile:
        sample = json.loads(zipfile.read('sample.json'))
    def scaled(n):
        return int(Decimal(n)*1_000_000)
    scope = sample['scope']['workload']
    workload = {'trial':[{'workload':scope,'id':r['id'],'load':r['load'],'rate':scaled(r['tokens_per_s']),
                          'lag':scaled(r['p90_ttft_ms']),'stamp':r['published']} for r in sample['rows']],
                'limits':[{'workload':scope,'floor':scaled(sample['minimum_tokens_per_s']),
                           'ceiling':scaled(sample['maximum_p90_ttft_ms']),'cutoff':sample['cutoff']}]}
    files = set(release['foundry_sha256'])
    dependencies = [('harness-engine.js','foundry-core.mjs'),('outcome-receipt.mjs','foundry-core.mjs'),
                    ('foundry-core.mjs','foundry-study.mjs'),('foundry-core.mjs','foundry-ui.mjs'),
                    ('foundry-study.mjs','foundry-ui.mjs'),('foundry-core.mjs','frontier-foundry-1.0.0.zip'),
                    ('foundry-study.mjs','frontier-foundry-1.1.0.zip'),('foundry-core.mjs','frontier-foundry-1.1.0.zip')]
    files.update(('index.html','fr.html'))
    dependencies.extend(('foundry-ui.mjs',name) for name in ('index.html','fr.html'))
    return ({'editions':edition,'endpoint':workload,'impact':graph(sorted(files),dependencies,['harness-engine.js'])},
            {'source_commit':BASE,'workflow_run':release['workflow_run'],
             'assets':{key:sha256((public/key).read_bytes()).hexdigest() for key in
                       ('atlas-release.json','member-value.json','endpoint-evidence-screen-1.0.0.zip')}})


def main(root, public, seed, selection=None):
    development = root/'constructor'
    confirmation = root/'evaluator'
    development.mkdir(mode=0o700, parents=True)
    confirmation.mkdir(mode=0o700)
    actual, provenance = source_inputs(public)
    rng = random.Random(seed)
    commitments = {}
    for name, mission in MISSIONS.items():
        dev = control(name,rng,f'd{rng.randrange(1000,9999)}')
        held = control(name,rng,f'h{rng.randrange(1000,9999)}')
        rng.shuffle(dev)
        rng.shuffle(held)
        held.append(case(name,'source','public-source-replay',actual[name]))
        save(development/f'{name}.json',mission)
        save(development/f'{name}-development.json',dev)
        save(confirmation/f'{name}-confirmation.json',held)
        save(confirmation/f'{name}-incumbent.json',{'hypothesis':'Conventional pre-registered SQL','sql':BASELINES[name]})
        commitments[name] = {'mission':digest(mission),'development':digest(dev),'confirmation':digest(held),
                             'incumbent':digest({'hypothesis':'Conventional pre-registered SQL','sql':BASELINES[name]})}
    cards = [
        {'id':'editions','goal':'Surface the latest verified member decision when source revisions disagree.',
         'evidence':'48 live member briefs, including corrections.','incumbent':'Manual or conventional sort and review.'},
        {'id':'endpoint','goal':'Choose a capacity point qualified by actual measurements across workloads.',
         'evidence':'A public Endpoint Screen has seven measured cases and a real abstention.',
         'incumbent':'Existing deterministic Endpoint Screen.'},
        {'id':'impact','goal':'Know which product evidence must be recomputed if a published prerequisite changes.',
         'evidence':'Published Foundry release hashes bind two companions and shared modules.',
         'incumbent':'Dependency inspection and a conventional graph traversal.'},
    ]
    save(development/'opportunities.json',cards)
    registration = {'schema':'frontier/inventor-registration-v1','commitments':commitments,
        'opportunities':digest(cards),'source':provenance,'model':SMALL_MODEL if selection else MODEL,
        'model_weights_sha256':SMALL_WEIGHTS if selection else WEIGHTS,
        'runtime_archive_sha256':RUNTIME,'output_budgets':{'opportunity':256,'construction':640,'method':512},
        'arms':['original','ordinary','augmented','withdrawn','conventional'],'public_replay_cases_per_mission':1}
    if selection:
        if (selection['status'] != 'SELECTED' or selection['binding'].get('input_sha256') != digest(cards) or
                selection['model'] != MODEL or selection['result']['choice'] not in MISSIONS):
            raise ValueError('A sealed opportunity selection from the larger model is required.')
        registration['opportunity_run_sha256'] = digest(selection)
        save(development/'fixed-opportunity.json', selection)
    save(root/'registration.json', registration)
    save(confirmation/'generation.json',{'seed':str(seed),'scope':'Public controlled examples and one release replay per mission.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('public',type=Path)
    parser.add_argument('--seed',type=int)
    parser.add_argument('--reuse-selection',type=Path)
    args = parser.parse_args()
    selected = json.loads(args.reuse_selection.read_bytes()) if args.reuse_selection else None
    main(args.root,args.public,secrets.randbits(63) if args.seed is None else args.seed,selected)
