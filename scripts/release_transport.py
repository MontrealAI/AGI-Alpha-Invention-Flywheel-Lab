#!/usr/bin/env python3
"""Exact-byte release transport and source-68 publication recovery; no inference."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = "MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
API_ROOT = "https://api.github.com/repos/" + REPO
SOURCE = "68c2c1a00c78579b76788955a87f74dace8cc404"
PRODUCT_TREE = "9ef854f565ba4fc82498cdd6a69a734df940522f"
RUN = 42786474290
REPO_ID = 1438763186
CUSTOMER_SHA = "2b7d979d84290f57d8865102f782b3571e2b42d9354080dced003e4a326b757a"
CUSTOMER = "ALPHA_GENESIS_HARNESS_0.3.0_source-bound_68c2c1a00c78.zip"
TAG = "alpha-genesis-harness-v0.3.0-rc-68c2c1a00c78"
TITLE = "ALPHA GENESIS HARNESS 0.3.0 — release candidate"
PRIOR_RELEASE_ID = 440177275
MODEL_ZIP = "LOCAL-MODEL-EVIDENCE_68c2c1a00c78.zip"
AUX_ZIP = "AUXILIARY-EVIDENCE_68c2c1a00c78.zip"
BASE_INVENTORY = "PUBLICATION-INVENTORY_68c2c1a00c78.json"
FINAL_INVENTORY = "OWNER-PUBLICATION-INVENTORY_68c2c1a00c78.json"
FAILURE_ZIP = "FAILED-PUBLICATION-OPERATION_68c2c1a00c78.zip"
DIAGNOSTIC_FAILURE_NAME = "Darwin-CODEX-HOST-VERIFICATION.stderr.txt"
CORE = ["local_inference", "single_agent", "multi_agent", "parallel_exploration"]
EMPTY_SHA = hashlib.sha256(b"").hexdigest()
PINS = {
    "assets": (13749388065, 5703277, "c11d378c3e2e1c2e09f7ac146e403000938de1b3acaae0ec7b29ab5addef7abb", "alpha-genesis-harness-"),
    "macos": (13749128766, 4686993, "0f51e30223192ee73ee21e357b6678de27e3262e5baf34f0e837a6064eeff91a", "alpha-genesis-harness-platform-macos-15-"),
    "windows": (13749937631, 3849654, "f13fad1077c7fd6c81144037e9ec8a993ec46f378b45d331b853a2a6f70bb5be", "alpha-genesis-harness-platform-windows-2025-"),
    "model": (13751912486, 67212, "ac763610c0a651e449ca6dbcdbb32d1c3e59a470eb52d9376e9143d1c9a39e64", "alpha-genesis-harness-local-"),
    "failed_publication": (13752187157, 59740, "e9f5e8e8a2746b329845d2b94eef4ff08da8646f3af881f3ed852c3a6e615a56", "alpha-genesis-harness-release-operation-"),
}
MAX_BYTES = 100 * 1024 * 1024
SAFE_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "LD_LIBRARY_PATH", "SYSTEMROOT")
TOKEN_PHASES = {"acquire", "publish-base", "download-base", "publish-final"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def decode(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def read(path):
    return decode(Path(path).read_bytes())


def safe_name(name, flat=False):
    if not isinstance(name, str) or not name or "\\" in name or any(ord(c) < 32 for c in name):
        return False
    p = PurePosixPath(name)
    if p.is_absolute() or name != p.as_posix() or any(x in ("", ".", "..") for x in p.parts):
        return False
    if flat and len(p.parts) != 1:
        return False
    for part in p.parts:
        if part.endswith((".", " ")) or any(c in part for c in ':*?"<>|'):
            return False
        if part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *("COM"+str(n) for n in range(1,10)), *("LPT"+str(n) for n in range(1,10))}:
            return False
    return True


def put(path, raw):
    path = Path(path)
    require(not path.is_symlink(), "Refuse symbolic-link output")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and path.read_bytes() == raw, "Existing file differs: " + path.name)
    else:
        with path.open("xb") as stream:
            stream.write(raw)


def record(raw):
    return {"bytes": len(raw), "sha256": digest(raw)}


def validate_record(raw, expected):
    require(type(expected.get("bytes")) is int and expected["bytes"] == len(raw)
            and expected.get("sha256") == digest(raw), "File length/hash differs")


def zip_members(raw, flat=False):
    require(len(raw) <= MAX_BYTES, "ZIP compressed size exceeds bound")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(0 < len(infos) <= 10000, "Invalid ZIP member count")
        names = [i.filename for i in infos]
        require(len(names) == len(set(n.casefold() for n in names)), "Duplicate/casefold ZIP member")
        require(sum(i.file_size for i in infos) <= MAX_BYTES, "ZIP expanded size exceeds bound")
        for info in infos:
            mode = info.external_attr >> 16
            require(info.orig_filename == info.filename and safe_name(info.filename, flat) and not info.is_dir()
                    and not info.external_attr & 0x10
                    and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    and stat.S_IFMT(mode) in (0, stat.S_IFREG)
                    and info.file_size <= MAX_BYTES and not info.flag_bits & 1, "Unsafe ZIP member")
        return {i.filename: archive.read(i) for i in infos}


def zip_bytes(files, original_model_format=False):
    require(files and all(safe_name(name) for name in files), "Unsafe archive inventory")
    require(len(files) == len(set(name.casefold() for name in files)), "Casefold archive collision")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026,1,1,0,0,0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            if original_model_format:
                # Preserve the exact source68 workflow writer: supplied ZipInfo uses default zlib level.
                archive.writestr(info, raw)
            else:
                archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return out.getvalue()


def folder_files(folder):
    folder = Path(folder)
    result = {}
    for path in sorted(folder.rglob("*")):
        require(not path.is_symlink(), "Symlink in file inventory")
        if path.is_dir():
            continue
        name = path.relative_to(folder).as_posix()
        require(path.is_file() and safe_name(name) and path.stat().st_size <= MAX_BYTES, "Unsafe input file")
        result[name] = path.read_bytes()
    require(len(result) == len(set(n.casefold() for n in result)), "Casefold input collision")
    return result


def inventory(files):
    return {name: record(raw) for name, raw in sorted(files.items())}


def verify_inventory(files, expected):
    require(set(files) == set(expected), "Inventory membership differs")
    for name, raw in files.items():
        require(safe_name(name), "Unsafe inventory path")
        validate_record(raw, expected[name])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def approved_download(url):
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    require(parts.scheme == "https" and not parts.username and not parts.password
            and parts.port is None and not parts.fragment, "Unsafe signed-download URL")
    require(host in {"release-assets.githubusercontent.com", "objects.githubusercontent.com"}
            or (host.startswith("productionresult") and host.endswith(".blob.core.windows.net"))
            or host.endswith(".actions.githubusercontent.com"), "Unapproved signed-download host")
    return url


class GitHub:
    def __init__(self, token):
        require(isinstance(token, str) and token, "Missing publication credential")
        self.token = token
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def unsigned_download(self, url):
        for _ in range(5):
            approved_download(url)
            request = urllib.request.Request(url, headers={"User-Agent":"harness-exact-release-recovery"})
            try:
                with self.opener.open(request, timeout=120) as response:
                    data = response.read(MAX_BYTES + 1)
                    require(len(data) <= MAX_BYTES, "Response exceeds transport bound")
                    return data
            except urllib.error.HTTPError as error:
                if error.code in (301,302,303,307,308):
                    url = urllib.parse.urljoin(url, error.headers["Location"])
                    continue
                raise RuntimeError("Signed download failed: HTTP " + str(error.code)) from None
        raise ValueError("Signed download redirect limit exceeded")

    def request(self, path, method="GET", value=None, raw=None, accept="application/vnd.github+json", missing=False, binary=False):
        url = path if path.startswith("https://") else API_ROOT + path
        parts = urllib.parse.urlsplit(url)
        require(parts.scheme == "https" and parts.hostname in {"api.github.com", "uploads.github.com"}
                and not parts.username and not parts.password and parts.port is None and not parts.fragment,
                "Unexpected authenticated API host")
        payload = encode(value) if value is not None else raw
        headers = {"Authorization": "Bearer " + self.token, "Accept": accept,
                   "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "harness-exact-release-recovery"}
        if payload is not None:
            headers["Content-Type"] = "application/json" if value is not None else "application/octet-stream"
            headers["Content-Length"] = str(len(payload))
        try:
            with self.opener.open(urllib.request.Request(url, data=payload, headers=headers, method=method), timeout=120) as response:
                data = response.read(MAX_BYTES + 1)
                require(len(data) <= MAX_BYTES, "Response exceeds transport bound")
                return data if binary else (decode(data) if data else None)
        except urllib.error.HTTPError as error:
            if error.code in (301,302,303,307,308) and method == "GET" and binary:
                return self.unsigned_download(urllib.parse.urljoin(url, error.headers["Location"]))
            if missing and error.code == 404:
                return None
            raise RuntimeError("GitHub request failed: HTTP " + str(error.code) + " " + method + " " + parts.path) from None

    def pages(self, path):
        all_rows = []
        for page in range(1,101):
            rows = self.request(path + ("&" if "?" in path else "?") + "per_page=100&page=" + str(page))
            require(isinstance(rows, list), "Invalid paginated API response")
            all_rows.extend(rows)
            if len(rows) < 100:
                return all_rows
        raise ValueError("API pagination exceeded bound")

    def asset_bytes(self, asset):
        require(str(asset.get("url","")) == API_ROOT + "/releases/assets/" + str(asset["id"]), "Foreign asset API URL")
        return self.request("/releases/assets/" + str(asset["id"]), accept="application/octet-stream", binary=True)


def source_guard(source_dir):
    source_dir = Path(source_dir)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(source_dir), *args], text=True).strip()
    require(git("rev-parse","HEAD") == SOURCE, "Checkout is not the qualified source")
    require(git("rev-parse",SOURCE + ":products/alpha-genesis-harness") == PRODUCT_TREE, "Product tree differs")
    require(not git("status","--porcelain","--untracked-files=no"), "Qualified checkout changed")
    return source_dir / "products/alpha-genesis-harness"


def acquire(root, api):
    input_records = {}
    for key, (identifier, size, expected, prefix) in PINS.items():
        meta = api.request("/actions/artifacts/" + str(identifier))
        run = meta.get("workflow_run", {})
        require(meta.get("id") == identifier and meta.get("size_in_bytes") == size
                and meta.get("digest") == "sha256:" + expected and meta.get("expired") is False
                and meta.get("name") == prefix + SOURCE + "-attempt-1"
                and run.get("id") == RUN and run.get("head_sha") == SOURCE
                and run.get("repository_id") == REPO_ID and run.get("head_repository_id") == REPO_ID,
                "Pinned artifact metadata differs: " + key)
        raw = api.request("/actions/artifacts/" + str(identifier) + "/zip", binary=True)
        validate_record(raw, {"bytes":size,"sha256":expected})
        put(root/"input-zips"/(key+".zip"), raw)
        members = zip_members(raw, flat=key not in {"model","failed_publication"})
        input_records[key] = {"artifact_id":identifier,"archive":record(raw),"files":inventory(members)}
        if key != "failed_publication":
            destination = root/("local-public" if key == "model" else "received-original")
            for name, data in members.items():
                put(destination/name, data)
    put(root/"INPUT-VERIFICATION.json", encode({"source_revision":SOURCE,"source_product_tree":PRODUCT_TREE,
        "qualification_run":RUN,"artifacts":input_records,"raw_wrapper_hashes_verified":True}))
    prior, lookup = find_release(api)
    snapshot = None
    if prior:
        snapshot = {key:prior[key] for key in ("id","tag_name","target_commitish","name","draft","prerelease","url","html_url")}
        snapshot["assets"] = [{key:row.get(key) for key in ("id","name","state","size","digest","created_at","updated_at")}
                              for row in release_assets(api,prior).values()]
    put(root/"PRIOR-RELEASE-INSPECTION.json", encode({"source_revision":SOURCE,"lookup":lookup,"release":snapshot}))
    print(json.dumps({"phase":"acquire","artifacts":list(input_records),"source_revision":SOURCE,
                      "prior_release":None if prior is None else {"id":prior["id"],"draft":prior["draft"]}}))


def package_auxiliary(original, failure_raw, inspection_raw):
    zeros = {name:raw for name,raw in original.items() if len(raw)==0}
    require(DIAGNOSTIC_FAILURE_NAME in zeros, "Observed failing stderr was not actually empty; refuse presumed diagnosis")
    require(all(name.endswith((".stdout.txt",".stderr.txt")) for name in zeros), "Unexpected empty non-diagnostic input")
    files = {"empty/"+name:raw for name,raw in zeros.items()}
    files["failure/"+FAILURE_ZIP] = failure_raw
    files["failure/PRIOR-RELEASE-INSPECTION.json"] = inspection_raw
    body = {"schema":"harness-empty-diagnostic-transport/v1","source_revision":SOURCE,
        "source_product_tree":PRODUCT_TREE,"customer_archive_sha256":CUSTOMER_SHA,
        "original_zero_files":inventory(zeros),"files":inventory(files),
        "failure_artifact":PINS["failed_publication"][0],
        "prior_release_inspection":record(inspection_raw),
        "rule":"Absent and empty are different. Restore exact zero bytes; never add a newline or placeholder."}
    files["AUXILIARY-MANIFEST.json"] = encode(body)
    return zip_bytes(files), body


def inspect_auxiliary(raw, expected_zero, failure_expected, inspection_expected):
    members = zip_members(raw)
    require("AUXILIARY-MANIFEST.json" in members, "Auxiliary manifest missing")
    body = decode(members.pop("AUXILIARY-MANIFEST.json"))
    require(body.get("schema") == "harness-empty-diagnostic-transport/v1"
            and body.get("source_revision") == SOURCE and body.get("source_product_tree") == PRODUCT_TREE
            and body.get("customer_archive_sha256") == CUSTOMER_SHA
            and body.get("original_zero_files") == expected_zero
            and body.get("failure_artifact") == PINS["failed_publication"][0]
            and body.get("prior_release_inspection") == inspection_expected, "Auxiliary identity differs")
    verify_inventory(members, body["files"])
    require(set(members) == {"empty/"+n for n in expected_zero} | {"failure/"+FAILURE_ZIP,"failure/PRIOR-RELEASE-INSPECTION.json"}, "Auxiliary unexpected member")
    validate_record(members["failure/"+FAILURE_ZIP], failure_expected)
    validate_record(members["failure/PRIOR-RELEASE-INSPECTION.json"], inspection_expected)
    restored = {}
    for name, info in expected_zero.items():
        require(safe_name(name, True) and info == {"bytes":0,"sha256":EMPTY_SHA}, "Invalid empty diagnostic identity")
        validate_record(members["empty/"+name], info)
        restored[name] = members["empty/"+name]
    return restored


def verified_inputs(root):
    receipt = read(root/"INPUT-VERIFICATION.json")
    require(receipt.get("source_revision") == SOURCE and receipt.get("source_product_tree") == PRODUCT_TREE
            and receipt.get("qualification_run") == RUN and receipt.get("raw_wrapper_hashes_verified") is True
            and set(receipt.get("artifacts",{})) == set(PINS), "Input verification identity differs")
    original, public = {}, {}
    for key,(identifier,size,expected,_) in PINS.items():
        raw = (root/"input-zips"/(key+".zip")).read_bytes()
        validate_record(raw, {"bytes":size,"sha256":expected})
        members = zip_members(raw, flat=key not in {"model","failed_publication"})
        entry = receipt["artifacts"][key]
        require(entry.get("artifact_id") == identifier and entry.get("archive") == record(raw),
                "Input wrapper identity differs")
        verify_inventory(members, entry["files"])
        if key == "failed_publication":
            continue
        target = public if key == "model" else original
        for name,data in members.items():
            require(name not in target or target[name] == data, "Different pinned artifact members collide")
            target[name] = data
    verify_inventory(folder_files(root/"received-original"),inventory(original))
    verify_inventory(folder_files(root/"local-public"),inventory(public))
    return original, public


def derive_base(root):
    original, public = verified_inputs(root)
    require(all(safe_name(n,True) for n in original), "Received assets must be flat")
    require(CUSTOMER in original and digest(original[CUSTOMER]) == CUSTOMER_SHA, "Customer archive differs")
    for name in ("PLATFORM-Darwin-VERIFICATION.json","PLATFORM-Windows-VERIFICATION.json"):
        r = decode(original[name])
        require(r.get("source_revision")==SOURCE and r.get("archive_sha256")==CUSTOMER_SHA and r.get("status")=="PASS", "Native receipt differs")
    hosted = decode(public["HOSTED-LOCAL-QUALIFICATION.json"])
    require(hosted.get("source_revision")==SOURCE and hosted.get("source_product_tree")==PRODUCT_TREE
            and hosted.get("source_unchanged") is True and hosted.get("release_qualification")=="PASS"
            and hosted.get("required_release_qualifications")==CORE
            and all(hosted.get("qualifications",{}).get(k)=="PASS" for k in CORE), "Required model gate did not pass")
    require(set(public)==set(hosted["published_sha256"])|{"HOSTED-LOCAL-QUALIFICATION.json"}, "Model evidence inventory differs")
    for name, expected in hosted["published_sha256"].items():
        require(digest(public[name])==expected, "Model evidence member differs")
    model_raw = zip_bytes(public, original_model_format=True)
    failure_raw = (root/"input-zips/failed_publication.zip").read_bytes()
    inspection_raw = (root/"PRIOR-RELEASE-INSPECTION.json").read_bytes()
    auxiliary, aux = package_auxiliary(original, failure_raw, inspection_raw)
    inspect_auxiliary(auxiliary, aux["original_zero_files"], {"bytes":PINS["failed_publication"][1],"sha256":PINS["failed_publication"][2]}, record(inspection_raw))
    files = {name:raw for name,raw in original.items() if raw}
    for name,raw in ((MODEL_ZIP,model_raw),(AUX_ZIP,auxiliary),("HOSTED-LOCAL-QUALIFICATION.json",public["HOSTED-LOCAL-QUALIFICATION.json"])):
        require(name not in files or files[name] == raw, "Derived asset collision")
        files[name] = raw
    for name, raw in ((MODEL_ZIP,model_raw),(AUX_ZIP,auxiliary)):
        require(name+".sha256" not in files, "Derived checksum collision")
        files[name+".sha256"] = (digest(raw)+"  "+name+"\n").encode()
    quote = decode(public["LOCAL-QUOTE-QUALIFICATION-006.json"])
    quote_snapshot = {key:quote.get(key) for key in ("schema","trial_id","status","overall_status","source_unchanged")}
    quote_snapshot["retained_arms"] = [
        {key:arm.get(key) for key in ("arm","id","status","model_calls")}
        for arm in quote.get("arms",[]) if isinstance(arm,dict)]
    provenance = {"schema":"harness-publication-transport-recovery/v1","source_revision":SOURCE,
        "source_product_tree":PRODUCT_TREE,"customer_archive_sha256":CUSTOMER_SHA,
        "original_qualification_run":RUN,"prior_publication_job":129751761654,"prior_release_id_observed":PRIOR_RELEASE_ID,
        "input_verification":read(root/"INPUT-VERIFICATION.json"),
        "diagnosis":{"actual_empty_file":DIAGNOSTIC_FAILURE_NAME,"bytes":0,"sha256":EMPTY_SHA,
                     "observed_http_error":"400 Bad Content-Length","zero_files":aux["original_zero_files"]},
        "recovery_implementation_sha256":digest(Path(__file__).read_bytes()),
        "scope":"Transport-only recovery. No product rebuild, source edit, model retry, native-platform rerun or acceptance change. Received/published archive smoke and owner verification execute separately without publication credentials.",
        "model_status":hosted["status"],"model_release_qualification":hosted["release_qualification"],
        "model_qualifications":hosted["qualifications"],"model_commands":hosted.get("commands"),
        "quote_checkpoint":quote_snapshot,
        "quote_scope":"Raw checkpoint retained unchanged. Missing arms are not completed experiments.",
        "completion":"NOT_YET_OPERATED_FROM_PUBLISHED_RELEASE"}
    require("RECOVERY-PROVENANCE.json" not in files and BASE_INVENTORY not in files, "Derived inventory collision")
    files["RECOVERY-PROVENANCE.json"] = encode(provenance)
    require(all(files.values()), "Direct release assets must be nonempty")
    files[BASE_INVENTORY] = encode({"source_revision":SOURCE,"customer_archive_sha256":CUSTOMER_SHA,"files":inventory(files)})
    state = {"source_revision":SOURCE,"files":inventory(files),
             "original_files":inventory(original),"zero_files":aux["original_zero_files"],
             "prior_release_inspection":record(inspection_raw)}
    return files, state, hosted, quote_snapshot


def checked_base(root, expected_state_sha=None):
    if expected_state_sha is not None:
        require(isinstance(expected_state_sha,str) and re.fullmatch(r"[0-9a-f]{64}",expected_state_sha),
                "Pinned base-state digest required from completed preparation step")
        require(digest((root/"BASE-STATE.json").read_bytes())==expected_state_sha,
                "Base state changed after credential-free preparation")
    files,state,_,_ = derive_base(root)
    require(read(root/"BASE-STATE.json") == state, "Prepared state differs from pinned inputs")
    verify_inventory(folder_files(root/"base-assets"),inventory(files))
    return state


def prepare(root, source_dir):
    product = source_guard(source_dir)
    files,state,hosted,quote_snapshot = derive_base(root)
    sys.path.insert(0, str(product/"scripts"))
    import package_release
    from owner_handoff import model_evidence_snapshot
    package_release.verify(root/"received-original"/CUSTOMER, expected_sha256=CUSTOMER_SHA,
                           expected_source_revision=SOURCE, compare_source_revision=SOURCE)
    for name,raw in files.items():
        put(root/"base-assets"/name,raw)
    model_evidence_snapshot(root/"base-assets"/MODEL_ZIP, SOURCE, PRODUCT_TREE)
    put(root/"BASE-STATE.json", encode(state))
    checked_base(root)
    source_guard(source_dir)
    print(json.dumps({"phase":"prepare","source_revision":SOURCE,"customer_archive_sha256":CUSTOMER_SHA,
                      "zero_files":state["zero_files"],"model_status":hosted["status"],
                      "model_release_qualification":hosted["release_qualification"],
                      "model_commands":hosted.get("commands"),"quote_checkpoint":quote_snapshot}))


def peeled_tag(api, required=True):
    ref = api.request("/git/ref/tags/"+urllib.parse.quote(TAG,safe=""), missing=True)
    if ref is None:
        require(not required, "Release tag absent")
        return None
    obj = ref["object"]
    for _ in range(8):
        if obj["type"]=="commit":
            require(obj["sha"]==SOURCE, "Existing tag points to a different commit")
            return obj["sha"]
        require(obj["type"]=="tag", "Unexpected Git tag object type")
        obj = api.request("/git/tags/"+obj["sha"])["object"]
    raise ValueError("Tag nesting exceeded bound")


def validate_release(release):
    expected_url = "https://github.com/"+REPO+"/releases/tag/"+TAG
    draft_url = re.fullmatch(re.escape("https://github.com/"+REPO+"/releases/tag/")+r"untagged-[A-Za-z0-9-]+",
                             str(release.get("html_url","")))
    require(release.get("tag_name")==TAG and release.get("target_commitish")==SOURCE
            and release.get("name")==TITLE and release.get("prerelease") is True
            and type(release.get("draft")) is bool
            and release.get("url")==API_ROOT+"/releases/"+str(release.get("id"))
            and (release.get("html_url")==expected_url or (release.get("draft") is True and draft_url)),
            "Existing release identity/type differs")


def find_release(api):
    prior = api.request("/releases/"+str(PRIOR_RELEASE_ID), missing=True)
    by_tag = api.request("/releases/tags/"+TAG, missing=True)
    matches = {r["id"]:r for r in api.pages("/releases") if r.get("tag_name")==TAG}
    if prior is not None:
        validate_release(prior)
        matches[prior["id"]] = prior
    if by_tag is not None:
        matches[by_tag["id"]] = by_tag
    require(len(matches)<=1, "Multiple releases claim this tag")
    release = next(iter(matches.values()), None)
    if release:
        validate_release(release)
    peeled_tag(api, required=bool(release and not release["draft"]))
    return release, {"known_failed_release_id":PRIOR_RELEASE_ID,"authenticated_prior_lookup":"PRESENT" if prior else "404_NOT_FOUND"}


def verified_asset(api, asset, expected):
    require(asset.get("state")=="uploaded" and type(asset.get("size")) is int
            and asset["size"]==expected["bytes"], "Existing asset is incomplete or has a different size: "+str(asset.get("name")))
    raw = api.asset_bytes(asset)
    validate_record(raw, expected)
    advertised = asset.get("digest")
    require(advertised in (None,"sha256:"+expected["sha256"]), "GitHub asset digest differs")
    return raw


def release_assets(api, release):
    rows = api.pages("/releases/"+str(release["id"])+"/assets")
    names = [r["name"] for r in rows]
    require(len(names)==len(set(names)) and len(names)==len(set(n.casefold() for n in names)), "Duplicate/casefold release assets")
    return {r["name"]:r for r in rows}


def check_existing_assets(api, release, expected, zeros):
    assets = release_assets(api,release)
    retained = []
    for name, asset in assets.items():
        if name in expected:
            verified_asset(api,asset,expected[name])
        elif name in zeros:
            require(type(asset.get("size")) is int and asset["size"]==0, "Known diagnostic asset has unexpected nonzero bytes")
            require(asset.get("state")=="uploaded", "Failed starter remains; cannot count as verified delivery")
            verified_asset(api,asset,zeros[name])
            retained.append({"name":name,"id":asset["id"],"state":asset["state"],"size":asset["size"],
                "disposition":"Existing uploaded empty diagnostic byte-verified; original zero bytes also preserved inside auxiliary ZIP."})
        else:
            raise ValueError("Unexpected existing release asset: "+name)
    return assets, retained


def upload_files(api, release, folder, expected, zeros):
    actual = folder_files(folder)
    verify_inventory(actual,expected)
    require(all(raw for raw in actual.values()), "Refuse direct empty upload")
    assets, quarantined = check_existing_assets(api,release,expected,zeros)
    for name, raw in actual.items():
        if name in assets:
            continue
        url = "https://uploads.github.com/repos/"+REPO+"/releases/"+str(release["id"])+"/assets?name="+urllib.parse.quote(name,safe="")
        try:
            asset = api.request(url, method="POST", raw=raw)
        except RuntimeError:
            # A concurrent upload can only be reused after strict byte verification.
            current = release_assets(api,release)
            require(name in current, "Upload failed without a verifiable existing asset: "+name)
            asset = current[name]
        require(asset.get("name")==name, "Uploaded asset name differs")
        verified_asset(api,asset,expected[name])
    return quarantined


def cleanup_empty_starters(root, api, release, state):
    inspection_raw = (root/"PRIOR-RELEASE-INSPECTION.json").read_bytes()
    validate_record(inspection_raw,state["prior_release_inspection"])
    prior = decode(inspection_raw)
    require(prior.get("source_revision")==SOURCE, "Prior release inspection source differs")
    auxiliary = (root/"base-assets"/AUX_ZIP).read_bytes()
    validate_record(auxiliary,state["files"][AUX_ZIP])
    inspect_auxiliary(auxiliary,state["zero_files"],
        {"bytes":PINS["failed_publication"][1],"sha256":PINS["failed_publication"][2]},state["prior_release_inspection"])
    snapshot = prior.get("release")
    preserved = {} if snapshot is None else {row["id"]:row for row in snapshot["assets"]}
    repaired = []
    for name, asset in release_assets(api,release).items():
        if asset.get("state") != "starter":
            continue
        require(release.get("draft") is True and snapshot and snapshot.get("draft") is True
                and snapshot.get("id")==release["id"], "Starter repair requires the same preserved unpublished draft")
        require(name in state["zero_files"] and state["zero_files"][name]=={"bytes":0,"sha256":EMPTY_SHA}
                and type(asset.get("size")) is int and asset["size"]==0, "Starter is not an independently verified empty diagnostic")
        saved = preserved.get(asset["id"])
        fields = ("id","name","state","size","digest")
        require(saved and all(saved.get(key)==asset.get(key) for key in fields),
                "Starter metadata was not preserved unchanged")
        latest = api.request("/releases/"+str(release["id"]))
        validate_release(latest)
        require(latest.get("draft") is True, "Release became public; starter deletion refused")
        current = api.request("/releases/assets/"+str(asset["id"]))
        require(all(current.get(key)==asset.get(key) for key in fields)
                and current.get("state")=="starter" and type(current.get("size")) is int
                and current["size"]==0, "Starter changed before deletion")
        api.request("/releases/assets/"+str(asset["id"]),method="DELETE")
        require(name not in release_assets(api,latest), "Starter deletion did not remove the failed asset")
        repaired.append({"preserved_asset":saved,"release_id":release["id"],
                         "disposition":"Deleted only failed zero-byte starter from matching unpublished draft; original metadata and empty bytes preserved in auxiliary archive."})
    return repaired


def publish_base(root, source_dir, api, expected_base_state_sha):
    require(expected_base_state_sha is not None, "Pinned base-state digest required")
    state = checked_base(root,expected_base_state_sha)
    require(state["source_revision"]==SOURCE, "Prepared source differs")
    release, inspection = find_release(api)
    if release is None:
        notes = (Path(source_dir)/"products/alpha-genesis-harness/docs/RELEASE-NOTES.md").read_text()
        release = api.request("/releases", method="POST", value={"tag_name":TAG,"target_commitish":SOURCE,
            "name":TITLE,"body":notes,"draft":True,"prerelease":True,"make_latest":"false"})
        validate_release(release)
    repaired = cleanup_empty_starters(root,api,release,state)
    retained = upload_files(api,release,root/"base-assets",state["files"],state["zero_files"])
    if release["draft"]:
        release = api.request("/releases/"+str(release["id"]), method="PATCH",
                              value={"draft":False,"prerelease":True,"make_latest":"false"})
    validate_release(release)
    require(release["draft"] is False, "Release is still draft")
    peeled_tag(api)
    put(root/"RELEASE-STATE.json", encode({"release_id":release["id"],"release_url":release["html_url"],
        "source_revision":SOURCE,"customer_archive_sha256":CUSTOMER_SHA,"inspection":inspection,
        "repaired_empty_starters":repaired,"retained_uploaded_empty_diagnostics":retained}))
    print(json.dumps({"phase":"publish-base","release_url":release["html_url"],"repaired_empty_starters":repaired,
                      "retained_uploaded_empty_diagnostics":retained}))


def download_base(root, api, expected_base_state_sha):
    require(expected_base_state_sha is not None, "Pinned base-state digest required")
    state = checked_base(root,expected_base_state_sha)
    release = api.request("/releases/tags/"+TAG)
    validate_release(release)
    require(not release["draft"], "Release is not public")
    peeled_tag(api)
    assets, quarantined = check_existing_assets(api,release,state["files"],state["zero_files"])
    require(set(state["files"]).issubset(assets), "Published asset missing")
    for name, expected in state["files"].items():
        put(root/"published-downloads"/name, verified_asset(api,assets[name],expected))
    put(root/"DOWNLOAD-VERIFICATION.json",encode({"source_revision":SOURCE,"release_id":release["id"],
        "files":state["files"],"all_downloaded_bytes_rehashed":True,"retained_uploaded_empty_diagnostics":quarantined}))
    print(json.dumps({"phase":"download-base","verified_files":len(state["files"]),"customer_archive_sha256":CUSTOMER_SHA}))


def restore(root):
    state = checked_base(root)
    files = folder_files(root/"published-downloads")
    verify_inventory(files,state["files"])
    zeros = inspect_auxiliary(files[AUX_ZIP],state["zero_files"],
        {"bytes":PINS["failed_publication"][1],"sha256":PINS["failed_publication"][2]},state["prior_release_inspection"])
    for name, raw in {**files,**zeros}.items():
        put(root/"published"/name,raw)
    for name, expected in state["original_files"].items():
        validate_record((root/"published"/name).read_bytes(),expected)
    require(digest((root/"published"/CUSTOMER).read_bytes())==CUSTOMER_SHA, "Restored customer ZIP differs")
    put(root/"RESTORATION-VERIFICATION.json",encode({"source_revision":SOURCE,"customer_archive_sha256":CUSTOMER_SHA,
        "restored_zero_files":state["zero_files"],"all_original_asset_bytes_verified":True}))
    print(json.dumps({"phase":"restore","zero_files":state["zero_files"],"original_files":len(state["original_files"])}))


def child_env(visual_modules=None):
    env = {key:os.environ[key] for key in SAFE_ENV if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    if visual_modules:
        env["NODE_PATH"] = str(Path(visual_modules).resolve())
    return env


def run_child(command, cwd, log_root, label, env=None):
    log_root.mkdir(parents=True,exist_ok=True)
    with (log_root/(label+".stdout.txt")).open("xb") as out, (log_root/(label+".stderr.txt")).open("xb") as err:
        result = subprocess.run(command,cwd=cwd,env=env or child_env(),stdin=subprocess.DEVNULL,stdout=out,stderr=err)
    require(result.returncode==0, "Credential-free child failed: "+label+" (see retained logs)")
    return result.returncode


def operate(root, source_dir, dom_modules, published=False):
    product = source_guard(source_dir)
    folder = root/("published" if published else "received-original")
    label = "published" if published else "received"
    require(digest((folder/CUSTOMER).read_bytes())==CUSTOMER_SHA, "Archive differs before operation")
    cmd=[sys.executable,"-B",str(product/"scripts/qualify_archive.py"),str(folder/CUSTOMER),
         "--expected-sha256",CUSTOMER_SHA,"--expected-source-revision",SOURCE,
         "--output",str(root/(label+"-operation")),"--dom-modules",str(Path(dom_modules).resolve())]
    run_child(cmd,product,root/"operation-logs",label)
    receipt=read(root/(label+"-operation")/"QUALIFICATION.json")
    require(receipt.get("source_revision")==SOURCE and receipt.get("archive_sha256")==CUSTOMER_SHA
            and receipt.get("verdict")=="PASSED IN SCOPE" and len(receipt.get("operations",[]))==15
            and all(type(row.get("returncode")) is int and row["returncode"]==0 for row in receipt["operations"]), "Archive operation incomplete")
    source_guard(source_dir)
    print(json.dumps({"phase":"operate-"+label,"source_revision":SOURCE,"archive_sha256":CUSTOMER_SHA,
                      "operations":len(receipt["operations"]),"verdict":receipt["verdict"],"child_environment_keys":sorted(child_env())}))


def assemble(root, source_dir, visual_modules):
    product=source_guard(source_dir)
    pub=root/"published";op=root/"published-operation/QUALIFICATION.json"
    common=[sys.executable,"-B"]
    run_child(common+[str(product/"scripts/reconcile_release_evidence.py"),"--archive",str(pub/CUSTOMER),
        "--expected-sha256",CUSTOMER_SHA,"--source-sha",SOURCE,"--source-product-tree",PRODUCT_TREE,
        "--operation-receipt",str(op),"--asset-dir",str(pub),"--live-receipt",str(pub/"HOSTED-LOCAL-QUALIFICATION.json"),
        "--model-evidence-archive",str(pub/MODEL_ZIP),"--output",str(root/"final-evidence")],
        product,root/"operation-logs","reconcile")
    run_child(common+[str(product/"scripts/owner_handoff.py"),"--source-sha",SOURCE,
        "--release-url","https://github.com/"+REPO+"/releases/tag/"+TAG,
        "--asset-dir",str(pub),"--customer-zip",str(pub/CUSTOMER),"--expected-sha256",CUSTOMER_SHA,
        "--operation-receipt",str(op),"--matrix",str(root/"final-evidence/QUALIFICATION-MATRIX.json"),
        "--model-evidence-archive",str(pub/MODEL_ZIP),"--output",str(root/"owner")],
        product,root/"operation-logs","owner")
    owner=read(root/"operation-logs/owner.stdout.txt")
    require(owner.get("source_revision")==SOURCE and owner.get("customer_archive_sha256")==CUSTOMER_SHA
            and owner.get("included_deliverable_types")==22 and owner.get("expected_deliverable_types")==22
            and owner.get("commercially_ready") is False, "Owner inventory incomplete")
    run_child(["node",str(product/"scripts/verify_owner_handoff.cjs"),owner["owner_directory"],
        str(root/"owner-visual"),SOURCE],product,root/"operation-logs","owner-visual",child_env(visual_modules))
    visual=read(root/"owner-visual/OWNER-VISUAL-VERIFICATION.json")
    require(visual.get("status")=="PASS" and visual.get("source_revision")==SOURCE, "Owner visual qualification failed")
    matrix=read(root/"final-evidence/QUALIFICATION-MATRIX.json")
    require(matrix.get("source_revision")==SOURCE and matrix.get("archive_sha256")==CUSTOMER_SHA
            and len(matrix.get("criteria",[]))==39 and matrix.get("commercially_validated") is False, "Final matrix identity/count differs")
    files={}
    for folder in (root/"final-evidence",root/"owner-visual"):
        for name,raw in folder_files(folder).items():
            require(safe_name(name,True) and name not in files,"Final asset collision")
            files[name]=raw
    for path in (root/"owner").iterdir():
        if path.is_file():
            require(path.name not in files,"Final owner asset collision")
            files[path.name]=path.read_bytes()
    for name in ("INPUT-VERIFICATION.json","DOWNLOAD-VERIFICATION.json","RESTORATION-VERIFICATION.json","RELEASE-STATE.json"):
        files[name]=(root/name).read_bytes()
    operation_files=folder_files(root/"published-operation")
    files["PUBLISHED-OPERATION-EVIDENCE_68c2c1a00c78.zip"]=zip_bytes(operation_files)
    completion={"schema":"harness-publication-recovery-completion/v1","source_revision":SOURCE,
        "source_product_tree":PRODUCT_TREE,"customer_archive_sha256":CUSTOMER_SHA,
        "published_operation":"PASSED IN SCOPE","operations":15,"matrix_criteria":39,
        "matrix_counts":{status:sum(row["status"]==status for row in matrix["criteria"]) for status in ("PASS","FAIL","BLOCKED","NOT TESTED")},
        "owner_deliverable_types":22,"owner_visual_status":visual["status"],
        "owner_zip_sha256":owner["owner_zip_sha256"],"commercially_ready":False,
        "no_model_retry":True,"scope":"Exact source68 publication transport recovery; existing scientific failures and external commercial blocks preserved.",
        "source_helper_hashes":{name:digest((product/"scripts"/name).read_bytes()) for name in
            ("qualify_archive.py","reconcile_release_evidence.py","owner_handoff.py","verify_owner_handoff.cjs")}}
    files["RECOVERY-COMPLETION.json"]=encode(completion)
    require(all(files.values()),"Final direct assets must be nonempty")
    files[FINAL_INVENTORY]=encode({"source_revision":SOURCE,"customer_archive_sha256":CUSTOMER_SHA,"files":inventory(files)})
    for name,raw in files.items():
        put(root/"final-assets"/name,raw)
    validate_final_files(files)
    put(root/"FINAL-STATE.json",encode({"source_revision":SOURCE,"files":inventory(files)}))
    source_guard(source_dir)
    print(json.dumps(completion))


def validate_final_files(files):
    bundle = "ALPHA_GENESIS_HARNESS_OWNER_HANDOFF_0.3.0_" + SOURCE[:12]
    owner_name = bundle + ".zip"
    operation_name = "PUBLISHED-OPERATION-EVIDENCE_" + SOURCE[:12] + ".zip"
    expected_names = {"QUALIFICATION-MATRIX.json","QUALIFICATION-MATRIX.md","RECONCILIATION.json",
        "OWNER-VISUAL-VERIFICATION.json","HARNESS-OWNER-desktop.png","HARNESS-OWNER-mobile.png",
        owner_name,owner_name+".sha256",bundle+".receipt.json","INPUT-VERIFICATION.json",
        "DOWNLOAD-VERIFICATION.json","RESTORATION-VERIFICATION.json","RELEASE-STATE.json",
        operation_name,"RECOVERY-COMPLETION.json",FINAL_INVENTORY}
    require(set(files)==expected_names, "Final publication inventory differs")
    declared = decode(files[FINAL_INVENTORY])
    require(declared.get("source_revision")==SOURCE and declared.get("customer_archive_sha256")==CUSTOMER_SHA,
            "Final public inventory identity differs")
    verify_inventory({n:b for n,b in files.items() if n!=FINAL_INVENTORY},declared["files"])
    matrix = decode(files["QUALIFICATION-MATRIX.json"])
    require(matrix.get("source_revision")==SOURCE and matrix.get("source_product_tree")==PRODUCT_TREE
            and matrix.get("archive_sha256")==CUSTOMER_SHA and matrix.get("commercially_validated") is False
            and len(matrix.get("criteria",[]))==39, "Final matrix identity differs")
    audit = decode(files["RECONCILIATION.json"])
    require(audit.get("source_revision")==SOURCE and audit.get("source_product_tree")==PRODUCT_TREE
            and audit.get("archive_sha256")==CUSTOMER_SHA and audit.get("commercially_ready") is False,
            "Final reconciliation identity differs")
    operation_files = zip_members(files[operation_name])
    operation = decode(operation_files["QUALIFICATION.json"])
    require(operation.get("source_revision")==SOURCE and operation.get("archive_sha256")==CUSTOMER_SHA
            and operation.get("verdict")=="PASSED IN SCOPE" and len(operation.get("operations",[]))==15
            and all(type(row.get("returncode")) is int and row["returncode"]==0
                    and isinstance(row.get("command"),list) and row["command"]
                    and all(isinstance(arg,str) and arg for arg in row["command"]) for row in operation["operations"]),
            "Final published operation incomplete")
    visual = decode(files["OWNER-VISUAL-VERIFICATION.json"])
    require(visual.get("source_revision")==SOURCE and visual.get("status")=="PASS"
            and visual.get("errors")==[] and not visual.get("error")
            and set(visual.get("screenshots",[]))=={"HARNESS-OWNER-desktop.png","HARNESS-OWNER-mobile.png"}
            and all(check in visual.get("checks",[]) for check in (
                "All 22 delivery categories rendered","390px responsive viewport without document overflow",
                "No network requests or JavaScript page errors")), "Owner visual proof incomplete")
    owner_files = zip_members(files[owner_name])
    prefix = bundle + "/"
    require(all(name.startswith(prefix) for name in owner_files), "Owner ZIP root differs")
    owner_files = {name[len(prefix):]:raw for name,raw in owner_files.items()}
    manifest = decode(owner_files["OWNER-FILE-MANIFEST.json"])
    require(manifest.get("schema")=="alpha-harness-owner-manifest/v1" and manifest.get("source_revision")==SOURCE
            and manifest.get("customer_archive_sha256")==CUSTOMER_SHA and manifest.get("self_excluded") is True,
            "Owner manifest identity differs")
    rows=manifest["files"]
    require(isinstance(rows,list) and all(isinstance(row,dict) and safe_name(row.get("path")) for row in rows)
            and len(rows)==len({row["path"] for row in rows}), "Owner manifest paths invalid")
    verify_inventory({n:b for n,b in owner_files.items() if n!="OWNER-FILE-MANIFEST.json"},
                     {row["path"]:{"bytes":row["bytes"],"sha256":row["sha256"]} for row in rows})
    identity=decode(owner_files["OWNER-HANDOFF.json"])
    require(identity.get("source_revision")==SOURCE and identity.get("source_product_tree")==PRODUCT_TREE
            and identity.get("archive_sha256")==CUSTOMER_SHA and identity.get("archive_name")==CUSTOMER
            and identity.get("commercially_ready") is False
            and identity.get("release_url")=="https://github.com/"+REPO+"/releases/tag/"+TAG,
            "Owner identity differs")
    deliverables=identity["required_deliverables"]
    def owner_path_present(path):
        if not isinstance(path,str):
            return False
        if path.endswith("/"):
            return safe_name(path[:-1]) and any(name.startswith(path) for name in owner_files)
        return safe_name(path) and path in owner_files
    require(len(deliverables)==22 and {row.get("id") for row in deliverables}=={str(n) for n in range(1,23)}
            and all(row.get("included") is True and row.get("paths")
            and all(owner_path_present(path) for path in row["paths"]) for row in deliverables),
            "Owner deliverable inventory incomplete")
    customer=owner_files["01-CUSTOMER-DOWNLOAD/"+CUSTOMER]
    require(digest(customer)==CUSTOMER_SHA, "Embedded customer archive changed")
    require(decode(owner_files["05-VERIFICATION/QUALIFICATION-MATRIX.json"])==matrix
            and owner_files["05-VERIFICATION/PUBLISHED-OPERATION.json"]==operation_files["QUALIFICATION.json"],
            "Owner embedded qualification receipts differ")
    receipt=decode(files[bundle+".receipt.json"])
    require(receipt.get("source_revision")==SOURCE and receipt.get("customer_archive_sha256")==CUSTOMER_SHA
            and receipt.get("owner_zip_sha256")==digest(files[owner_name])
            and receipt.get("owner_zip_bytes")==len(files[owner_name])
            and receipt.get("included_deliverable_types")==22 and receipt.get("expected_deliverable_types")==22
            and receipt.get("commercially_ready") is False, "Owner release receipt differs")
    require(files[owner_name+".sha256"]==(digest(files[owner_name])+"  "+owner_name+"\n").encode(),
            "Owner checksum differs")
    completion=decode(files["RECOVERY-COMPLETION.json"])
    require(completion.get("source_revision")==SOURCE and completion.get("source_product_tree")==PRODUCT_TREE
            and completion.get("customer_archive_sha256")==CUSTOMER_SHA
            and completion.get("owner_zip_sha256")==digest(files[owner_name])
            and completion.get("commercially_ready") is False and completion.get("no_model_retry") is True,
            "Recovery completion identity differs")
    customer_files=zip_members(customer)
    for name,expected in completion["source_helper_hashes"].items():
        matches=[raw for path,raw in customer_files.items() if path.endswith("/scripts/"+name)]
        require(len(matches)==1 and digest(matches[0])==expected, "Recovery helper differs from exact customer source")
    require(set(completion["source_helper_hashes"])=={"qualify_archive.py","reconcile_release_evidence.py",
            "owner_handoff.py","verify_owner_handoff.cjs"}, "Recovery source-helper inventory differs")


def checked_final(root, expected_state_sha):
    require(isinstance(expected_state_sha,str) and re.fullmatch(r"[0-9a-f]{64}",expected_state_sha),
            "Pinned final-state digest required from completed owner assembly step")
    raw=(root/"FINAL-STATE.json").read_bytes()
    require(digest(raw)==expected_state_sha, "Final state changed after credential-free assembly")
    final=decode(raw)
    require(final.get("source_revision")==SOURCE, "Final source differs")
    files=folder_files(root/"final-assets")
    verify_inventory(files,final["files"])
    validate_final_files(files)
    return final


def publish_final(root, api, expected_final_state_sha, expected_base_state_sha):
    require(expected_base_state_sha is not None, "Pinned base-state digest required")
    base=checked_base(root,expected_base_state_sha);final=checked_final(root,expected_final_state_sha)
    require(final["source_revision"]==SOURCE,"Final source differs")
    require(not set(base["files"]).intersection(final["files"]),"Base/final asset collision")
    release=api.request("/releases/tags/"+TAG);validate_release(release);peeled_tag(api)
    require(release["draft"] is False,"Cannot finalize a draft")
    all_expected={**base["files"],**final["files"]}
    # Validate base and any already uploaded final assets before adding anything.
    check_existing_assets(api,release,all_expected,base["zero_files"])
    actual=folder_files(root/"final-assets");verify_inventory(actual,final["files"])
    for name,raw in actual.items():
        require(raw,"Refuse direct empty final upload")
        assets=release_assets(api,release)
        if name not in assets:
            url="https://uploads.github.com/repos/"+REPO+"/releases/"+str(release["id"])+"/assets?name="+urllib.parse.quote(name,safe="")
            try:asset=api.request(url,method="POST",raw=raw)
            except RuntimeError:
                current=release_assets(api,release);require(name in current,"Final upload failed");asset=current[name]
        else:asset=assets[name]
        verified_asset(api,asset,final["files"][name])
    assets,quarantined=check_existing_assets(api,release,all_expected,base["zero_files"])
    require(set(all_expected).issubset(assets),"Final release asset missing")
    result={"source_revision":SOURCE,"release_url":release["html_url"],"asset_count":len(all_expected),
        "every_published_file_rehashed":True,"retained_uploaded_empty_diagnostics":quarantined,
        "customer_archive_sha256":CUSTOMER_SHA,"owner":read(root/"RECOVERY-COMPLETION.json") if (root/"RECOVERY-COMPLETION.json").exists() else read(root/"final-assets/RECOVERY-COMPLETION.json")}
    put(root/"PUBLICATION-COMPLETED.json",encode(result))
    print(json.dumps(result))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("acquire","prepare","operate-received","publish-base","download-base","restore","operate-published","assemble","publish-final"))
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--source-dir",type=Path,required=True)
    parser.add_argument("--dom-modules",type=Path)
    parser.add_argument("--visual-modules",type=Path)
    parser.add_argument("--expected-final-state-sha256")
    parser.add_argument("--expected-base-state-sha256")
    args=parser.parse_args()
    root=args.root.resolve();root.mkdir(parents=True,exist_ok=True)
    api=GitHub(os.environ.get("GH_TOKEN")) if args.phase in TOKEN_PHASES else None
    if api is None:
        environment=child_env()
        os.environ.clear();os.environ.update(environment)
    if args.phase=="acquire":acquire(root,api)
    elif args.phase=="prepare":prepare(root,args.source_dir)
    elif args.phase=="publish-base":publish_base(root,args.source_dir,api,args.expected_base_state_sha256)
    elif args.phase=="download-base":download_base(root,api,args.expected_base_state_sha256)
    elif args.phase=="restore":restore(root)
    elif args.phase.startswith("operate-"):
        require(args.dom_modules is not None,"Pinned DOM modules required")
        operate(root,args.source_dir,args.dom_modules,args.phase=="operate-published")
    elif args.phase=="assemble":
        require(args.visual_modules is not None,"Pinned visual modules required")
        assemble(root,args.source_dir,args.visual_modules)
    elif args.phase=="publish-final":publish_final(root,api,args.expected_final_state_sha256,args.expected_base_state_sha256)


if __name__=="__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status":"REFUSED","error_type":type(error).__name__,"error":str(error)}),file=sys.stderr)
        raise SystemExit(1)
