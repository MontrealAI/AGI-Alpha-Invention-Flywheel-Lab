import hashlib
import json
import re
import sys
from pathlib import Path


timing = re.compile(r'\bslot print_timing: id\s+(\d+) \| task (\d+) \|\s+(prompt eval|eval|total) time\s+=\s+([0-9.]+) ms /\s+(\d+) tokens')
source = Path(sys.argv[1])
reports = {}
digest = hashlib.sha256()
with source.open('rb') as stream:
    for raw_line in stream:
        digest.update(raw_line)
        record = timing.search(raw_line.decode('ascii', errors='ignore'))
        if record:
            slot, task, phase, elapsed, tokens = record.groups()
            current = reports.setdefault((int(slot), int(task)), {'slot': int(slot), 'task': int(task)})
            current[phase.replace(' ', '_')] = {'milliseconds': float(elapsed), 'tokens': int(tokens)}
print(json.dumps({'source_log_sha256': digest.hexdigest(),
                  'scope': 'Recorded llama.cpp task timings only', 'tasks': list(reports.values())}, sort_keys=True))
