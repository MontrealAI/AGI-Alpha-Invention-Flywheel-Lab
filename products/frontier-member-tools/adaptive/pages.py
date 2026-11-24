"""Read the explicitly scoped public Actions and Pages evidence."""

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO = 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
WORKFLOW = 403584675
API = f'https://api.github.com/repos/{REPO}/actions'
PAGES = f'https://montrealai.github.io/{REPO.split("/")[1]}/frontier-omega-alpha/'
EVENTS = ('push', 'pull_request', 'schedule')
TERMINAL = {'success', 'failure', 'cancelled', 'skipped', 'neutral', 'timed_out', 'action_required', 'startup_failure', 'stale'}
FIELDS = {'id', 'number', 'event', 'sha', 'created', 'started', 'completed', 'conclusion'}
SHA = re.compile(r'[0-9a-f]{40}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def timestamp(value):
    return int(datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get(url, limit):
    request = Request(url, headers={'User-Agent':'MONTREAL.AI-Frontier-Local',
                                    'Accept':'application/json,*/*;q=0.8'})
    with build_opener(NoRedirect).open(request, timeout=12) as response:
        content = response.read(limit + 1)
    if not 0 < len(content) <= limit:
        raise ValueError('PUBLIC_RESPONSE_SIZE')
    return content


def validate(row):
    if type(row) is not dict or set(row) != FIELDS:
        raise ValueError('WORKFLOW_RECORD')
    if any(type(row[key]) is not int or not 0 < row[key] < 2**53 for key in ('id','number','created','started')):
        raise ValueError('WORKFLOW_ID_TIME')
    if (row['event'] not in EVENTS or not isinstance(row['sha'], str) or not SHA.fullmatch(row['sha'])
            or row['started'] < row['created']):
        raise ValueError('WORKFLOW_SCOPE')
    done = row['completed']
    if done is None:
        if row['conclusion'] is not None:
            raise ValueError('WORKFLOW_ACTIVE')
    elif type(done) is not int or not row['started'] <= done <= row['created'] + 7*86400 or row['conclusion'] not in TERMINAL:
        raise ValueError('WORKFLOW_COMPLETION')
    return row


def normalize(row):
    if (row['workflow_id'] != WORKFLOW or row['path'] != '.github/workflows/research-pages.yml'
            or row['event'] not in EVENTS or row['run_attempt'] != 1
            or row['event'] != 'pull_request' and row['head_branch'] != 'main'):
        return None
    completed = row['status'] == 'completed'
    created = timestamp(row['created_at'])
    started = timestamp(row['run_started_at']) if row['run_started_at'] else created
    return validate({'id':row['id'],'number':row['run_number'],'event':row['event'],
                     'sha':row['head_sha'],'created':created,'started':started,
                     'completed':timestamp(row['updated_at']) if completed else None,
                     'conclusion':row['conclusion'] if completed else None})


def current(run=None):
    if run is None:
        raw = get(f'{API}/workflows/{WORKFLOW}/runs?per_page=12', 250000)
        values = json.loads(raw)['workflow_runs']
    elif type(run) is int and 0 < run < 2**53:
        values = [json.loads(get(f'{API}/runs/{run}', 50000))]
    else:
        raise ValueError('RUN_ID')
    return [row for val in values if (row := normalize(val)) is not None]


def witness(row):
    if row['event'] != 'push' or row['conclusion'] != 'success':
        return {'state':'ABSTAIN','reason':'COMPLETED_MAIN_PUSH_REQUIRED'}
    marker = '?run=' + str(row['id'])
    raw = get(PAGES + 'atlas-release.json' + marker, 200000)
    receipt = json.loads(raw)
    if receipt.get('source_commit') != row['sha'] or str(receipt.get('workflow_run')) != str(row['id']):
        return {'state':'ABSTAIN','reason':'CURRENT_PAGES_RECEIPT_DIFFERS'}
    checks = {
        'atlas-ledger.json':receipt.get('ledger_sha256'),
        'member-value.json':receipt.get('member_value_sha256'),
    }
    for name, expected in checks.items():
        if not isinstance(expected,str) or not HASH.fullmatch(expected):
            return {'state':'REJECTED','reason':'MISSING_PUBLIC_DIGEST'}
        body = get(PAGES + name + marker, 20_000_000)
        if sha256(body).hexdigest() != expected:
            return {'state':'REJECTED','reason':'PUBLIC_BYTES_DIFFER','asset':name}
    return {'state':'MATCHED_PUBLIC_RELEASE','receipt_sha256':sha256(raw).hexdigest(),
            'checked_assets':checks,'run_id':row['id'],'source_commit':row['sha']}
