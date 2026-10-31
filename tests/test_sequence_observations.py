import unittest
from connected_enterprise.joint_planning import observed_sequence_buyers

class SequenceObservations(unittest.TestCase):
    def test_actual_reactivation_response_not_future_probability(self):
        state={'buyers':[{'id':'a','active':False},{'id':'b','active':True}]}
        got=observed_sequence_buyers(state,{'reactivations':[{'customer_id':'a','responded':True},{'customer_id':'b','responded':False}]})
        self.assertTrue(got['a']['active'])
        self.assertFalse(got['b']['active'])
        self.assertFalse(state['buyers'][0]['active'])
        self.assertTrue(state['buyers'][1]['active'])

    def test_no_response_preserves_current_observation(self):
        self.assertEqual(observed_sequence_buyers({'buyers':[{'id':'a','active':False}]},{'reactivations':[]}),{'a':{'id':'a','active':False}})

    def test_rebased_runner_preserves_common_production_contract(self):
        import importlib.util,sys
        from pathlib import Path
        scripts=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(scripts))
        try:
            spec=importlib.util.spec_from_file_location('sequence_current',scripts/'run_sequence026.py')
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
            from connected_enterprise.engine import validate_config
            for arm in ('joint','sequence'):
                cfg=mod.config('central',arm);validate_config(cfg)
                self.assertEqual(cfg['mechanism_policy']['cost_contract']['production_envelope_microUSD'],cfg['production_cost'])
                self.assertEqual(sum(cfg['mechanism_policy']['costs']['conventional'].values()),0)
        finally:sys.path.remove(str(scripts))
