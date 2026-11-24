"""Compile a bottleneck inventory from already published project receipts."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

BASE='68cd14692a63f4b001d3635c7470f34d264516ae'
ROOT=Path(__file__).resolve().parents[2]


def inventory(release):
    bindings={}

    def get(path):
        raw=(ROOT/path).read_bytes()
        bindings[path]=sha256(raw).hexdigest()
        return json.loads(raw)

    old=get('publication/inventor/evidence.json')
    repairs=get('publication/adaptive/runs.json')
    evaluation=get('publication/adaptive/verification.json')
    stages=get('publication/adaptive/operation.json')
    raw=release.read_bytes()
    atlas=json.loads(raw)
    if atlas['source_commit']!=BASE:
        raise ValueError('PUBLIC_SOURCE_DRIFT')
    counts=Counter(e.get('diagnosis') or e.get('reason') or e['status']
                   for x in repairs.values() for e in x['events'])
    controls={name:row['assessment']['matched'] for name,row in old['assessments'].items()}
    observations=[
        {'id':'E1','finding':'Original release-dependency instrument failed held transitive closure. Conventional queries passed.',
         'measurements':{k:controls[k] for k in ('first','impact-conventional')}},
        {'id':'E2','finding':'The builder hit response, context and language-validation failures across three representations.',
         'measurements':dict(counts)},
        {'id':'E3','finding':'Active case ranking changed the PR construction inclusion set and the read/delay trade-off. Every model policy stayed below the quality gate.',
         'measurements':{'changed':evaluation['transfer']['observed_selection']['augmented']['changed_selection'],
                         'verdict':evaluation['monitoring']['pull_request']['candidates']['augmented']['verdict']}},
        {'id':'E4','finding':'Portable local training and receipts are available. The fitted timing model lost its registered overall comparison.',
         'measurements':{'examples':evaluation['public_cases'],'verdict':evaluation['forecast']['verdict']}},
        {'id':'E5','finding':'The local worker independently matched an actual public release. Its live read costs and software dependencies are measurable.',
         'measurements':{'reads_reserved':stages['reads_reserved'],'events':stages['observed']}},
        {'id':'E6','finding':'Production distributes four reproducible companion archives. An independent evaluator often needs a particular subset of their exact files.',
         'measurements':{'release_sha256':sha256(raw).hexdigest(),'reference_count':atlas['records'],
                         'archive_count':sum(key.endswith('.zip') for key in atlas['foundry_sha256'])}},
    ]
    objectives=[
        {'id':'learning-replay','capability':'Recover evidence and runnable verification for a fitted operational model.',
         'beneficiary':'MONTREAL.AI independent reviewer','limitations':['E4','E5','E6'],
         'incumbent':'Download the whole learning companion or fetch known pinned files.',
         'leverage':'Lower the evidence acquisition cost of challenging future specialized models.'},
        {'id':'local-runner','capability':'Bootstrap a portable research runtime with reproducible local model interfaces.',
         'beneficiary':'MONTREAL.AI constructor operator','limitations':['E2','E5','E6'],
         'incumbent':'Install the full public Foundry companion and use its documented paths.',
         'leverage':'Reduce setup barriers for building and challenging independent successors.'},
        {'id':'inventor-audit','capability':'Restore the exact inputs and independently executable verdict of an invention experiment.',
         'beneficiary':'MONTREAL.AI invention evaluator','limitations':['E1','E2','E3','E6'],
         'incumbent':'Fetch the complete inventor package or manually locate the pinned source and frozen case files.',
         'leverage':'Turn evidence from opaque or rejected experiments into portable challenges for a new investigator.'},
    ]
    return {'schema':'frontier/bottleneck-map-v1','source':BASE,'record_bindings':bindings,
            'public_release':{'source':atlas['source_commit'],'workflow':atlas['workflow_run'],
                              'digest':sha256(raw).hexdigest()},
            'observations':observations,'objectives':objectives,
            'resources':{'route':'operator-local HARNESS','available':'CPU, public research artifacts','paid_inference':0}}


if __name__=='__main__':
    print(json.dumps(inventory(Path(sys.argv[1])),sort_keys=True,separators=(',',':'),ensure_ascii=False))
