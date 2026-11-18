"""Run both transfer missions through the real invited HTTPS staging service and job queue."""
import argparse
from http.cookiejar import CookieJar
import json
from pathlib import Path
import ssl
import subprocess
import sys
from time import perf_counter, sleep
from urllib import request
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qualify import PRODUCT, accepted, check, encoded, produce


def qualify_https(directory):
    with subprocess.Popen([sys.executable, "-IB", str(PRODUCT / "qa/studio_staging.py")],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as child:
        try:
            launch = json.loads(child.stdout.readline())
            origin = launch["origin"]
            parsed = urlsplit(origin)
            check(parsed.scheme == "https" and parsed.hostname == "localhost", "Local staging origin required")
            context = ssl.create_default_context(cadata=launch["ca_pem"])
            client = request.build_opener(request.ProxyHandler({}), request.HTTPSHandler(context=context),
                                          request.HTTPCookieProcessor(CookieJar()))

            def api(path, body=None, raw=False):
                req = request.Request(origin + path, encoded(body) if body is not None else None,
                                      {"Origin": origin, "Content-Type": "application/json", "X-Ignition-Request": "1"})
                with client.open(req, timeout=10) as resp:
                    data = resp.read()
                return data if raw else json.loads(data)

            session = api("/api/session", {"invite": launch["invites"][0]})
            check(session == {"authenticated": True, "environment": "staging"}, "Fresh staging sign-in failed")

            def build(_work, out, label, mission):
                start = perf_counter()
                body = {**mission, "request_id": "staging-transfer-" + label}
                created = api("/api/runs", body)
                path = "/api/runs/" + created["id"]
                state = created
                while state["status"] in {"queued", "running"} and perf_counter() - start < 60:
                    sleep(0.025)
                    state = api(path)
                check(state["status"] == "verified", "Staging job did not verify: " + str(state.get("error")))
                duplicate = api("/api/runs", body)
                evidence = api(path + "/evidence?version=" + str(state["version"]))
                check(evidence["artifact"]["sha256"] == state["artifact"]["sha256"],
                      "Evidence and completed mission artifact differ")
                archive = out / (label + ".zip")
                archive.write_bytes(api(path + "/bundle?version=" + str(state["version"]), raw=True))
                return accepted(state, duplicate, archive, start, "invited_loopback_https_staging")

            produce(directory, build)
            check(api("/api/logout", {})["authenticated"] is False, "Staging sign-out failed")
        finally:
            child.stdin.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    qualify_https(parser.parse_args().directory.resolve())
