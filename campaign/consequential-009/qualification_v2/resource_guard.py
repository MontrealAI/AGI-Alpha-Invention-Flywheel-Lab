"""Current qualification adapter for a vanished native SQLite rollback journal.

The authenticated historical guard remains unchanged. Each call loads a private
copy; only storage enumeration and receipt provenance/accounting are adapted.
This is a trusted-command resource monitor, not a sandbox.
"""
import errno
import hashlib
import importlib.util
import json
from pathlib import Path
import stat

INHERITED_GUARD = '8a10193e2cc29ca277560c7b2153d616e8cb46e64fbc7f54c102518dc2b71cbd'
POLICY = '2424d01efa170aae95d52495b0b3138e77240a5ac5a01cf18975fb46301174a0'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class StorageScan:
    def __init__(self, output, allowed_journals=()):
        self.output = Path(output).absolute()
        self.allowed_journals = set(allowed_journals)
        self.vanished_count = 0
        self.vanished_examples = []

    def sizes(self, output):
        if Path(output).absolute() != self.output:
            raise ValueError('QUALIFICATION009_SCAN_ROOT')
        sizes = []
        for path in self.output.rglob('*'):
            try:
                info = path.lstat()
            except FileNotFoundError as error:
                relative = path.relative_to(self.output).as_posix()
                if error.errno != errno.ENOENT or relative not in self.allowed_journals:
                    raise
                # An enumerated native journal may vanish at SQLite commit.
                # No missing database, arbitrary file, permission or I/O error
                # receives this exception. Do not retry any financial action.
                database = path.with_name('exchange.sqlite').lstat()
                if not stat.S_ISREG(database.st_mode):
                    raise
                self.vanished_count += 1
                if len(self.vanished_examples) < 8:
                    self.vanished_examples.append(relative)
                continue
            if stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                sizes.append(info.st_size)
        return sizes


def _finish(receipt, output, scanner):
    """Same inherited fixed-point cap checks, using one lstat per entry."""
    sizes = scanner.sizes(output) if output.is_dir() else []
    receipt['qualification_boundary']['vanished_journal_enoent_observations'] = scanner.vanished_count
    receipt['qualification_boundary']['vanished_journal_examples'] = scanner.vanished_examples.copy()
    base = sum(sizes)
    for _ in range(12):
        encoded_bytes = len((json.dumps(receipt, indent=2, allow_nan=False) + '\n').encode())
        receipt['output_bytes'] = base + encoded_bytes
        overrun = None
        if receipt['output_bytes'] > receipt['limits']['storage_bytes']:
            overrun = 'final-aggregate-output-storage-limit'
        elif max([encoded_bytes, *sizes]) > receipt['limits']['output_bytes']:
            overrun = 'final-output-file-limit'
        elif receipt['waited_cpu_seconds'] > receipt['limits']['cpu_seconds']:
            overrun = 'final-observed-cpu-limit'
        elif receipt['wall_seconds'] > receipt['limits']['wall_seconds']:
            overrun = 'final-wall-limit'
        if overrun and receipt['state'] != 'interrupted':
            receipt['state'], receipt['reason'] = 'overrun', overrun
        updated_bytes = len((json.dumps(receipt, indent=2, allow_nan=False) + '\n').encode())
        if receipt['output_bytes'] == base + updated_bytes:
            break
    return receipt


def run(command, output, ledger, run_id, limits, cwd=None):
    root = Path(cwd).resolve()
    guard_path = root / 'experiments/resource006_v3.py'
    if sha(guard_path.read_bytes()) != INHERITED_GUARD:
        raise ValueError('QUALIFICATION009_INHERITED_GUARD_IDENTITY')
    policy_raw = (root / 'campaign/consequential-009/COMMERCIAL_POLICY.json').read_bytes()
    if sha(policy_raw) != POLICY:
        raise ValueError('QUALIFICATION009_POLICY_IDENTITY')
    worlds = json.loads(policy_raw)['buyer_worlds']
    allowed = {'artifacts/' + world['id'] + '/exchange.sqlite-journal' for world in worlds} if run_id == 'commerce' else set()
    scanner = StorageScan(output, allowed)
    boundary = {
        'schema': 'agi-alpha/consequential009-monitor-adapter/v2',
        'adapter_sha256': sha(Path(__file__).read_bytes()),
        'inherited_guard_sha256': INHERITED_GUARD,
        'authenticated_policy_sha256': POLICY,
        'scope': 'Current engineering qualification under an explicit versioned monitor; historical guard and financial execution source unchanged. Only enumerated native commerce rollback-journal ENOENT with an existing regular database may be omitted from that scan. No command or transaction retries.',
        'vanished_journal_enoent_observations': 0,
        'vanished_journal_examples': [],
    }
    spec = importlib.util.spec_from_file_location('_qualification009_private_guard', guard_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    # Private module only: no mutation of the canonical historical import.
    guard.__file__ = __file__
    inherited_write = guard._write

    def write(path, value):
        if value.get('schema') == 'agi-alpha/trusted-experiment-run006/v3':
            value['qualification_boundary'] = dict(boundary)
            value['qualification_boundary']['vanished_journal_enoent_observations'] = scanner.vanished_count
            value['qualification_boundary']['vanished_journal_examples'] = scanner.vanished_examples.copy()
        inherited_write(path, value)

    guard._write = write
    guard._usage = lambda path: sum(scanner.sizes(path))
    guard._final_receipt = lambda receipt, path: _finish(receipt, path, scanner)
    return guard.run(command, output, ledger, run_id, limits, cwd)
