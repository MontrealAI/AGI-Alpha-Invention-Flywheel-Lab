"""Source pins and limited acquisition for the registered dispatch experiment."""

import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter_ns
from urllib.request import urlopen

EVIDENCE_REVISION = "3cc6bc95a13f991b5158e5bd5064b766b21632a4"
BASE_URL = "https://data.mendeley.com/public-files/datasets/b78bc94d95/files"
PLANTS = 8
KM_PER_CAR_MINUTE = 0.36
TRUCK_MULTIPLIER = 1.4
DEV_CASE = "cdp_o5_01s"
EVALUATION_CASES = ("cdp_o45_08d", "cdp_o50_d", "cdp_o5_06d")
PINS = {
    DEV_CASE: ("204f059b-2169-47f9-9d69-7abbacf73fbb", 1922,
               "1e121f7f695f040a74e493b2a26057d655fd6e2a316e219ffaf0d7c7917dd1ea"),
    "cdp_o5_06d": ("8bb8a385-a0ae-4bcb-ac35-a8bd6d36faff", 1954,
                   "efe911936baf5febd3b4ebd7ead392f21ebbf6438fa7c6a42ee76a9e61b0d35a"),
    "cdp_o45_08d": ("dcac9669-c76f-40fd-a922-c2932bcaebb0", 4812,
                    "66a5e28901d8a9357d87045d69aa8eaf145fee366b28fe5887b216b9401455ce"),
    "cdp_o50_d": ("e085eaff-68e1-4adc-b1a8-c5a3eb2befbd", 4935,
                  "3239317645729f0a888151193f2e1fcd23d1a203ac550dd37668fdceae5a82e9"),
}


def check_bytes(case, raw):
    _, size, expected_hash = PINS[case]
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("source length or SHA-256 disagrees with registration")


def acquire(case, directory):
    file_id, byte_limit, digest = PINS[case]
    url = f"{BASE_URL}/{file_id}/file_downloaded"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{case}.mat"
    cached = path.exists()
    start = perf_counter_ns()
    if cached:
        with path.open("rb") as stream:
            raw = stream.read(byte_limit + 1)
    else:
        with urlopen(url, timeout=15) as stream:
            raw = stream.read(byte_limit + 1)
    check_bytes(case, raw)
    if not cached:
        temp = path.with_suffix(".part")
        temp.write_bytes(raw)
        temp.replace(path)
    milliseconds = (perf_counter_ns() - start) / 1e6
    return raw, {"case": case, "source_url": url, "sha256": digest, "bytes": len(raw),
                 "request_count": int(not cached), "transport": "cache" if cached else "https",
                 "wall_ms": round(milliseconds, 6)}


def normalized(case, repo):
    PINS[case]
    path = f"{EVIDENCE_REVISION}:production060/data/days/{case}.json"
    raw = subprocess.run(["git", "show", path], cwd=Path(repo), capture_output=True,
                         check=True, timeout=15).stdout
    data = json.loads(raw)
    if data["id"] != case or data["n_orders"] != len(data["orders"]):
        raise ValueError("wrong or inconsistent order inventory")
    if data["source"].get("sha256") != PINS[case][2]:
        raise ValueError("order inventory is bound to a different source")
    return data
