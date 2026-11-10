# SPDX-License-Identifier: Apache-2.0
"""Independent adversarial release-archive acceptance, using fabricated ZIPs.

These tests are not evidence of a downloaded public release or native OS support.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import os
from unittest import mock
import unittest
import warnings
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package_release.py"
spec = importlib.util.spec_from_file_location("independent_release_target", SCRIPT)
package = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(package)
ROOT = "ALPHA_GENESIS_HARNESS_0.1.0/"
MANIFEST = ROOT + "RELEASE-MANIFEST.json"


class IndependentReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fixture.zip"
        # Deliberately made by this evaluator, not by target build().
        self.files = {name: ("Independent fixture for " + name).encode() for name in package.REQUIRED}
        self.files["VERSION.json"] = b'{"version":"0.1.0"}'
        self.manifest = {
            "schema":"alpha-genesis-harness-release/v1",
            "version":"0.1.0",
            "source_revision":"0"*40,
            "source_product_tree":None,
            "build_mode":"candidate",
            "source_matches_commit":False,
            "files":[{"path":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()} for name,data in sorted(self.files.items())],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, extra=None, duplicate=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.path,"w",zipfile.ZIP_DEFLATED) as out:
                for name,data in self.files.items():out.writestr(ROOT+name,data)
                out.writestr(MANIFEST,json.dumps(self.manifest))
                if extra:
                    for name,data in extra:out.writestr(name,data)
                if duplicate:out.writestr(ROOT+duplicate,self.files[duplicate])
        return self.path

    def rejects(self):
        with self.assertRaises((ValueError,KeyError,zipfile.BadZipFile)):
            package.verify(self.path)

    def test_valid_fabricated_inventory_is_only_integrity_not_source_authentication(self):
        result=package.verify(self.write())
        self.assertEqual(result["integrity"],"PASSED IN SCOPE")
        self.assertFalse(result["source_matches_commit"])

    def test_single_byte_change_is_detected(self):
        self.files["app/engine.js"] += b"!"
        self.write();self.rejects()

    def test_omitted_member_is_detected(self):
        del self.files["app/engine.js"]
        self.write();self.rejects()

    def test_unlisted_member_is_detected(self):
        self.write(extra=[(ROOT+"app/extra.js",b"console.log(1)")]);self.rejects()

    def test_traversal_is_rejected_even_when_manifest_and_hashes_agree(self):
        name="app/../../escape.js";data=b"danger"
        self.files[name]=data
        self.manifest["files"].append({"path":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
        self.write();self.rejects()

    def test_duplicate_zip_member_is_rejected(self):
        self.write(duplicate="app/engine.js");self.rejects()

    def test_duplicate_manifest_record_is_rejected(self):
        self.manifest["files"].append(dict(self.manifest["files"][0]))
        self.write();self.rejects()

    def test_symbolic_link_is_rejected(self):
        self.write()
        data=b"../../escape"
        with zipfile.ZipFile(self.path,"a") as out:
            info=zipfile.ZipInfo(ROOT+"app/link.js")
            info.create_system=3;info.external_attr=0o120777<<16
            out.writestr(info,data)
        self.rejects()

    def test_malformed_source_revision_is_rejected(self):
        self.manifest["source_revision"]="main"
        self.write();self.rejects()

    def test_manifest_cannot_certify_its_own_source_identity(self):
        self.manifest["source_matches_commit"]=True
        self.manifest["build_mode"]="source-bound"
        self.manifest["source_product_tree"]="1"*40
        self.write()
        try:result=package.verify(self.path)
        except (ValueError,KeyError):return
        self.assertFalse(result["source_matches_commit"],"A self-asserted manifest cannot independently prove source identity")

    def test_external_digest_mismatch_rejects_a_self_consistent_archive(self):
        self.write()
        with self.assertRaises(ValueError):package.verify(self.path, expected_sha256="f"*64)

    def test_external_digest_match_is_reported_without_source_certification(self):
        self.write()
        result=package.verify(self.path, expected_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertTrue(result["external_archive_hash_matched"])
        self.assertFalse(result["source_matches_commit"])

    def test_external_revision_mismatch_is_rejected(self):
        self.write()
        with self.assertRaises(ValueError):package.verify(self.path, expected_source_revision="f"*40)

    def test_noncanonical_paths_are_rejected(self):
        for name in ["app//extra.js","app/./extra.js"]:
            with self.subTest(name=name):
                self.files[name]=b"extra"
                self.manifest["files"].append({"path":name,"bytes":5,"sha256":hashlib.sha256(b"extra").hexdigest()})
                self.write();self.rejects()
                del self.files[name];self.manifest["files"].pop()

    def test_path_swap_cannot_rebind_hash_to_different_archive_contents(self):
        self.write()
        first=self.path.read_bytes()
        first_hash=hashlib.sha256(first).hexdigest()
        self.manifest["source_revision"]="f"*40
        self.write()
        replacement=Path(self.tmp.name)/"replacement.zip"
        replacement.write_bytes(self.path.read_bytes())
        self.path.write_bytes(first)
        original_open=Path.open
        swapped=[]
        target=self.path
        class SwappingReader:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def read(self,*args):
                result=self.stream.read(*args)
                if not swapped:
                    os.replace(replacement,target)
                    swapped.append(True)
                return result
        def controlled_open(path,*args,**kwargs):
            stream=original_open(path,*args,**kwargs)
            return SwappingReader(stream) if path==target and args and args[0]=="rb" else stream
        with mock.patch.object(Path,"open",controlled_open):
            result=package.verify(self.path, expected_sha256=first_hash)
        self.assertTrue(swapped,"Deterministic replacement must actually occur")
        self.assertTrue(result["external_archive_hash_matched"])
        self.assertEqual(result["source_revision"],"0"*40)

    def test_private_key_bytes_cannot_enter_a_verified_package(self):
        data=b"-----BEGIN " + b"PRIVATE KEY-----\nnot a key\n-----END " + b"PRIVATE KEY-----"
        self.files["app/engine.js"]=data
        for record in self.manifest["files"]:
            if record["path"]=="app/engine.js":record.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        self.write();self.rejects()


if __name__ == "__main__":
    unittest.main()
