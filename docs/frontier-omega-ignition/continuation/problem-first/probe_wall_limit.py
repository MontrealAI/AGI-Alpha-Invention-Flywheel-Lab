"""Use pinned real local inference to exercise the loopback total time allowance."""
import argparse
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('repo', 'assets', 'work'):
        parser.add_argument('--' + arg, type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve() / 'products/frontier-omega-ignition'))
    import qualify_live as q
    from field_trials import observe
    from ignition.provider import LocalProvider, ProviderUnavailable
    from qa import research_server

    work = args.work.resolve()
    work.mkdir(mode=0o700)
    record = {'source': q.checked_source(), 'runtime': q.runtime_source(), 'hardware': observe.hardware(),
              'scope': 'Actual pinned CPU stream interrupted by the workbench wall limit. A short response checks continued use.'}
    record['hardware']['threads'] = min(4, record['hardware']['threads'])
    start = time.monotonic()
    keys = ('model', 'declared_model_sha256', 'wall_timeout_seconds', 'timeout_seconds', 'request_sha256',
            'response_sha256', 'status', 'error_code', 'usage', 'wall_seconds', 'application_model_calls')
    try:
        binary, weights = observe.prepare(args.assets.resolve(), work, record)
        with research_server.server(binary, weights, work, record) as port:
            def route(seconds, tokens):
                return LocalProvider('llama-cpp', q.MODEL_ALIAS, port, q.pinned.MODEL_SHA, output_tokens=tokens,
                                     timeout=30, wall_timeout=seconds, streaming=True, schema_output=True)

            short = route(1, 256)
            try:
                short.propose('choose_hypothesis', {'purpose': 'Diagnostic text. Do not perform work. '
                                                   + 'Time limit test. ' * 650, 'candidates': []})
            except ProviderUnavailable as failure:
                wire = short.receipts[-1]
                record['short_allowance'] = {key: wire[key] for key in keys if key in wire}
                assert 'PROVIDER_WALL_LIMIT' in str(failure) and wire['response_sha256'] is None
                assert wire['wall_seconds'] <= 1.5
            else:
                raise AssertionError('The workbench accepted a late response.')
            adequate = route(60, 128)
            result = adequate.propose('choose_hypothesis', {'purpose': 'Abstain. No candidate has been provided.',
                                                            'candidates': []})
            wire = adequate.receipts[-1]
            record['adequate_allowance'] = {key: wire[key] for key in keys if key in wire}
            assert result == {'choice': 'abstain'}
            record['passed'] = True
    finally:
        record['wall_seconds'] = round(time.monotonic() - start, 3)
        (work / 'receipt.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
