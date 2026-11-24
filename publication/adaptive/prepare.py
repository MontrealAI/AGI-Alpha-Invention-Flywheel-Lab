"""Produce minimal, time-separated study input from the Actions API pages."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pages import canonical, digest, normalize

ANCHOR = 338
FIT = 230
DEVELOPMENT = 273


def prepare(source, output):
    raw_inputs = json.loads((source/'sources.json').read_bytes())
    selected = {}
    exclusions = []
    for index, receipt in enumerate(raw_inputs, 1):
        raw = (source/f'{index}.json').read_bytes()
        if sha256(raw).hexdigest() != receipt['sha256']:
            raise ValueError('INPUT_DIGEST')
        for item in json.loads(raw)['workflow_runs']:
            if item['run_number'] > ANCHOR:
                continue
            try:
                row = normalize(item)
            except (ValueError, TypeError) as error:
                exclusions.append({'number':item['run_number'],'reason':str(error)})
                continue
            if row and row['completed'] is not None:
                before = selected.setdefault(row['number'],row)
                if before != row:
                    raise ValueError('DUPLICATE_WORKFLOW')
    records = sorted(selected.values(), key=lambda x:x['number'])
    if records[-1]['id'] != 45438435432 or len(records)<150:
        raise ValueError('ANCHOR_OR_COHORT')
    partitions = {
        'fit':[x for x in records if x['number']<=FIT],
        'development':[x for x in records if FIT<x['number']<=DEVELOPMENT],
        'confirmation':[x for x in records if DEVELOPMENT<x['number']],
    }
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    for label, rows in partitions.items():
        (output/f'{label}.json').write_bytes(canonical(rows)+b'\n')
    receipt = {'source':raw_inputs,'excluded_invalid':exclusions,'cutoffs':[FIT,DEVELOPMENT,ANCHOR],
               'counts':{label:len(rows) for label,rows in partitions.items()},
               'commitments':{label:digest(rows) for label,rows in partitions.items()}}
    (output/'inputs.json').write_bytes(canonical(receipt)+b'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    print(canonical(prepare(args.source,args.output)).decode())
