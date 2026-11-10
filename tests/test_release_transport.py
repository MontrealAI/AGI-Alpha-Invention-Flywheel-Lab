"""Synthetic transport regressions; no API calls, credentials, inference or publication."""
import copy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/release_transport.py"
spec = importlib.util.spec_from_file_location("release_transport", SCRIPT)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def release(**changes):
    result = {"id":123,"tag_name":transport.TAG,"target_commitish":transport.SOURCE,
              "name":transport.TITLE,"prerelease":True,"draft":False,
              "url":transport.API_ROOT+"/releases/123",
              "html_url":"https://github.com/"+transport.REPO+"/releases/tag/"+transport.TAG}
    result.update(changes)
    return result


class AssetAPI:
    def __init__(self, files=None, states=None):
        self.rows = {}
        self.bodies = {}
        self.posts = []
        for number,(name,raw) in enumerate((files or {}).items(),1):
            self.add(name,raw,number,(states or {}).get(name,"uploaded"))
    def add(self,name,raw,identifier,state="uploaded"):
        self.rows[name] = {"id":identifier,"name":name,"state":state,"size":len(raw),
                          "url":transport.API_ROOT+"/releases/assets/"+str(identifier),
                          "digest":"sha256:"+transport.digest(raw)}
        self.bodies[identifier]=raw
    def pages(self,path):
        return list(self.rows.values())
    def asset_bytes(self,row):
        return self.bodies[row["id"]]
    def request(self,path,method="GET",raw=None,**kwargs):
        if method=="POST":
            name=transport.urllib.parse.parse_qs(transport.urllib.parse.urlsplit(path).query)["name"][0]
            self.posts.append(name);self.add(name,raw,len(self.rows)+1)
            return self.rows[name]
        raise AssertionError("Unexpected synthetic API request")


class RecoveryTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.original={transport.DIAGNOSTIC_FAILURE_NAME:b"", "Windows-CODEX-HOST-VERIFICATION.stdout.txt":b"recorded", "other.stderr.txt":b""}
        self.failure=b"preserved original artifact fixture"
        self.inspection=transport.encode({"source_revision":transport.SOURCE,"release":None})
        self.aux,self.manifest=transport.package_auxiliary(self.original,self.failure,self.inspection)

    def test_auxiliary_preserves_exact_empty_and_failure_bytes_deterministically(self):
        again,_=transport.package_auxiliary(self.original,self.failure,self.inspection)
        self.assertEqual(self.aux,again)
        restored=transport.inspect_auxiliary(self.aux,self.manifest["original_zero_files"],transport.record(self.failure),transport.record(self.inspection))
        self.assertEqual(restored,{transport.DIAGNOSTIC_FAILURE_NAME:b"","other.stderr.txt":b""})
        for value in self.manifest["original_zero_files"].values():
            self.assertEqual(value,{"bytes":0,"sha256":transport.EMPTY_SHA})

    def test_nonempty_or_absent_failed_stderr_cannot_be_classified_as_empty(self):
        for value in ({}, {transport.DIAGNOSTIC_FAILURE_NAME:b"\n"}):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,"not actually empty"):
                transport.package_auxiliary(value,self.failure,self.inspection)

    def test_empty_non_diagnostic_file_is_refused(self):
        with self.assertRaisesRegex(ValueError,"non-diagnostic"):
            transport.package_auxiliary({**self.original,"receipt.json":b""},self.failure,self.inspection)

    def test_auxiliary_refuses_extra_missing_changed_and_foreign_source_members(self):
        original=transport.zip_members(self.aux)
        for mutation in ("extra","missing","changed","source","failure_artifact"):
            files=dict(original)
            if mutation=="extra":files["extra.txt"]=b"x"
            if mutation=="missing":files.pop("empty/"+transport.DIAGNOSTIC_FAILURE_NAME)
            if mutation=="changed":files["empty/"+transport.DIAGNOSTIC_FAILURE_NAME]=b"\n"
            if mutation in ("source","failure_artifact"):
                body=transport.decode(files["AUXILIARY-MANIFEST.json"])
                body["source_revision" if mutation=="source" else "failure_artifact"]="0"*40
                files["AUXILIARY-MANIFEST.json"]=transport.encode(body)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                transport.inspect_auxiliary(transport.zip_bytes(files),self.manifest["original_zero_files"],transport.record(self.failure),transport.record(self.inspection))

    def test_unsafe_and_duplicate_zip_members_are_refused(self):
        for names in (["../escape"],["/absolute"],["a\\b"],["A.txt","a.txt"],["same","same"],["NUL.txt"]):
            out=io.BytesIO()
            with zipfile.ZipFile(out,"w") as package:
                for name in names:package.writestr(name,b"x")
            with self.subTest(names=names),self.assertRaises(ValueError):
                transport.zip_members(out.getvalue())
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as package:
            info=zipfile.ZipInfo("link");info.create_system=3;info.external_attr=0o120777<<16
            package.writestr(info,b"target")
        with self.assertRaisesRegex(ValueError,"Unsafe ZIP"):
            transport.zip_members(out.getvalue())

    def test_existing_local_file_is_never_clobbered(self):
        target=self.root/"x"
        transport.put(target,b"original")
        transport.put(target,b"original")
        with self.assertRaisesRegex(ValueError,"Existing file differs"):
            transport.put(target,b"changed")
        self.assertEqual(target.read_bytes(),b"original")

    def test_matching_existing_asset_reuses_verified_bytes_without_upload(self):
        folder=self.root/"assets";folder.mkdir();(folder/"x.txt").write_bytes(b"original")
        api=AssetAPI({"x.txt":b"original"})
        transport.upload_files(api,release(),folder,{"x.txt":transport.record(b"original")},{})
        self.assertEqual(api.posts,[])

    def test_mismatching_or_incomplete_nonzero_asset_is_refused_without_upload(self):
        folder=self.root/"assets";folder.mkdir();(folder/"x.txt").write_bytes(b"original")
        for api in (AssetAPI({"x.txt":b"different"}),AssetAPI({"x.txt":b"replaced"}),AssetAPI({"x.txt":b"original"},{"x.txt":"starter"})):
            with self.assertRaises(ValueError):
                transport.upload_files(api,release(),folder,{"x.txt":transport.record(b"original")},{})
            self.assertEqual(api.posts,[])

    def test_unknown_existing_asset_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError,"Unexpected existing"):
            transport.check_existing_assets(AssetAPI({"unknown":b"x"}),release(),{},{})

    def test_new_nonempty_asset_is_uploaded_then_rehashed(self):
        folder=self.root/"assets";folder.mkdir();(folder/"x.txt").write_bytes(b"original")
        api=AssetAPI()
        transport.upload_files(api,release(),folder,{"x.txt":transport.record(b"original")},{})
        self.assertEqual(api.posts,["x.txt"])
        self.assertEqual(api.bodies[1],b"original")

    def test_empty_asset_cannot_be_sent_directly(self):
        folder=self.root/"assets";folder.mkdir();(folder/"x.txt").write_bytes(b"")
        api=AssetAPI()
        with self.assertRaisesRegex(ValueError,"direct empty"):
            transport.upload_files(api,release(),folder,{"x.txt":transport.record(b"")},{})
        self.assertFalse(api.posts)

    def test_release_source_tag_repo_and_type_are_checked(self):
        for changes in ({"target_commitish":"main"},{"tag_name":"wrong"},{"prerelease":False},{"name":"other"},
                        {"url":"https://api.github.com/repos/other/repo/releases/123"}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                transport.validate_release(release(**changes))

    def test_tag_must_peel_to_exact_source(self):
        class API:
            def request(self,path,**kwargs):
                if "/git/ref/" in path:return {"object":{"type":"tag","sha":"1"*40}}
                return {"object":{"type":"commit","sha":"2"*40}}
        with self.assertRaisesRegex(ValueError,"different commit"):
            transport.peeled_tag(API())

    def test_non404_errors_do_not_create_an_absent_release(self):
        class API:
            def request(self,*args,**kwargs):raise RuntimeError("HTTP 403")
        with self.assertRaisesRegex(RuntimeError,"403"):
            transport.find_release(API())

    def test_token_free_environment_is_an_allowlist(self):
        secrets={"GH_TOKEN":"do-not-copy","GITHUB_TOKEN":"do-not-copy","ACTIONS_RUNTIME_TOKEN":"do-not-copy",
                 "AWS_SECRET_ACCESS_KEY":"do-not-copy","PATH":"/trusted","HOME":"/home/runner","LANG":"C"}
        with patch.dict(os.environ,secrets,clear=True):
            child=transport.child_env("/pinned/modules")
        self.assertEqual(set(child),{"PATH","HOME","LANG","NODE_PATH","PYTHONDONTWRITEBYTECODE","PYTHONUNBUFFERED"})
        self.assertNotIn("do-not-copy",str(child))

    def test_authenticated_redirect_is_disabled_and_signed_hosts_are_bounded(self):
        request=urllib.request.Request("https://api.github.com/repos/x/y/actions/artifacts/1/zip",
                                       headers={"Authorization":"Bearer do-not-forward"})
        self.assertIsNone(transport.NoRedirect().redirect_request(request,None,302,"Found",{},
                            "https://release-assets.githubusercontent.com/object"))
        for url in ("http://release-assets.githubusercontent.com/x","https://example.com/x",
                    "https://user@release-assets.githubusercontent.com/x",
                    "https://release-assets.githubusercontent.com:443/x",
                    "https://release-assets.githubusercontent.com.evil.test/x",
                    "https://release-assets.githubusercontent.com/x#fragment"):
            with self.subTest(url=url),self.assertRaises(ValueError):
                transport.approved_download(url)

    def test_binary_redirect_has_no_publication_authorization(self):
        requests=[]
        class Opener:
            def open(self,request,**kwargs):
                requests.append(request)
                if len(requests)==1:
                    raise urllib.error.HTTPError(request.full_url,302,"Found",
                        {"Location":"https://release-assets.githubusercontent.com/object?signature=public"},None)
                return io.BytesIO(b"exact")
        api=transport.GitHub("never-forward")
        api.opener=Opener()
        self.assertEqual(api.request("/actions/artifacts/1/zip",accept="application/octet-stream"),b"exact")
        self.assertEqual(requests[0].get_header("Authorization"),"Bearer never-forward")
        self.assertIsNone(requests[1].get_header("Authorization"))
        self.assertEqual(len(requests),2)

    def test_api_403_429_500_are_never_absence(self):
        for code in (403,429,500):
            class Opener:
                def open(self,request,**kwargs):
                    raise urllib.error.HTTPError(request.full_url,code,"Failure",{},None)
            api=transport.GitHub("token");api.opener=Opener()
            with self.subTest(code=code),self.assertRaises(RuntimeError):
                api.request("/releases/123",missing=True)

    def test_pin_metadata_mismatch_refuses_before_download(self):
        class API:
            def __init__(self):self.calls=[]
            def request(self,path,**kwargs):
                self.calls.append(path)
                return {"id":1,"size_in_bytes":0}
        api=API()
        with self.assertRaisesRegex(ValueError,"Pinned artifact"):
            transport.acquire(self.root,api)
        self.assertEqual(len(api.calls),1)
        self.assertFalse((self.root/"input-zips").exists())

    def test_zip_rejects_nul_name_dos_directory_and_unsupported_compression(self):
        raw=transport.zip_bytes({"a-b":b"value"})
        nul=raw.replace(b"a-b",b"a\x00b")
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as archive:
            entry=zipfile.ZipInfo("directory-without-slash");entry.external_attr=0x10
            archive.writestr(entry,b"value")
        dos=out.getvalue()
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_BZIP2) as archive:
            archive.writestr("compressed",b"value")
        for invalid in (nul,dos,out.getvalue()):
            with self.subTest(size=len(invalid)),self.assertRaisesRegex(ValueError,"Unsafe ZIP"):
                transport.zip_members(invalid)

    def test_model_zip_reproduces_source68_writer_semantics(self):
        files={"a.txt":(b"repeat "+bytes(range(100)))*100,"empty.txt":b""}
        output=io.BytesIO()
        with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,raw in sorted(files.items()):
                info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
                info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,raw)
        self.assertEqual(transport.zip_bytes(files,original_model_format=True),output.getvalue())

    def test_unpublished_draft_html_url_can_be_untagged_but_public_cannot(self):
        url="https://github.com/"+transport.REPO+"/releases/tag/untagged-abc123"
        transport.validate_release(release(draft=True,html_url=url))
        with self.assertRaises(ValueError):
            transport.validate_release(release(draft=False,html_url=url))

    def input_fixture(self, duplicate=b"same"):
        members={"assets":{"same.txt":b"same","source.json":b"source"},
                 "macos":{"same.txt":duplicate,"native.json":b"native"},
                 "model":{"nested/receipt.json":b"actual"},
                 "failed_publication":{"failed.txt":b"failure"}}
        pins={};rows={};original={};public={}
        for index,(key,files) in enumerate(members.items(),1):
            raw=transport.zip_bytes(files)
            pins[key]=(index,len(raw),transport.digest(raw),"fixture-")
            transport.put(self.root/"input-zips"/(key+".zip"),raw)
            rows[key]={"artifact_id":index,"archive":transport.record(raw),"files":transport.inventory(files)}
            if key=="failed_publication":continue
            target=public if key=="model" else original
            target.update(files)
        for folder,files in (("received-original",original),("local-public",public)):
            for name,raw in files.items():transport.put(self.root/folder/name,raw)
        transport.put(self.root/"INPUT-VERIFICATION.json",transport.encode({
            "source_revision":transport.SOURCE,"source_product_tree":transport.PRODUCT_TREE,
            "qualification_run":transport.RUN,"raw_wrapper_hashes_verified":True,"artifacts":rows}))
        return pins,original,public

    def test_pinned_wrapper_inventories_accept_only_identical_duplicate_members(self):
        pins,original,public=self.input_fixture()
        with patch.dict(transport.PINS,pins,clear=True):
            self.assertEqual(transport.verified_inputs(self.root),(original,public))

    def test_differing_duplicate_pinned_members_are_refused(self):
        pins,_,_=self.input_fixture(duplicate=b"different")
        with patch.dict(transport.PINS,pins,clear=True),self.assertRaisesRegex(ValueError,"collide"):
            transport.verified_inputs(self.root)

    def test_stale_extra_received_or_model_file_is_refused(self):
        pins,_,_=self.input_fixture()
        for folder in ("received-original","local-public"):
            extra=self.root/folder/"stale.txt";extra.write_bytes(b"not pinned")
            with patch.dict(transport.PINS,pins,clear=True),self.subTest(folder=folder),self.assertRaisesRegex(ValueError,"membership"):
                transport.verified_inputs(self.root)
            extra.unlink()

    def test_input_receipt_cannot_rebind_wrapper_identity(self):
        pins,_,_=self.input_fixture()
        receipt=transport.read(self.root/"INPUT-VERIFICATION.json")
        receipt["artifacts"]["model"]["artifact_id"]=999
        (self.root/"INPUT-VERIFICATION.json").write_bytes(transport.encode(receipt))
        with patch.dict(transport.PINS,pins,clear=True),self.assertRaisesRegex(ValueError,"wrapper identity"):
            transport.verified_inputs(self.root)

    def starter_fixture(self, draft=True, state="starter", raw=b"", preserve=True):
        class API(AssetAPI):
            def __init__(self, release_value):
                super().__init__({transport.DIAGNOSTIC_FAILURE_NAME:raw},
                                 {transport.DIAGNOSTIC_FAILURE_NAME:state})
                self.release_value=release_value;self.deletes=[];self.fresh_changes={}
            def request(self,path,method="GET",**kwargs):
                if path=="/releases/123":
                    return {**self.release_value,**self.fresh_changes}
                if path.startswith("/releases/assets/"):
                    identifier=int(path.rsplit("/",1)[1])
                    row=next(row for row in self.rows.values() if row["id"]==identifier)
                    if method=="GET":return dict(row)
                    if method=="DELETE":
                        self.deletes.append(identifier);del self.rows[row["name"]];return None
                return super().request(path,method=method,**kwargs)
        current=release(draft=draft)
        api=API(current)
        snapshot={**current,"assets":[dict(row) for row in api.rows.values()]} if preserve else None
        inspection=transport.encode({"source_revision":transport.SOURCE,"release":snapshot})
        auxiliary,manifest=transport.package_auxiliary(self.original,self.failure,inspection)
        transport.put(self.root/"PRIOR-RELEASE-INSPECTION.json",inspection)
        transport.put(self.root/"base-assets"/transport.AUX_ZIP,auxiliary)
        saved={"zero_files":manifest["original_zero_files"],"prior_release_inspection":transport.record(inspection),
               "files":{transport.AUX_ZIP:transport.record(auxiliary)}}
        pin=(transport.PINS["failed_publication"][0],len(self.failure),transport.digest(self.failure),"fixture-")
        return api,current,saved,pin

    def test_only_preserved_verified_empty_starter_in_same_unpublished_draft_is_deleted(self):
        api,current,state,pin=self.starter_fixture()
        with patch.dict(transport.PINS,{"failed_publication":pin}):
            result=transport.cleanup_empty_starters(self.root,api,current,state)
        self.assertEqual(api.deletes,[1])
        self.assertEqual(result[0]["preserved_asset"]["state"],"starter")
        self.assertEqual(result[0]["preserved_asset"]["size"],0)
        self.assertTrue((self.root/"base-assets"/transport.AUX_ZIP).is_file())

    def test_public_release_starter_cannot_be_deleted(self):
        api,current,state,pin=self.starter_fixture(draft=False)
        with patch.dict(transport.PINS,{"failed_publication":pin}),self.assertRaisesRegex(ValueError,"unpublished"):
            transport.cleanup_empty_starters(self.root,api,current,state)
        self.assertEqual(api.deletes,[])

    def test_nonzero_starter_cannot_be_deleted(self):
        api,current,state,pin=self.starter_fixture(raw=b"not empty")
        with patch.dict(transport.PINS,{"failed_publication":pin}),self.assertRaisesRegex(ValueError,"empty diagnostic"):
            transport.cleanup_empty_starters(self.root,api,current,state)
        self.assertEqual(api.deletes,[])

    def test_uploaded_empty_asset_is_not_deleted(self):
        api,current,state,pin=self.starter_fixture(state="uploaded")
        with patch.dict(transport.PINS,{"failed_publication":pin}):
            result=transport.cleanup_empty_starters(self.root,api,current,state)
        self.assertEqual(result,[]);self.assertEqual(api.deletes,[])
        _,retained=transport.check_existing_assets(api,current,{},state["zero_files"])
        self.assertEqual(retained[0]["state"],"uploaded")

    def test_unpreserved_starter_cannot_be_deleted(self):
        api,current,state,pin=self.starter_fixture(preserve=False)
        with patch.dict(transport.PINS,{"failed_publication":pin}),self.assertRaisesRegex(ValueError,"preserved"):
            transport.cleanup_empty_starters(self.root,api,current,state)
        self.assertEqual(api.deletes,[])

    def test_changed_starter_metadata_cannot_be_deleted(self):
        api,current,state,pin=self.starter_fixture()
        api.rows[transport.DIAGNOSTIC_FAILURE_NAME]["digest"]="sha256:"+"0"*64
        with patch.dict(transport.PINS,{"failed_publication":pin}),self.assertRaisesRegex(ValueError,"metadata"):
            transport.cleanup_empty_starters(self.root,api,current,state)
        self.assertEqual(api.deletes,[])

    def test_release_becoming_public_before_delete_is_refused(self):
        api,current,state,pin=self.starter_fixture()
        api.fresh_changes={"draft":False}
        with patch.dict(transport.PINS,{"failed_publication":pin}),self.assertRaisesRegex(ValueError,"became public"):
            transport.cleanup_empty_starters(self.root,api,current,state)
        self.assertEqual(api.deletes,[])

    def test_remaining_starter_is_never_verified_delivery(self):
        api=AssetAPI({transport.DIAGNOSTIC_FAILURE_NAME:b""},{transport.DIAGNOSTIC_FAILURE_NAME:"starter"})
        with self.assertRaisesRegex(ValueError,"starter remains"):
            transport.check_existing_assets(api,release(),{},{transport.DIAGNOSTIC_FAILURE_NAME:transport.record(b"")})

    def test_prepared_asset_and_state_changed_together_are_refused(self):
        customer=b"immutable customer archive fixture"
        sha=transport.digest(customer)
        native=transport.encode({"source_revision":transport.SOURCE,"archive_sha256":sha,"status":"PASS"})
        original={transport.CUSTOMER:customer,transport.DIAGNOSTIC_FAILURE_NAME:b"",
                  "PLATFORM-Darwin-VERIFICATION.json":native,"PLATFORM-Windows-VERIFICATION.json":native}
        quote=transport.encode({"status":"RUNNING","arms":[]})
        hosted={"source_revision":transport.SOURCE,"source_product_tree":transport.PRODUCT_TREE,
                "source_unchanged":True,"release_qualification":"PASS","required_release_qualifications":transport.CORE,
                "qualifications":{name:"PASS" for name in transport.CORE},"status":"FAIL","commands":[],
                "published_sha256":{"LOCAL-QUOTE-QUALIFICATION-006.json":transport.digest(quote)}}
        public={"HOSTED-LOCAL-QUALIFICATION.json":transport.encode(hosted),"LOCAL-QUOTE-QUALIFICATION-006.json":quote}
        inputs={"assets":original,"model":public,"failed_publication":{"failed.txt":b"failure"}}
        pins={};rows={}
        for index,(key,members) in enumerate(inputs.items(),1):
            raw=transport.zip_bytes(members)
            pins[key]=(index,len(raw),transport.digest(raw),"fixture-")
            transport.put(self.root/"input-zips"/(key+".zip"),raw)
            rows[key]={"artifact_id":index,"archive":transport.record(raw),"files":transport.inventory(members)}
            if key!="failed_publication":
                folder="local-public" if key=="model" else "received-original"
                for name,data in members.items():transport.put(self.root/folder/name,data)
        transport.put(self.root/"INPUT-VERIFICATION.json",transport.encode({"source_revision":transport.SOURCE,
            "source_product_tree":transport.PRODUCT_TREE,"qualification_run":transport.RUN,
            "raw_wrapper_hashes_verified":True,"artifacts":rows}))
        transport.put(self.root/"PRIOR-RELEASE-INSPECTION.json",self.inspection)
        with patch.dict(transport.PINS,pins,clear=True),patch.object(transport,"CUSTOMER_SHA",sha):
            files,state,_,_=transport.derive_base(self.root)
            for name,raw in files.items():transport.put(self.root/"base-assets"/name,raw)
            transport.put(self.root/"BASE-STATE.json",transport.encode(state))
            self.assertEqual(transport.checked_base(self.root),state)
            anchored_sha=transport.digest((self.root/"BASE-STATE.json").read_bytes())
            for changed_path in ("PRIOR-RELEASE-INSPECTION.json","INPUT-VERIFICATION.json"):
                prior=(self.root/changed_path).read_bytes()
                modified=transport.decode(prior);modified["injected_metadata"]="not part of the anchored preparation"
                (self.root/changed_path).write_bytes(transport.encode(modified))
                mutated_files,mutated_state,_,_=transport.derive_base(self.root)
                for name,data in mutated_files.items():(self.root/"base-assets"/name).write_bytes(data)
                (self.root/"BASE-STATE.json").write_bytes(transport.encode(mutated_state))
                with self.subTest(changed_path=changed_path),self.assertRaisesRegex(ValueError,"after credential-free preparation"):
                    transport.checked_base(self.root,anchored_sha)
                (self.root/changed_path).write_bytes(prior)
                for name,data in files.items():(self.root/"base-assets"/name).write_bytes(data)
                (self.root/"BASE-STATE.json").write_bytes(transport.encode(state))

            changed=b"coherently replaced archive"
            (self.root/"base-assets"/transport.CUSTOMER).write_bytes(changed)
            state["files"][transport.CUSTOMER]=transport.record(changed)
            (self.root/"BASE-STATE.json").write_bytes(transport.encode(state))
            with self.assertRaisesRegex(ValueError,"pinned inputs"):
                transport.checked_base(self.root)
            (self.root/"base-assets"/transport.CUSTOMER).write_bytes(customer)
            state["files"][transport.CUSTOMER]=transport.record(customer)
            (self.root/"base-assets"/"extra.txt").write_bytes(b"extra")
            state["files"]["extra.txt"]=transport.record(b"extra")
            (self.root/"BASE-STATE.json").write_bytes(transport.encode(state))
            with self.assertRaisesRegex(ValueError,"pinned inputs"):
                transport.checked_base(self.root)

    def final_fixture(self):
        helpers={name:(name+" exact source").encode() for name in
                 ("qualify_archive.py","reconcile_release_evidence.py","owner_handoff.py","verify_owner_handoff.cjs")}
        customer=transport.zip_bytes({"edition/scripts/"+name:raw for name,raw in helpers.items()})
        sha=transport.digest(customer)
        bundle="ALPHA_GENESIS_HARNESS_OWNER_HANDOFF_0.3.0_"+transport.SOURCE[:12]
        matrix={"source_revision":transport.SOURCE,"source_product_tree":transport.PRODUCT_TREE,
                "archive_sha256":sha,"commercially_validated":False,"criteria":[{"id":str(i)} for i in range(39)]}
        operation={"source_revision":transport.SOURCE,"archive_sha256":sha,"verdict":"PASSED IN SCOPE",
                   "operations":[{"command":["fixture",str(i)],"returncode":0} for i in range(15)]}
        operation_raw=transport.encode(operation)
        owner={"source_revision":transport.SOURCE,"source_product_tree":transport.PRODUCT_TREE,
               "archive_sha256":sha,"archive_name":transport.CUSTOMER,"commercially_ready":False,
               "release_url":"https://github.com/"+transport.REPO+"/releases/tag/"+transport.TAG,
               "required_deliverables":[{"id":str(i),"included":True,
                   "paths":["02-EXPLORE-THE-EDITION/examples/" if i==12 else "04-SCREENSHOTS/" if i==14 else "00-OWNER-START.html"]} for i in range(1,23)]}
        members={"00-OWNER-START.html":b"<h1>fixture</h1>","OWNER-HANDOFF.json":transport.encode(owner),
                 "02-EXPLORE-THE-EDITION/examples/README.md":b"source68 examples",
                 "04-SCREENSHOTS/HARNESS-actual.png":b"recorded screenshot",
                 "01-CUSTOMER-DOWNLOAD/"+transport.CUSTOMER:customer,
                 "05-VERIFICATION/QUALIFICATION-MATRIX.json":transport.encode(matrix),
                 "05-VERIFICATION/PUBLISHED-OPERATION.json":operation_raw}
        manifest={"schema":"alpha-harness-owner-manifest/v1","source_revision":transport.SOURCE,
                  "customer_archive_sha256":sha,"self_excluded":True,
                  "files":[{"path":name,**transport.record(raw)} for name,raw in members.items()]}
        members["OWNER-FILE-MANIFEST.json"]=transport.encode(manifest)
        archive=transport.zip_bytes({bundle+"/"+name:raw for name,raw in members.items()})
        files={"QUALIFICATION-MATRIX.json":transport.encode(matrix),"QUALIFICATION-MATRIX.md":b"fixture",
               "RECONCILIATION.json":transport.encode({"source_revision":transport.SOURCE,
                   "source_product_tree":transport.PRODUCT_TREE,"archive_sha256":sha,"commercially_ready":False}),
               "OWNER-VISUAL-VERIFICATION.json":transport.encode({"source_revision":transport.SOURCE,"status":"PASS",
                   "errors":[],"screenshots":["HARNESS-OWNER-desktop.png","HARNESS-OWNER-mobile.png"],
                   "checks":["All 22 delivery categories rendered","390px responsive viewport without document overflow",
                             "No network requests or JavaScript page errors"]}),
               "HARNESS-OWNER-desktop.png":b"desktop","HARNESS-OWNER-mobile.png":b"mobile",
               bundle+".zip":archive,bundle+".zip.sha256":(transport.digest(archive)+"  "+bundle+".zip\n").encode(),
               bundle+".receipt.json":transport.encode({"source_revision":transport.SOURCE,
                   "customer_archive_sha256":sha,"owner_zip_sha256":transport.digest(archive),
                   "owner_zip_bytes":len(archive),"included_deliverable_types":22,"expected_deliverable_types":22,
                   "commercially_ready":False}),
               "PUBLISHED-OPERATION-EVIDENCE_"+transport.SOURCE[:12]+".zip":transport.zip_bytes({"QUALIFICATION.json":operation_raw}),
               "RECOVERY-COMPLETION.json":transport.encode({"source_revision":transport.SOURCE,
                   "source_product_tree":transport.PRODUCT_TREE,"customer_archive_sha256":sha,
                   "owner_zip_sha256":transport.digest(archive),"commercially_ready":False,"no_model_retry":True,
                   "source_helper_hashes":{name:transport.digest(raw) for name,raw in helpers.items()}})}
        for name in ("INPUT-VERIFICATION.json","DOWNLOAD-VERIFICATION.json","RESTORATION-VERIFICATION.json","RELEASE-STATE.json"):
            files[name]=b"{}"
        self.refresh_final_inventory(files,sha)
        return files,sha

    def refresh_final_inventory(self,files,sha):
        files.pop(transport.FINAL_INVENTORY,None)
        files[transport.FINAL_INVENTORY]=transport.encode({"source_revision":transport.SOURCE,
            "customer_archive_sha256":sha,"files":transport.inventory(files)})

    def test_final_owner_embedded_customer_receipts_and_source_are_checked(self):
        files,sha=self.final_fixture()
        with patch.object(transport,"CUSTOMER_SHA",sha):
            transport.validate_final_files(files)
            for name,field,value in (("QUALIFICATION-MATRIX.json","source_revision","0"*40),
                    ("OWNER-VISUAL-VERIFICATION.json","errors",["page error"]),
                    ("RECOVERY-COMPLETION.json","customer_archive_sha256","0"*64)):
                changed=dict(files);body=transport.decode(changed[name]);body[field]=value
                changed[name]=transport.encode(body);self.refresh_final_inventory(changed,sha)
                with self.subTest(name=name),self.assertRaises(ValueError):
                    transport.validate_final_files(changed)

    def test_final_state_changed_with_asset_is_rejected_by_fixed_ci_digest(self):
        files,sha=self.final_fixture()
        for name,raw in files.items():transport.put(self.root/"final-assets"/name,raw)
        state={"source_revision":transport.SOURCE,"files":transport.inventory(files)}
        raw=transport.encode(state);transport.put(self.root/"FINAL-STATE.json",raw)
        expected=transport.digest(raw)
        with patch.object(transport,"CUSTOMER_SHA",sha):
            transport.checked_final(self.root,expected)
            (self.root/"final-assets/QUALIFICATION-MATRIX.md").write_bytes(b"altered together")
            state["files"]["QUALIFICATION-MATRIX.md"]=transport.record(b"altered together")
            (self.root/"FINAL-STATE.json").write_bytes(transport.encode(state))
            with self.assertRaisesRegex(ValueError,"after credential-free assembly"):
                transport.checked_final(self.root,expected)

    def test_coherently_rewritten_owner_zip_cannot_replace_embedded_customer(self):
        files,sha=self.final_fixture()
        bundle="ALPHA_GENESIS_HARNESS_OWNER_HANDOFF_0.3.0_"+transport.SOURCE[:12]
        members=transport.zip_members(files[bundle+".zip"])
        manifest_path=bundle+"/OWNER-FILE-MANIFEST.json"
        customer_path=bundle+"/01-CUSTOMER-DOWNLOAD/"+transport.CUSTOMER
        members[customer_path]=b"replaced customer"
        manifest=transport.decode(members[manifest_path])
        for row in manifest["files"]:
            if bundle+"/"+row["path"]==customer_path:row.update(transport.record(members[customer_path]))
        members[manifest_path]=transport.encode(manifest)
        archive=transport.zip_bytes(members)
        files[bundle+".zip"]=archive
        files[bundle+".zip.sha256"]=(transport.digest(archive)+"  "+bundle+".zip\n").encode()
        receipt=transport.decode(files[bundle+".receipt.json"])
        receipt.update(owner_zip_sha256=transport.digest(archive),owner_zip_bytes=len(archive))
        files[bundle+".receipt.json"]=transport.encode(receipt)
        completion=transport.decode(files["RECOVERY-COMPLETION.json"])
        completion["owner_zip_sha256"]=transport.digest(archive)
        files["RECOVERY-COMPLETION.json"]=transport.encode(completion)
        self.refresh_final_inventory(files,sha)
        with patch.object(transport,"CUSTOMER_SHA",sha),self.assertRaisesRegex(ValueError,"Embedded customer"):
            transport.validate_final_files(files)

    def test_authenticated_transport_disables_ambient_proxy_handlers(self):
        with patch.object(transport.urllib.request,"build_opener") as build:
            transport.GitHub("token")
        handlers=build.call_args.args
        self.assertIsInstance(handlers[0],urllib.request.ProxyHandler)
        self.assertEqual(handlers[0].proxies,{})
        self.assertIsInstance(handlers[1],transport.NoRedirect)


if __name__=="__main__":
    unittest.main()
