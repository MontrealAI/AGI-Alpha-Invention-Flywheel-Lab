# SPDX-License-Identifier: Apache-2.0
"""Only explicitly supported machine-response roles opt into JSON mode."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.workflow_demo import FixtureRuntime, proposal, specification
from bridge.workflows import WorkflowService


class WorkflowJSONModeTests(unittest.TestCase):
    def run_fixture(self, supported, kind, extra_roles=False):
        responses = (["Supplied-context analysis"] if extra_roles else []) + [proposal(True), {"verdict":"accept","feedback":"Frozen cases pass."}] + (["Costs remain unknown."] if extra_roles else [])
        runtime = FixtureRuntime(responses)
        runtime.provider = lambda ident: SimpleNamespace(remote=False, kind=kind, models={"fixture":SimpleNamespace(json_mode=supported)})
        spec = specification()
        if extra_roles:
            spec['roles'].update(researcher={}, economist={})
        spec['roles'] = {role:{'provider':'fixture','model':'fixture'} for role in spec['roles']}
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(runtime, folder)
            try:
                state = service.create(spec)
                while state['status'] == 'ready':
                    state = service.step(state['id'])
                self.assertEqual(state['status'], 'complete')
            finally:
                service.close()
        return runtime.calls

    def test_capable_builder_and_critic_use_json_but_analysis_roles_remain_text(self):
        calls = self.run_fixture(True, 'openai', extra_roles=True)
        self.assertEqual([call.get('json_mode', False) for call in calls], [False, True, True, False])

    def test_plain_and_unsupported_provider_capabilities_remain_text(self):
        for supported, kind in [(False, 'openai'), (True, 'anthropic')]:
            with self.subTest(supported=supported, kind=kind):
                self.assertTrue(all('json_mode' not in call for call in self.run_fixture(supported, kind)))


if __name__ == '__main__':
    unittest.main()
