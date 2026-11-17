"""Run from the IGNITION product root: python -m frontier_study [--mission file]."""
import argparse
import json
from pathlib import Path

from . import default_mission, investigate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mission", type=Path, help="JSON mission with question, outcome, requirements, permissions and cutoff")
    parser.add_argument("--previous", type=Path, help="Prior report for the watch transition")
    args = parser.parse_args()
    mission = json.loads(args.mission.read_text()) if args.mission else default_mission()
    previous = json.loads(args.previous.read_text()) if args.previous else None
    print(json.dumps(investigate(mission, previous=previous), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
