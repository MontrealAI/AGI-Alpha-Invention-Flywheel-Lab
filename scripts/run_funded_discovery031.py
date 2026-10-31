"""Explicit opt-in synthetic research smoke; no customer/business launch."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.finance import JournalAccount
from connected_enterprise.funded_discovery031 import run_research


def campaign():
    # A disposable synthetic account, not a reset or clone of an operating one.
    with tempfile.TemporaryDirectory(prefix='funded-discovery031-') as directory:
        directory = Path(directory)
        root = directory / 'source'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('__pycache__', '*inputs*', '.git'))
        manifest = prepare_services(root, 'discovery031-inputs', cohort_seed=311031)
        account = JournalAccount(root, manifest, directory / 'research.sqlite',
                                 opening=100_000_000, working=1_000_000,
                                 contract='discovery031-synthetic-research')
        try:
            result = run_research(root, account, directory / 'study', ident='study031',
                                  enabled=True, allow_seed=True)
            paid = [entry for entry in account.export()['connected_journal']['entries']
                    if entry['status'] == 'COMPLETE']
            if sum(entry['request']['amount'] for entry in paid) != result['native_cost_microUSD']:
                raise ValueError('STUDY_COST_RECONCILIATION_FAILED')
            result['paid_operations'] = len(paid)
            result['native_audit'] = account.audit()
            # Only compact inert evidence leaves the temporary directory.
            return result
        finally:
            account.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = campaign()
    with Path(args.output).open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'cases': len(report['rows']), 'accepted': sum(x['accepted'] for x in report['rows']),
                      'native_cost_microUSD': report['native_cost_microUSD'], 'actual_profit': None}))
