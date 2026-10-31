import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('export023',Path(__file__).resolve().parents[1]/'scripts/export_recovered023.py')
export023=importlib.util.module_from_spec(spec);spec.loader.exec_module(export023)
sha=lambda value:hashlib.sha256(value).hexdigest()


class RecoveredExportTests(unittest.TestCase):
    def test_unbound_private_file_is_not_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir();(source/'bound.py').write_bytes(b'bound source\n');(source/'private.key').write_bytes(b'x'*32)
            target=root/'public';export023.copy_source(source,target,{'bound.py':sha(b'bound source\n')},{'jobs':[]})
            self.assertEqual([p.name for p in target.iterdir()],['bound.py'])

    def test_bound_source_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'bound.py').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'BOUND_SOURCE_CONTENT_CHANGED'):export023.copy_source(root,root/'public',{'bound.py':sha(b'original')},{'jobs':[]})

    def test_manifest_cannot_export_absolute_or_parent_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ['../private.key','/tmp/private.key']:
                with self.subTest(name=name),self.assertRaisesRegex(ValueError,'RELATIVE_BOUND_SOURCE_REQUIRED'):export023.copy_source(root,root/'public',{name:'0'*64},{'jobs':[]})

    def test_historical_verifier_files_outside_runtime_inventory_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'old';source.mkdir();(source/'runtime.py').write_bytes(b'runtime');(source/'extra_verifier.py').write_bytes(b'verifier')
            body={'historical_root':str(source),'from_source':{'sha256':'a'*64},'operating':{'from_runtime':{'files':{'runtime.py':sha(b'runtime')}}},'verifier_files':{'runtime.py':sha(b'runtime'),'extra_verifier.py':sha(b'verifier')},'prior_record':{}}
            target=root/'public';export023.copy_history(target,{'source_transitions':{'old':{'body':body}}},{'jobs':[]})
            self.assertEqual((target/'historical-source-versions'/('a'*64)/'extra_verifier.py').read_bytes(),b'verifier')


if __name__=='__main__':unittest.main()
