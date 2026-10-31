import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
imp=load('import023','import_portable023.py');exp=load('export023','export_recovered023.py')

class PortableExtractionTests(unittest.TestCase):
    def archive(self,root,files):
        values={n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()}
        manifest={'files':values,'bytes':sum(len(b) for b in files.values()),'guards':{'files':10000,'bytes':512*1024*1024}}
        p=root/'public.zip'
        with zipfile.ZipFile(p,'w') as z:
            for n,b in files.items():z.writestr(n,b)
            z.writestr('INTEGRITY.json',json.dumps(manifest))
        return p

    def test_keyfree_roundtrip_preserves_blob_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);raw=b'{"exact":"signed history"}';name=hashlib.sha256(raw).hexdigest()
            p=self.archive(r,{'transition-evidence/'+name:raw,'RESULT.json':b'{}'})
            got=imp.extract(p,r/'public');self.assertFalse(got['audit_performed'])
            self.assertEqual((r/'public/transition-evidence'/name).read_bytes(),raw)

    def test_manifest_tampering_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=self.archive(r,{'RESULT.json':b'{}'})
            with zipfile.ZipFile(p,'a') as z:z.writestr('unregistered',b'x')
            with self.assertRaisesRegex(ValueError,'INTEGRITY_MISMATCH'):imp.extract(p,r/'public')
            self.assertFalse((r/'public').exists())

    def test_traversal_private_paths_and_noncanonical_rejected(self):
        for name in ['../escape','/absolute','a/../b','a//b','a\\b','private.key','account.sqlite','__pycache__/x']:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                r=Path(d);p=self.archive(r,{name:b'x'})
                with self.assertRaises(ValueError):imp.extract(p,r/'public')
                self.assertFalse((r/'public').exists())

    def test_symlink_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=r/'bad.zip'
            with zipfile.ZipFile(p,'w') as z:
                i=zipfile.ZipInfo('link');i.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(i,'../outside')
            with self.assertRaisesRegex(ValueError,'REGULAR_UNENCRYPTED'):imp.extract(p,r/'out')
            p=self.archive(r,{'RESULT.json':b'{}'})
            with zipfile.ZipFile(p,'a') as z:z.writestr('RESULT.json',b'{}')
            with self.assertRaisesRegex(ValueError,'DUPLICATE_ARCHIVE'):imp.extract(p,r/'out')

    def test_archive_guard_includes_integrity_and_all_blobs(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=self.archive(r,{'RESULT.json':b'{}'})
            with patch.object(imp,'MAX_FILES',1),self.assertRaisesRegex(ValueError,'ARCHIVE_GUARD'):imp.extract(p,r/'out')
            with patch.object(imp,'MAX_BYTES',1),self.assertRaisesRegex(ValueError,'ARCHIVE_GUARD'):imp.extract(p,r/'out')

    def test_existing_destination_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);p=self.archive(r,{'RESULT.json':b'{}'});(r/'out').mkdir();(r/'out/keep').write_text('existing')
            with self.assertRaises(FileExistsError):imp.extract(p,r/'out')
            self.assertEqual((r/'out/keep').read_text(),'existing')

class PortableCASReachabilityTests(unittest.TestCase):
    def ticket(self,prior=None):
        from connected_enterprise.transition_evidence import externalize,V1,FIELDS
        body={k:'test' for k in FIELDS};body.update(schema=V1,counter=1,prior_record=prior or {},prior_envelope={})
        blobs={};wire=externalize(body,blobs);return {'body':wire,'signature':'0'*64},blobs

    def test_reachable_only_nested_wire_history_unchanged(self):
        from connected_enterprise.transition_evidence import evidence_directory,persist_evidence
        first,a=self.ticket();record={'source_transitions':{'first':first}};second,b=self.ticket(record)
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);store=r/'owned';store.mkdir();allblobs={**a,**b};extra=b'{"unreachable":true}';allblobs[hashlib.sha256(extra).hexdigest()]=extra;persist_evidence(store,allblobs)
            output=r/'public';output.mkdir();wire=json.dumps(second,sort_keys=True)
            with evidence_directory(store):exp.copy_transition_evidence(output,{'source_transitions':{'second':second}})
            names={p.name for p in (output/'transition-evidence').iterdir()}
            self.assertEqual(names,set(a)|set(b));self.assertEqual(wire,json.dumps(second,sort_keys=True))
            # No original store or path is available during public resolution.
            store.rename(r/'unavailable')
            with evidence_directory(output/'transition-evidence'):
                self.assertEqual(exp.reachable_evidence({'source_transitions':{'second':second}}),{**a,**b})

    def test_combined_archive_guard_rejects_before_blob_output(self):
        from connected_enterprise.transition_evidence import evidence_scope
        t,blobs=self.ticket()
        with tempfile.TemporaryDirectory() as d,evidence_scope(blobs):
            r=Path(d);(r/'source.py').write_text('source')
            with patch.object(exp,'MAX_FILES',1),self.assertRaisesRegex(ValueError,'ARCHIVE_GUARD'):exp.copy_transition_evidence(r,{'source_transitions':{'a':t}})
            self.assertFalse((r/'transition-evidence').exists())

    def test_missing_scope_and_tampered_blobs_fail_closed(self):
        from connected_enterprise.transition_evidence import evidence_directory,persist_evidence
        t,blobs=self.ticket()
        with self.assertRaisesRegex(ValueError,'EXPLICIT_TRANSITION'):exp.reachable_evidence({'source_transitions':{'a':t}})
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);persist_evidence(r,blobs);next(r.iterdir()).write_bytes(b'{}changed')
            with evidence_directory(r),self.assertRaisesRegex(ValueError,'MISSING_OR_CHANGED'):exp.reachable_evidence({'source_transitions':{'a':t}})

if __name__=='__main__':unittest.main()
