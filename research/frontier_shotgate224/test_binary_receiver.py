"""Supplemental post-frozen physical certificate for executable binary comparator.

Not part of the preimplementation primary 609-pair selection or original QEC score.
"""
from __future__ import annotations
import math
import unittest
import numpy as np

from shotgate import helstrom_one_shot_error, frame_one_shot_error
from binary_receiver import BinaryHelstrom
from noise_experiment import NoiseExperiment
from recovery import Recovery
from public_fixtures import pollatsek_ruskai_7, shor_9, apply_local
from second_public_fixtures import pauli_hypotheses


class ActualBinaryReceiverTests(unittest.TestCase):
    def test_physical_two_hypothesis_execution_and_logical_nondisturbance(self):
        cases=((pollatsek_ruskai_7, ("Z5","Z6")),
               (shor_9, ("Y1","X2")))
        for factory, names in cases:
            with self.subTest(code=factory.__name__):
                n, codewords=factory()
                experiment=NoiseExperiment(n,codewords,pauli_hypotheses(n))
                i,j=(experiment.hypothesis_names.index(name) for name in names)
                receiver=BinaryHelstrom(experiment,i,j)
                certificate=receiver.certificate()
                self.assertLess(certificate["physical_completeness_residual"],2e-8)
                self.assertEqual(certificate["fine_kraus_operators"],
                                 experiment.syndrome_rank)
                physical_helstrom=helstrom_one_shot_error(
                    experiment._syndrome_states[i],experiment._syndrome_states[j])
                self.assertAlmostEqual(
                    certificate["equal_prior_one_shot_error"],physical_helstrom,
                    delta=2e-8)
                p=experiment.response_matrix()
                frame=frame_one_shot_error(p[:,i],p[:,j])
                self.assertLessEqual(physical_helstrom,frame+2e-8)
                for logical in (np.array([math.sqrt(.37),1j*math.sqrt(.63)]),
                                np.array([.6+.1j,-.3+.7j])/math.sqrt(.95)):
                    expected=np.outer(logical,logical.conj())
                    state=Recovery(n,codewords).encode(logical)
                    for index in (i,j):
                        h=experiment.hypotheses[index]
                        branches=[apply_local(state,n,h["qubit"],k)
                                  for k in h["kraus"]]
                        measured=receiver.execute(branches)
                        self.assertAlmostEqual(measured["input_mass"],1,delta=2e-8)
                        self.assertAlmostEqual(measured["erasure"],0,delta=2e-8)
                        probabilities=certificate[
                            "probabilities_first_hypothesis" if index == i
                            else "probabilities_second_hypothesis"]
                        for k,label in enumerate(("first","second")):
                            actual=measured["logical_density_by_label"][label]
                            self.assertLess(float(np.max(abs(actual-
                                probabilities[k]*expected))),2e-8)
                            self.assertAlmostEqual(
                                measured["probabilities"][label],probabilities[k],
                                delta=2e-8)

    def test_reject_invalid_pair(self):
        n,codewords=pollatsek_ruskai_7()
        exp=NoiseExperiment(n,codewords,pauli_hypotheses(n))
        for indices in ((0,0),(-1,0),(0,exp.H)):
            with self.assertRaises(ValueError):
                BinaryHelstrom(exp,*indices)


if __name__=="__main__":
    unittest.main()
