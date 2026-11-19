"""Execute a frozen blank brief through the real invited Studio without seeding a solution."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import threading
import time
from urllib import error, request


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


@contextmanager
def signed_in_studio(work, port, receipt, q):
    from ignition.hosted import HostedService
    from ignition.hosted_auth import Access

    settings = {"IGNITION_MODEL_PROVIDER": "llama-cpp", "IGNITION_MODEL_ID": q.MODEL_ALIAS,
                "IGNITION_MODEL_PORT": str(port), "IGNITION_MODEL_SHA256": q.pinned.MODEL_SHA,
                "IGNITION_MODEL_SCHEMA": "1", "IGNITION_MODEL_STREAM": "1", "IGNITION_MODEL_TIMEOUT": "300",
                "IGNITION_MODEL_OUTPUT_TOKENS": "2048"}
    previous = {key: os.environ.get(key) for key in settings}
    os.environ.update(settings)
    try:
        cert, key = work / 'staging-cert.pem', work / 'staging-key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost',
                        '-out', str(cert), '-keyout', str(key)], check=True, capture_output=True, timeout=15)
        access = Access(work / 'state', 'staging')
        studio = HostedService(access, 'https://localhost', port=0)
        studio.origin = f'https://localhost:{studio.server_port}'
        studio.authority = f'localhost:{studio.server_port}'
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        studio.socket = context.wrap_socket(studio.socket, server_side=True)
        runner = threading.Thread(target=studio.serve_forever, daemon=True)
        runner.start()
        try:
            client = request.build_opener(request.ProxyHandler({}), request.HTTPCookieProcessor(CookieJar()),
                                          request.HTTPSHandler(context=ssl.create_default_context(cafile=str(cert))))
            def call(path, body=None):
                req = request.Request(studio.origin + path, data=json.dumps(body).encode() if body is not None else None,
                                      headers={'Origin': studio.origin, 'Content-Type': 'application/json',
                                               'X-Ignition-Request': '1'})
                with client.open(req, timeout=15) as res:
                    return json.load(res) if res.headers.get_content_type() == 'application/json' else res.read()

            try:
                call('/api/runs')
            except error.HTTPError as denied:
                receipt['unauthenticated_status'] = denied.code
                denied.close()
            assert receipt.get('unauthenticated_status') == 401
            receipt['authentication'] = call('/api/session', {'invite': access.issue('qualification')})
            receipt['readiness'] = call('/readyz')
            receipt['configuration'] = call('/api/status')['provider']
            assert receipt['authentication'] == {'authenticated': True, 'environment': 'staging'}
            assert receipt['readiness'] == {'status': 'ok', 'revision': receipt['source_revision']}
            assert receipt['configuration']['declared_model_sha256'] == q.pinned.MODEL_SHA
            assert not call('/api/runs')['runs']
            yield call, studio.controller_for('qualification').store
        finally:
            studio.shutdown()
            runner.join()
            studio.server_close()
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def observe_mission(args, q, call, store, receipt, data):
    registered = data['input']
    work_seconds = data['mission_minutes'] * 60
    when = datetime.now(timezone.utc)
    registered['mission']['time'] = {'deadline': (when + timedelta(seconds=work_seconds)).isoformat()}
    receipt['dispatch_utc'] = when.isoformat()
    receipt['request_sha256'] = q.digest(registered)
    run = call('/api/runs', registered)['id']
    receipt['mission_id'] = run
    endpoint = '/api/runs/' + run
    deadline = time.monotonic() + work_seconds
    decision_at = None
    last = None
    while True:
        state = call(endpoint)
        step = {'status': state['status'], 'stage': state['stage'], 'attempts': state.get('attempts', 0)}
        if step != last:
            write(args.work / 'progress.json', step)
            print(json.dumps(step), flush=True)
            last = step
        if state['status'] == 'awaiting_contract':
            if decision_at is None:
                decision_at = time.monotonic() + args.review_seconds
                write(args.work / 'proposal.json', state['proposed_contract'])
            approval = args.work / 'approve.json'
            if approval.is_file() and args.review_seconds:
                review = json.loads(approval.read_text())
                assert set(review) == {'contract_sha256', 'confirmations'}
                assert review['contract_sha256'] == state['contract_sha256']
                call(endpoint + '/approve', {'version': state['version'], **review})
                receipt['approval_submitted'] = True
                continue
            if (args.work / 'decline.json').is_file() or time.monotonic() >= decision_at:
                break
        elif state['status'] not in {'queued', 'running'}:
            break
        if time.monotonic() >= deadline:
            receipt['budget_deadline_reached'] = True
            operation = state['operation']
            call(endpoint+'/operation', {'operation': 'stop', 'version': state['version'],
                                         'sequence': operation['sequence']})
            state = call(endpoint)
            break
        time.sleep(.5)

    version = state['version']
    evidence = call(endpoint + f'/evidence?version={version}')
    write(args.work / 'evidence.json', evidence)
    raw = store.get(run, version)
    receipt.update(status=state['status'], stage=state['stage'], artifact=evidence['artifact'],
                   calls=q.compact_calls(raw), attempts=state.get('attempts', 0),
                   source_acquisition=raw.get('source_result'), research=state.get('research'),
                   error=state.get('error'), evaluation=state.get('evaluation'))
    receipt['catalogue_diagnostic'] = q.diagnostic(raw, receipt['calls'])
    receipt['call_wall_limit_respected'] = all((r.get('wall_seconds') or 0) <= 300 for r in receipt['calls'])
    if state['status'] == 'verified':
        package = call(endpoint + f'/bundle?version={version}')
        (args.work / 'recipient.zip').write_bytes(package)
        receipt.update(delivered=True, bundle_sha256=sha256(package).hexdigest(),
                       receiver=q.check_portable(package, args.work))


def public_record(receipt):
    keys = ('protocol', 'started_at', 'finished_at', 'source_revision', 'runtime_source_sha256', 'brief_sha256',
            'registration_sha', 'hardware', 'model', 'assets', 'wall_seconds', 'cpu_seconds', 'status', 'stage',
            'attempts', 'authentication', 'readiness', 'unauthenticated_status', 'call_wall_limit_respected',
            'catalogue_diagnostic', 'delivered', 'budget_deadline_reached', 'driver_error', 'cash_collected_usd')
    selected = {key: receipt[key] for key in keys if key in receipt}
    selected['calls'] = [{k: row[k] for k in ('stage','status','request_sha256','response_sha256','error_code',
                                             'reported_model','wall_seconds','usage') if k in row}
                         for row in receipt.get('calls', [])]
    acquisition = receipt.get('source_acquisition') or {}
    selected['publisher_inputs'] = [{'url':row['url'],'published_at':row.get('published_at'),
                                     'response_sha256':row.get('source_response_sha256')}
                                    for row in acquisition.get('sources', [])]
    selected['publisher_failures'] = [{k: row.get(k) for k in ('feed','role','reason_code')}
                                        for row in acquisition.get('failures', [])]
    research = receipt.get('research') or {}
    selected['research'] = {'decision':research.get('decision'), 'requested_output':research.get('requested_output'),
                            'candidates':[{k: c[k] for k in ('id','kind','standing','mechanics','family_assessment') if k in c}
                                          for c in research.get('candidates', [])]}
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('repo', 'brief', 'work', 'assets'):
        parser.add_argument('--'+option, required=True, type=Path)
    parser.add_argument('--registration-sha', required=True)
    parser.add_argument('--review-seconds', type=int, default=0)
    args = parser.parse_args()
    raw = args.brief.read_bytes()
    data = json.loads(raw)
    assert not data['input']['mission'].get('construction_spec')
    assert not {'confirmations', 'artifact', 'evaluation'} & set(data['input'])
    relative = f'docs/frontier-omega-ignition/continuation/problem-first/{args.brief.name}'
    assert subprocess.check_output(['git','-C',str(args.brief.parents[4]),'show',
                                    args.registration_sha+':'+relative]) == raw
    args.work.mkdir(mode=0o700, parents=True)
    sys.path.insert(0, str(args.repo / 'products/frontier-omega-ignition'))
    import qualify_live as q
    from field_trials import observe
    from qa import research_server
    from qa.qualify_model_dispatch import cpu_time
    revision = q.checked_source()
    assert revision == data['engine_revision']
    hardware = observe.hardware()
    hardware['threads'] = min(4, hardware['threads'])
    receipt = {'protocol':data['protocol'],'started_at':q.stamp(),'source_revision':revision,'hardware':hardware,
               'runtime_source_sha256':q.runtime_source(),'registration_sha':args.registration_sha,
               'brief_sha256':sha256(raw).hexdigest(),'cash_collected_usd':0,'model':q.MODEL_ALIAS,'delivered':False}
    start, cpu = time.monotonic(), cpu_time()
    try:
        binary, weights = observe.prepare(args.assets.resolve(),args.work,receipt)
        with research_server.server(binary, weights, args.work, receipt) as port:
            with signed_in_studio(args.work, port, receipt, q) as (call, store):
                observe_mission(args, q, call, store, receipt, data)
    except Exception as failure:
        receipt['driver_error'] = type(failure).__name__
        receipt['driver_error_detail'] = str(failure)[:500]
        raise
    finally:
        receipt.update(finished_at=q.stamp(),wall_seconds=round(time.monotonic()-start,3),
                       cpu_seconds=round(cpu_time()-cpu,3))
        write(args.work/'receipt.json',receipt)
        write(args.work/'public-receipt.json',public_record(receipt))
    return 0 if receipt.get('delivered') and receipt['call_wall_limit_respected'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
