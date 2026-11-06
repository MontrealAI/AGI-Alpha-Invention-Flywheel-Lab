"""Failing-first boundary cases and full-case substitution tests, no live systems."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from continuity_omega.demo import case_for
from continuity_omega.engine import construct,digest
from continuity_omega.checker import audit
from continuity_omega.verification import case_digest
from continuity_omega.review import load_json,render_html

ROOT=Path(__file__).resolve().parents[1]

class VerificationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.case=case_for()
        self.handoff,self.passport=construct(self.case)
        self.pin=case_digest(self.case)

    def test_correct_caller_pin_is_not_origin_authentication(self):
        r=audit(self.case,self.handoff,self.passport,expected_case_sha256=self.pin)
        self.assertEqual(r['verdict'],'PASS_SYNTHETIC_ONLY')
        self.assertEqual(r['case_binding'],'CALLER_PIN_MATCHED')
        self.assertEqual(r['origin_authentication'],'NOT_ESTABLISHED')
        self.assertEqual(r['timing_evidence'],'STIPULATED_NOT_MEASURED')
        self.assertIs(r['external_certification'],False)

    def test_unpinned_consistency_is_explicit(self):
        r=audit(self.case,self.handoff,self.passport)
        self.assertEqual(r['case_binding'],'UNPINNED')
        self.assertEqual(r['verdict'],'PASS_SYNTHETIC_ONLY')

    def test_coherent_replacement_cannot_rewrite_original_contract(self):
        self.case['source_events'][3]['quantity']=1200
        self.case['source_seal']=digest(self.case['source_events'])
        h,p=construct(self.case)
        self.assertEqual(audit(self.case,h,p)['verdict'],'PASS_SYNTHETIC_ONLY')
        r=audit(self.case,h,p,expected_case_sha256=self.pin)
        self.assertEqual(r['verdict'],'FAIL')
        self.assertIn('FROZEN_CASE_CHANGED',r['failures'])

    def test_objective_supplier_budget_and_rights_are_all_pinned(self):
        edits=[('objective','deadline_hours',49),('buyer','maximum_offer',5900),
               ('economics','offer',5750)]
        for parent,key,value in edits:
            c=copy.deepcopy(self.case);c[parent][key]=value
            h,p=construct(c)
            self.assertIn('FROZEN_CASE_CHANGED',audit(c,h,p,expected_case_sha256=self.pin)['failures'])
        c=copy.deepcopy(self.case);c['suppliers'][0]['capacity_units']+=1
        h,p=construct(c)
        self.assertIn('FROZEN_CASE_CHANGED',audit(c,h,p,expected_case_sha256=self.pin)['failures'])

    def test_false_boolean_currency_is_not_one_dollar(self):
        c=copy.deepcopy(self.case)
        c['economics']['costs']={k:0 for k in c['economics']['costs']}
        c['suppliers'][0]['quoted_cost']=0;c['economics']['offer']=1
        h,p=construct(c)
        c['economics']['offer']=True;p['economics']['offer']=True
        r=audit(c,h,p)
        self.assertEqual(r['verdict'],'FAIL')
        self.assertIn('OFFER_TYPE_INVALID',r['failures'])

    def test_all_top_level_nonrecord_inputs_fail_without_crashing(self):
        for bad in [None,True,1,[],"x"]:
            for position in range(3):
                args=[self.case,self.handoff,self.passport];args[position]=bad
                with self.subTest(position=position,bad=bad):
                    self.assertEqual(audit(*args)['verdict'],'FAIL')

    def test_every_input_field_type_mutation_is_structured_and_pin_bound(self):
        """All single-node replacements must fail if they change the pinned JSON."""
        def nodes(obj,path=()):
            yield path
            if isinstance(obj,dict):
                for key,value in obj.items():yield from nodes(value,path+(key,))
            elif isinstance(obj,list):
                for key,value in enumerate(obj):yield from nodes(value,path+(key,))
        changed=0
        for path in nodes(self.case):
            for replacement in [None,True,False,-1,0,1,1.0,"",[],{}]:
                c=copy.deepcopy(self.case)
                if not path:c=copy.deepcopy(replacement)
                else:
                    target=c
                    for key in path[:-1]:target=target[key]
                    target[path[-1]]=copy.deepcopy(replacement)
                if case_digest(c)==self.pin:continue
                changed+=1
                r=audit(c,self.handoff,self.passport,expected_case_sha256=self.pin)
                self.assertEqual(r['verdict'],'FAIL',(path,replacement))
        self.assertEqual(changed,945)

    def test_output_nested_type_mutations_do_not_crash(self):
        for root,keys in [(self.handoff,list(self.handoff)),(self.passport,list(self.passport))]:
            for key in keys:
                for val in [None,[],{},True,1.0]:
                    mutated=copy.deepcopy(root);mutated[key]=val
                    args=(self.case,mutated,self.passport) if root is self.handoff else (self.case,self.handoff,mutated)
                    self.assertEqual(audit(*args)['verdict'],'FAIL',(key,val))

    def test_malformed_selected_reservation_returns_explicit_failure(self):
        self.case['suppliers'][0]['existing_reservations']=[None]
        self.assertIn('SUPPLIER_RESERVATION_INVALID',audit(self.case,self.handoff,self.passport)['failures'])

    def test_unsupported_event_amendment_field_is_not_silently_ignored(self):
        self.case['source_events'][3]['spec_sha256']='a'*64
        self.case['source_seal']=digest(self.case['source_events'])
        self.assertIn('EVENT_FIELDS_INVALID',audit(self.case,self.handoff,self.passport)['failures'])

    def test_unknown_authority_fields_are_rejected(self):
        self.passport['approved_for_real_execution']=True
        self.assertIn('PASSPORT_SHAPE_INVALID',audit(self.case,self.handoff,self.passport)['failures'])

    def test_invalid_expected_pins_fail_closed(self):
        for pin in ['',True,'x'*64,'0'*64]:
            r=audit(self.case,self.handoff,self.passport,expected_case_sha256=pin)
            self.assertEqual(r['verdict'],'FAIL')

    def test_strict_json_reader_rejects_duplicates_and_nonfinite_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.json'
            for text in ['{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}']:
                p.write_text(text)
                with self.assertRaises(ValueError):load_json(p)

    def test_nonfinite_direct_input_is_rejected(self):
        self.case['economics']['offer']=float('nan')
        self.assertEqual(audit(self.case,self.handoff,self.passport)['verdict'],'FAIL')

    def test_html_escapes_untrusted_findings(self):
        html=render_html({'verdict':'FAIL','failures':['<script>alert(1)</script>']})
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('VERIFICATION FAILED',html)
        self.assertNotIn('SYNTHETIC CHECK PASSED',html)

    def test_pinned_cli_and_fresh_inspection_ignore_stored_badges(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';report=Path(tmp)/'report'
            def run(*args):
                return subprocess.run([sys.executable,'-m',*args],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(run('continuity_omega','demo','--out',str(data)).returncode,0)
            a=run('continuity_omega.review','--in-dir',str(data),'--expected-case-sha256',self.pin,'--report-dir',str(report))
            self.assertEqual(a.returncode,0,a.stdout+a.stderr)
            self.assertIn('CALLER_PIN_MATCHED',(report/'index.html').read_text())
            again=run('continuity_omega.review','--in-dir',str(data),'--expected-case-sha256',self.pin,'--report-dir',str(report))
            self.assertNotEqual(again.returncode,0)
            h=json.loads((data/'HANDOFF.json').read_text());h['required_units']=1
            (data/'HANDOFF.json').write_text(json.dumps(h))
            inspected=run('continuity_omega','inspect','--in-dir',str(data),'--expected-case-sha256',self.pin)
            self.assertEqual(inspected.returncode,3,inspected.stdout+inspected.stderr)
            self.assertEqual(json.loads(inspected.stdout)['fresh_audit']['verdict'],'FAIL')
            self.assertEqual(json.loads((data/'AUDIT.json').read_text())['verdict'],'PASS_SYNTHETIC_ONLY')

    def test_cli_invalid_json_returns_structured_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'INPUT.json').write_text('{"schema":1,"schema":2}')
            r=subprocess.run([sys.executable,'-m','continuity_omega.review','--in-dir',str(p),
                '--expected-case-sha256',self.pin],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(r.returncode,3)
            self.assertEqual(json.loads(r.stdout)['verdict'],'FAIL')

if __name__=='__main__':unittest.main()
