"""Adapter to the repository's authoritative simulation; never a second ledger."""
from __future__ import annotations
import hashlib
import importlib
from pathlib import Path
import shutil
import sys
from .common import regular


class Backend:
    def __init__(self, repo: Path):
        self.repo = Path(repo).absolute()
        regular(self.repo / 'connected_enterprise/finance.py')
        for prefix in ('commercial', 'adaptive_enterprise', 'connected_enterprise', 'enterprise', 'vendor', 'portfolio25'):
            for name, module in list(sys.modules.items()):
                if name == prefix or name.startswith(prefix + '.'):
                    location = getattr(module, '__file__', None)
                    if location and not Path(location).resolve().is_relative_to(self.repo.resolve()):
                        raise ValueError('NATIVE_MODULE_FROM_DIFFERENT_CHECKOUT:' + name)
        sys.path.insert(0, str(self.repo))
        self.finance = importlib.import_module('connected_enterprise.finance')
        self.substrate = importlib.import_module('adaptive_enterprise.instruments')
        self.checker = importlib.import_module('adaptive_enterprise.checkers').audit_delivery
        self.names = sorted(set(self.finance.SOURCE_PATHS) | set(self.substrate.SOURCE_PATHS))

    def identity(self):
        return {name: hashlib.sha256(regular(self.repo / name).read_bytes()).hexdigest() for name in self.names}

    def prepare(self, runtime: Path, seed: int, cycles: int):
        # Bootstrap is distinct from live-account recovery. No money exists here.
        for name in self.names:
            target = runtime / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(regular(self.repo / name), target)
        count = max(32, 16 + cycles * 2)
        return self.substrate.prepare_services(runtime, 'services', cohort_seed=seed, jobs_per_service=count)

    def account(self, runtime, manifest, output, config):
        return self.finance.JournalAccount(runtime, manifest, output / 'account.sqlite',
            opening=config['opening_cents'] * 10_000,
            working=config['working_reserve_cents'] * 10_000,
            contract='genesis002-registered-synthetic-enterprise-v1')
