# SPDX-License-Identifier: Apache-2.0
"""Shared pre-dispatch service capacity, using authored responses only."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError, Runtime
from bridge.services import AccessRuntime
from bridge.workflow_demo import FixtureRuntime, proposal, specification
from bridge.workflows import WorkflowService


class SingleCapacityPlan:
    max_concurrent = 1
    def __init__(self, hold_at=1, fail_primary=False):
        self._lock = threading.RLock()
        self._active = {}
        self.epoch = 0
        self.calls, self.busy = [], 0
        self.entered, self.release = threading.Event(), threading.Event()
        self.hold_at, self.fail_primary = hold_at, fail_primary
    def execution_identity(self):
        return ('synthetic-authorized-account', self.epoch)
    def generate(self, data, on_event=None, *, expected_execution_identity=None, cancelled_before_dispatch=None):
        with self._lock:
            if cancelled_before_dispatch and cancelled_before_dispatch():
                error = BridgeError("CANCELLED", "Fixture queued request cancelled.")
                error.pre_dispatch = True
                raise error
            if expected_execution_identity != self.execution_identity():
                raise BridgeError('CHATGPT_ACCOUNT_CHANGED', 'Fixture authority changed.')
            if self._active:
                self.busy += 1
                raise BridgeError('BUSY', 'Fixture service has one active slot.')
            self._active[data['run_id']] = threading.Event()
            self.calls.append(data)
            number = len(self.calls)
        try:
            if number == self.hold_at:
                self.entered.set()
                if not self.release.wait(5):
                    raise AssertionError('Test did not release its fixture request.')
            payload = data.get('prompt', '')
            correct = not (self.fail_primary and 'Use the strongest direct conventional approach first.' in payload)
            if on_event:
                on_event({'delta': 'fixture progress'})
            return {'text': json.dumps(proposal(correct)), 'provider': data['provider'], 'model': data['model'], 'cost': {'amount': None}}
        finally:
            with self._lock:
                self._active.pop(data['run_id'], None)
    def cancel(self, run_id):
        with self._lock:
            active = self._active.get(run_id)
            if active is not None:
                active.set()
            return {'cancelled': active is not None}
    def close(self):
        self.epoch += 1


class SharedCodex:
    max_concurrent = 1
    def __init__(self, plan):
        self.plan = plan
    def execution_identity(self):
        return self.plan.execution_identity()
    def generate(self, data, on_event=None, **kwargs):
        return self.plan.generate(data, on_event=on_event, **kwargs)
    def cancel(self, run_id):
        return self.plan.cancel(run_id)
    def close(self):
        pass


class WorkflowCapacityTests(unittest.TestCase):
    def setup_runtime(self, **kwargs):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runtime = AccessRuntime(FixtureRuntime([]), {'local_only': False}, private_root=temporary.name)
        plan = SingleCapacityPlan(**kwargs)
        runtime._services.update(chatgpt=plan, codex=SharedCodex(plan))
        self.addCleanup(runtime.close)
        self.addCleanup(plan.release.set)
        service = WorkflowService(runtime, Path(temporary.name) / 'runs')
        self.addCleanup(service.close)
        return runtime, plan, service

    def spec(self, strategy='parallel-exploration', provider='chatgpt'):
        spec = specification()
        spec['roles'] = {'builder': {'provider': provider, 'model': 'fixture'}}
        spec['local_only'] = False
        if strategy == 'single-model':
            spec.update(strategy=strategy, max_iterations=1, max_actions=1)
        else:
            count = 3 if strategy == 'adaptive' else 2
            spec.update(strategy=strategy, approaches=['Direct affine equation', 'Expanded affine equation'], max_iterations=count, max_actions=count)
        return spec

    def background(self, action):
        result, errors = [], []
        def run():
            try:
                result.append(action())
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=run)
        thread.start()
        return thread, result, errors

    def finish_thread(self, thread, errors):
        thread.join(5)
        self.assertFalse(thread.is_alive(), 'Capacity queue deadlocked.')
        self.assertEqual(errors, [])

    def wait_until(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            threading.Event().wait(.01)
        self.assertTrue(condition())

    def run_parent(self, service, ident):
        state = service.get(ident)
        while state['status'] == 'ready':
            state = service.step(ident)
        return state

    def test_parallel_branches_wait_without_spending_their_only_iteration(self):
        runtime, plan, service = self.setup_runtime()
        parent = service.create(self.spec())
        thread, result, errors = self.background(lambda: self.run_parent(service, parent['id']))
        self.assertTrue(plan.entered.wait(2))
        self.wait_until(lambda: any(service.get(b['run_id'])['waiting_for_capacity'] for b in parent['branches']))
        queued = [service.get(b['run_id']) for b in parent['branches'] if service.get(b['run_id'])['waiting_for_capacity']]
        self.assertEqual(len(queued), 1)
        self.assertEqual((queued[0]['model_calls'], queued[0]['iteration']), (0, 0))
        plan.release.set()
        self.finish_thread(thread, errors)
        self.assertEqual(result[0]['status'], 'complete')
        self.assertEqual(result[0]['model_calls'], 2)
        self.assertEqual([b['status'] for b in result[0]['branches']], ['complete', 'complete'])
        self.assertEqual(plan.busy, 0)

    def test_adaptive_alternatives_share_plan_capacity_after_recorded_failure(self):
        runtime, plan, service = self.setup_runtime(hold_at=2, fail_primary=True)
        parent = service.create(self.spec('adaptive'))
        thread, result, errors = self.background(lambda: self.run_parent(service, parent['id']))
        self.assertTrue(plan.entered.wait(2))
        self.wait_until(lambda: any(service.get(b['run_id'])['waiting_for_capacity'] for b in parent['branches'][1:]))
        plan.release.set()
        self.finish_thread(thread, errors)
        self.assertEqual(result[0]['status'], 'complete')
        self.assertEqual(result[0]['model_calls'], 3)
        self.assertEqual([b['status'] for b in result[0]['branches']], ['exhausted', 'complete', 'complete'])
        self.assertEqual(plan.busy, 0)

    def test_independent_parents_share_the_same_selected_plan_slot(self):
        runtime, plan, service = self.setup_runtime()
        parents = [service.create(self.spec()) for _ in range(2)]
        threads = [self.background(lambda p=p: self.run_parent(service, p['id'])) for p in parents]
        self.assertTrue(plan.entered.wait(2))
        self.wait_until(lambda: len(service._waiting) == 3)
        self.assertEqual(sum(service.get(b['run_id'])['model_calls'] for p in parents for b in p['branches']), 1)
        plan.release.set()
        for thread, result, errors in threads:
            self.finish_thread(thread, errors)
            self.assertEqual(result[0]['status'], 'complete')
            self.assertEqual(result[0]['model_calls'], 2)
        self.assertEqual(len(plan.calls), 4)
        self.assertEqual(plan.busy, 0)

    def test_direct_chatgpt_and_queued_codex_workflow_share_capacity_and_cancel(self):
        runtime, plan, service = self.setup_runtime()
        direct = self.background(lambda: runtime.generate({'provider':'chatgpt', 'model':'fixture', 'prompt':'direct request', 'run_id':'direct-first'}))
        self.assertTrue(plan.entered.wait(2))
        state = service.create(self.spec('single-model', 'codex'))
        queued = self.background(lambda: service.step(state['id']))
        self.wait_until(lambda: service.get(state['id'])['waiting_for_capacity'])
        service.cancel(state['id'])
        self.finish_thread(queued[0], queued[2])
        cancelled = service.get(state['id'])
        self.assertEqual(cancelled['status'], 'cancelled')
        self.assertEqual((cancelled['model_calls'], cancelled['iteration']), (0, 0))
        plan.release.set()
        self.finish_thread(direct[0], direct[2])
        self.assertEqual(len(plan.calls), 1)

    def test_account_change_while_queued_cannot_spend_an_attempt_on_new_account(self):
        runtime, plan, service = self.setup_runtime()
        direct = self.background(lambda: runtime.generate({'provider':'chatgpt','model':'fixture','prompt':'direct','run_id':'hold-account'}))
        self.assertTrue(plan.entered.wait(2))
        state = service.create(self.spec('single-model'))
        queued = self.background(lambda: service.step(state['id']))
        self.wait_until(lambda: service.get(state['id'])['waiting_for_capacity'])
        plan.epoch += 1
        self.finish_thread(queued[0], queued[2])
        state = service.get(state['id'])
        self.assertEqual(state['status'], 'paused')
        self.assertEqual((state['model_calls'], state['iteration']), (0, 0))
        self.assertEqual(state['events'][-1]['kind'], 'admission_refused')
        plan.release.set()
        self.finish_thread(direct[0], direct[2])
        self.assertEqual(len(plan.calls), 1)

    def test_direct_queued_cancellation_and_nested_request_do_not_dispatch(self):
        runtime, plan, service = self.setup_runtime()
        direct = self.background(lambda: runtime.generate({'provider':'chatgpt','model':'fixture','prompt':'first','run_id':'first'}))
        self.assertTrue(plan.entered.wait(2))
        waiting = self.background(lambda: runtime.generate({'provider':'codex','model':'fixture','prompt':'queued','run_id':'queued'}))
        self.wait_until(lambda: 'queued' in runtime._queued_requests)
        self.assertTrue(runtime.cancel('queued')['cancelled'])
        waiting[0].join(3)
        self.assertFalse(waiting[0].is_alive())
        self.assertEqual([e.code for e in waiting[2]], ['CANCELLED'])
        plan.release.set()
        self.finish_thread(direct[0], direct[2])
        with self.assertRaises(BridgeError) as error:
            runtime.generate({'provider':'chatgpt','model':'fixture','prompt':'outer','run_id':'outer'},
                on_event=lambda _: runtime.generate({'provider':'chatgpt','model':'fixture','prompt':'nested','run_id':'nested'}))
        self.assertEqual(error.exception.code, 'EXECUTION_REENTRANCY')
        self.assertEqual(len(plan.calls), 2)

    def test_identity_change_after_slot_grant_restores_only_unsent_allowance(self):
        runtime, plan, service = self.setup_runtime(hold_at=0)
        generate = runtime._generate_admitted
        def change_then_generate(data, on_event, admission, cancel):
            plan.epoch += 1
            return generate(data, on_event, admission, cancel)
        runtime._generate_admitted = change_then_generate
        state = service.step(service.create(self.spec('single-model'))['id'])
        self.assertEqual(state['status'], 'paused')
        self.assertEqual((state['model_calls'], state['iteration']), (0, 0))
        self.assertEqual(plan.calls, [])
        self.assertEqual(state['events'][-1]['kind'], 'model_not_dispatched')
        self.assertEqual(service._request_costs(state), [])

    def test_completed_cancel_before_facade_registration_cannot_dispatch(self):
        runtime, plan, service = self.setup_runtime(hold_at=0)
        created = service.create(self.spec('single-model'))
        generate = runtime.generate
        def cancel_then_generate(data, on_event=None, _admission=None):
            service.cancel(created['id'])
            return generate(data, on_event=on_event, _admission=_admission)
        runtime.generate = cancel_then_generate
        state = service.step(created['id'])
        self.assertEqual(state['status'], 'cancelled')
        self.assertEqual((state['model_calls'], state['iteration']), (0, 0))
        self.assertEqual(plan.calls, [])
        self.assertEqual(state['events'][-1]['kind'], 'model_not_dispatched')
        self.assertEqual(service._request_costs(state), [])

    def test_bare_runtime_parallel_calls_also_queue_at_declared_global_capacity(self):
        entered, release = threading.Event(), threading.Event()
        calls = []
        def sender(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                entered.set()
                if not release.wait(5):
                    raise AssertionError('Fixture was not released.')
            return {'choices': [{'message': {'content': json.dumps(proposal(True))}}], 'usage': {'prompt_tokens': 0, 'completion_tokens': 1}}
        runtime = Runtime({'local_only': True, 'max_concurrent_requests': 1, 'max_attempts': 1,
            'providers': {'fixture': {'kind': 'openai', 'base_url': 'http://127.0.0.1:2', 'models': {
                'fixture': {'input_per_million': 0, 'output_per_million': 0, 'max_output_tokens': 2048}}}}}, sender=sender)
        self.addCleanup(release.set)
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(runtime, folder)
            self.addCleanup(service.close)
            spec = self.spec(provider='fixture')
            spec['local_only'] = True
            parent = service.create(spec)
            thread, result, errors = self.background(lambda: self.run_parent(service, parent['id']))
            self.assertTrue(entered.wait(2))
            # The executor itself can also serialize a one-slot base runtime;
            # either queue location must leave the second branch unconsumed.
            self.assertEqual(sum(service.get(b['run_id'])['model_calls'] for b in parent['branches']), 1)
            release.set()
            self.finish_thread(thread, errors)
            self.assertEqual(result[0]['status'], 'complete')
            self.assertEqual(result[0]['model_calls'], 2)
            self.assertEqual(len(calls), 2)
            self.assertEqual([b['status'] for b in result[0]['branches']], ['complete', 'complete'])

    def test_all_base_providers_share_one_global_runtime_capacity(self):
        runtime, plan, service = self.setup_runtime()
        base = SingleCapacityPlan()
        base.provider = lambda name: SimpleNamespace(remote=False)
        base.status = lambda: {'providers': [{'id': name, 'local': True} for name in ('local-a','local-b')]}
        generate = base.generate
        base.generate = lambda data, on_event=None: generate(data, on_event, expected_execution_identity=base.execution_identity())
        runtime.base = base
        self.addCleanup(base.release.set)
        states = [service.create(self.spec('single-model', provider)) for provider in ('local-a', 'local-b')]
        threads = [self.background(lambda s=s: service.step(s['id'])) for s in states]
        self.assertTrue(base.entered.wait(2))
        self.wait_until(lambda: len(service._waiting) == 1)
        self.assertEqual(sum(service.get(s['id'])['model_calls'] for s in states), 1)
        base.release.set()
        for thread, result, errors in threads:
            self.finish_thread(thread, errors)
            self.assertEqual(result[0]['status'], 'complete')
        self.assertEqual(len(base.calls), 2)
        self.assertEqual(base.busy, 0)


if __name__ == '__main__':
    unittest.main()
