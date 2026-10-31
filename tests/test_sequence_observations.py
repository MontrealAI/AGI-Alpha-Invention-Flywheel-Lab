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
