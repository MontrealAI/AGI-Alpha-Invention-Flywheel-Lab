"""Read only two pinned same-repository artifacts; never execute archive contents.

Official artifact transport allowlist:
https://docs.github.com/en/actions/reference/runners/github-hosted-runners
Only the GitHub artifact API receives the ephemeral token. Signed redirects use
fresh unauthenticated requests. No URL query, token, environment or full transcript
is printed. Published lines begin INSPECT, with JSON escaping control characters.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import re
import stat
import sys
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
API = 'https://api.github.com/repos/' + REPO + '/actions/artifacts/'
PINS = (
    {'kind': 'wasi', 'id': 13749646988, 'bytes': 163848,
     'sha256': 'e80728df16739bda01cb2be79364f0aebc09442ba95b917fe68ce986c11e8578',
     'head': '663f33e3df8fbc0b070993c163506ed37d4f2673', 'run': 42785601400,
     'members': ('RESULT.json', 'worker-001.json')},
    {'kind': 'model', 'id': 13749851820, 'bytes': 74907,
     'sha256': 'aefe68874e689cebd3cb0581d9b20d07e90b0d51c33c41119836ba6719f183eb',
     'head': '323ee38c25b1a0194c343bad9d6ee5757b827a53', 'run': 42783849641,
     'members': ('HOSTED-LOCAL-QUALIFICATION.json',
                 'LOCAL-QUOTE-QUALIFICATION-006.json', 'LOCAL-WORKFLOWS-HOSTED.json')},
)
MAX_MEMBERS, MAX_MEMBER_BYTES, MAX_TOTAL_BYTES = 256, 4 * 1024**2, 16 * 1024**2


class Refusal(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def opener():
    # Ignore proxy environment variables. Neither opener has stored credentials.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refusal('duplicate_json_key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal('nonfinite_json')))


def signed_url_allowed(url):
    try:
        p = urllib.parse.urlsplit(url)
        hostname = p.hostname or ''
        allowed = (re.fullmatch(r'[a-z0-9]{3,24}\.blob\.core\.windows\.net', hostname) is not None
                   or hostname == 'results-receiver.actions.githubusercontent.com')
        return bool(p.scheme == 'https' and allowed and p.port in (None, 443)
                    and p.username is None and p.password is None and not p.fragment
                    and p.path.startswith('/') and p.query)
    except ValueError:
        return False


def bounded_read(response, limit):
    data = response.read(limit + 1)
    if len(data) > limit:
        raise Refusal('response_size_limit')
    return data


def api_request(pin, token, suffix=''):
    if suffix not in ('', '/zip') or pin not in PINS:
        raise Refusal('unpinned_api_target')
    return urllib.request.Request(
        API + str(pin['id']) + suffix,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2026-03-10', 'User-Agent': 'pinned-artifact-inspector'})


def validate_metadata(value, pin):
    if not isinstance(value, dict):
        raise Refusal('invalid_metadata')
    run = value.get('workflow_run', {})
    if (value.get('id') != pin['id'] or value.get('size_in_bytes') != pin['bytes']
            or value.get('digest') != 'sha256:' + pin['sha256']
            or value.get('expired') is not False
            or run.get('id') != pin['run'] or run.get('head_sha') != pin['head']
            or run.get('repository_id') != 1438763186
            or run.get('head_repository_id') != 1438763186):
        raise Refusal('artifact_metadata_pin_mismatch')


def download(pin, token):
    auth = opener()
    with auth.open(api_request(pin, token), timeout=60) as response:
        if response.status != 200:
            raise Refusal('artifact_metadata_status')
        metadata = strict_json(bounded_read(response, 65536))
    validate_metadata(metadata, pin)
    try:
        response = auth.open(api_request(pin, token, '/zip'), timeout=60)
    except urllib.error.HTTPError as error:
        try:
            if error.code not in (301, 302, 303, 307, 308):
                raise Refusal('artifact_redirect_http_' + str(error.code))
            location = error.headers.get('Location', '')
        finally:
            error.close()
    else:
        response.close()
        raise Refusal('artifact_download_requires_explicit_signed_redirect')
    # A separate opener and a fresh header dictionary ensure no API token crosses hosts.
    public = opener()
    for _ in range(3):
        if not signed_url_allowed(location):
            raise Refusal('artifact_storage_url_refused')
        request = urllib.request.Request(location, headers={'User-Agent': 'pinned-artifact-inspector'})
        try:
            with public.open(request, timeout=60) as response:
                if response.status != 200:
                    raise Refusal('artifact_storage_status')
                data = bounded_read(response, pin['bytes'])
            break
        except urllib.error.HTTPError as error:
            try:
                if error.code not in (301, 302, 303, 307, 308):
                    raise Refusal('artifact_storage_http_' + str(error.code))
                location = error.headers.get('Location', '')
            finally:
                error.close()
    else:
        raise Refusal('artifact_redirect_limit')
    if len(data) != pin['bytes'] or hashlib.sha256(data).hexdigest() != pin['sha256']:
        raise Refusal('artifact_wrapper_pin_mismatch')
    return data


def safe_members(archive):
    members, seen, total = {}, set(), 0
    items = archive.infolist()
    if not 1 <= len(items) <= MAX_MEMBERS:
        raise Refusal('zip_member_count')
    for item in items:
        name = item.filename
        path = PurePosixPath(name)
        mode = stat.S_IFMT(item.external_attr >> 16)
        if (not name or len(name) > 240 or '\\' in name or ':' in name
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or path.is_absolute() or path.as_posix() != name
                or any(part in ('.', '..') for part in name.split('/'))
                or name.casefold() in seen or item.is_dir()
                or mode not in (0, stat.S_IFREG) or item.flag_bits & 1
                or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                or not 0 <= item.file_size <= MAX_MEMBER_BYTES):
            raise Refusal('unsafe_zip_member')
        seen.add(name.casefold())
        total += item.file_size
        members[name] = item
    if total > MAX_TOTAL_BYTES:
        raise Refusal('zip_expansion_limit')
    return members


def read_selected(data, pin):
    # Never extract to disk, import modules, call eval/exec, or run subprocesses.
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = safe_members(archive)
        if not all(name in members for name in pin['members']):
            raise Refusal('required_receipt_missing')
        result = {}
        for name in pin['members']:
            with archive.open(members[name]) as stream:
                raw = bounded_read(stream, MAX_MEMBER_BYTES)
            if len(raw) != members[name].file_size:
                raise Refusal('member_size_mismatch')
            result[name] = strict_json(raw)
        return result


def clip(value, limit=2000):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True, allow_nan=False)
    if len(text) <= limit:
        return value
    return {'excerpt': text[:limit], 'characters': len(text), 'truncated': True,
            'sha256_utf8': hashlib.sha256(text.encode()).hexdigest()}


def diagnostics(value, path='', result=None):
    result = [] if result is None else result
    if len(result) >= 24:
        return result
    if isinstance(value, dict):
        for key, item in value.items():
            if len(result) >= 24:
                break
            if key in {'prompt', 'context', 'messages', 'response', 'text', 'content', 'files'}:
                continue
            current = path + '/' + str(key)
            if key in {'error', 'errors', 'failure', 'reason', 'message', 'error_code', 'code'}:
                result.append({'path': current, 'value': clip(item, 1000)})
                if len(result) >= 24:
                    break
            elif isinstance(item, (dict, list)):
                diagnostics(item, current, result)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            diagnostics(item, path + '/' + str(i), result)
            if len(result) >= 24:
                break
    return result


def compact_model(value):
    if not isinstance(value, dict):
        raise Refusal('model_receipt_not_object')
    keys = ('schema', 'status', 'release_qualification', 'qualifications', 'quote_overall_status',
            'source_revision', 'source_product_tree', 'product_tree_sha', 'source_unchanged',
            'error', 'execution_error', 'claims')
    output = {key: clip(value[key], 3000) for key in keys if key in value}
    for collection in ('arms', 'runs'):
        if collection not in value:
            continue
        rows = value[collection]
        if not isinstance(rows, list) or len(rows) > 16:
            raise Refusal('unexpected_model_arm_count')
        output[collection] = []
        for row in rows:
            entry = {key: clip(row[key], 3000) for key in
                     ('id', 'policy', 'status', 'reason', 'model_calls', 'iterations', 'actions',
                      'verification', 'selected_branch') if key in row}
            entry['diagnostics'] = diagnostics(row)
            observations = row.get('observations', [])
            entry['observation_error_counts'] = dict(Counter(
                str(item['error_code']) for item in observations if isinstance(item, dict) and 'error_code' in item))
            entry['selected_observations'] = []
            for item in observations[-2:]:
                selected = {key: clip(item[key], 1000) for key in ('error_code', 'wall_seconds') if key in item}
                response = item.get('response')
                if isinstance(response, dict):
                    selected['response'] = {key: clip(response[key], 4000 if key == 'text' else 1500)
                                            for key in ('text', 'finish_reason', 'tool_calls', 'usage') if key in response}
                entry['selected_observations'].append(selected)
            output[collection].append(entry)
    output['scope'] = 'Selected failure fields and final two observations per arm; not a full transcript or new qualification.'
    return output


def scrub(value, token=''):
    if isinstance(value, dict):
        return {scrub(key, token): scrub(item, token) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub(item, token) for item in value]
    if not isinstance(value, str):
        return value
    text = value.replace(token, '[REDACTED_EPHEMERAL_TOKEN]') if token else value
    text = re.sub(r'(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{16,}', '[REDACTED_TOKEN]', text)
    text = re.sub(r'sk-[A-Za-z0-9_-]{16,}', '[REDACTED_TOKEN]', text)
    text = re.sub(r'Bearer\s+[A-Za-z0-9._-]+', 'Bearer [REDACTED]', text)
    # Sanitize raw string leaves before serialization so embedded quotes remain valid JSON.
    return re.sub(r'(https?://[^\s?"<>]+)\?[^\s"<>]*', r'\1?[REDACTED_QUERY]', text)


def sanitized_line(value, token=''):
    text = json.dumps(scrub(value, token), ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    # Defang both modern and legacy Actions command markers inside untrusted strings.
    text = text.replace('::', r'\u003a\u003a').replace('##[', r'\u0023\u0023[')
    if len(text) > 131072:
        raise Refusal('diagnostic_output_limit')
    return 'INSPECT ' + text


class PreparationTests(unittest.TestCase):
    def test_signed_storage_allowlist(self):
        self.assertTrue(signed_url_allowed('https://productionresultssa1.blob.core.windows.net/a?sig=x'))
        self.assertTrue(signed_url_allowed('https://results-receiver.actions.githubusercontent.com/a?sig=x'))
        for value in ('http://productionresultssa1.blob.core.windows.net/a?sig=x',
                      'https://api.github.com/a?sig=x', 'https://evil.example/a?sig=x',
                      'https://productionresultssa1.blob.core.windows.net.evil.example/a?sig=x',
                      'https://u:p@productionresultssa1.blob.core.windows.net/a?sig=x',
                      'https://productionresultssa1.blob.core.windows.net:444/a?sig=x'):
            self.assertFalse(signed_url_allowed(value))

    def test_token_and_redirect_separation(self):
        request = api_request(PINS[0], 'synthetic-test-token', '/zip')
        self.assertEqual(request.full_url, API + '13749646988/zip')
        self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-test-token')
        self.assertIsNone(NoRedirect().redirect_request(request, None, 302, '', {}, 'https://evil.example'))
        public = urllib.request.Request('https://productionresultssa1.blob.core.windows.net/a?sig=x',
                                        headers={'User-Agent': 'pinned-artifact-inspector'})
        self.assertIsNone(public.get_header('Authorization'))
        with self.assertRaises(Refusal):
            api_request({'id': 1}, 'synthetic-test-token')

    def test_zip_paths_and_symlinks_refused(self):
        for name in ('../x', '/x', 'a/../x', 'a\\x', 'x:x', 'a//b'):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr(name, '{}')
            with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive, self.assertRaises(Refusal):
                safe_members(archive)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            item = zipfile.ZipInfo('link'); item.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(item, 'outside')
        with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive, self.assertRaises(Refusal):
            safe_members(archive)

    def test_strict_json_and_allowlisted_member_read(self):
        with self.assertRaises(Refusal):
            strict_json('{"x":1,"x":2}')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('RESULT.json', '{"status":"FAIL"}')
            archive.writestr('worker-001.json', '{"outcome":"ERROR"}')
            archive.writestr('never-executed.py', 'raise RuntimeError("DO NOT EXECUTE")')
        result = read_selected(buffer.getvalue(), PINS[0])
        self.assertEqual(set(result), set(PINS[0]['members']))

    def test_bounded_projection_and_log_redaction(self):
        projected = compact_model({'runs': [{'status': 'failed', 'prompt': 'not published',
                       'observations': [{'response': {'text': 'x' * 6000}, 'prompt': 'not published'}]}]})
        text = sanitized_line(projected)
        self.assertNotIn('not published', text)
        self.assertIn('"truncated":true', text)
        self.assertNotIn('synthetic-test-token', sanitized_line({'error': 'synthetic-test-token'}, 'synthetic-test-token'))
        self.assertNotIn('sig=private', sanitized_line({'x': 'https://example.org/a?sig=private'}))
        rendered = sanitized_line({'x': '\n::error::untrusted ##[warning]legacy'})
        self.assertTrue(rendered.startswith('INSPECT '))
        self.assertNotIn('::', rendered)
        self.assertNotIn('##[', rendered)
        recovered = json.loads(sanitized_line({'x': 'https://example.org/a?x=y"tail'})[8:])
        self.assertEqual(recovered['x'], 'https://example.org/a?[REDACTED_QUERY]"tail')
        nested = {'child': [{'error': str(i)} for i in range(30)], 'error': 'later'}
        self.assertEqual(len(diagnostics(nested)), 24)

    def test_metadata_refuses_identity_drift(self):
        pin = PINS[0]
        value = {'id': pin['id'], 'size_in_bytes': pin['bytes'], 'digest': 'sha256:' + pin['sha256'],
                 'expired': False, 'workflow_run': {'id': pin['run'], 'head_sha': pin['head'],
                 'repository_id': 1438763186, 'head_repository_id': 1438763186}}
        validate_metadata(value, pin)
        value['workflow_run']['head_sha'] = '0' * 40
        with self.assertRaises(Refusal):
            validate_metadata(value, pin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PreparationTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    start = int(os.environ.get('AGI_JOB_START_EPOCH', '0'))
    if not 0 <= time.time() - start < 360 * 60 - 300:
        raise Refusal('platform_start_missing_or_expired')
    token = os.environ.get('GITHUB_TOKEN', '')
    if not token or os.environ.get('GITHUB_REPOSITORY') != REPO:
        raise Refusal('same_repository_ephemeral_token_required')
    failed = False
    for pin in PINS:
        try:
            values = read_selected(download(pin, token), pin)
            print(sanitized_line({'kind': pin['kind'], 'artifact_id': pin['id'],
                                  'wrapper_sha256_verified': pin['sha256'], 'wrapper_bytes': pin['bytes'],
                                  'source_revision': pin['head'], 'run_id': pin['run']}, token), flush=True)
            for name, value in values.items():
                print(sanitized_line({'kind': pin['kind'], 'member': name,
                                      'data': value if pin['kind'] == 'wasi' else compact_model(value)}, token), flush=True)
        except Exception as error:
            failed = True
            # Never stringify network exceptions; they can embed signed URLs.
            detail = str(error) if isinstance(error, Refusal) else type(error).__name__
            print(sanitized_line({'kind': pin['kind'], 'inspection': 'FAIL', 'error': detail}, token), flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Refusal as error:
        print(sanitized_line({'inspection': 'FAIL', 'error': str(error)}), flush=True)
        raise SystemExit(1)
