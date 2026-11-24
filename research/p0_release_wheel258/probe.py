"""P0-258: public wheel fixture, no account or key access."""
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

EXPECTED = {
    "cryptography": ("50.0.2", "cryptography-50.0.2-cp311-abi3-manylinux_2_34_x86_64.whl"),
    "cffi": ("2.1.1", "cffi-2.1.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"),
    "pycparser": ("3.11", "pycparser-3.11-py3-none-any.whl"),
}
def sha(b):
    return hashlib.sha256(b).hexdigest()

def digest_file(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

def inventory(root):
    members = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError("SYMLINK_MEMBER")
        if p.is_dir():
            continue
        if not p.is_file():
            raise ValueError("NONREGULAR_MEMBER")
        members[p.relative_to(root).as_posix()] = {
            "size": p.stat().st_size, "sha256": digest_file(p)}
    return members

def check(root, frozen):
    if inventory(root) != frozen:
        raise ValueError("MEMBER_HASH_OR_IDENTITY_CHANGED")

def read_public(url, host):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != host or parsed.username or parsed.password:
        raise ValueError("UNEXPECTED_PUBLIC_HOST")
    with urllib.request.urlopen(url, timeout=60) as f:
        if urllib.parse.urlsplit(f.geturl()).hostname != host:
            raise ValueError("UNEXPECTED_REDIRECT_HOST")
        return f.read()

CHILD = """
import hashlib, json, sys, pathlib
stage = pathlib.Path(sys.argv[1]).resolve()
assert sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
assert all('site-packages' not in p and 'dist-packages' not in p for p in sys.path)
sys.path.insert(0, str(stage))
import cryptography, cffi, pycparser, _cffi_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.bindings import _rust
mods = [cryptography, cffi, pycparser, _cffi_backend, _rust]
paths = {m.__name__: pathlib.Path(m.__file__).resolve().relative_to(stage).as_posix() for m in mods}
h = hashes.Hash(hashes.SHA256()); h.update(b'abc')
answer = h.finalize().hex()
assert answer == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
assert all('site-packages' not in p and 'dist-packages' not in p for p in sys.path)
libs = {}
for line in pathlib.Path('/proc/self/maps').read_text().splitlines():
    fields = line.split(None,5)
    if len(fields) != 6 or 'x' not in fields[1] or not fields[5].startswith('/'):
        continue
    p = pathlib.Path(fields[5])
    if not p.is_file():
        raise ValueError('UNREADABLE_EXECUTABLE_MAPPING')
    name = 'stage/' + p.relative_to(stage).as_posix() if p.is_relative_to(stage) else str(p)
    if name not in libs:
        with p.open('rb') as f:
            libs[name] = hashlib.file_digest(f, 'sha256').hexdigest()
print(json.dumps({'answer':answer,'module_paths':paths,'mapped_executable_files':libs},sort_keys=True))
"""

def run(receipt):
    assert sys.version_info[:3] == (3, 12, 16), "EXACT_INTERPRETER_REQUIRED"
    assert platform.system() == "Linux" and platform.machine() == "x86_64", "EXACT_ARCH_REQUIRED"
    exe = Path(sys.executable).resolve()
    receipt["interpreter"] = {"version": platform.python_version(), "sha256": digest_file(exe),
                              "platform": platform.platform()}
    with tempfile.TemporaryDirectory(prefix="p0-wheel258-") as directory:
        root = Path(directory)
        stage = root / "stage"
        stage.mkdir()
        lock = []
        for name, (version, filename) in EXPECTED.items():
            metadata = read_public(f"https://pypi.org/pypi/{name}/{version}/json", "pypi.org")
            d = json.loads(metadata)
            assert d["info"]["version"] == version
            hits = [x for x in d["urls"] if x["filename"] == filename]
            assert len(hits) == 1, "EXACT_WHEEL_NOT_UNIQUE"
            item = hits[0]
            expected_sha = item["digests"]["sha256"]
            assert not item["yanked"] and re.fullmatch("[0-9a-f]{64}", expected_sha)
            assert item["packagetype"] == "bdist_wheel"
            assert urllib.parse.urlsplit(item["url"]).path.endswith("/" + filename)
            blob = read_public(item["url"], "files.pythonhosted.org")
            assert len(blob) == item["size"] and sha(blob) == expected_sha, "WHEEL_IDENTITY_MISMATCH"
            path = root / filename
            path.write_bytes(blob)
            lock.append(path.as_uri() + " --hash=sha256:" + expected_sha)
            receipt["wheels"][name] = {"version": version, "filename": filename, "size": len(blob),
                                        "sha256": expected_sha, "index_sha256": sha(metadata),
                                        "public_url": item["url"]}
        receipt["cases"]["exact_public_wheels"] = "PASS"
        requirements = root / "lock.txt"
        requirements.write_text("\n".join(lock) + "\n")
        # Do not inherit arbitrary pip configuration or environment. No indexes or dependencies.
        env = {"PATH": os.defpath, "HOME": str(root), "PIP_CONFIG_FILE": os.devnull,
               "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
        done = subprocess.run([str(exe), "-I", "-m", "pip", "install", "--no-index",
            "--no-deps", "--require-hashes", "--no-compile", "--target", str(stage),
            "-r", str(requirements)], env=env, capture_output=True, text=True, cwd=root)
        receipt["pip_exit"] = done.returncode
        if done.returncode:
            raise RuntimeError("OFFLINE_WHEEL_INSTALL_FAILED")
        frozen = inventory(stage)
        assert frozen
        receipt["inventory"] = frozen
        receipt["inventory_sha256"] = sha(canonical(frozen))
        check(stage, frozen)
        receipt["cases"]["offline_install"] = "PASS"
        child = subprocess.run([str(exe), "-I", "-S", "-B", "-c", CHILD, str(stage)],
                               env={"PATH": os.defpath, "HOME": str(root)},
                               cwd=root, capture_output=True, text=True)
        receipt["child_exit"] = child.returncode
        if child.returncode:
            raise RuntimeError("ISOLATED_CHILD_FAILED")
        receipt["child"] = json.loads(child.stdout)
        check(stage, frozen)
        receipt["cases"]["isolated_native_computation"] = "PASS"
        member = stage / "pycparser/__init__.py"
        original = member.read_bytes()
        member.write_bytes(original + b"\n# changed\n")
        try:
            check(stage, frozen)
        except ValueError as exc:
            assert str(exc) == "MEMBER_HASH_OR_IDENTITY_CHANGED"
            receipt["cases"]["changed_member_refused"] = "PASS"
        else:
            raise AssertionError("CHANGED_MEMBER_ACCEPTED")
        member.write_bytes(original)
        check(stage, frozen)
        extra = stage / "p0_unregistered_synthetic.py"
        extra.write_text("SYNTHETIC = True\n")
        try:
            check(stage, frozen)
        except ValueError as exc:
            assert str(exc) == "MEMBER_HASH_OR_IDENTITY_CHANGED"
            receipt["cases"]["extra_member_refused"] = "PASS"
        else:
            raise AssertionError("EXTRA_MEMBER_ACCEPTED")
        extra.unlink()
        check(stage, frozen)

if __name__ == "__main__":
    out = Path(sys.argv[1])
    if out.exists():
        raise FileExistsError("FRESH_RECEIPT_REQUIRED")
    start = time.monotonic()
    cpu_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {"schema":"p0-release-wheel258/v1","source_commit":os.environ.get("GITHUB_SHA"),
               "script_sha256":digest_file(Path(__file__)), "wheels":{}, "cases":{},
               "scope":"prospective public wheel fixture; historical bytes and native financial qualification unestablished",
               "actual_billing_usd":None, "financial_integration":False, "real_commerce":False}
    try:
        run(receipt)
        receipt["accepted"] = len(receipt["cases"]) == 5
    except Exception as exc:
        # Keep public diagnostics narrow; never dump inherited environment.
        receipt["accepted"] = False
        receipt["error_type"] = type(exc).__name__
        receipt["error"] = str(exc)[:350]
    finally:
        cpu_end = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt["wall_seconds"] = time.monotonic() - start
        receipt["waited_child_cpu_seconds"] = (cpu_end.ru_utime + cpu_end.ru_stime -
                                               cpu_start.ru_utime - cpu_start.ru_stime)
        out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"accepted":receipt["accepted"],"cases":receipt["cases"],
                      "error":receipt.get("error")},sort_keys=True))
    raise SystemExit(0 if receipt["accepted"] else 1)
