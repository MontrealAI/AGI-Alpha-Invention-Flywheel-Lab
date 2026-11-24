def verify_historical(ticket, manifest, *, root=None):
    body = ticket_body(ticket)
    candidates = [Path(body['historical_root']).absolute()]
    if root is not None:
        candidates.append(Path(root).absolute() / 'historical-source-versions' / body['from_source']['sha256'])
    selected = None
    for candidate in candidates:
        try:
            if candidate.is_dir() and source_inventory(candidate) == body['verifier_files']:
                selected = candidate
                break
        except (ValueError, OSError):
            continue
    if selected is None:
        raise ValueError('PINNED_HISTORICAL_VERIFIER_CHANGED')
    root = selected
    from commercial.ledger import load_jobs
    load_jobs(root, manifest)
    cache_key = digest({'ticket': ticket, 'manifest': manifest, 'root': str(root),
                        'verifier_files': body['verifier_files']})
    if cache_key in _HISTORICAL_AUDITS:
        return copy.deepcopy(_HISTORICAL_AUDITS[cache_key])
    payload = {'record': body['prior_record'], 'manifest': manifest, 'root': str(root), 'evidence_dir': current_store_directory()}
    code = """import json,sys,contextlib,importlib.util
from connected_enterprise.finance import audit_journal
p=json.load(sys.stdin);scope=contextlib.nullcontext()
if p.get('evidence_dir') and importlib.util.find_spec('connected_enterprise.transition_evidence'):
 from connected_enterprise.transition_evidence import evidence_directory
 scope=evidence_directory(p['evidence_dir'])
with scope:
 r=audit_journal(p['record'],root=p['root'],manifest=p['manifest'])
 assert r['accepted'];print(json.dumps(r,sort_keys=True))
"""
    env = {**os.environ, 'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-c', code], input=json.dumps(payload),
                          text=True, capture_output=True, cwd=root, env=env, timeout=60)
    if done.returncode:
        raise ValueError('PINNED_HISTORICAL_AUDIT_FAILED:' + done.stderr[-1200:])
    receipt = json.loads(done.stdout)
    if not receipt.get('accepted'):
        raise ValueError('PINNED_HISTORICAL_AUDIT_NOT_ACCEPTED')
    if source_inventory(root) != body['verifier_files']:
        raise ValueError('HISTORICAL_VERIFIER_CHANGED_DURING_AUDIT')
    load_jobs(root, manifest)
    if len(_HISTORICAL_AUDITS) >= 128:
        _HISTORICAL_AUDITS.pop(next(iter(_HISTORICAL_AUDITS)))
    _HISTORICAL_AUDITS[cache_key] = copy.deepcopy(receipt)
    return receipt
