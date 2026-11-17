"""Run from products/frontier-omega-ignition with python3 -m ignition."""
import argparse
import json
import sys
import uuid
from pathlib import Path

from .controller import Controller
from .server import Service
from .store import StateError, Store, strict_json


def main():
    parser = argparse.ArgumentParser(prog="python3 -m ignition")
    parser.add_argument("--state", default="~/.frontier-ignition", help="private local mission directory")
    parser.add_argument("--assisted", nargs=2, metavar=("PROVIDER","MODEL"),
                        help="enable an explicitly operator-assisted model exchange")
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("serve").add_argument("--port",type=int,default=8784)
    p = sub.add_parser("start")
    p.add_argument("file",type=Path)
    p.add_argument("--request-id",default=None)
    for cmd in ("show","resume","respond","approve","export","amend","try","history"):
        p = sub.add_parser(cmd)
        p.add_argument("id")
        if cmd in {"respond","amend","try","export"}:
            p.add_argument("file",type=Path)
        if cmd in {"respond","approve"}:
            p.add_argument("--sha256",required=True)
        if cmd in {"amend","resume","respond","approve","try","export"}:
            p.add_argument("--version",type=int,required=True)
        if cmd == "amend":
            p.add_argument("--request-id",required=True)
    args = parser.parse_args()
    ctrl = Controller(Store(args.state),assisted=args.assisted)
    cmd = args.command
    if cmd == "serve":
        with Service(ctrl,args.port) as server:
            print(f"FRONTIER Ω IGNITION  http://127.0.0.1:{server.server_port}  |  {ctrl.identity()['mode']}",flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        return
    if cmd in {"start","amend"}:
        doc = strict_json(args.file.read_bytes())
        body = {k:doc[k] for k in ("mission","sources") if k in doc}
        body["request_id"] = args.request_id or uuid.uuid4().hex
        if cmd == "amend":
            body["version"] = args.version
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
        if cmd == "respond":
            ctrl.intervene(args.id,args.version,cmd,{"sha256":args.sha256,"response":strict_json(args.file.read_bytes())})
        if cmd == "approve":
            ctrl.intervene(args.id,args.version,cmd,{"contract_sha256":args.sha256})
        value = ctrl.advance(args.id,args.version)
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    try:
        main()
    except (StateError, ValueError, OSError) as exc:
        sys.exit(str(exc))
