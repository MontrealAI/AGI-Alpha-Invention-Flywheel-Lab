#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Start the shipped local application without installing dependencies or models."""
from pathlib import Path
import runpy
import sys


def main():
    if sys.version_info < (3, 10):
        print("Python 3.10 or later is required. / Python 3.10 ou ultérieur est requis.", file=sys.stderr)
        return 1
    product = Path(__file__).resolve().parent
    server = product / "bridge" / "server.py"
    if not server.is_file() or server.is_symlink():
        print("Extract the complete trusted download first. / Décompressez le téléchargement complet.", file=sys.stderr)
        return 1
    sys.path.insert(0, str(server.parent))
    sys.argv[0] = str(server)
    runpy.run_path(str(server), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
