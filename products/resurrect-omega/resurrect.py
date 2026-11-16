#!/usr/bin/env python3
"""RESURRECT Ω: reconstruct an authorized black-box JSONL executable on a finite contract domain.

The legacy binary is the oracle. No decompilation, no cloud API, no customer data upload.
A generated self-contained Python replacement is accepted only after a fresh, independent
full-domain replay. The implementation does not claim general program reconstruction.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from collections import defaultdict

SCHEMA = "resurrect-omega.jsonl.v1"
IMAGE = "python:3.12-slim"
MAX_CASES = 25_000
MAX_BYTES = 8_000_000


class Hold(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def read_manifest(path):
    manifest = load(path)
    if type(manifest) is not dict or set(manifest) != {"schema", "name", "authorization", "binary", "axes"}:
        raise Hold("manifest requires schema,name,authorization,binary,axes and no other fields")
    if manifest["schema"] != SCHEMA:
        raise Hold("unsupported schema")
    if type(manifest["name"]) is not str or not manifest["name"]:
        raise Hold("name is required")
    if manifest["authorization"] != "I_OWN_OR_AM_AUTHORIZED_TO_REIMPLEMENT":
        raise Hold("explicit rights attestation required; rights still require independent confirmation")
    binary = manifest["binary"]
    if type(binary) is not str or not binary or len(binary) > 1024:
        raise Hold("binary path required")
    axes = manifest["axes"]
    if type(axes) is not dict or not 1 <= len(axes) <= 12:
        raise Hold("1–12 finite input axes required")
    combinations = 1
    for key, values in axes.items():
        if type(key) is not str or not key.isidentifier() or key.startswith("_"):
            raise Hold("invalid input key")
        if type(values) is not list or not values or len(values) > MAX_CASES:
            raise Hold("axes must contain nonempty finite lists")
        if any(type(v) not in (str, int, bool) or (type(v) is str and len(v) > 100) for v in values):
            raise Hold("axes support bounded strings, integers and booleans only")
        encoded = [canonical(v) for v in values]
        if len(set(encoded)) != len(values):
            raise Hold(f"duplicate values in axis {key}")
        combinations *= len(values)
        if combinations > MAX_CASES:
            raise Hold(f"domain exceeds {MAX_CASES} cases; partition or narrow with buyer's approval")
    return manifest


def domain(manifest):
    fields = sorted(manifest["axes"])
    for values in itertools.product(*(manifest["axes"][key] for key in fields)):
        yield dict(zip(fields, values))


def get_binary(manifest, source):
    value = Path(manifest["binary"])
    path = (value if value.is_absolute() else Path(source).resolve().parent / value).resolve()
    if not path.is_file():
        raise Hold(f"binary not available: {path}")
    if path.stat().st_size > 20_000_000:
        raise Hold("20 MB binary size limit in this prototype")
    if not os.access(path, os.X_OK):
        raise Hold("binary is not executable")
    return path


def process(binary, role, input_items, unsafe_local=False, timeout=120):
    if not input_items:
        raise Hold("empty comparison")
    data = "\n".join(canonical(v) for v in input_items) + "\n"
    if len(data.encode()) > MAX_BYTES:
        raise Hold("input exceeds bounded byte budget")
    if unsafe_local:
        command = [sys.executable, "-I", str(binary)] if role == "candidate" else [str(binary)]
    else:
        if not shutil.which("docker"):
            raise Hold("Docker unavailable: fail closed; --unsafe-local only for trusted checked-in demos")
        destination = "/job/candidate.py" if role == "candidate" else "/job/oracle"
        command = [
            "docker", "run", "--rm", "-i", "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=65534:65534",
            "--pids-limit=32", "--memory=256m", "--cpus=1",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
            "--mount", f"type=bind,src={binary},dst={destination},readonly",
            IMAGE, *(["python", "-I", destination] if role == "candidate" else [destination])
        ]
    try:
        run = subprocess.run(command, input=data, text=True, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as err:
        raise Hold("process timeout: no accepted result") from err
    except OSError as err:
        raise Hold(f"process could not start: {err}") from err
    if run.returncode != 0 or run.stderr.strip():
        raise Hold(f"{role} exited={run.returncode}; stderr tail={run.stderr[-300:]!r}")
    if len(run.stdout.encode()) > MAX_BYTES:
        raise Hold("output too large")
    raw = run.stdout.splitlines()
    if len(raw) != len(input_items):
        raise Hold(f"{role} output count mismatch expected={len(input_items)} actual={len(raw)}")
    try:
        return [json.loads(item) for item in raw]
    except json.JSONDecodeError as err:
        raise Hold(f"{role} emitted non-JSON line") from err


def capture(manifest_path, dest, unsafe_local=False):
    manifest = read_manifest(manifest_path)
    binary = get_binary(manifest, manifest_path)
    requests = list(domain(manifest))
    results = process(binary, "reference", requests, unsafe_local)
    observations = {"schema": "resurrect-omega.observations.v1", "manifest_sha256": sha(manifest),
                    "binary_sha256": file_sha(binary), "cases": [
                        {"input": question, "output": answer} for question, answer in zip(requests, results)
                    ], "scope": "FINITE_DECLARED_JSONL_DOMAIN_ONLY"}
    save(dest, observations)
    return {"status": "CAPTURED", "observations": str(dest), "cases": len(requests),
            "binary_sha256": observations["binary_sha256"]}


def _validated_observations(manifest, obs):
    if obs.get("schema") != "resurrect-omega.observations.v1" or obs.get("manifest_sha256") != sha(manifest):
        raise Hold("observations not bound to this frozen manifest")
    expected = [canonical(item) for item in domain(manifest)]
    cases = obs.get("cases")
    if type(cases) is not list or len(cases) != len(expected):
        raise Hold("observations are incomplete")
    if [canonical(case.get("input")) for case in cases] != expected:
        raise Hold("observations are missing, duplicated or reordered")
    for case in cases:
        if type(case) is not dict or set(case) != {"input", "output"}:
            raise Hold("invalid captured case")
    return cases


def synthesize(manifest_path, observations_path, destination):
    manifest = read_manifest(manifest_path)
    obs = load(observations_path)
    cases = _validated_observations(manifest, obs)
    axes = sorted(manifest["axes"])
    retained = list(axes)
    # Remove genuinely irrelevant input dimensions by testing all controlled pairs.
    for dropped in axes:
        remaining = [axis for axis in retained if axis != dropped]
        groups = defaultdict(set)
        for case in cases:
            key = canonical([case["input"][axis] for axis in remaining])
            groups[key].add(canonical(case["output"]))
        if all(len(outputs) == 1 for outputs in groups.values()):
            retained = remaining
    mapping = {}
    for case in cases:
        key = canonical([case["input"][field] for field in retained])
        response = canonical(case["output"])
        if key in mapping and mapping[key] != response:
            raise Hold("cannot compress: same input key has conflicting outputs")
        mapping[key] = response
    body = f'''#!/usr/bin/env python3
"""Bounded replacement generated by RESURRECT OMEGA. Authorized domain ONLY.

