"""Build the cycle007 evidence edition with the existing qualified publisher."""
import argparse
import json
from pathlib import Path

from build_cycle006_paper import build


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--markdown', default='docs/research/cycle-007.md')
    parser.add_argument('--manifest', default='docs/research/cycle-007.inputs.json')
    parser.add_argument('--output', default=str(Path(__file__).resolve().parents[1] / 'docs/research/cycle-007'))
    args = parser.parse_args()
    source = Path(args.markdown).read_text()
    if any(marker in source for marker in ('DENOVO_RESULT_PENDING', 'RETENTION_RESULT_PENDING', 'FINAL_RESOURCE_AND_PACKAGE_RESULT_PENDING', 'CONNECTED_COMMAND_PENDING')):
        raise ValueError('INCOMPLETE_CYCLE007_EDITION')
    print(json.dumps(build(args.markdown, args.manifest, args.output), indent=2))
