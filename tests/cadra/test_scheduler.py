"""Scheduling through the shipped reducer and real CAS Run publication.

No parallel test-only scheduler. Synthetic agent/tool observations are explicit;
these tests do not claim real engineering-stage execution or throughput.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from .test_run_guard import guard, example, raw_document, binding, pending, AT
from .test_cadra import contract

schedule = guard.scheduler


def footprint(*files, dirs=(), exclusive=False):
    return dict(mode='exclusive' if exclusive else 'parallel', files=list(files), dirs=list(dirs))


def fixed(inputs=None):
    return dict(snapshot='scratch/fixed/manifest.json', sha256='a' * 64, inputs=inputs or {})


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / '.yuzio/cadra/runs/run-20261025-01.md'
        self.path.parent.mkdir(parents=True)
        self.data = example(); self.data['scheduler'] = schedule.initial()
        base = self.data['tasks'][0]
        self.data['tasks'] = []
        self.data['preflight'] = self.data['preflight'][:1]
        for slug in ('a', 'b', 'c'):
            task = deepcopy(base); task['slug'] = task['definition']['slug'] = slug
            task['definition']['ready_scope']['scope'] = footprint(slug + '.swift')
            self.data['tasks'].append(task)
            self.data['preflight'].append(dict(scope='task', slug=slug, status='passed', at=AT,
                                               inputs={}, evidence='synthetic ready input audit'))
            (self.root / (slug + '.swift')).write_text('// original ' + slug + '\n')
        self.clock = datetime.fromisoformat(AT)
        self.sha = guard.publish(self.path, raw_document(self.data), None, 'first', 1, 'create')

    def now(self):
        self.clock += timedelta(seconds=1)
        return self.clock.isoformat()

    def save(self, proposal=None):
        proposal = self.data if proposal is None else proposal
        owner = proposal['executor']
        self.sha = guard.publish(self.path, raw_document(proposal), self.sha, owner['instance_id'], owner['generation'])
        self.data = proposal

    def task(self, slug):
        return next(t for t in self.data['tasks'] if t['slug'] == slug)

    def event(self, kind, **payload):
        proposed = schedule.append_event(self.data, kind, self.now(), **payload)
        self.save(proposed)
        return schedule.replay(self.data)

    def group(self):
        members = schedule.select_group(self.data)
        self.event('group', members=members, before={s: {} for s in members},
                   before_refs={s: 'scratch/before-' + s for s in members})

    def stage(self, slug, stage='code', refresh=None, dispatch=True):
        task = self.task(slug)
        role = 'reviewer' if stage == 'review' else 'worker'; ref = role + '-1'
        if not any(b['id'] == ref for b in task['agents']):
            task['agents'].append(binding(role, slug + '-' + role, ref)); self.save()
        number = len(task['calls']) + 1
        before = deepcopy(task['calls'][-1]['result']['contract']) if task['calls'] else None
        call = dict(id=number, stage=stage, execution_mode='unattended', reason='synthetic stage',
                    agent_ref=ref, dispatch_evidence=None, before=before, dispatch='prepared',
                    closed=False, result=None, prepared_at=self.now(),
                    charged=dict(calls=1, remediation=0, retry_stage=None))
        if refresh is not None: call['refresh'] = refresh
        task['calls'].append(call); task['budget']['calls'] += 1
        task['checkpoint']['pending_call'] = number; task['state'] = 'running'; self.save()
        if dispatch:
            call.update(dispatch='dispatched', dispatch_evidence=dict(agent_id=slug + '-' + role,
                        source='synthetic host tool handle', at=self.now())); self.save()

    def close_stage(self, slug, next_stage='review', accepted=False):
        task = self.task(slug); call = task['calls'][-1]
        sr = contract(call['stage'], next_stage, 'stage_completed',
                      sum(c['stage'] == call['stage'] for c in task['calls']))
        sr['task'] = slug; sr['next']['allowed'] = next_stage is not None
        if accepted:
            self.assertEqual(call['stage'], 'validate')
            sr.update(status='completed', acceptance={'status': 'passed'},
                      candidate={'commit': None, 'snapshot': 'synthetic-fixed-candidate'})
            sr['next'] = dict(stage=None, allowed=False, reason='task_completed')
        call.update(closed=True, result=dict(contract=sr, handoff='synthetic-stage.md'))
        task['checkpoint'].update(pending_call=None, last_delivery=call['result']); self.save()

    def proof(self, slug):
        task = self.task(slug); call = task['calls'][-1] if task['calls'] else None
        b = next((b for b in task['agents'] if call and b['id'] == call['agent_ref']), None)
        return dict(agent_id=b['agent_id'] if b else None, host_id=b['host_id'] if b else None,
                    tools_stopped=True, observed_at=self.now(), source='synthetic exact host tools stopped')

    def wait_payload(self, slug, kind, wanted=None, cand=None):
        task = self.task(slug); call = task['calls'][-1] if task['calls'] else None
        view = schedule.replay(self.data)
        fields = dict(slug=slug, resource=kind, call_id=call['id'] if call else None,
                      scope=wanted or view['scope'][slug], candidate=cand or fixed(), stop=self.proof(slug))
        if kind == 'verification': fields['argv'] = ['/usr/bin/true']
        if call and not call['closed']:
            body = {k: deepcopy(fields[k]) for k in ['slug', 'resource', 'call_id', 'scope', 'candidate']}
            body.update(run_id=self.data['run_id'], generation=self.data['executor']['generation'], agent_ref=call['agent_ref'])
            if kind == 'verification': body['argv'] = fields['argv']
            content = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            name = f'.yuzio/cohestra/handoffs/{slug}/scratch/resources/{view["next_seq"]}.json'
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as f: f.write(content)
            fields['request'] = dict(path=name, sha256=hashlib.sha256(content).hexdigest(), body=body)
        return fields

    def wait(self, slug, kind, wanted=None, cand=None):
        return self.event('wait', **self.wait_payload(slug, kind, wanted, cand))

    def grant(self, **extra):
        view = schedule.replay(self.data); seq = schedule.next_request(view)
        self.event('grant', seq=seq, before={}, before_ref='scratch/resume-before',
                   candidate=view['group']['candidate'], **extra)

    def reject(self, proposal, message):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, message):
            guard.publish(self.path, raw_document(proposal), self.sha, 'first', 1)
        self.assertEqual(before, self.path.read_bytes())

    def test_scan_skips_conflict_and_preserves_queue_order(self):
        self.data['tasks'][1]['definition']['ready_scope']['scope'] = footprint('a.swift')
        # Set admission before initial creation of a separate Run, not mutate frozen definition.
        self.assertEqual(schedule.select_group(self.data), ['a', 'c'])
        self.assertEqual([t['slug'] for t in self.data['tasks']], ['a', 'b', 'c'])
        self.data['tasks'][0]['definition']['ready_scope']['scope']['mode'] = 'exclusive'
        self.assertEqual(schedule.select_group(self.data), ['a'])

    def test_real_group_has_two_parallel_stage_calls(self):
        self.group(); self.stage('a'); self.stage('b')
        self.assertEqual([t['state'] for t in self.data['tasks']], ['running', 'running', 'queued'])
        self.assertEqual(sum(t['budget']['calls'] for t in self.data['tasks']), 2)

    def test_third_stage_and_group_refill_rejected(self):
        self.group(); self.stage('a'); self.stage('b')
        new = deepcopy(self.data); new['tasks'][2]['state'] = 'running'
        self.reject(new, 'at most two active stages')
        with self.assertRaisesRegex(ValueError, 'cannot be refilled'):
            schedule.append_event(self.data, 'group', self.now(), members=['c'], before={'c': {}}, before_refs={'c': 'before'})

    def test_membership_immutable_and_group_selection_enforced(self):
        new = schedule.append_event(self.data, 'group', self.now(), members=['a', 'c'], before={'a': {}, 'c': {}}, before_refs={'a':'before','c':'before'})
        self.reject(new, 'scan queue')
        self.group(); new = deepcopy(self.data); new['scheduler']['events'][0]['members'] = ['a', 'c']
        self.reject(new, 'append-only|before images')

    def test_cross_file_wait_releases_all_and_oldest_ineligible_does_not_block(self):
        self.group(); self.stage('a'); self.stage('b')
        self.wait('a', 'files', footprint('a.swift', 'b.swift'))
        self.assertNotIn('a', schedule.replay(self.data)['leases'])
        self.assertIsNone(schedule.next_request(schedule.replay(self.data)))
        self.wait('b', 'files', footprint('b.swift', 'a.swift'))
        self.assertEqual(schedule.replay(self.data)['leases'], {})
        self.grant()
        self.assertIn('a', schedule.replay(self.data)['leases'])
        self.assertEqual(self.task('a')['budget']['calls'], 1)
        self.wait('a', 'verification')
        # B's file request is now executable, so it must run before a barrier.
        self.assertEqual(schedule.next_request(schedule.replay(self.data)), 2)
        self.grant()
        self.assertEqual(self.task('b')['budget']['calls'], 1)

    def test_executable_fifo_skips_ineligible_head(self):
        self.group(); self.stage('a'); self.stage('b')
        self.wait('a', 'verification')
        self.wait('b', 'files', footprint('b.swift'))
        self.assertEqual(schedule.next_request(schedule.replay(self.data)), 2)
        self.grant()
        self.assertEqual(self.task('b')['state'], 'running')

    def test_out_of_order_grant_and_partial_scope_rejected(self):
        self.group(); self.stage('a'); self.stage('b')
        self.wait('a', 'files'); self.wait('b', 'files')
        with self.assertRaisesRegex(ValueError, 'executable FIFO'):
            schedule.append_event(self.data, 'grant', self.now(), seq=2, before={}, before_ref='before')
        self.grant()
        fields = self.wait_payload('a', 'files', footprint('other.swift'))
        with self.assertRaisesRegex(ValueError, 'cannot shrink'):
            schedule.append_event(self.data, 'wait', self.now(), **fields)

    def test_release_requires_current_agent_and_stopped_tools(self):
        self.group(); self.stage('a')
        for fault in ['agent', 'active', 'stale']:
            fields = self.wait_payload('a', 'verification')
            if fault == 'agent': fields['stop']['agent_id'] = 'other'
            if fault == 'active': fields['stop']['tools_stopped'] = False
            if fault == 'stale': fields['stop']['observed_at'] = AT
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                schedule.append_event(self.data, 'wait', self.now(), **fields)
            # Remove only this test's unregistered request to reuse its unconsumed seq.
            (self.root / fields['request']['path']).unlink()

    def test_wait_cannot_omit_or_forge_request_identity(self):
        self.group(); self.stage('a')
        fields = self.wait_payload('a', 'verification'); fields.pop('request')
        with self.assertRaisesRegex(ValueError, 'request path'):
            schedule.append_event(self.data, 'wait', self.now(), **fields)

    def test_modified_request_file_rejected_without_publishing(self):
        self.group(); self.stage('a')
        fields = self.wait_payload('a', 'verification')
        (self.root / fields['request']['path']).write_text('{}')
        new = schedule.append_event(self.data, 'wait', self.now(), **fields)
        self.reject(new, 'request file changed')

    def test_phase_internal_verification_barrier_and_serial_commands(self):
        self.group(); self.stage('a'); self.stage('b')
        self.wait('a', 'verification')
        with self.assertRaisesRegex(ValueError, 'all writes must stop'):
            schedule.append_event(self.data, 'barrier', self.now(), candidate=fixed())
        self.wait('b', 'verification'); self.event('barrier', candidate=fixed()); self.grant()
        self.assertEqual(schedule.replay(self.data)['active'], 1)
        self.assertIsNone(schedule.next_request(schedule.replay(self.data)))
        self.event('finish', seq=1, stop=self.proof('a'), outcome='failed', source='synthetic failed command log')
        self.assertEqual(self.task('a')['state'], 'waiting')
        self.assertEqual(schedule.next_request(schedule.replay(self.data)), 2)
        self.grant()
        self.event('finish', seq=2, stop=self.proof('b'), outcome='passed', source='synthetic command result')
        self.event('window_end'); self.grant()
        self.assertEqual(self.task('a')['state'], 'running')
        self.assertEqual(self.task('b')['state'], 'waiting')
        self.assertEqual(self.task('a')['budget']['calls'], 1)
        self.assertFalse(self.task('a')['calls'][0]['closed'])

    def test_writes_cannot_resume_in_verification_window(self):
        self.group(); self.stage('a'); self.stage('b')
        self.wait('a', 'verification'); self.wait('b', 'verification')
        self.event('barrier', candidate=fixed()); self.grant()
        self.event('finish', seq=1, stop=self.proof('a'), outcome='passed', source='log')
        with self.assertRaisesRegex(ValueError, 'executable FIFO'):
            schedule.append_event(self.data, 'grant', self.now(), seq=3, before={}, before_ref='before')
        with self.assertRaisesRegex(ValueError, 'drain verification'):
            schedule.append_event(self.data, 'window_end', self.now())

    def test_waiting_task_cannot_hold_files_or_close_pending_call(self):
        self.group(); self.stage('a')
        new = deepcopy(self.data); new['tasks'][0]['state'] = 'waiting'
        self.reject(new, 'release every resource')
        fields = self.wait_payload('a', 'finalization')
        with self.assertRaisesRegex(ValueError, 'finalization cannot hide pending'):
            schedule.append_event(self.data, 'wait', self.now(), **fields)

    def test_completion_requires_group_stability(self):
        self.group(); self.stage('a'); self.close_stage('a')
        new = deepcopy(self.data); new['tasks'][0].update(state='completed', result={'state':'completed'})
        self.reject(new, 'stable group close')
        self.wait('a', 'finalization'); self.wait('b', 'finalization')
        self.event('close', candidate=fixed())
        new = deepcopy(self.data)
        for t in new['tasks'][:2]:t.update(state='completed', result={'state':'completed'})
        self.save(new)
        self.group()
        self.assertEqual(schedule.replay(self.data)['group']['members'], ['c'])

    def test_completion_without_group_is_rejected_for_task_and_run(self):
        for status in ('running', 'completed'):
            proposal = deepcopy(self.data)
            for task in proposal['tasks']:
                task.update(state='completed', result={'state': 'completed'})
            proposal['status'] = status
            with self.subTest(status=status):
                self.reject(proposal, 'completed task requires stable group close')

    def test_no_call_completion_still_uses_group_finalization(self):
        self.group()
        self.wait('a', 'finalization'); self.wait('b', 'finalization')
        self.event('close', candidate=fixed())
        proposal = deepcopy(self.data)
        for task in proposal['tasks'][:2]:
            task.update(state='completed', result={'state': 'completed'})
        self.save(proposal)
        self.assertTrue(all(not self.task(s)['calls'] for s in ('a', 'b')))

    def test_input_comparison_normalizes_aliases_and_requires_explicit_absence(self):
        for old, new in [('Shared.swift', 'shared.swift'), ('Caf\u00e9.swift', 'Cafe\u0301.swift')]:
            with self.subTest(old=old, new=new):
                self.assertEqual(schedule.affected({old: None}, {new: 'b' * 64}), [old])
                self.assertEqual(schedule.affected({old: 'a' * 64}, {new: 'a' * 64}), [])
                self.assertEqual(schedule.affected({old: None}, {new: None}), [])
                self.assertEqual(schedule.affected({old: None}, {}), [old])
        self.assertEqual(schedule.affected({'a.swift': 'a' * 64},
                                         {'a.swift': 'a' * 64, 'other.swift': 'b' * 64}), [])

    def test_duplicate_input_aliases_are_rejected(self):
        for paths in [('Shared.swift', 'shared.swift'), ('Caf\u00e9.swift', 'Cafe\u0301.swift')]:
            inputs = dict.fromkeys(paths, 'a' * 64)
            with self.subTest(paths=paths):
                with self.assertRaisesRegex(ValueError, 'input.*aliases'):
                    schedule.candidate(fixed(inputs))
                proposal = deepcopy(self.data)
                proposal['tasks'][0]['definition']['ready_scope']['inputs'] = inputs
                self.reject(proposal, 'input.*aliases')

    def test_group_close_rejects_absent_dependency_created_through_alias(self):
        self.group()
        self.wait('a', 'finalization', cand=fixed({'Shared.swift': None}))
        self.wait('b', 'finalization', cand=fixed({'shared.swift': 'b' * 64}))
        before = self.path.read_bytes()
        for inputs in ({'shared.swift': 'b' * 64}, {}):
            with self.subTest(inputs=inputs), self.assertRaisesRegex(ValueError, 'invalidates task evidence'):
                self.event('close', candidate=fixed(inputs))
            self.assertEqual(before, self.path.read_bytes())

    def test_finished_stage_finalizes_after_peer_policy_stop_without_file_grant(self):
        self.data['tasks'][0]['definition']['execution_policy'] = {'stop_queue_on_failure': True}
        self.path.unlink()
        self.sha = guard.publish(self.path, raw_document(self.data), None, 'first', 1, 'create')
        self.group(); self.stage('a')
        self.stage('b'); self.close_stage('b', 'review')
        self.stage('b', 'review'); self.close_stage('b', 'validate'); self.stage('b', 'validate')
        self.wait('b', 'verification'); self.wait('a', 'verification')
        self.event('barrier', candidate=fixed()); self.grant()
        self.event('finish', seq=1, stop=self.proof('b'), outcome='passed', source='synthetic command log')
        self.event('abort', slug='a', call_id=1, stop=self.proof('a'), state='failed',
                   reason='known failure', source='synthetic host stop')
        self.event('window_end'); self.close_stage('b', None, accepted=True)
        budget = deepcopy(self.task('b')['budget'])
        calls = deepcopy(self.task('b')['calls'])
        delivery = deepcopy(self.task('b')['checkpoint']['last_delivery'])
        # A policy stop must still forbid business writes.
        with self.assertRaisesRegex(ValueError, 'stop_queue_on_failure'):
            self.grant()
        view = self.wait('b', 'finalization')
        continuation = next(r for r in view['requests'] if r.get('resume_of') == 1)
        self.assertEqual(continuation['status'], 'cancelled')
        self.assertNotIn('b', view['leases'])
        self.assertEqual(self.task('b')['budget'], budget)
        self.assertEqual(self.task('b')['calls'], calls)
        self.assertEqual(self.task('b')['checkpoint']['last_delivery'], delivery)
        self.event('close', candidate=fixed(), residuals={'a': 'synthetic safe residual audit'})
        proposal = deepcopy(self.data)
        proposal['tasks'][1].update(state='completed', result={'state': 'completed', 'last_delivery': delivery})
        proposal['tasks'][2].update(state='skipped', result={'state': 'skipped', 'last_delivery': None})
        proposal['status'] = 'stopped'
        self.save(proposal)
        self.assertFalse(guard.unfinished(self.data))

    def test_finalization_does_not_cancel_unfinished_stage_continuation(self):
        self.group(); self.stage('a'); self.stage('b'); self.close_stage('b')
        self.wait('b', 'finalization'); self.wait('a', 'verification')
        self.event('barrier', candidate=fixed()); self.grant()
        self.event('finish', seq=2, stop=self.proof('a'), outcome='passed', source='synthetic command log')
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.wait('a', 'finalization')
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(schedule.replay(self.data)['requests'][-1]['status'], 'waiting')

    def test_finalization_does_not_cancel_ordinary_file_wait(self):
        self.group(); self.stage('a'); self.close_stage('a')
        self.wait('a', 'files')
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already has waiting request'):
            self.wait('a', 'finalization')
        self.assertEqual(before, self.path.read_bytes())

    def test_changed_dependency_requires_refresh_with_real_stage_budget(self):
        self.group(); self.stage('a'); self.close_stage('a', None)
        self.wait('a', 'finalization', cand=fixed({'a.swift':'a'*64}))
        self.wait('b', 'finalization', cand=fixed({'b.swift':'a'*64}))
        end = fixed({'a.swift':'b'*64, 'b.swift':'a'*64})
        with self.assertRaisesRegex(ValueError, 'invalidates task evidence'):
            schedule.append_event(self.data, 'close', self.now(), candidate=end)
        self.event('invalidate', slug='a', stage='review', candidate=end, paths=['a.swift'], source='partner changed dependency')
        refresh = deepcopy(self.data['scheduler']['events'][-1])
        self.grant(); self.stage('a', 'review', refresh)
        self.assertEqual(self.task('a')['budget']['calls'], 2)
        self.assertEqual(self.task('a')['calls'][-1]['before']['next']['allowed'], False)

    def test_invalidation_outside_flow_and_unrelated_hash_change(self):
        self.assertEqual(schedule.affected({'a.swift':'a'*64}, {'a.swift':'a'*64,'other.swift':'b'*64}), [])
        self.group(); self.stage('a'); self.close_stage('a'); self.wait('a', 'finalization', cand=fixed({'a.swift':'a'*64}))
        with self.assertRaisesRegex(ValueError, 'change evidence'):
            schedule.append_event(self.data, 'invalidate', self.now(), slug='a', stage='review',
                                  candidate=fixed({'a.swift':'a'*64}), paths=[], source='none')

    def test_journal_cannot_be_edited_or_wait_queue_reordered(self):
        self.group(); self.stage('a'); self.wait('a', 'verification')
        new = deepcopy(self.data); new['scheduler']['events'][-1]['at'] = AT
        self.reject(new, 'regressed|predates|append-only')
        new = deepcopy(self.data); new['scheduler']['events'][-1]['id'] += 1
        self.reject(new, 'contiguous')

    def test_queued_skip_and_failed_residuals_not_automatically_safe(self):
        self.group(); self.stage('a'); self.stage('b')
        self.wait('a', 'files')
        new = deepcopy(self.data); new['tasks'][0].update(state='failed', result={'state':'failed'})
        self.save(new)
        self.close_stage('b'); self.wait('b', 'finalization')
        with self.assertRaisesRegex(ValueError, 'safe residual'):
            schedule.append_event(self.data, 'close', self.now(), candidate=fixed())
        self.event('close', candidate=fixed(), residuals={'a':'independent residual check: source remains valid'})

    def test_abort_failed_waiter_allows_partner_verification_and_keeps_history(self):
        self.group(); self.stage('a'); self.stage('b')
        self.wait('a', 'files')
        new = deepcopy(self.data); new['tasks'][0].update(state='failed', result={'state':'failed','reason':'synthetic role failure'})
        self.save(new)
        original = deepcopy(self.task('a'))
        self.wait('b', 'verification')
        seq = schedule.next_request(schedule.replay(self.data))
        unsafe = schedule.append_event(self.data,'grant',self.now(),seq=seq,before={},before_ref='before')
        unsafe['tasks'][0] = deepcopy(original)
        self.reject(unsafe,'terminal member cannot receive')
        self.event('abort', slug='a', call_id=1, stop=self.proof('a'), state='failed',
                   reason='role stopped', source='synthetic host confirms stopped, original failure retained')
        self.assertEqual(self.task('a'), original)
        self.event('barrier', candidate=fixed()); self.grant()
        self.event('finish', seq=2, stop=self.proof('b'), outcome='passed', source='command log')
        self.event('window_end'); self.grant(); self.close_stage('b'); self.wait('b','finalization')
        self.event('close', candidate=fixed(), residuals={'a':'independent safe residual audit'})
        self.assertFalse(self.task('a')['calls'][0]['closed'])
        self.assertEqual(self.task('a')['budget']['calls'],1)

    def test_abort_without_request_retains_uncertain_command_and_releases_files(self):
        self.group(); self.stage('a'); self.stage('b')
        self.event('abort',slug='a',call_id=1,stop=self.proof('a'),state='failed',
                   reason='actual role interruption',source='synthetic host stop evidence')
        view=schedule.replay(self.data)
        self.assertNotIn('a',view['leases'])
        self.assertFalse(self.task('a')['calls'][0]['closed'])
        self.wait('b','verification'); self.event('barrier',candidate=fixed())

    def test_closed_call_cannot_request_new_verification(self):
        self.group();self.stage('a');self.close_stage('a')
        fields=self.wait_payload('a','verification')
        new=schedule.append_event(self.data,'wait',self.now(),**fields)
        self.reject(new,'original.*pending')

    def test_stop_queue_policy_blocks_next_stage_of_partner(self):
        # Frozen policy must be configured in the initial admitted definition.
        base=deepcopy(self.data);base['tasks'][0]['definition']['execution_policy']={'stop_queue_on_failure':True}
        self.path.unlink();self.data=base
        self.sha=guard.publish(self.path,raw_document(base),None,'first',1,'create')
        self.group();self.stage('a');self.stage('b');self.close_stage('b')
        self.event('abort',slug='a',call_id=1,stop=self.proof('a'),state='failed',reason='failed',source='stop audit')
        self.wait('b','files')
        blocked=schedule.append_event(self.data,'grant',self.now(),seq=schedule.next_request(schedule.replay(self.data)),before={},before_ref='before')
        self.reject(blocked,'stop_queue_on_failure')
        # Reacquisition cannot be used to resume an old call under the stop policy.

    def finish_policy_group(self, stop_queue=True):
        self.data['tasks'][0]['definition']['execution_policy'] = {'stop_queue_on_failure': stop_queue}
        self.path.unlink()
        self.sha = guard.publish(self.path, raw_document(self.data), None, 'first', 1, 'create')
        self.group(); self.stage('a'); self.stage('b'); self.close_stage('b', 'review')
        self.stage('b', 'review'); self.close_stage('b', 'validate')
        self.stage('b', 'validate'); self.close_stage('b', None, accepted=True)
        self.wait('b', 'finalization')
        self.event('abort', slug='a', call_id=1, stop=self.proof('a'), state='failed',
                   reason='synthetic failure', source='synthetic host stop audit')
        self.event('close', candidate=fixed(), residuals={'a': 'synthetic safe residual audit'})
        proposal = deepcopy(self.data)
        proposal['tasks'][1].update(state='completed', result={
            'state': 'completed', 'last_delivery': deepcopy(self.task('b')['checkpoint']['last_delivery'])})
        self.save(proposal)

    def prior_guard_later_group(self, prepared=False):
        self.finish_policy_group()
        # Existing records may contain a later group admitted by the old guard.
        # Keep them readable, but reject any new work after the recorded stop.
        self.data = schedule.append_event(self.data, 'group', self.now(), members=['c'],
                                         before={'c': {}}, before_refs={'c': 'synthetic prior guard before'})
        task = self.task('c')
        task['agents'] = [binding('worker', 'c-worker', 'worker-1')]
        if prepared:
            pending({'tasks': [task]})
            task['calls'][0]['prepared_at'] = self.now()
        guard.validate(self.data)
        raw = raw_document(self.data)
        self.path.write_bytes(raw)
        self.sha = guard.digest(raw)

    def test_stop_queue_policy_survives_group_close(self):
        self.finish_policy_group()
        proposal = schedule.append_event(self.data, 'group', self.now(), members=['c'],
                                         before={'c': {}}, before_refs={'c': 'synthetic next group before'})
        self.reject(proposal, 'stop_queue_on_failure')
        self.assertEqual(self.task('c')['state'], 'queued')
        self.assertEqual(self.task('c')['budget']['calls'], 0)
        # The policy stop still permits queue and Run finalization.
        proposal = deepcopy(self.data)
        proposal['tasks'][2].update(state='skipped', result={'state': 'skipped', 'last_delivery': None})
        proposal['status'] = 'stopped'
        self.save(proposal)
        self.assertFalse(guard.unfinished(self.data))

    def test_default_failure_still_allows_next_group(self):
        self.finish_policy_group(stop_queue=False)
        self.group(); self.stage('c')
        self.assertEqual(self.task('c')['calls'][0]['dispatch'], 'dispatched')

    def test_prior_group_policy_blocks_new_call_intent(self):
        self.prior_guard_later_group()
        proposal = deepcopy(self.data)
        pending({'tasks': [proposal['tasks'][2]]})
        self.reject(proposal, 'stop_queue_on_failure')

    def test_prior_group_policy_blocks_prepared_dispatch(self):
        self.prior_guard_later_group(prepared=True)
        proposal = deepcopy(self.data)
        call = proposal['tasks'][2]['calls'][0]
        call.update(dispatch='dispatched', dispatch_evidence={
            'agent_id': 'c-worker', 'source': 'synthetic new host dispatch', 'at': self.now()})
        self.reject(proposal, 'stop_queue_on_failure')
        call['dispatch_evidence']['historical'] = {
            'observed_at': self.now(), 'source': 'synthetic historical registration after stop'}
        self.reject(proposal, 'after scheduling stop boundary')

    def test_prior_group_policy_blocks_resource_grant(self):
        self.prior_guard_later_group(prepared=True)
        self.wait('c', 'files')
        view = schedule.replay(self.data)
        proposal = schedule.append_event(self.data, 'grant', self.now(), seq=schedule.next_request(view),
                                         before={}, before_ref='synthetic prior guard resume')
        self.reject(proposal, 'stop_queue_on_failure')

    def takeover(self):
        old=deepcopy(self.data['executor']);when=self.now()
        children=[]
        for task in self.data['tasks']:
            for b in task['agents']:
                children.append(dict(agent_id=b['agent_id'],host_id=b['host_id'],state='stopped',tools_stopped=True,
                                     observed_at=when,source='synthetic actual host child stop'))
        obs={**{k:old[k] for k in ['instance_id','generation','host_id','thread_id','turn_id']},
             'observed_at':when,'source_kind':'host','source':'synthetic exact parent turn stopped',
             'state':'stopped','tools_stopped':True,'children':children}
        new=deepcopy(self.data);new['executor'].update(instance_id='second',generation=2,claimed_at=when,
            progress={'at':when,'event':'takeover'})
        new['ownership_history'].append({'previous':old,'observation':obs})
        self.sha=guard.publish(self.path,raw_document(new),self.sha,'second',2,'takeover',obs)
        self.data=new

    def test_takeover_preserves_wait_order_and_requires_fresh_original_role_observation(self):
        self.group();self.stage('a');self.stage('b');self.wait('a','files');self.wait('b','files')
        before=deepcopy(self.data['tasks']);events=deepcopy(self.data['scheduler']['events'])
        old_stop=deepcopy(events[-2]['stop'])
        self.takeover()
        self.assertEqual(self.data['tasks'],before)
        self.assertEqual(self.data['scheduler']['events'],events)
        with self.assertRaisesRegex(ValueError,'confirmed stopped tools'):
            schedule.append_event(self.data,'grant',self.now(),seq=1,before={},before_ref='resume')
        with self.assertRaisesRegex(ValueError,'new stop observation'):
            schedule.append_event(self.data,'grant',self.now(),seq=1,before={},before_ref='resume',stop=old_stop)
        proof=self.proof('a')
        new=schedule.append_event(self.data,'grant',self.now(),seq=1,before={},before_ref='resume',stop=proof)
        self.sha=guard.publish(self.path,raw_document(new),self.sha,'second',2)
        self.data=new
        self.assertEqual(self.task('a')['budget']['calls'],1)
        self.assertEqual(self.task('a')['calls'][0]['agent_ref'],'worker-1')

    def test_takeover_of_granted_command_records_original_outcome_without_regrant(self):
        self.group();self.stage('a');self.stage('b');self.wait('a','verification');self.wait('b','verification')
        self.event('barrier',candidate=fixed());self.grant()
        historical_stop=self.proof('a')
        self.takeover()
        self.assertIsNone(schedule.next_request(schedule.replay(self.data)))
        stop=historical_stop
        new=schedule.append_event(self.data,'finish',self.now(),seq=1,stop=stop,outcome='passed',source='original command log checked')
        guard.publish(self.path,raw_document(new),self.sha,'second',2)
        self.assertEqual(new['tasks'][0]['budget']['calls'],1)
        self.assertEqual(len([e for e in new['scheduler']['events'] if e['kind']=='grant']),1)

    def test_independent_reviewers_can_run_together_and_mix_with_worker(self):
        self.group();self.stage('a');self.stage('b');self.close_stage('a')
        self.stage('a','review')
        self.assertEqual([self.task(s)['calls'][-1]['stage'] for s in ['a','b']],['review','code'])
        self.close_stage('b');self.stage('b','review')
        self.assertEqual([self.task(s)['calls'][-1]['stage'] for s in ['a','b']],['review','review'])
        self.assertNotEqual(self.task('a')['agents'][-1]['agent_id'],self.task('b')['agents'][-1]['agent_id'])

    def test_candidate_refresh_cannot_add_stage_outside_explicit_flow(self):
        self.data['tasks'][0]['definition']['flow']=['review']
        self.data['tasks'][0]['start_action']['stage']='review'
        self.path.unlink()
        self.sha=guard.publish(self.path,raw_document(self.data),None,'first',1,'create')
        self.group();self.stage('a','review');self.close_stage('a',None)
        self.wait('a','finalization',cand=fixed({'a.swift':'a'*64}))
        with self.assertRaisesRegex(ValueError,'outside allowed flow'):
            schedule.append_event(self.data,'invalidate',self.now(),slug='a',stage='validate',
                candidate=fixed({'a.swift':'b'*64}),paths=['a.swift'],source='changed input')

    def test_refresh_is_consumed_once_and_no_closed_call_is_rewritten(self):
        self.group();self.stage('a');self.close_stage('a',None)
        before=deepcopy(self.task('a')['calls'][0])
        self.wait('a','finalization',cand=fixed({'a.swift':'a'*64}))
        self.event('invalidate',slug='a',stage='review',candidate=fixed({'a.swift':'b'*64}),
                   paths=['a.swift'],source='changed input')
        refresh=deepcopy(self.data['scheduler']['events'][-1]);self.grant()
        self.stage('a','review',refresh);self.close_stage('a','validate')
        with self.assertRaisesRegex(ValueError,'consumed candidate refresh'):
            self.stage('a','review',refresh)
        actual,_=guard.current(self.path.read_bytes())
        self.assertEqual(actual['tasks'][0]['calls'][0],before)
        self.assertEqual(actual['tasks'][0]['budget']['calls'],2)

    def test_stopped_run_cannot_grant_resources(self):
        self.group();self.stage('a');self.wait('a','files')
        stopped=deepcopy(self.data);stopped['status']='stopped';self.save(stopped)
        blocked=schedule.append_event(self.data,'grant',self.now(),seq=1,before={},before_ref='before')
        self.reject(blocked,'resource grant requires running Run')

    def test_bool_call_or_event_ids_are_not_integer_provenance(self):
        self.group();self.stage('a')
        fields=self.wait_payload('a','files');fields['call_id']=True
        with self.assertRaisesRegex(ValueError,'invalid wait call id'):
            schedule.append_event(self.data,'wait',self.now(),**fields)
        altered=deepcopy(self.data);altered['scheduler']['events'][0]['id']=True
        self.reject(altered,'event ids')

    def test_unavailable_reviewer_does_not_prevent_safe_verification_window(self):
        self.group();self.stage('a');self.stage('b');self.close_stage('b')
        fields=self.wait_payload('b','agent');fields['stage']='review'
        self.event('wait',**fields);self.wait('a','verification')
        self.assertIsNone(schedule.next_request(schedule.replay(self.data)))
        self.event('barrier',candidate=fixed());self.grant()
        self.event('finish',seq=2,stop=self.proof('a'),outcome='passed',source='original command result')
        self.event('window_end')
        # B's older role request is skipped until its actual reviewer exists.
        self.assertEqual(schedule.next_request(schedule.replay(self.data)),3)
        self.task('b')['agents'].append(binding('reviewer','b-reviewer','reviewer-1'));self.save()
        self.event('agent_ready',seq=1,agent_ref='reviewer-1',source='actual synthetic host role available')
        self.assertEqual(schedule.next_request(schedule.replay(self.data)),1)
        self.grant();self.stage('b','review')
        self.assertEqual(self.task('b')['budget']['calls'],2)

    def test_candidate_refresh_cannot_omit_explicit_invalidation_evidence(self):
        self.group();self.stage('a');self.close_stage('a',None)
        self.wait('a','finalization',cand=fixed({'a.swift':'a'*64}))
        self.event('invalidate',slug='a',stage='review',candidate=fixed({'a.swift':'b'*64}),
                   paths=['a.swift'],source='actual changed input')
        self.grant()
        with self.assertRaisesRegex(ValueError,'preserve invalidation evidence'):
            self.stage('a','review')
        actual,_=guard.current(self.path.read_bytes())
        self.assertEqual(actual['tasks'][0]['budget']['calls'],1)

    def test_consumed_resource_request_cannot_be_replayed_or_aliased(self):
        self.group();self.stage('a');self.stage('b');self.close_stage('b');self.wait('b','finalization')
        original=self.wait_payload('a','verification');self.event('wait',**original)
        self.event('barrier',candidate=fixed());self.grant()
        self.event('finish',seq=2,stop=self.proof('a'),outcome='passed',source='actual synthetic result')
        self.event('window_end');self.grant()
        for alias in [original['request']['path'],original['request']['path'].replace('/resources/','/resources/./'),
                      original['request']['path'].replace('/resources/','/resources//'),
                      original['request']['path'].replace('.json','.JSON')]:
            fields=deepcopy(original);fields['request']['path']=alias;fields['stop']=self.proof('a')
            with self.subTest(alias=alias),self.assertRaisesRegex(ValueError,'already consumed|canonical request path'):
                self.event('wait',**fields)
        self.assertEqual(self.task('a')['budget']['calls'],1)

    def test_finish_continuation_cannot_launder_old_stop_into_current_generation(self):
        self.group();self.stage('a');self.stage('b');self.wait('a','verification');self.wait('b','verification')
        self.event('barrier',candidate=fixed());self.grant();historical=self.proof('a');self.takeover()
        self.event('finish',seq=1,stop=historical,outcome='passed',source='original pre-takeover command log')
        self.grant(stop=self.proof('b'))
        self.event('finish',seq=2,stop=self.proof('b'),outcome='passed',source='known second command result')
        self.event('window_end')
        with self.assertRaisesRegex(ValueError,'confirmed stopped tools|new stop observation'):
            self.grant()
        self.grant(stop=self.proof('a'))
        self.assertEqual(self.task('a')['budget']['calls'],1)

    def test_new_generation_wait_cannot_make_historical_stop_fresh(self):
        self.group();self.stage('a');historical=self.proof('a');self.takeover()
        fields=self.wait_payload('a','files');fields['stop']=historical;self.event('wait',**fields)
        with self.assertRaisesRegex(ValueError,'confirmed stopped tools|new stop observation'):
            self.grant()
        self.grant(stop=self.proof('a'))

    def test_prepared_dispatch_rechecks_failure_policy_and_accepts_historical_registration(self):
        self.data['tasks'][0]['definition']['execution_policy']={'stop_queue_on_failure':True}
        self.path.unlink();self.sha=guard.publish(self.path,raw_document(self.data),None,'first',1,'create')
        self.group();self.stage('a');self.stage('b',dispatch=False)
        self.event('abort',slug='a',call_id=1,stop=self.proof('a'),state='failed',reason='known failure',source='actual synthetic stop')
        proposal=deepcopy(self.data);call=proposal['tasks'][1]['calls'][-1]
        call.update(dispatch='dispatched',dispatch_evidence={'agent_id':'b-worker','at':self.now(),'source':'new host dispatch'})
        self.reject(proposal,'stop_queue_on_failure')
        call['dispatch_evidence'].update(at=call['prepared_at'],historical={
            'observed_at':self.now(),'source':'host original dispatch log checked; no new launch'})
        self.save(proposal)
        self.assertEqual(self.task('b')['budget']['calls'],1)

    def test_prepared_dispatch_rechecks_stopped_run(self):
        self.group();self.stage('a',dispatch=False)
        stopped=deepcopy(self.data);stopped['status']='stopped'
        stopped['executor']['progress']={'at':self.now(),'event':'explicit user stop'};self.save(stopped)
        proposal=deepcopy(self.data);call=proposal['tasks'][0]['calls'][-1]
        call.update(dispatch='dispatched',dispatch_evidence={'agent_id':'a-worker','at':self.now(),'source':'new host dispatch'})
        self.reject(proposal,'dispatch requires running Run')

    def test_resource_wait_cannot_be_mistaken_for_stage_delivery(self):
        self.group();self.stage('a');self.wait('a','verification')
        before=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'unfinished resource|resource wait'):
            self.close_stage('a')
        self.assertEqual(self.path.read_bytes(),before)
        actual,_=guard.current(before)
        self.assertFalse(actual['tasks'][0]['calls'][0]['closed'])
        self.assertEqual(actual['tasks'][0]['checkpoint']['pending_call'],1)

    def test_actual_stage_delivery_after_recorded_finish_is_allowed_without_writes(self):
        self.group();self.stage('a');self.stage('b');self.wait('a','verification');self.wait('b','verification')
        self.event('barrier',candidate=fixed());self.grant()
        self.event('finish',seq=1,stop=self.proof('a'),outcome='passed',source='actual synthetic command result')
        self.close_stage('a')
        self.assertTrue(self.task('a')['calls'][0]['closed'])
        self.assertEqual(self.task('a')['budget']['calls'],1)

    def test_pending_file_expansion_cannot_close_stage_or_replace_delivery(self):
        self.group();self.stage('a');self.wait('a','files',footprint('a.swift','extra.swift'))
        proposal=deepcopy(self.data);proposal['tasks'][0]['checkpoint']['last_delivery']={'fake':'stage result'}
        self.reject(proposal,'resource wait cannot replace last delivery')
        with self.assertRaisesRegex(ValueError,'unfinished resource wait'):
            self.close_stage('a')
        actual,_=guard.current(self.path.read_bytes())
        self.assertFalse(actual['tasks'][0]['calls'][0]['closed'])

    def test_active_verification_cannot_close_its_phase(self):
        self.group();self.stage('a');self.stage('b');self.wait('a','verification');self.wait('b','verification')
        self.event('barrier',candidate=fixed());self.grant()
        with self.assertRaisesRegex(ValueError,'unfinished resource wait'):
            self.close_stage('a')

    def test_late_dispatch_record_before_release_is_allowed_but_no_new_launch(self):
        self.group();self.stage('a',dispatch=False)
        self.wait('a','files')
        proposal=deepcopy(self.data);call=proposal['tasks'][0]['calls'][-1]
        call.update(dispatch='dispatched',dispatch_evidence={'agent_id':'a-worker','at':self.now(),'source':'new launch'})
        self.reject(proposal,'complete file lease|observation predates call')
        call['dispatch_evidence'].update(at=call['prepared_at'],historical={
            'observed_at':self.now(),'source':'host confirms original dispatch before observed pause'})
        self.save(proposal)
        self.assertEqual(self.task('a')['state'],'waiting')
        self.assertEqual(self.task('a')['budget']['calls'],1)

    def test_historical_marker_cannot_authorize_dispatch_after_stop(self):
        self.data['tasks'][0]['definition']['execution_policy']={'stop_queue_on_failure':True}
        self.path.unlink();self.sha=guard.publish(self.path,raw_document(self.data),None,'first',1,'create')
        self.group();self.stage('a');self.stage('b',dispatch=False)
        self.event('abort',slug='a',call_id=1,stop=self.proof('a'),state='failed',reason='failure',source='host stop')
        proposal=deepcopy(self.data);call=proposal['tasks'][1]['calls'][-1]
        call.update(dispatch='dispatched',dispatch_evidence={'agent_id':'b-worker','at':self.now(),'source':'late launch',
                    'historical':{'observed_at':self.now(),'source':'claims historical registration'}})
        self.reject(proposal,'after scheduling stop boundary')

    def test_directory_scope_rejects_descendant_links_and_wrong_path_kind(self):
        (self.root/'Views').mkdir();(self.root/'Views/other').symlink_to(self.root)
        with self.assertRaisesRegex(ValueError,'symlink'):
            schedule.validate_paths(self.root,footprint(dirs=['Views']))
        (self.root/'Views/other').unlink()
        import os
        os.link(self.root/'a.swift',self.root/'Views/alias.swift')
        with self.assertRaisesRegex(ValueError,'hardlink'):
            schedule.validate_paths(self.root,footprint(dirs=['Views']))
        (self.root/'Views/alias.swift').unlink()
        with self.assertRaisesRegex(ValueError,'directory scope'):
            schedule.validate_paths(self.root,footprint('Views'))
        with self.assertRaisesRegex(ValueError,'directory scope'):
            schedule.validate_paths(self.root,footprint(dirs=['a.swift']))

    def test_future_file_ancestor_conflicts_with_nested_file_or_directory(self):
        self.assertTrue(schedule.overlap(footprint('Future'),footprint('Future/Child.swift')))
        self.assertTrue(schedule.overlap(footprint('Future'),footprint(dirs=['Future/Nested'])))
        self.assertFalse(schedule.overlap(footprint('FutureA'),footprint('FutureB/Child.swift')))

    def test_request_identity_does_not_accept_boolean_or_float_as_integer(self):
        self.group();self.stage('a')
        fields=self.wait_payload('a','files')
        for key,value in [('generation',True),('call_id',1.0)]:
            altered=deepcopy(fields);body=altered['request']['body'];body[key]=value
            content=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            altered['request']['sha256']=hashlib.sha256(content).hexdigest()
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'identity requires integers'):
                schedule.append_event(self.data,'wait',self.now(),**altered)

    def test_resource_request_file_cannot_be_a_hardlink_alias(self):
        self.group();self.stage('a');fields=self.wait_payload('a','files')
        import os
        os.link(self.root/fields['request']['path'],self.root/'request-alias.json')
        proposed=schedule.append_event(self.data,'wait',self.now(),**fields)
        self.reject(proposed,'linked resource request')

    def test_old_protocol_rejected_and_missing_scheduler_not_a_serial_fallback(self):
        new = deepcopy(self.data); new['protocol'] = '0.10'
        self.reject(new, 'unsupported Cadra')
        new = deepcopy(self.data); del new['scheduler']
        self.reject(new, 'journal required')
        new = deepcopy(self.data); new['tasks'][0]['definition']['ready_scope']['revision'] = 2
        self.reject(new, 'scope revision mismatch')

    def test_path_overlap_directory_aliases_and_exclusive(self):
        self.assertTrue(schedule.overlap(footprint('Views/A.swift'), footprint(dirs=['views'])))
        self.assertFalse(schedule.overlap(footprint('Views2/A.swift'), footprint(dirs=['views'])))
        self.assertTrue(schedule.overlap(footprint('x'), footprint(exclusive=True)))
        self.assertTrue(schedule.overlap(footprint('caf\u00e9.swift'), footprint('cafe\u0301.swift')))
        for p in ['../escape','/absolute','x/../a','x//y','x/./y','.git/config','.yuzio/cadra/x']:
            with self.subTest(path=p), self.assertRaises(ValueError): schedule.scope(footprint(p))
        with self.assertRaisesRegex(ValueError, 'aliases'):schedule.scope(footprint('A.swift','a.swift'))

    def test_filesystem_aliases_symlinks_and_future_paths(self):
        (self.root/'alias.swift').symlink_to(self.root/'a.swift')
        with self.assertRaisesRegex(ValueError, 'symlink'):schedule.validate_paths(self.root,footprint('alias.swift'))
        (self.root/'outside').symlink_to(self.root.parent)
        with self.assertRaises(ValueError):schedule.validate_paths(self.root,footprint('outside/future.swift'))
        schedule.validate_paths(self.root,footprint('future/new.swift'))
        import os
        os.link(self.root/'a.swift',self.root/'hard.swift')
        with self.assertRaisesRegex(ValueError,'hardlink'):schedule.validate_paths(self.root,footprint('hard.swift'))

    def test_inspect_reports_wait_without_mutating_record(self):
        self.group(); self.stage('a'); self.wait('a','verification')
        before=self.path.read_bytes()
        proc=subprocess.run([sys.executable,'-B',str(Path(guard.__file__)),'inspect','--run',str(self.path)],
                            capture_output=True,text=True,check=True)
        result=json.loads(proc.stdout)
        self.assertEqual(result['scheduling']['waiting'][0]['kind'],'verification')
        self.assertEqual(self.path.read_bytes(),before)

    def test_two_wait_publications_cannot_erase_each_other(self):
        self.group();self.stage('a');self.stage('b')
        proposals=[]
        for slug in ['a','b']:
            fields=self.wait_payload(slug,'verification')
            data=schedule.append_event(self.data,'wait',self.now(),**fields)
            p=self.root/(slug+'.md');p.write_bytes(raw_document(data));proposals.append(p)
        ps=[subprocess.Popen([sys.executable,'-B',str(Path(guard.__file__)),'update','--run',str(self.path),
            '--proposal',str(p),'--expected-sha256',self.sha,'--instance','first','--generation','1'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE) for p in proposals]
        for p in ps:p.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in ps),[0,1])
        actual,_=guard.current(self.path.read_bytes())
        self.assertEqual(len(schedule.summary(actual)['waiting']),1)


if __name__ == '__main__':unittest.main()
