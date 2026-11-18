"""Four private, simultaneous local tenants; benchmark the real service/lease/SQLite path."""
import argparse
import concurrent.futures
import contextlib
import http.client
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ignition.hosted import HostedService
from ignition.hosted_auth import Access
from ignition.store import PRODUCT


def run():
    with tempfile.TemporaryDirectory() as directory:
        access = Access(Path(directory) / "private", "staging")
        service = HostedService(access, "https://ignition.example.test", 0)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        gate = threading.Barrier(4)
        try:
            def run_one(index):
                def request(path, body=None, cookie=""):
                    with contextlib.closing(http.client.HTTPConnection("127.0.0.1",service.server_port,timeout=10)) as conn:
                        start = time.monotonic()
                        conn.request("GET" if body is None else "POST",path,body=json.dumps(body).encode() if body is not None else None,
                                     headers={"Host":"ignition.example.test","Origin":"https://ignition.example.test",
                                              "X-Ignition-Request":"1", "Content-Type":"application/json","Cookie":cookie})
                        res = conn.getresponse()
                        result = json.loads(res.read())
                        return res.status, result, res.getheader("Set-Cookie"), time.monotonic()-start
                code = access.issue(f"ephemeral-{index}")
                status, _, cookie, _ = request("/api/session",{"invite":code})
                assert status==200
                cookie = cookie.split(";")[0]
                sample = json.loads((PRODUCT/"examples"/"integrity.json").read_bytes())
                mission = sample["mission"]
                mission["resources"].update(execution_strategy="direct",direct_method="specialist",max_model_calls=0)
                body = {"mission":mission,"sources":sample["sources"],"request_id":"local-load-qualification"}
                gate.wait(timeout=10)
                status, state, _, intake = request("/api/runs",body,cookie)
                assert status == 202, status
                rid = state["id"]
                poll_samples = []
                started = time.monotonic()
                while time.monotonic() - started < 15:
                    status,state,_,duration = request(f"/api/runs/{rid}",cookie=cookie)
                    assert status == 200, status
                    poll_samples.append(duration)
                    if state["status"] == "verified":
                        break
                    time.sleep(0.04)
                assert state["status"] == "verified", state["status"]
                for _ in range(12):
                    status,state,_,duration = request(f"/api/runs/{rid}",cookie=cookie)
                    assert status == 200 and state["id"] == rid
                    poll_samples.append(duration)
                return intake, poll_samples, time.monotonic()-started, rid
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(run_one,range(4)))
        finally:
            service.shutdown()
            thread.join()
            service.server_close()
    ids=set(r[3] for r in results)
    assert len(ids) == len(results), "Tenant-local idempotency keys must produce isolated missions"
    def p95(items):
        values=sorted(items)
        return values[math.ceil(len(values)*0.95)-1]
    intake=p95(r[0] for r in results)
    reads=[v for _,samples,_,_ in results for v in samples]
    read=p95(reads)
    return {"surface":"isolated staging backend on loopback; TLS and external routing excluded",
            "tenants":4,"workers":2,"completed_real_local_compiler_jobs":len(results),
            "model_calls":0,"intake_samples":len(results),"status_read_samples":len(reads),
            "p95_intake_seconds":round(intake,4),"p95_status_read_seconds":round(read,4),
            "max_time_from_accepted_intake_through_last_read_seconds":round(max(r[2] for r in results),4),
            "limits":{"p95_intake_seconds":2,"p95_status_read_seconds":1},
            "passed":intake<2 and read<1}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args=parser.parse_args()
    result=run()
    text=json.dumps(result, indent=2)+"\n"
    if args.out: args.out.write_text(text)
    print(text,end="")
    sys.exit(0 if result["passed"] else 1)
