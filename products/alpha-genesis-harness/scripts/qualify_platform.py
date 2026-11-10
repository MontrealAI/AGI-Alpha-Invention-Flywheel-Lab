#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run exact-archive core/launcher/browser checks on the actual host OS."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

from package_release import MAX_ARCHIVE, verify_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--expected-source-revision', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--visual-modules', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    system = platform.system()
    receipt = {'status': 'FAIL', 'source_revision': args.expected_source_revision,
               'archive_sha256': args.expected_sha256, 'host': platform.platform(),
               'python': platform.python_version(), 'operations': [],
               'scope': 'Actual hosted OS: extracted archive integrity, JavaScript engine, native launcher help, Python loopback startup and headless browser first use. No full cross-platform Python/security suite, authenticated model, signed installer or Finder/Explorer double-click qualification.'}
    try:
        if args.archive.stat().st_size >= MAX_ARCHIVE:
            raise ValueError('Archive exceeds the processing envelope')
        data = args.archive.read_bytes()
        if hashlib.sha256(data).hexdigest() != args.expected_sha256:
            raise ValueError('Archive SHA-256 differs from trusted build output')
        manifest = verify_snapshot(data, expected_sha256=args.expected_sha256,
                                   expected_source_revision=args.expected_source_revision)
        if manifest.get('build_mode') != 'source-bound' or not manifest.get('source_claim_matches_commit'):
            raise ValueError('Expected a source-bound archive')
        with tempfile.TemporaryDirectory(prefix='harness-platform-') as folder:
            with zipfile.ZipFile(io.BytesIO(data)) as bundle:
                bundle.extractall(folder)
            roots = list(Path(folder).iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise ValueError('Expected one product root')
            product = roots[0]
            modules = args.visual_modules.resolve(strict=True)
            expected = json.loads((product / 'tests/visual/package.json').read_text())['dependencies']['playwright-core']
            actual = json.loads((modules / 'playwright-core/package.json').read_text())['version']
            if actual != expected:
                raise ValueError('Browser dependency differs from exact packaged requirement')
            browser_candidates = ([Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')] if system == 'Darwin' else [])
            if system == 'Windows':
                browser_candidates += [Path(os.environ.get(name, root)) / 'Google/Chrome/Application/chrome.exe'
                                       for name, root in [('PROGRAMFILES', 'C:/Program Files'), ('PROGRAMFILES(X86)', 'C:/Program Files (x86)'), ('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))]]
            for name in ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']:
                found = shutil.which(name)
                if found:
                    browser_candidates.append(Path(found))
            browser = next((candidate for candidate in browser_candidates if candidate.is_file()), None)
            if browser is None:
                raise ValueError('No supported Chrome/Chromium executable found on this host')
            env = {key: os.environ[key] for key in ('PATH', 'PATHEXT', 'COMSPEC', 'SYSTEMROOT', 'WINDIR', 'HOME', 'USERPROFILE', 'LOCALAPPDATA') if key in os.environ}
            runtime_temp = Path(folder).resolve() / 'runtime-temp'
            runtime_temp.mkdir()
            env.update({name: str(runtime_temp) for name in ('TEMP', 'TMP', 'TMPDIR')})
            env.update({'PYTHON': sys.executable, 'NODE_PATH': str(modules), 'CHROME_BIN': str(browser),
                        'EXPECTED_SOURCE': args.expected_source_revision, 'HARNESS_SCREENSHOT_DIR': str(output),
                        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'LANG': 'C.UTF-8'})
            tests = sorted(str(item.relative_to(product)) for item in (product / 'tests').glob('*.test.cjs'))
            if not tests:
                raise ValueError('Missing engine acceptance tests')
            launcher = ([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', 'Launch-HARNESS.cmd', '--help']
                        if system == 'Windows' else ['sh', str(product / ('Launch-HARNESS.command' if system == 'Darwin' else 'Launch-HARNESS.sh')), '--help'])
            commands = [['node', '--test', *tests], launcher, ['node', 'evidence/UI_BROWSER_REPLAY.cjs']]
            for number, command in enumerate(commands, 1):
                result = subprocess.run(command, cwd=product, env=env, stdin=subprocess.DEVNULL,
                                        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
                (output / f'{system}-operation-{number}.stdout.txt').write_text(result.stdout, encoding='utf-8')
                (output / f'{system}-operation-{number}.stderr.txt').write_text(result.stderr, encoding='utf-8')
                receipt['operations'].append({'command': command, 'returncode': result.returncode})
                if result.returncode:
                    raise ValueError(f'Operation {number} failed; inspect preserved logs')
                if number == 2 and ('usage:' not in result.stdout or '--workspace' not in result.stdout):
                    raise ValueError('Native launcher did not emit the actual connector help')
            browser_report = json.loads((output / 'BROWSER-VERIFICATION.json').read_text(encoding='utf-8'))
            expected_platform = {'Darwin': 'darwin', 'Windows': 'win32', 'Linux': 'linux'}.get(system)
            if (not isinstance(browser_report, dict) or browser_report.get('status') != 'PASS'
                    or browser_report.get('source_revision') != args.expected_source_revision
                    or browser_report.get('platform') != expected_platform or browser_report.get('errors') != []):
                raise ValueError('Browser receipt does not establish a successful matching-source host operation')
            receipt['browser_report'] = browser_report
            receipt['status'] = 'PASS'
    except Exception as error:
        receipt['status'] = 'FAIL'
        receipt['error'] = str(error)
    finally:
        # Unique names allow immutable OS evidence to share a release asset directory.
        for item in list(output.glob('HARNESS-*.png')):
            item.rename(item.with_name(system + '-' + item.name))
        report = output / 'BROWSER-VERIFICATION.json'
        if report.exists():
            report.rename(output / (system + '-BROWSER-VERIFICATION.json'))
        (output / ('PLATFORM-' + system + '-VERIFICATION.json')).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': receipt['status'], 'host': receipt['host'], 'error': receipt.get('error')}))
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
