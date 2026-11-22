"""Refuse absent original authority before canonical code can create anything."""
from pathlib import Path


def require_existing(path):
    path = Path(path).absolute()
    suffixes = ('', '.actions.jsonl', '.persistence.json',
                '.adaptive-simulation-key', '.connected-journal.json')
    for suffix in suffixes:
        file = path.with_name(path.name + suffix)
        if not file.is_file() or file.is_symlink() or any(p.is_symlink() for p in file.parents):
            raise ValueError('ORIGINAL_ACCOUNT_AUTHORITY_REQUIRED_NO_RESEED')
    return path


def open_existing(root, manifest, path, *, opening, working, contract):
    from enterprise078.native import BusinessAccount
    return BusinessAccount(root, manifest, require_existing(path), opening=opening,
                           working=working, contract=contract)
