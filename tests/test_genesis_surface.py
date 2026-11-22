"""Executable digital-construction checks, not tests of physical validity."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from research.genesis_surface import model
from research.genesis_surface.check import check, homogeneous_obstruction
from research.genesis_surface.build import build, audit, layout, scad

ROOT=Path(__file__).resolve().parents[1]
REQUEST=ROOT/'campaign/genesis-surface/REQUEST.json'

class SurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=model.read(REQUEST); cls.design=model.construct(cls.spec)

    def test_independent_numerical_acceptance(self):
        self.assertTrue(check(self.spec,self.design)['accepted'])

    def test_uncertainty_is_not_hidden(self):
        v=check(self.spec,self.design)
        self.assertFalse(v['declared_box_sensitivity_pass'])
        self.assertFalse(v['physical_qualified']);self.assertFalse(v['commercial_qualified'])

    def test_no_fixed_prescribed_surface(self):
        s=copy.deepcopy(self.spec);s['maximum_contacts']=5
        self.assertEqual(model.construct(s)['status'],'INFEASIBLE_IN_DECLARED_MODEL')

    def test_reversed_target_is_reconstructed(self):
        s=model.read(REQUEST.with_name('SUCCESSOR_REQUEST.json'))
        c=model.construct(s);v=check(s,c)
        self.assertTrue(v['accepted']);self.assertNotEqual(c['contacts'],self.design['contacts'])
        self.assertGreater(v['rows'][0]['ratio'],v['rows'][1]['ratio'])

    def test_single_family_obstruction(self):
        self.assertTrue(homogeneous_obstruction(self.spec)['infeasible_for_every_single_constant_ratio_family'])
        for f in self.spec['families']:
            self.assertEqual(model.construct(self.spec,f['id'])['status'],'INFEASIBLE_IN_DECLARED_MODEL')

    def test_declared_constant_ratio_model(self):
        for f in self.spec['families']:
            s=copy.deepcopy(self.spec)
            for state in s['states']:
                state.update(normal_N=[0,100],static_N=[0,100],dynamic_N=[1e-12,100],ratio=[0,100])
            c=copy.deepcopy(self.design);c['request_sha256']=model.digest(s)
            c['contacts']=[{'family':f['id'],'height_mm':.12,'count':2}];c['family_restriction']=f['id']
            rows=check(s,c)['rows']
            self.assertAlmostEqual(rows[0]['ratio'],f['static_MPa']/f['dynamic_MPa'])
            self.assertAlmostEqual(rows[0]['ratio'],rows[1]['ratio'])

    def test_changed_request_rejected(self):
        s=copy.deepcopy(self.spec);s['states'][1]['ratio'][0]=1.19
        with self.assertRaises(ValueError):check(s,self.design)

    def test_zero_contacts_rejected(self):
        c=copy.deepcopy(self.design);c['contacts'][0]['count']=0
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_nonintegral_contacts_rejected(self):
        c=copy.deepcopy(self.design);c['contacts'][0]['count']=1.5
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_boolean_contacts_rejected(self):
        c=copy.deepcopy(self.design);c['contacts'][0]['count']=True
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_unknown_material_rejected(self):
        c=copy.deepcopy(self.design);c['contacts'][0]['family']='not-calibrated'
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_unregistered_height_rejected(self):
        c=copy.deepcopy(self.design);c['contacts'][0]['height_mm']=.119
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_duplicate_sites_rejected(self):
        c=copy.deepcopy(self.design);c['contacts'].append(copy.deepcopy(c['contacts'][0]))
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_capacity_rejected(self):
        c=copy.deepcopy(self.design);c['contacts'][0]['count']=300
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_physical_self_approval_rejected(self):
        c=copy.deepcopy(self.design);c['physical_qualification']=True
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_commercial_self_approval_rejected(self):
        c=copy.deepcopy(self.design);c['commercial_qualification']=True
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_wrong_status_rejected(self):
        c=copy.deepcopy(self.design);c['status']='PROVED'
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_failed_geometry_rejected(self):
        c=copy.deepcopy(self.design);c['status']='INFEASIBLE_IN_DECLARED_MODEL'
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_changed_family_constraint_rejected(self):
        c=copy.deepcopy(self.design);c['family_restriction']=self.spec['families'][0]['id']
        with self.assertRaises(ValueError):check(self.spec,c)

    def test_nonfinite_request_rejected(self):
        for value in (True,float('nan'),float('inf'),-1):
            s=copy.deepcopy(self.spec);s['families'][0]['radius_mm']=value
            with self.assertRaises(ValueError):model.validate(s)

    def test_overlapping_caps_rejected(self):
        s=copy.deepcopy(self.spec);s['pitch_mm']=.1
        with self.assertRaises(ValueError):model.validate(s)

    def test_outside_contact_approximation_rejected(self):
        s=copy.deepcopy(self.spec);s['states'][0]['indentation_mm']=.5
        with self.assertRaises(ValueError):model.validate(s)

    def test_missing_provenance_rejected(self):
        s=copy.deepcopy(self.spec);s['source']={}
        with self.assertRaises(ValueError):model.validate(s)

    def test_javascript_source_rejected(self):
        s=copy.deepcopy(self.spec);s['source']['url']='javascript:alert(1)'
        with self.assertRaises(ValueError):model.validate(s)

    def test_target_inversion_rejected(self):
        s=copy.deepcopy(self.spec);s['states'][0]['normal_N']=[2,1]
        with self.assertRaises(ValueError):model.validate(s)

    def test_zero_dynamic_target_rejected(self):
        s=copy.deepcopy(self.spec);s['states'][0]['dynamic_N'][0]=0
        with self.assertRaises(ValueError):model.validate(s)

    def test_nominal_outside_declared_interval_rejected(self):
        s=copy.deepcopy(self.spec);s['families'][0]['static_range_MPa']=[1,2]
        with self.assertRaises(ValueError):model.validate(s)

    def test_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'q.json';p.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError):model.read(p)

    def test_layout_matches_counts_and_does_not_overlap(self):
        g=layout(self.spec,self.design)
        self.assertEqual(len(g['sites']),sum(x['count'] for x in self.design['contacts']))
        locs={(p['x_mm'],p['y_mm']) for p in g['sites']}
        self.assertEqual(len(locs),len(g['sites']))
        for a in g['sites']:
            self.assertTrue(0<a['x_mm']<g['width_mm'] and 0<a['y_mm']<g['depth_mm'])
        self.assertIn('NOT physically qualified',scad(self.spec,g))

    def test_complete_export_and_reaudit(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'case';build(REQUEST,out)
            self.assertTrue(audit(out)['accepted'])
            for name in ('surface.scad','layout.svg','design.json','OPEN_ME.html','response.csv'):
                self.assertTrue((out/name).is_file())
            with self.assertRaises(FileExistsError):build(REQUEST,out)

    def test_modified_cad_detected(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'case';build(REQUEST,out)
            (out/'surface.scad').write_text('cube([1,1,1]);')
            with self.assertRaises(ValueError):audit(out)

    def test_coherently_resealed_cad_detected(self):
        with tempfile.TemporaryDirectory() as t:
            import hashlib
            out=Path(t)/'case';build(REQUEST,out)
            (out/'surface.scad').write_text('cube([1,1,1]);')
            m=model.read(out/'MANIFEST.json');m['output_sha256']['surface.scad']=hashlib.sha256((out/'surface.scad').read_bytes()).hexdigest()
            (out/'MANIFEST.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'CAD/layout'):audit(out)

    def test_symlink_output_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'real').mkdir();(root/'linked').symlink_to(root/'real',target_is_directory=True)
            with self.assertRaises(ValueError):build(REQUEST,root/'linked'/'out')

class MeshTests(unittest.TestCase):
    def test_mesh_header_length_and_binding(self):
        import struct
        from research.genesis_surface.mesh import export_mesh
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)/'design';build(REQUEST,d)
            out=Path(t)/'mesh';rec=export_mesh(d,out,.4)
            data=(out/'surface-preview.stl').read_bytes()
            self.assertEqual(struct.unpack('<I',data[80:84])[0],rec['triangles'])
            self.assertEqual(len(data),84+50*rec['triangles'])
            self.assertFalse(rec['physical_qualified']);self.assertFalse(rec['manufacturing_recipe'])
            with self.assertRaises(FileExistsError):export_mesh(d,out,.4)

    def test_mesh_rejects_invalid_resolution(self):
        from research.genesis_surface.mesh import export_mesh
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)/'design';build(REQUEST,d)
            for value in (0,-1,float('nan'),float('inf'),True,1e-8,100):
                with self.assertRaises(ValueError):export_mesh(d,Path(t)/'mesh',value)

    def test_infeasible_report_has_no_broken_cad_link(self):
        with tempfile.TemporaryDirectory() as t:
            s=model.read(REQUEST);s['maximum_contacts']=5
            p=Path(t)/'input.json';p.write_text(json.dumps(s));o=Path(t)/'out'
            r=build(p,o);self.assertFalse(r['independent_check']['accepted'])
            self.assertNotIn('href="surface.scad"',(o/'OPEN_ME.html').read_text())
            self.assertTrue(audit(o)['accepted'])

if __name__=='__main__':unittest.main()