Original binary SHA-256: {obs["binary_sha256"]}
This is a behavior table, NOT recovered author source or a general clone.
"""
import json
import sys

MANIFEST_SHA256 = {sha(manifest)!r}
AXES = {canonical(manifest["axes"])}
FIELDS = {canonical(retained)}
TABLE = {canonical(mapping)}


def answer(request):
    if type(request) is not dict or set(request) != set(AXES):
        raise ValueError("out-of-contract input keys")
    for name, values in AXES.items():
        typed = json.dumps(request[name], sort_keys=True, separators=(",", ":"))
        if typed not in {{json.dumps(v, sort_keys=True, separators=(",", ":")) for v in values}}:
            raise ValueError("out-of-contract input value: " + name)
    key = json.dumps([request[v] for v in FIELDS], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if key not in TABLE:
        raise ValueError("input not reconstructed")
    return json.loads(TABLE[key])


if __name__ == "__main__":
    for line in sys.stdin:
        try:
            print(json.dumps(answer(json.loads(line)), sort_keys=True, separators=(",", ":")))
        except (ValueError, KeyError, TypeError) as exc:
            print("HOLD: " + str(exc), file=sys.stderr)
            sys.exit(2)
'''
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(body, encoding="utf-8")
    destination.chmod(0o644)
    return {"status": "SYNTHESIZED_NOT_VERIFIED", "candidate": str(destination),
            "input_axes": len(axes), "retained_axes": retained, "table_rows": len(mapping),
            "original_cases": len(cases)}


def verify(manifest_path, candidate_path, unsafe_local=False):
    manifest = read_manifest(manifest_path)
    reference = get_binary(manifest, manifest_path)
    candidate = Path(candidate_path).resolve()
    if not candidate.is_file() or candidate.stat().st_size > 20_000_000:
        raise Hold("candidate source missing or too large")
    # Fresh reference run, reversed order; no dependency on previous observations.
    questions = list(reversed(list(domain(manifest))))
    expected = process(reference, "reference", questions, unsafe_local)
    observed = process(candidate, "candidate", questions, unsafe_local)
    bad = []
    for idx, (want, got) in enumerate(zip(expected, observed)):
        if canonical(want) != canonical(got):
            bad.append({"input": questions[idx], "reference": want, "candidate": got})
            if len(bad) >= 3: break
    return {"status": "PASS_FINITE_DOMAIN" if not bad else "FAIL_MISMATCH",
            "scope": "complete declared finite JSONL domain; no general equivalence claim",
            "schema": "resurrect-omega.verdict.v1", "cases_checked": len(questions),
            "manifest_sha256": sha(manifest), "binary_sha256": file_sha(reference),
            "candidate_sha256": file_sha(candidate), "mismatches": bad,
            "mode": "unsafe_local_trusted_only" if unsafe_local else "docker_isolated"}


def demo(destination, unsafe_local=False):
    root = Path(__file__).resolve().parent
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    oracle = destination / "legacy_pricing"
    # Source stays in repository only as a transparent synthetic fixture; the
    # synthesis engine receives binary plus oracle outputs, never this C file.
    compiler = shutil.which("cc") or shutil.which("gcc")
    if not compiler:
        raise Hold("C compiler required for demo fixture")
    subprocess.run([compiler, "-O2", "-o", str(oracle), str(root / "examples" / "legacy_pricing.c")],
                   check=True, capture_output=True, timeout=30)
    manifest = {"schema": SCHEMA, "name": "authorized_synthetic_price_engine",
                "authorization": "I_OWN_OR_AM_AUTHORIZED_TO_REIMPLEMENT", "binary": str(oracle),
                "axes": {"region": ["NA", "EU", "APAC"], "tier": ["BASIC", "PRO"],
                         "seats": [1, 2, 3, 4]}}
    manifest_path = destination / "manifest.json"
    save(manifest_path, manifest)
    c = capture(manifest_path, destination / "observations.json", unsafe_local)
    s = synthesize(manifest_path, destination / "observations.json", destination / "replacement.py")
    v = verify(manifest_path, destination / "replacement.py", unsafe_local)
    save(destination / "VERDICT.json", v)
    return {"capture": c, "synthesis": s, "verification": v, "artifact_dir": str(destination)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reconstruct an authorized finite-domain executable")
    sub = parser.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("manifest")
    cap.add_argument("--out", required=True)
    make = sub.add_parser("synthesize")
    make.add_argument("manifest")
    make.add_argument("observations")
    make.add_argument("--out", required=True)
    ver = sub.add_parser("verify")
    ver.add_argument("manifest")
    ver.add_argument("candidate")
    ver.add_argument("--out")
    agent = sub.add_parser("agent", help="Opt-in Codex agent reconstruction + independent Docker replay")
    agent.add_argument("manifest")
    agent.add_argument("observations")
    agent.add_argument("--out", required=True)
    agent.add_argument("--authorize-disclosure", action="store_true",
                       help="Explicitly permit selected examples to be sent to authenticated Codex provider")
    agent.add_argument("--rounds", type=int, default=2)
    dm = sub.add_parser("demo")
    dm.add_argument("--out", default="/tmp/resurrect-omega-demo")
    for item in (cap, ver, dm):
        item.add_argument("--unsafe-local", action="store_true", help="TRUSTED DEMO CODE ONLY; NEVER customer binaries")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "capture": out = capture(args.manifest, args.out, args.unsafe_local)
        elif args.cmd == "synthesize": out = synthesize(args.manifest, args.observations, args.out)
        elif args.cmd == "verify":
            out = verify(args.manifest, args.candidate, args.unsafe_local)
            if args.out: save(args.out, out)
        elif args.cmd == "agent":
            from agentic import develop_with_codex
            out = develop_with_codex(args.manifest,args.observations,args.out,
                                     authorize_disclosure=args.authorize_disclosure,
                                     rounds=args.rounds)
        elif args.cmd == "demo": out = demo(args.out, args.unsafe_local)
        print(json.dumps(out, sort_keys=True, indent=2))
        if args.cmd == "verify" and out["status"] != "PASS_FINITE_DOMAIN": return 2
        if args.cmd == "agent" and out["status"] != "AGENT_CANDIDATE_FINITE_DOMAIN_ACCEPTED": return 2
        if args.cmd == "demo" and out["verification"]["status"] != "PASS_FINITE_DOMAIN": return 2
        return 0
    except (Hold, OSError, subprocess.CalledProcessError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "HOLD", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
