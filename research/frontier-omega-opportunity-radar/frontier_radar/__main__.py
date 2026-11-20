"""CLI. No message transport is configured; exports are for review only."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from . import core, ingest, replay, shadow, triage


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--db", type=Path, default=Path(".frontier-radar.sqlite3"))
    cli.add_argument("--as-of", help="ISO-8601 time with timezone; never use to backdate collection")
    commands = cli.add_subparsers(dest="command", required=True)
    for name in ("atlas", "briefing", "alerts", "replay", "health", "leads", "revisits"):
        commands.add_parser(name)
    fetch = commands.add_parser("collect")
    fetch.add_argument("--source", action="append", choices=sorted(ingest.SOURCES))
    poll = commands.add_parser("shadow")
    poll.add_argument("--source", action="append", choices=sorted(ingest.SOURCES))
    commands.add_parser("drafts")
    commands.add_parser("decisions")
    args = cli.parse_args()
    now = core.instant(args.as_of) if args.as_of else datetime.now(timezone.utc)
    if args.command == "collect":
        if args.as_of:
            cli.error("Collection must record observed wall-clock time.")
        print(json.dumps(ingest.run(args.db, args.source), indent=2, ensure_ascii=False))
        return
    if args.command == "health":
        print(json.dumps(ingest.health(args.db), indent=2, ensure_ascii=False))
        return
    if args.command == "leads":
        print(json.dumps(ingest.observations(args.db), indent=2, ensure_ascii=False))
        return
    if args.command == "drafts":
        print(json.dumps(shadow.drafts(args.db), indent=2, ensure_ascii=False))
        return
    if args.command == "decisions":
        print(json.dumps(shadow.decisions(args.db), indent=2, ensure_ascii=False))
        return
    atlas, records = core.load_data()
    if args.command == "revisits":
        print(json.dumps(triage.route(ingest.observations(args.db), records), indent=2, ensure_ascii=False))
        return
    if args.command == "shadow":
        if args.as_of:
            cli.error("Shadow execution requires current wall-clock time.")
        print(json.dumps(shadow.run(args.db, atlas, records, now, source_ids=args.source), indent=2, ensure_ascii=False))
        return
    if args.command == "atlas":
        if args.as_of:
            payload = {"milestones": core.atlas_at(atlas, now), "mode": "as_of"}
        else:
            payload = atlas
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif args.command == "briefing":
        print(core.briefing(atlas, records, now, None if args.as_of else ingest.health(args.db)), end="")
    elif args.command == "replay":
        print(json.dumps(replay.run(atlas, records, now), indent=2, ensure_ascii=False))
    else:
        decisions = [core.assess(r, now) for r in records]
        drafts = [core.alert_text(r, d) for r, d in zip(records, decisions) if d["alert"]]
        print(json.dumps({"mode": "preview_only", "decisions": decisions, "drafts": drafts},
                         indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
