#!/usr/bin/env python3
"""Start FRONTIER Ω with its twelve-dossier inventory. No paid API or credentials."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    from frontier_omega.workbench import main
    if '--seed' not in sys.argv:
        for name in ('public-opportunities-20261116.json', 'expanded-opportunities-20261116.json'):
            sys.argv.extend(['--seed', str(ROOT / 'examples/frontier-omega' / name)])
    if '--sources' not in sys.argv:
        sys.argv.extend(['--sources', str(ROOT / 'examples/frontier-omega/workbench-release-sources.json')])
    main()
