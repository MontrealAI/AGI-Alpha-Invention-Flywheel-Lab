"""Frozen linked portable158 negative cases; no financial/account fixture or real data."""
from __future__ import annotations

import hashlib
import io
import json
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from scripts.package_governance_linked158 import (FILES, MANIFEST, build, verify,
                                                   canonical, sha)

COMMIT = '7501d5bfd775e7f9f725fa53b0bd455cdb669748'


class LinkedPortable158(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root/'fake-repo'
        for p in FILES:
            target = self.source/p
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('Public synthetic source fixture: '+p+'\n', encoding='utf-8')
        self.archive = self.root/'bundle.zip'
        self.receipt = self.root/'receipt.json'
        self.record = build(self.source,self.archive,self.receipt,COMMIT)

    def checked(self, archive=None, **overrides):
        params = dict(expected_archive=self.record['archive_sha256'],
                      expected_manifest=self.record['manifest_sha256'],
                      expected_commit=COMMIT)
        params.update(overrides)
        return verify(archive or self.archive, **params)

    def rewrite(self, changes=None, extra=()):
        changes = changes or {}
        path = self.root/'tampered.zip'
        with zipfile.ZipFile(self.archive) as z:
            items = [(i, z.read(i)) for i in z.infolist()]
        with zipfile.ZipFile(path,'w') as z:
            for info,data in items:
                if info.filename not in changes:
                    z.writestr(info,data)
                elif changes[info.filename] is not None:
                    z.writestr(info,changes[info.filename])
            for name, data, mode in extra:
                info = zipfile.ZipInfo(name)
                info.external_attr = mode << 16
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    z.writestr(info,data)
        return path

    def test_T1_deterministic_and_create_only(self):
        other = self.root/'second.zip'
        report = build(self.source,other,self.root/'second-receipt.json',COMMIT)
        self.assertEqual(self.archive.read_bytes(),other.read_bytes())
        self.assertEqual(report,self.record)
        with self.assertRaises(FileExistsError):
            build(self.source,self.archive,self.root/'third.json',COMMIT)
        extracted = self.root/'clean'
        self.assertTrue(self.checked(extract=extracted)['accepted'])
        for p in FILES:
            self.assertEqual((extracted/p).read_bytes(),(self.source/p).read_bytes())
        with self.assertRaises(FileExistsError):
            self.checked(extract=extracted)

    def test_T2_external_anchors_required(self):
        for change, phrase in [
            ({'expected_archive':'0'*64},'EXTERNAL_ARCHIVE_MISMATCH'),
            ({'expected_manifest':'0'*64},'EXTERNAL_MANIFEST_MISMATCH'),
            ({'expected_commit':'0'*40},'INVALID_SOURCE_MANIFEST'),
            ({'expected_commit':'bad'},'SOURCE_COMMIT_REQUIRED'),
            ({'expected_archive':'invalid'},'EXTERNAL_SHA256_ANCHOR_REQUIRED'),
        ]:
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,phrase):
                self.checked(**change)

    def test_T3_tampered_source_even_rehashed_zip(self):
        bad=self.rewrite({FILES[4]:b'Unapproved content replacement'})
        with self.assertRaisesRegex(ValueError,'SOURCE_FILE_HASH_MISMATCH'):
            self.checked(bad,expected_archive=sha(bad.read_bytes()))

    def test_T4_rehashed_manifest_requires_independent_anchor(self):
        with zipfile.ZipFile(self.archive) as z:
            m=json.loads(z.read(MANIFEST))
        m['files'][FILES[4]]='0'*64
        bad=self.rewrite({MANIFEST:canonical(m)})
        with self.assertRaisesRegex(ValueError,'EXTERNAL_MANIFEST_MISMATCH'):
            self.checked(bad,expected_archive=sha(bad.read_bytes()))

    def test_T5_duplicate_json_fields_rejected_with_new_external_anchor(self):
        with zipfile.ZipFile(self.archive) as z:
            raw=z.read(MANIFEST).decode()
        bad = self.rewrite({MANIFEST:raw.replace('"schema":', '"schema":"fake","schema":',1).encode()})
        with zipfile.ZipFile(bad) as z:
            manifest_sha=sha(z.read(MANIFEST))
        with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_FIELD'):
            self.checked(bad,expected_archive=sha(bad.read_bytes()),
                         expected_manifest=manifest_sha)

    def test_T6_unsafe_archive_path_and_extra(self):
        for name, phrase in [('../outside','UNSAFE_ARCHIVE_PATH'),
                             ('unregistered.dat','UNREGISTERED_ARCHIVE_MEMBER')]:
            bad=self.rewrite(extra=[(name,b'x',stat.S_IFREG|0o644)])
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,phrase):
                self.checked(bad,expected_archive=sha(bad.read_bytes()))

    def test_T7_duplicates_and_links(self):
        bad=self.rewrite(extra=[(FILES[0],b'duplicate',stat.S_IFREG|0o644)])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_ARCHIVE_MEMBER'):
            self.checked(bad,expected_archive=sha(bad.read_bytes()))
        bad=self.rewrite(extra=[('sym',b'/etc/passwd',stat.S_IFLNK|0o777)])
        with self.assertRaisesRegex(ValueError,'NONREGULAR_ARCHIVE_MEMBER'):
            self.checked(bad,expected_archive=sha(bad.read_bytes()))

    def test_T8_missing_entries_refused(self):
        bad=self.rewrite({FILES[0]:None})
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_ARCHIVE'):
            self.checked(bad,expected_archive=sha(bad.read_bytes()))

    def test_T9_bounded_files_and_symlink_source(self):
        (self.source/FILES[4]).write_bytes(b'x'*(4_000_000+1))
        with self.assertRaisesRegex(ValueError,'SOURCE_FILE_TOO_LARGE'):
            build(self.source,self.root/'oversize.zip',self.root/'oversize.json',COMMIT)
        (self.source/FILES[4]).unlink()
        (self.source/FILES[4]).symlink_to(self.source/FILES[5])
        with self.assertRaisesRegex(ValueError,'SOURCE_OUTSIDE_ROOT_OR_SYMLINK'):
            build(self.source,self.root/'symlink.zip',self.root/'symlink.json',COMMIT)

    def test_T10_no_financial_or_private_payload_in_inventory(self):
        self.assertEqual(len(FILES),10)
        self.assertEqual(len(set(FILES)),len(FILES))
        for name in FILES:
            self.assertNotIn('account',name.lower())
            self.assertNotIn('private',name.lower())
            self.assertNotIn('.env',name.lower())
        self.assertIn('products/governance_impact140/native_reassessment153.py',FILES)
        self.assertIn('products/governance_impact140/native_risk152.py',FILES)
        self.assertIn('products/governance_impact140/engine.py',FILES)


if __name__=='__main__':
    unittest.main()
