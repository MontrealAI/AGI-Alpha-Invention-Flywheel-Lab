import hashlib
import base64
import json
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET
from unittest import mock
from flywheel_wheel.atlas import RINGS, MECHANISMS, SCRIPT, render_svg, render_html
from flywheel_wheel.readout import EvidenceError, empty_snapshot
from flywheel_wheel.__main__ import main

class AtlasTests(unittest.TestCase):
    def test_six_real_concentric_rings_with_48_segments(self):
        root=ET.fromstring(render_svg()); ns={'s':'http://www.w3.org/2000/svg'}
        rings=[g for g in root.findall('s:g',ns) if g.attrib.get('class')=='ring']
        self.assertEqual(len(rings),6)
        self.assertEqual(len(root.findall('.//s:textPath',ns)),48)
        self.assertEqual(len({r[3] for r in RINGS}),6)
        self.assertIn('0 0 2240 1800',render_svg())

    def test_readonly_accessible_wheel(self):
        s=render_svg();self.assertIn('aria-labelledby="atlas-title atlas-desc"',s)
        for label in ('INCENTIVES','ASSETS','CAPITAL','PROOF IS NOT AUTHORITY'):self.assertIn(label,s)
        self.assertNotIn('<image',s)

    def test_no_false_claim_or_money_from_geometry(self):
        s=render_html();self.assertIn('not proof of economic superiority',s)
        self.assertIn('No execution, investment, payment or permission',s)
        self.assertEqual(len(MECHANISMS),15)

    def test_csp_only_exact_static_script_allowed(self):
        expected=base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
        s=render_html();self.assertIn("script-src 'sha256-"+expected+"'",s)
        self.assertEqual(s.count('<script>'),1)
        self.assertNotIn("fetch(",s);self.assertNotIn('innerHTML',s)

    def test_keyboard_buttons_only_highlight_visuals(self):
        s=render_html();self.assertEqual(s.count('data-select='),7)
        self.assertIn('aria-pressed="true"',s);self.assertIn('aria-live="polite"',s)
        self.assertIn('prefers-reduced-motion',s)

    def test_external_source_text_is_escaped(self):
        v=empty_snapshot();v['scope']='</text><script>alert(1)</script>'
        self.assertNotIn('<script>alert',render_svg(v))
        self.assertNotIn('<script>alert',render_html(v))

    def test_funding_flag_rejected(self):
        v=empty_snapshot();v['funding_authority']=True
        with self.assertRaises(EvidenceError):render_svg(v)

    def test_atlas_cli_is_offline_and_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'atlas'
            self.assertEqual(main(['atlas','--output',str(path)]),0)
            ET.parse(path/'wheel.svg')
            self.assertEqual(json.loads((path/'snapshot.json').read_text())['scope'],'ARCHITECTURE_ONLY_NO_ENTERPRISE_INPUT')
            self.assertEqual(main(['atlas','--output',str(path)]),2)

    def test_economic_cli_requires_trusted_frozen_source(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch('flywheel_wheel.__main__.live_context') as called:
                self.assertEqual(main(['couple','--enterprise',d,'--world','x','--output',str(Path(d)/'new'),'--request','x','--universe','y']),2)
                called.assert_not_called()

    def test_atlas_rejects_unrequested_enterprise_execution(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(['atlas','--enterprise',d,'--output',str(Path(d)/'new')]),2)

if __name__=='__main__':unittest.main()
