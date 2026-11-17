"""ALPHA × FRONTIER Ω: continuous qualified-order ignition, not an auto-sale generator.

Uses existing ALPHA production/payment engine and FRONTIER Ω source records.
The configured external adapters retain their independent payment, customer,
cost reconciliation and owner permission gates. No API keys are supplied.
"""
from __future__ import annotations
import argparse
import json
import signal
import threading
from pathlib import Path
from frontier_omega.core import Reservoir
from .__main__ import build, secret, doctor
from .core import read
from .frontier_bridge import admission_preflight, submit_qualified
from .frontier_intake import QualifiedInbox


def _keys(config):
    return {buyer: secret(env).encode() for buyer, env in config["buyer_key_env"].items()}


def ignite(engine, reservoir, poll, *, cycles=None):
    """One supervised process: frontier event inbox + commercial inbox + ALPHA.

    Private JSON files are supplied by buyer-authorized adapters; the sensor
    cannot turn a public announcement into authenticated consent.
    """
    if cycles is not None and (type(cycles) is not int or cycles < 1):
        raise ValueError("POSITIVE_IGNITION_CYCLES_REQUIRED")
    stop = threading.Event()
    errors = []
    inbox = QualifiedInbox(engine, reservoir)
    def worker(fn):
        try:
            fn()
        except BaseException as exc:
            errors.append({"type": type(exc).__name__, "message": str(exc)[:200]})
            stop.set()
    sensor = threading.Thread(
        name="frontier-source-inbox", daemon=True,
        target=lambda: worker(lambda: reservoir.watch(
            interval=poll, stopped=stop.is_set)))
    converter = threading.Thread(
        name="frontier-qualified-inbox", daemon=True,
        target=lambda: worker(lambda: inbox.watch(
            interval=poll, stopped=stop.is_set)))
    old_signals = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            old_signals[sig] = signal.getsignal(sig)
            signal.signal(sig, lambda *_: stop.set())
    sensor.start()
    converter.start()
    try:
        # Existing economic worker owns its own exclusive lock and accounts.
        report = engine.run(watch=True, poll=poll, max_ticks=cycles, stop=stop)
    finally:
        stop.set()
        sensor.join(timeout=10)
        converter.join(timeout=10)
        for sig, previous in old_signals.items():
            signal.signal(sig, previous)
        if sensor.is_alive() or converter.is_alive():
            raise RuntimeError("FRONTIER_WORKER_FAILED_TO_STOP")
    if errors:
        raise RuntimeError("FRONTIER_WORKER_FAILED: " + json.dumps(errors))
    return {
        "status": "STOPPED_AFTER_SUPERVISED_RUN",
        "source_sensor": "LOCAL_EVENT_INGESTION_NO_LIVE_WEB_CRAWLING",
        "buyer_handoff": "AUTHORIZED_REGISTERED_REQUESTS_ONLY",
        "financial_scope": engine.policy["scope"],
        "engine": report,
        "real_payment_established_by_ignition": False
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", required=True, type=Path)
    parser.add_argument("--reservoir-root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    sub = parser.add_subparsers(dest="cmd", required=True)
    preview = sub.add_parser("preflight")
    preview.add_argument("--bundle", required=True, type=Path)
    submit = sub.add_parser("submit")
    submit.add_argument("--bundle", required=True, type=Path)
    sub.add_parser("intake-once")
    fire = sub.add_parser("ignite")
    fire.add_argument("--poll", type=float, default=5.0)
    fire.add_argument("--max-cycles", type=int)
    sub.add_parser("status")
    sub.add_parser("doctor")
    args = parser.parse_args()
    cfg = read(args.config)
    if args.cmd == "doctor":
        result = {
            "alpha_engine": doctor(cfg),
            "conversion": "NO_PURCHASE_FROM_FRONTIER_SIGNAL_ALONE",
            "external_payment_and_treasury_qualification": "NOT_EVALUATED_OFFLINE"
        }
    else:
        reservoir = Reservoir(args.reservoir_root)
        if args.cmd == "preflight":
            result = admission_preflight(
                reservoir, read(args.bundle), _keys(cfg))
        elif args.cmd == "status":
            from .store import State
            result = {
                "frontier": reservoir.report()["counts"],
                "alpha": State(args.engine_root, cfg["policy"]).summary(),
                "financial_authority_added": False
            }
        else:
            engine = build(args.engine_root, cfg)
            try:
                if args.cmd == "submit":
                    receipt = submit_qualified(engine, reservoir, read(args.bundle))
                    result = dict(receipt, frontier_link_receipt=str(receipt["frontier_link_receipt"]))
                elif args.cmd == "intake-once":
                    worker = QualifiedInbox(engine, reservoir)
                    with worker.lock():
                        result = worker.scan()
                else:
                    if args.poll < .05:
                        parser.error("--poll must be >= 0.05 seconds")
                    result = ignite(engine, reservoir, args.poll, cycles=args.max_cycles)
            finally:
                engine.close()
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
