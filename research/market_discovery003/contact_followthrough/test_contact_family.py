"""Checks of the declared numerical construction, not physical qualification."""
from pathlib import Path
import math
import tempfile
import unittest
from dataclasses import replace

import numpy as np

from contact_family import (SPEC_BLOB, construct_parent, film_gain, git_blob,
                            load_parent, mechanical, scalar_oracle, tiled,
                            transport_screen, write_geometry)

HERE=Path(__file__).resolve().parent

class ContactFamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=load_parent(HERE/'parent_spec.json')
        cls.parent,cls.width,cls.receipt=construct_parent(cls.spec)
        cls.reference=cls.spec['reference_height_mm']

    def test_exact_parent_source_and_tamper_rejection(self):
        data=(HERE/'parent_spec.json').read_bytes()
        self.assertEqual(git_blob(data),SPEC_BLOB)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'altered.json';path.write_bytes(data+b' ')
            with self.assertRaises(ValueError): load_parent(path)

    def test_nominal_contract_checked_with_scalar_evaluator(self):
        for state in self.spec['states']:
            actual=scalar_oracle(self.parent,self.reference,state['indentation_mm'])
            actual['ratio']=actual['static_N']/actual['dynamic_N']
            for key,limits in state.items():
                if key=='indentation_mm': continue
                with self.subTest(key=key,stroke=state['indentation_mm']):
                    self.assertGreaterEqual(actual[key],limits[0]-1e-8)
                    self.assertLessEqual(actual[key],limits[1]+1e-8)

    def test_scalar_vector_agreement_on_active_set_changes(self):
        for stroke in np.linspace(0,.1,101):
            a=mechanical(self.parent,self.reference,float(stroke))
            b=scalar_oracle(self.parent,self.reference,float(stroke))
            for key in b:
                self.assertAlmostEqual(a[key],b[key],places=11)

    def test_similarity_preserves_force_area_and_shear_at_rescaled_stroke(self):
        for k in (1,2,3,4):
            variant=tiled(self.parent,self.width,k)
            self.assertEqual(len(variant),len(self.parent)*k*k)
            for stroke in np.linspace(.001,.1,31):
                a=scalar_oracle(self.parent,self.reference,float(stroke))
                b=scalar_oracle(variant,self.reference/k,float(stroke)/k)
                for key in ('normal_N','static_N','dynamic_N','area_mm2'):
                    self.assertAlmostEqual(a[key],b[key],places=10)
                for key in ('normal_stiffness_N_per_mm','independent_transport_proxy_mm'):
                    self.assertAlmostEqual(k*a[key],b[key],places=10)

    def test_same_stroke_is_not_preserved(self):
        variant=tiled(self.parent,self.width,4)
        a=mechanical(self.parent,self.reference,.02)['normal_N']
        wrong=mechanical(variant,self.reference/4,.02)['normal_N']
        self.assertGreater(wrong,10*a)

    def test_fixed_footprint_contains_contact_disks(self):
        for k in (1,2,4):
            v=tiled(self.parent,self.width,k)
            radii=mechanical(v,self.reference/k,.1/k)['contact_radii_mm']
            for c,r in zip(v,radii):
                self.assertGreaterEqual(min(c.x_mm,c.y_mm)-r,0.)
                self.assertLessEqual(max(c.x_mm,c.y_mm)+r,self.width)

    def test_interaction_screen_is_not_the_independent_sum(self):
        for k in (1,2,4):
            v=tiled(self.parent,self.width,k)
            m=mechanical(v,self.reference/k,.1/k)
            t=transport_screen(v,m['contact_radii_mm'],self.width)
            self.assertTrue(t['positive_patch_flux'])
            self.assertLess(t['linear_system_residual'],1e-10)
            self.assertLess(t['conductance_proxy_mm'],m['independent_transport_proxy_mm'])
            self.assertGreaterEqual(t['conductance_proxy_mm'],t['uniform_flux_conductance_lower_in_this_matrix_model_mm']-1e-10)
            self.assertTrue(t['below_circumscribed_disk_ceiling'])

    def test_exact_single_disk_normalization(self):
        parent=self.parent[:1]
        t=transport_screen(parent,np.array([.1]),self.width)
        self.assertAlmostEqual(t['conductance_proxy_mm'],.2)

    def test_surface_film_can_erase_most_of_the_ideal_gain(self):
        self.assertEqual(film_gain(4,0),4.)
        self.assertAlmostEqual(film_gain(4,9),40/37)
        self.assertLess(film_gain(4,9),1.09)
        self.assertLess(film_gain(1.56,9),1.04)
        self.assertAlmostEqual(film_gain(4,1e9),1.,places=8)

    def test_invalid_parameters_and_overlapping_disks_rejected(self):
        for k in (0,-1,True,1.5):
            with self.assertRaises(ValueError): tiled(self.parent,self.width,k)
        for k,b in ((0,0),(2,-1),(float('nan'),1),(2,float('inf'))):
            with self.assertRaises(ValueError): film_gain(k,b)
        dup=[self.parent[0],self.parent[0]]
        with self.assertRaises(ValueError): transport_screen(dup,np.array([.1,.1]),self.width)

    def test_geometry_export_has_expected_number_of_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            write_geometry(out,self.parent,self.width,1)
            scad=(out/'layout_x1.scad').read_text()
            self.assertEqual(scad.count('sphere(r='),len(self.parent))
            self.assertIn('no physical/material qualification',scad)
            self.assertEqual(len((out/'layout_x1.csv').read_text().splitlines()),len(self.parent)+1)

if __name__=='__main__': unittest.main()
