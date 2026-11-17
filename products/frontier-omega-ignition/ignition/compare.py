# SPDX-License-Identifier: Apache-2.0
"""Run a dated matched comparison with a frozen contract and two attributed arms."""
import argparse
import json
from pathlib import Path

from .research import assess_comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    opts = parser.parse_args()
    inputs = [json.loads(path.read_text(encoding="utf-8")) for path in (opts.protocol, opts.before, opts.after)]
    print(json.dumps(assess_comparison(*inputs), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
