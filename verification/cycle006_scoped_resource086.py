"""Prospective opt-in cycle006 resource observer; frozen worker and historical failures untouched."""
from __future__ import annotations
import argparse
import errno
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys

ORIGINAL_GUARD_SHA256 = '8a10193e2cc29ca277560c7b2153d616e8cb46e64fbc7f54c102518dc2b71cbd'
ALLOWED = frozenset(
    'artifacts/' + family + '-conditional-settlement/' + base + '.sqlite-journal'
    for family in ('norman', 'wessels')
    for base in ('same-artifact-cohort', 'liquidity-deferral')
)
RUN_ID = 'cycle006-connected-reproduction'

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

class Observer:
    def __init__(self, output: Path):
        self.output = Path(output).absolute()
        self.vanished = 0
        self.examples: list[str] = []

    def sizes(self, output: Path) -> list[int]:
        if Path(output).absolute() != self.output:
            raise ValueError('CYCLE006_OBSERVER_ROOT_MISMATCH')
        counts = []
        for entry in self.output.rglob('*'):
            try:
                info = entry.lstat()
            except FileNotFoundError as error:
                relative = entry.relative_to(self.output).as_posix()
                if error.errno != errno.ENOENT or relative not in ALLOWED:
                    raise
                # An enumerated SQLite rollback journal may vanish at commit.
                # Never ignore a missing database, result or unregistered file.
                db = entry.with_name(entry.name.removesuffix('-journal'))
                if not stat.S_ISREG(db.lstat().st_mode):
                    raise ValueError('CYCLE006_JOURNAL_WITHOUT_REGULAR_DATABASE')
                self.vanished += 1
                if len(self.examples) < 8:
                    self.examples.append(relative)
                continue
            if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                counts.append(info.st_size)
        return counts

    def finish(self, receipt: dict, output: Path) -> dict:
        sizes = self.sizes(output) if Path(output).is_dir() else []
        boundary = receipt['observer086']
        boundary['vanished_journal_enoent_observations'] = self.vanished
        boundary['examples'] = self.examples.copy()
        base = sum(sizes)
        for _ in range(12):
            encoded = len((json.dumps(receipt, indent=2, allow_nan=False) + '\n').encode())
            receipt['output_bytes'] = base + encoded
            overrun = None
            if receipt['output_bytes'] > receipt['limits']['storage_bytes']:
                overrun = 'final-aggregate-output-storage-limit'
            elif max([encoded, *sizes]) > receipt['limits']['output_bytes']:
                overrun = 'final-output-file-limit'
            elif receipt['waited_cpu_seconds'] > receipt['limits']['cpu_seconds']:
                overrun = 'final-observed-cpu-limit'
            elif receipt['wall_seconds'] > receipt['limits']['wall_seconds']:
                overrun = 'final-wall-limit'
            if overrun and receipt['state'] != 'interrupted':
                receipt['state'], receipt['reason'] = 'overrun', overrun
            updated = len((json.dumps(receipt, indent=2, allow_nan=False) + '\n').encode())
            if receipt['output_bytes'] == base + updated:
                break
        return receipt

def prospective_run(frozen_root: Path, command, output, ledger, run_id, limits, cwd=None):
    """Load exact v3 privately; preserve its reservation, guards and cleanup."""
    if run_id != RUN_ID:
        raise ValueError('CYCLE006_UNREGISTERED_RUN_ID')
    frozen_root = Path(frozen_root).resolve()
    guard_path = frozen_root / 'experiments/resource006_v3.py'
    if guard_path.is_symlink() or sha(guard_path.read_bytes()) != ORIGINAL_GUARD_SHA256:
        raise ValueError('CYCLE006_HISTORICAL_GUARD_IDENTITY')
    observer = Observer(output)
    spec = importlib.util.spec_from_file_location('_cycle006_private_historical_guard086', guard_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    original_write = guard._write
    boundary = {
        'schema': 'agi-alpha/cycle006-scoped-monitor086/v1',
        'adapter_sha256': sha(Path(__file__).read_bytes()),
        'historical_guard_sha256': ORIGINAL_GUARD_SHA256,
        'allowed_vanishing_paths': sorted(ALLOWED),
        'vanished_journal_enoent_observations': 0,
        'examples': [],
        'scope': 'Prospective opt-in observer only; four exact journal ENOENT paths '
                 'with extant native regular DB. No changes to frozen worker, '
                 'allocation, resource bounds, accounting or cleanup.'
    }

    def write(path, value):
        if value.get('schema') == 'agi-alpha/trusted-experiment-run006/v3':
            value['observer086'] = dict(boundary)
            value['observer086']['vanished_journal_enoent_observations'] = observer.vanished
            value['observer086']['examples'] = observer.examples.copy()
        original_write(path, value)

    def terminal(receipt, output_path):
        receipt['observer086'] = dict(boundary)
        return observer.finish(receipt, output_path)

    guard._write = write
    guard._usage = lambda output_path: sum(observer.sizes(output_path))
    guard._final_receipt = terminal
    return guard.run(command, output, ledger, run_id, limits, cwd)

def run_frozen(frozen_root: Path, output: Path) -> int:
    """Authenticate full pinned source before adapting outer monitor only."""
    frozen_root = Path(frozen_root).resolve()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    runner_path = frozen_root / 'run_cycle006.py'
    if runner_path.is_symlink():
        raise ValueError('CYCLE006_FROZEN_RUNNER_SYMLINK')
    spec = importlib.util.spec_from_file_location('_cycle006_exact_runner086', runner_path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.source_identity(frozen_root, frozen_root / runner.FREEZE)
    sys.path.insert(0, str(frozen_root))
    try:
        import experiments
        old = getattr(experiments, 'resource006_v3', None)
        class Selected:
            @staticmethod
            def run(command, out, ledger, run_id, limits, cwd=None):
                return prospective_run(frozen_root, command, out, ledger, run_id, limits, cwd)
        experiments.resource006_v3 = Selected()
        try:
            return int(runner.main(['--output', str(output)]) or 0)
        finally:
            if old is None:
                del experiments.resource006_v3
            else:
                experiments.resource006_v3 = old
    finally:
        sys.path.remove(str(frozen_root))

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    return run_frozen(args.frozen_root, args.output)

if __name__ == '__main__':
    raise SystemExit(main())
