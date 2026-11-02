"""Fixed public closure for the retained numerical research checkpoint.

Inventory inclusion grants no scientific or commercial qualification. New files
require an explicit inventory change; local datasets and runtime state never
enter this closure through directory discovery.
"""
from pathlib import Path


EXPERIMENT = 'experiments/capability_transfer_20261102'
MEMBERS = (
    'ACQUISITION_HISTORY.md',
    'AGENTS.md',
    'CLAIM_CORRECTIONS.md',
    'DATA_ACCESS_OPTIONS.md',
    'EXECUTION_HISTORY.md',
    'FROZEN_STAGE_B.json',
    'FROZEN_STAGE_B_SERIALIZATION_FIX.json',
    'INDEPENDENT_NUMERICAL_REVIEW.md',
    'OPPORTUNITIES.md',
    'PREREGISTRATION.md',
    'PROTOCOL_FACTS.md',
    'PUBLIC_COST_AUDIT.md',
    'README.md',
    'RESEARCH_COST_ENVELOPE.json',
    'STAGE_B.md',
    'STAGE_C.md',
    'economics.py',
    'fetch_catalog.py',
    'instrument.py',
    'plot_result.py',
    'release_inventory.py',
    'results/CAPABILITY_ORIGINAL.json',
    'results/CATALOG_ATTEMPT_3.json',
    'results/CURRENT_DECISION.json',
    'results/MANIFEST.json',
    'results/MIDPOINT_DIAGNOSTIC.json',
    'results/RESEARCH_ACCOUNT_AUDIT.json',
    'results/RESEARCH_ACCOUNT_PUBLIC.json.gz',
    'results/RESEARCH_REGISTRATION.json',
    'results/STAGE_B_RESULT.json',
    'results/midpoint.svg',
    'run_midpoint_diagnostic.py',
    'run_stage_b.py',
    'test_catalog.py',
    'test_economics.py',
    'test_instrument.py',
    'test_release_inventory.py',
    'verifier.py',
)
SOURCE_PATHS = tuple(EXPERIMENT + '/' + name for name in MEMBERS) + (
    '.github/workflows/capability-transfer.yml',
)


def source_paths(root):
    """Require the entire reviewed closure; refuse missing or linked members."""
    root = Path(root)
    for name in SOURCE_PATHS:
        path = root / name
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('CAPABILITY_TRANSFER_PUBLIC_SOURCE_REQUIRED:' + name)
    return SOURCE_PATHS
