"""Run FRONTIER Ω as a private, persistent sensor for the ALPHA Economic Engine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import threading

from .core import Reservoir, load_file


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("./frontier-omega-private"),
                   help="Private state directory (0700). Never commit buyer data.")
    sub = p.add_subparsers(dest="cmd", required=True)
    seed = sub.add_parser("seed", help="Import public opportunity dossiers and capability observations")
    seed.add_argument("--file", type=Path, required=True)
    add = sub.add_parser("add", help="Add one problem, capability or reported trial JSON record")
    add.add_argument("--file", type=Path, required=True)
    show = sub.add_parser("list", help="List immutable records from a chosen table")
    show.add_argument("table", choices=("problems", "frontiers", "trials", "triggers"))
    sub.add_parser("scan", help="Read private inbox/*.json into the persistent reservoir")
    watch = sub.add_parser("watch", help="Continuously ingest private inbox and emit retest signals")
    watch.add_argument("--interval", type=float, default=5.0)
    watch.add_argument("--cycles", type=int, help="Optional finite qualification run")
    compare = sub.add_parser("compare", help="Matched historical versus new reported trial comparison")
    compare.add_argument("--problem", required=True)
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)
    sub.add_parser("report", help="Emit readable machine JSON report; contains no earned money claim")
    browser = sub.add_parser("dashboard", help="Build a private, searchable browser inventory")
    browser.add_argument("--name", default="FRONTIER-OMEGA.html", help="Filename within private state directory")
    sub.add_parser("audit", help="Audit local hash records and relationships")
    args = p.parse_args()
    if getattr(args, "cycles", None) is not None and args.cycles < 1:
        p.error("--cycles must be >= 1")
    machine = Reservoir(args.root)
    if args.cmd == "seed":
        result = machine.seed(load_file(args.file))
    elif args.cmd == "add":
        result = machine.add(load_file(args.file))
    elif args.cmd == "list":
        result = machine.rows(args.table)
    elif args.cmd == "scan":
        with machine.lock():
            result = {"receipts": machine.ingest_inbox(), "counts": machine.report()["counts"]}
    elif args.cmd == "watch":
        stop = threading.Event()
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        result = machine.watch(args.interval, args.cycles, stop.is_set)
    elif args.cmd == "compare":
        result = machine.compare(args.problem, args.before, args.after)
    elif args.cmd == "dashboard":
        from .dashboard import write_dashboard
        with machine.lock():
            result = write_dashboard(machine, args.name)
    elif args.cmd == "audit":
        with machine.lock():
            result = machine.audit()
    else:
        result = machine.report()
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
