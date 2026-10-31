import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET
from flywheel_wheel.precision import render_svg,render_html,SCRIPT,publish
from flywheel_wheel.readout import EvidenceError
from flywheel_wheel.__main__ import main

# Presentation-only fixture. The shipped default renderer uses the existing atlas.RINGS.
RINGS=tuple((n,n.upper(),c,0,tuple('STEP'+str(k) for k in range(8)),n+' loop') for n,c in
            zip(('invention','evidence','incentives','assets','commerce','capital'),
                ('#BDA0FF','#69DCE8','#F3C881','#83DFC0','#83B7FF','#FFAC89')))

class PrecisionTests(unittest.TestCase):
    def test_full_wheel_has_six_rings_48_stages(self):
        root=ET.fromstring(render_svg(RINGS));ns={'s':'http://www.w3.org/2000/svg'}
        self.assertEqual(root.get('viewBox'),'0 0 2800 3040')
        self.assertEqual(len(root.findall('.//s:textPath',ns)),48)
        self.assertEqual(sum(g.get('class')=='ring' for g in root.findall('s:g',ns)),6)

    def test_complete_wheel_extent_is_inside_canvas(self):
        from flywheel_wheel.precision import CX,CY
        self.assertGreater(CX-1284,0);self.assertLess(CX+1284,2800)
        self.assertGreater(CY-1176,286);self.assertLess(CY+1176,2740)

    def test_keyboard_trace_and_strict_script_hash(self):
        out=render_html(render_svg(RINGS))
        token=base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
        self.assertIn("script-src 'sha256-"+token+"'",out)
        self.assertEqual(out.count('<button'),4)
        self.assertIn('aria-live="polite"',out)
        self.assertNotIn('fetch(',out);self.assertNotIn('innerHTML',out)

    def test_xml_and_labels_escaped(self):
        rings=list(RINGS);r=list(rings[0]);r[1]='<script>boom</script>';rings[0]=tuple(r)
        s=render_svg(rings);ET.fromstring(s);self.assertNotIn('<script>boom',s)

    def test_incomplete_ring_model_refused(self):
        with self.assertRaises(EvidenceError):render_svg(RINGS[:5])

    def test_create_only_artifacts_are_not_economic_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'plate';r=publish(target,RINGS)
            self.assertIs(r['funding_authority'],False)
            self.assertEqual({p.name for p in target.iterdir()},{'wheel.svg','index.html','snapshot.json'})
            with self.assertRaises(EvidenceError):publish(target,RINGS)

    def test_overlap_rejected_before_native_audit(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch('flywheel_wheel.__main__.live_readout') as audited:
                self.assertEqual(main(['audit-render','--enterprise',d,'--output',str(Path(d)/'view'),'--trust-frozen-source']),2)
                audited.assert_not_called()

    def test_existing_output_refused_before_financial_context(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'native').mkdir();(root/'view').mkdir()
            with mock.patch('flywheel_wheel.__main__.live_context') as audited:
                self.assertEqual(main(['couple','--enterprise',str(root/'native'),'--output',str(root/'view'),
                    '--trust-frozen-source','--request','missing','--universe','missing','--world','x']),2)
                audited.assert_not_called()

if __name__=='__main__':unittest.main()
