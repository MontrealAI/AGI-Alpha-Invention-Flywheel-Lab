"""Run from products/frontier-omega-ignition with python3 -m ignition."""
import argparse
import json
import sys
import uuid
from pathlib import Path

from . import commercial_handoff
from .controller import Controller
from .server import Service
from .store import StateError, Store, strict_json


def main():
    parser = argparse.ArgumentParser(prog="python3 -m ignition")
    parser.add_argument("--state", default="~/.frontier-ignition", help="private local mission directory")
    parser.add_argument("--assisted", nargs=2, metavar=("PROVIDER","MODEL"),
                        help="enable an explicitly operator-assisted model exchange")
    sub = parser.add_subparsers(dest="command",required=True)
    campaign = sub.add_parser("pursue", help="run a frozen shortlist through construction, checking and local commercial handoff")
    campaign.add_argument("shortlist", type=Path)
    campaign.add_argument("--request-id", required=True, help="stable private pursuit identity, also used on restart")
    campaign.add_argument("--reuse-from", help="prior local pursuit with an unchanged verified negative quantum result")
    commercial_handoff.register_cli(sub)
    control = sub.add_parser("control", help="pause, resume or permanently stop a mission")
    control.add_argument("id")
    control.add_argument("operation", choices=("pause", "resume", "stop"))
    control.add_argument("--version", type=int, required=True)
    control.add_argument("--sequence", type=int, help="last seen operation sequence")
    control.add_argument("--reason", default="")
    sub.add_parser("inventory")
    edition = sub.add_parser("reading-edition", help="build a local page-linked reading edition")
    edition.add_argument("--pdf", type=Path, required=True)
    edition.add_argument("--source", type=Path, required=True)
    edition.add_argument("--output", type=Path, required=True, help="new local recipient directory")
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8784)
    serve.add_argument("--recover", action="store_true", help="resume active queued or interrupted revisions within their existing grants")
    p = sub.add_parser("start")
    p.add_argument("file",type=Path)
    p.add_argument("--request-id",default=None)
    for cmd in ("show","resume","respond","approve","choose","export","amend","try","history","successor"):
        p = sub.add_parser(cmd)
        p.add_argument("id")
        if cmd in {"respond","amend","try","export","successor","approve"}:
            p.add_argument("file",type=Path)
        if cmd == "choose":
            p.add_argument("choice", help="registered mapping ID or abstain")
        if cmd in {"respond","approve","choose"}:
            p.add_argument("--sha256",required=True)
        if cmd in {"amend","resume","respond","approve","choose","try","export","successor"}:
            p.add_argument("--version",type=int,required=True)
        if cmd == "successor":
            p.add_argument("--rights",required=True)
        if cmd in {"amend","successor"}:
            p.add_argument("--request-id",required=True)
    args = parser.parse_args()
    cmd = args.command
    if cmd == "reading-edition":
        from reading_room.edition import build
        summary = build(args.pdf, args.source, args.output)
        print(json.dumps({"directory": str(args.output), **summary}, ensure_ascii=False, indent=2))
        return
    ctrl = Controller(Store(args.state),assisted=args.assisted)
    if cmd == "serve":
        with Service(ctrl, args.port, recover=args.recover) as server:
            print(f"FRONTIER Ω IGNITION  http://127.0.0.1:{server.server_port}  |  {ctrl.identity()['mode']}",flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        return
    if cmd == "pursue":
        from .pursuit import pursue
        value = pursue(ctrl, args.shortlist, args.request_id, reuse_from=args.reuse_from)
    elif cmd == "control":
        value = ctrl.set_operation(args.id, args.version, args.operation, args.reason,
                                   expected_sequence=args.sequence)
        if args.operation == "resume":
            value = ctrl.advance(args.id, args.version)
    elif cmd == "commercial":
        value = commercial_handoff.dispatch_cli(args, ctrl)
    elif cmd == "inventory":
        value = list(ctrl.store.inventory())
    elif cmd in {"start","amend","successor"}:
        doc = strict_json(args.file.read_bytes())
        body = {k:doc[k] for k in ("mission","sources") if k in doc}
        body["request_id"] = args.request_id or uuid.uuid4().hex
        if cmd == "amend":
            body["version"] = args.version
        if cmd == "successor":
            rid,version = ctrl.successor(args.id,args.version,body,args.rights)
        else:
            rid, version = ctrl.create(body,getattr(args,"id",None))
        value = ctrl.advance(rid,version)
    elif cmd == "show":
        value = ctrl.view(args.id)
    elif cmd == "history":
        value = [ctrl.public(s) for s in ctrl.store.history(args.id)]
    elif cmd == "export":
        data = ctrl.deliver(args.id,args.version)
        with args.file.open("xb") as f:
            f.write(data)
        value = {"saved":str(args.file),"bytes":len(data)}
    elif cmd == "try":
        value = ctrl.deliver(args.id,args.version,strict_json(args.file.read_bytes()),trial=True)
    else:
        if cmd == "choose":
            ctrl.intervene(args.id,args.version,cmd,{"sha256":args.sha256,"choice":args.choice})
        if cmd == "respond":
            ctrl.intervene(args.id,args.version,cmd,{"sha256":args.sha256,"response":strict_json(args.file.read_bytes())})
        if cmd == "approve":
            ctrl.intervene(args.id,args.version,cmd,{"contract_sha256":args.sha256,
                                                      "confirmations":strict_json(args.file.read_bytes())})
        value = ctrl.advance(args.id,args.version)
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    try:
        main()
    except (StateError, ValueError, OSError) as exc:
        sys.exit(str(exc))
