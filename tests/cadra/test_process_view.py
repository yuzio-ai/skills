"""Exercise shipped process extraction; fixtures are not real agent execution."""
from copy import deepcopy
from datetime import timedelta, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from .test_run_guard import example, binding, pending, document, raw_document, AT, LATER
from . import test_scheduler as scheduler_fixtures
from .test_cadra import contract

SCRIPT = Path(__file__).resolve().parents[2] / 'cadra/scripts/process_view.py'
spec = importlib.util.spec_from_file_location('cadra_process_view', SCRIPT)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def history():
    """Seven recorded stages with two remediations and blocked native evidence."""
    data = example()
    task = data['tasks'][0]
    task['agents'] = [binding(), binding('reviewer', 'agent-reviewer', 'reviewer-1')]
    stages = ['code', 'review', 'fix', 'review', 'fix', 'review', 'validate']
    rounds = {}
    previous = None
    for number, stage in enumerate(stages, 1):
        rounds[stage] = rounds.get(stage, 0) + 1
        next_stage = stages[number] if number < len(stages) else None
        state = contract(stage, next_stage, 'blocking_findings' if next_stage == 'fix' else 'stage_completed', rounds[stage])
        state['task'] = task['slug']
        if stage in ('review', 'fix'):
            state['findings'] = dict(blocking=int(next_stage == 'fix'), non_blocking=0, unresolved=0)
        if stage == 'validate':
            state.update(status='blocked', acceptance={'status': 'blocked'},
                         blocked={'value': True, 'reason': 'missing_permission'})
            state['stage_result']['status'] = 'blocked'
            state['next'] = dict(stage=None, allowed=False, reason='blocked')
        role = 'reviewer' if stage == 'review' else 'worker'
        charge = dict(calls=1, remediation=int(stage == 'fix'), retry_stage=None)
        task['calls'].append(dict(id=number, stage=stage, before=deepcopy(previous),
            reason='synthetic stage', execution_mode='unattended', agent_ref=role+'-1',
            prepared_at=AT, dispatch='dispatched',
            dispatch_evidence=dict(agent_id='agent-'+role, source='synthetic host dispatch', at=AT),
            closed=True, result=dict(contract=state, handoff=f'{stage}-{rounds[stage]:02}.md', index_sync=True),
            charged=charge))
        previous = state
    task.update(state='blocked', result=dict(state='blocked', acceptance={'status': 'blocked'}, at=LATER))
    task['checkpoint'].update(pending_call=None, last_delivery=task['calls'][-1]['result'])
    task['budget'].update(calls=7, remediation=2)
    data['status'] = 'stopped'
    return reader.guard.header(document(data))


def receipt(event, at):
    return dict(event_id=event['id'], at=at, source='guard readback')


class ProcessViewTests(unittest.TestCase):
    def test_remediation_rounds_and_historical_result_are_preserved(self):
        data = history()
        before = deepcopy(data)
        view = reader.process_view(data)
        calls = view['tasks'][0]['calls']
        self.assertEqual([c['stage_result']['round'] for c in calls], [1, 1, 1, 2, 2, 3, 1])
        self.assertEqual([calls[n]['findings']['blocking'] for n in (1, 2, 3, 4, 5)], [1, 0, 1, 0, 0])
        self.assertEqual(calls[-1]['blocked']['reason'], 'missing_permission')
        self.assertEqual(view['tasks'][0]['result']['acceptance']['status'], 'blocked')
        self.assertTrue(all(c['delivered_at'] is None for c in calls))
        self.assertEqual(data, before)

    def test_pending_dispatch_and_partial_result_never_become_completion(self):
        for dispatch in (False, True):
            data = example(); pending(data)
            task = data['tasks'][0]; task['agents'] = [binding()]
            call = task['calls'][0]
            call['result'] = {'contract': contract('code', 'review')}
            if dispatch:
                call.update(dispatch='dispatched', dispatch_evidence=dict(agent_id='agent-worker', source='host', at=AT))
            view = reader.process_view(data)['tasks'][0]['calls'][0]
            self.assertEqual(view['status'], 'pending')
            self.assertIsNone(view['stage_result'])
            self.assertIsNone(view['handoff'])

    def test_missing_sync_and_explicit_sync_failure_are_distinct(self):
        data = history(); call = data['tasks'][0]['calls'][-1]
        call['result'] = call['result']['contract']
        direct = reader.process_view(data)['tasks'][0]['calls'][-1]
        self.assertEqual(direct['status'], 'recorded')
        self.assertIsNone(direct['index_sync'])
        call['result'] = dict(contract=call['result'], index_sync=False)
        failed = reader.process_view(data)['tasks'][0]['calls'][-1]
        self.assertEqual(failed['status'], 'unknown')
        self.assertTrue(failed['gaps'])

    def test_unknown_details_and_no_call_result_are_not_fabricated(self):
        data = example()
        row = reader.process_view(data)['tasks'][0]
        self.assertEqual(row['calls'], [])
        self.assertIsNone(row['result'])
        data = history(); data['tasks'][0]['calls'][0]['result'] = {'unknown_delivery': True}
        row = reader.process_view(data)['tasks'][0]['calls'][0]
        self.assertEqual(row['status'], 'unknown')
        self.assertIsNone(row['findings'])

    def test_scheduler_fail_then_pass_remains_ordered_and_linked_to_call(self):
        harness = scheduler_fixtures.SchedulerTests()
        harness.setUp(); self.addCleanup(harness.doCleanups)
        harness.group(); harness.stage('a'); harness.stage('b')
        harness.wait('a', 'verification'); harness.wait('b', 'verification')
        harness.event('barrier', candidate=scheduler_fixtures.fixed())
        readbacks = []
        for slug, outcome in [('a', 'failed'), ('b', 'passed')]:
            view = reader.guard.scheduler.replay(harness.data)
            seq = reader.guard.scheduler.next_request(view)
            harness.grant(verification_readbacks=readbacks)
            if outcome == 'failed':
                grant = harness.data['scheduler']['events'][-1]
                grant_readback = receipt(grant, harness.now())
                harness.clock += timedelta(seconds=10)
                started = harness.now()
                harness.clock += timedelta(seconds=3)
                ended = harness.now()
                harness.clock += timedelta(seconds=11)
                timing = dict(command_started=dict(at=started, source='host process start'),
                              command_exited=dict(at=ended, source='host process exit'),
                              delay_reasons={'grant_to_start': 'approval', 'end_to_finish': 'tool wait'})
                harness.event('finish', seq=seq, outcome=outcome, timing=timing, verification_readbacks=[grant_readback],
                              source='host compile failed, exit 1, zero tests', stop=harness.proof(slug))
                finish_event = harness.data['scheduler']['events'][-1]
                harness.clock += timedelta(seconds=11)
                readbacks = [receipt(finish_event, harness.now())]
            else:
                harness.event('finish', seq=seq, outcome=outcome, source='synthetic command outcome',
                              stop=harness.proof(slug))
        harness.event('window_end')
        harness.grant()
        file_grant = harness.data['scheduler']['events'][-1]
        file_readback = receipt(file_grant, harness.now())
        harness.grant()
        resumed_at = harness.now()
        changed = harness.root / 'a.swift'
        changed.write_text('// fixed compilation\n')
        new_candidate = dict(snapshot='scratch/fixed-retry/manifest.json', sha256='b' * 64,
                             inputs={'a.swift': reader.guard.digest(changed.read_bytes())})
        harness.event('wait', **harness.wait_payload('a', 'verification', cand=new_candidate),
                      verification_readbacks=[file_readback],
                      verification_resume=dict(seq=1, at=resumed_at, source='original worker continuation'))
        harness.event('wait', **harness.wait_payload('b', 'verification', cand=new_candidate),
                      verification_resume=dict(seq=1, at=harness.now(), source='unrelated worker'))
        harness.event('barrier', candidate=new_candidate)
        for slug in ('a', 'b'):
            seq = reader.guard.scheduler.next_request(reader.guard.scheduler.replay(harness.data))
            harness.grant()
            harness.event('finish', seq=seq, outcome='passed', source='synthetic later command', stop=harness.proof(slug))
        view = reader.process_view(harness.data)
        finished = [e for e in view['events'] if e['kind'] == 'finish']
        self.assertEqual([e['outcome'] for e in finished if e['tasks'] == ['a']], ['failed', 'passed'])
        self.assertEqual([e['tasks'] for e in finished], [['a'], ['b'], ['a'], ['b']])
        self.assertTrue(all(e['call_id'] == 1 for e in finished))
        self.assertEqual([t['slug'] for t in view['tasks']], ['a', 'b', 'c'])
        self.assertEqual(finished[0]['source'], 'host compile failed, exit 1, zero tests')
        failure = finished[0]['timing']
        self.assertEqual(failure['seconds'], dict(grant_to_start=11, command=4, end_to_finish=25,
                                                 finish_to_resume=8, finish_to_files_grant=6, grant_to_finish=40))
        self.assertEqual(failure['event_seconds'], dict(grant_to_finish=29, finish_to_files_grant=17))
        self.assertEqual(failure['resumed'], dict(at=resumed_at, source='original worker continuation'))
        self.assertEqual(failure['delay_reasons'], timing['delay_reasons'])
        legacy = finished[1]['timing']['seconds']
        self.assertTrue(all(legacy[key] is None for key in
                            ('grant_to_start', 'command', 'end_to_finish', 'finish_to_resume')))
        self.assertIsNone(legacy['finish_to_files_grant'])
        self.assertIsNotNone(finished[1]['timing']['event_seconds']['finish_to_files_grant'])
        self.assertEqual([e['candidate']['sha256'] for e in view['events']
                          if e['kind'] == 'grant' and e['resource'] == 'verification'],
                         ['a' * 64, 'a' * 64, 'b' * 64, 'b' * 64])

        bad = deepcopy(harness.data)
        wait = next(e for e in bad['scheduler']['events'] if e.get('verification_resume', {}).get('at') == resumed_at)
        for early in (finish_event['at'], file_grant['at']):
            with self.subTest(resumed_before_readback=early):
                wait['verification_resume']['at'] = early
                first = next(e for e in reader.process_view(bad)['events'] if e['kind'] == 'finish')
                self.assertIsNone(first['timing']['resumed'])
                self.assertIsNone(first['timing']['seconds']['finish_to_resume'])
        stopped_at = wait['stop']['observed_at']
        for observed_at, expected in ((stopped_at, stopped_at), (wait['at'], None)):
            with self.subTest(resumed_at=observed_at):
                wait['verification_resume']['at'] = observed_at
                first = next(e for e in reader.process_view(bad)['events'] if e['kind'] == 'finish')
                resumed = first['timing']['resumed']
                self.assertEqual(resumed['at'] if resumed else None, expected)
        wait['verification_resume']['at'] = resumed_at
        del wait['verification_readbacks']
        first = next(e for e in reader.process_view(bad)['events'] if e['kind'] == 'finish')
        self.assertIsNone(first['timing']['seconds']['finish_to_resume'])

    def test_finish_to_resume_can_come_from_process_only_delivery(self):
        harness = scheduler_fixtures.SchedulerTests()
        harness.setUp(); self.addCleanup(harness.doCleanups)
        harness.group(); harness.stage('a'); harness.stage('b')
        harness.wait('a', 'verification'); harness.wait('b', 'verification')
        harness.event('barrier', candidate=scheduler_fixtures.fixed())
        harness.grant()
        grant = harness.data['scheduler']['events'][-1]
        grant_readback = receipt(grant, harness.now())
        ended = harness.now()
        harness.event('finish', seq=1, outcome='passed', source='runner exit', stop=harness.proof('a'),
                      timing=dict(command_started=dict(at=ended, source=''),
                                  command_exited=dict(at=ended, source='host process exit')),
                      verification_readbacks=[grant_readback])
        finish_readback = receipt(harness.data['scheduler']['events'][-1], harness.now())
        resumed_at = harness.now()
        harness.close_stage('a', verification_resume=dict(seq=1, at=resumed_at, source='process-only handoff turn'),
                            verification_readbacks=[finish_readback], verified_at=harness.now())

        finish = next(e for e in reader.read_view(harness.path)['events'] if e['kind'] == 'finish')
        self.assertEqual(finish['timing']['seconds'], dict(grant_to_start=None, command=None, end_to_finish=3,
                                                          finish_to_resume=1, finish_to_files_grant=None, grant_to_finish=4))
        self.assertEqual(finish['timing']['resumed']['at'], resumed_at)

        # Observation problems affect the projection only.
        bad = deepcopy(harness.data)
        event = bad['scheduler']['events'][-1]
        event['timing']['command_started'] = dict(at=event['at'], source='contradictory process start')
        bad['tasks'][0]['calls'][0]['result']['verification_resume']['at'] = ended
        finish = next(e for e in reader.process_view(bad)['events'] if e['kind'] == 'finish')
        self.assertEqual(finish['outcome'], 'passed')
        self.assertTrue(all(finish['timing']['seconds'][key] is None for key in
                            ('grant_to_start', 'command', 'end_to_finish', 'finish_to_resume')))

        # Earlier records did not identify whether timestamps were process or runner phase boundaries.
        event['timing'] = dict(started=dict(at=ended, source='runner timestamp'),
                               ended=dict(at=event['at'], source='runner timestamp'))
        finish = next(e for e in reader.process_view(bad)['events'] if e['kind'] == 'finish')
        self.assertIsNone(finish['timing']['seconds']['command'])
        self.assertIsNone(finish['timing']['seconds']['end_to_finish'])

        # The peer drains its verification window, then A obtains files for a new stage.
        harness.grant()
        harness.event('finish', seq=2, outcome='passed', source='peer exit', stop=harness.proof('b'))
        harness.event('window_end')
        harness.grant()
        next_stage_grant = receipt(harness.data['scheduler']['events'][-1], harness.now())
        harness.grant(verification_readbacks=[next_stage_grant])
        harness.stage('a', 'review')

        after = next(e for e in reader.read_view(harness.path)['events'] if e['kind'] == 'finish')
        self.assertEqual(after['timing']['seconds']['finish_to_resume'], 1)
        self.assertEqual(after['timing']['resumed']['at'], resumed_at)

        # A verified process-only observation also works without a delivery timestamp.
        marked = deepcopy(harness.data)
        result = marked['tasks'][0]['calls'][0]['result']
        del result['verified_at']
        result['verification_resume']['process_only'] = True
        after = next(e for e in reader.process_view(marked)['events'] if e['kind'] == 'finish')
        self.assertEqual(after['timing']['seconds']['finish_to_resume'], 1)

    def test_process_only_resume_can_overlap_file_grant_publication(self):
        harness = scheduler_fixtures.SchedulerTests()
        harness.setUp(); self.addCleanup(harness.doCleanups)
        harness.group(); harness.stage('a'); harness.stage('b')
        harness.wait('a', 'verification'); harness.wait('b', 'verification')
        harness.event('barrier', candidate=scheduler_fixtures.fixed())
        harness.grant()
        harness.event('finish', seq=1, outcome='passed', source='A exit', stop=harness.proof('a'))
        finish = harness.data['scheduler']['events'][-1]
        finish_readback = receipt(finish, harness.now())
        harness.grant(verification_readbacks=[finish_readback])
        harness.event('finish', seq=2, outcome='passed', source='B exit', stop=harness.proof('b'))
        harness.event('window_end')

        scheduler = reader.guard.scheduler
        view = scheduler.replay(harness.data)
        proposal = scheduler.append_event(harness.data, 'grant', harness.now(),
                                          seq=scheduler.next_request(view), before={},
                                          before_ref='before', candidate=view['group']['candidate'])
        resumed_at = harness.now()
        file_readback = receipt(proposal['scheduler']['events'][-1], harness.now())
        harness.save(proposal)
        harness.close_stage('a', verification_readbacks=[file_readback], verified_at=harness.now(),
                            verification_resume=dict(seq=1, at=resumed_at, source='process-only handoff',
                                                     process_only=True))

        row = next(e for e in reader.read_view(harness.path)['events'] if e['kind'] == 'finish')
        self.assertEqual(row['timing']['seconds']['finish_to_resume'], 6)
        self.assertEqual(row['timing']['seconds']['finish_to_files_grant'], 7)

        for changed in (dict(process_only=False), dict(at=finish['at'])):
            with self.subTest(changed=changed):
                data = deepcopy(harness.data)
                data['tasks'][0]['calls'][0]['result']['verification_resume'].update(changed)
                row = next(e for e in reader.process_view(data)['events'] if e['kind'] == 'finish')
                self.assertIsNone(row['timing']['seconds']['finish_to_resume'])

    def test_readback_on_another_call_can_postdate_its_handoff_verification(self):
        harness = scheduler_fixtures.SchedulerTests()
        harness.setUp(); self.addCleanup(harness.doCleanups)
        harness.group(); harness.stage('a'); harness.stage('b')
        harness.wait('a', 'verification'); harness.wait('b', 'verification')
        harness.event('barrier', candidate=scheduler_fixtures.fixed())
        harness.grant()
        harness.event('finish', seq=1, outcome='passed', source='A exit', stop=harness.proof('a'))
        a_verified_at = harness.now()
        harness.grant()
        exited = harness.now()
        harness.event('finish', seq=2, outcome='passed', source='B exit', stop=harness.proof('b'),
                      timing=dict(command_exited=dict(at=exited, source='B outer process')))
        b_finish = harness.data['scheduler']['events'][-1]
        b_readback = receipt(b_finish, harness.now())
        harness.close_stage('a', verified_at=a_verified_at, verification_readbacks=[b_readback])

        row = next(e for e in reader.read_view(harness.path)['events'] if e['kind'] == 'finish' and e['seq'] == 2)
        self.assertEqual(row['timing']['seconds']['end_to_finish'], 3)

        data = deepcopy(harness.data)
        data['tasks'][0]['calls'][0]['result']['verification_readbacks'][0]['at'] = exited
        row = next(e for e in reader.process_view(data)['events'] if e['kind'] == 'finish' and e['seq'] == 2)
        self.assertIsNone(row['timing']['seconds']['end_to_finish'])

    def test_conflicting_readback_times_stay_unknown_in_either_order(self):
        harness = scheduler_fixtures.SchedulerTests()
        harness.setUp(); self.addCleanup(harness.doCleanups)
        harness.group(); harness.stage('a'); harness.stage('b')
        harness.wait('a', 'verification'); harness.wait('b', 'verification')
        harness.event('barrier', candidate=scheduler_fixtures.fixed())
        harness.grant()
        exited = harness.now()
        harness.event('finish', seq=1, outcome='passed', source='actual exit', stop=harness.proof('a'),
                      timing=dict(command_exited=dict(at=exited, source='outer process')))
        finish = harness.data['scheduler']['events'][-1]
        first = receipt(finish, harness.now())
        harness.clock += timedelta(seconds=12)
        second = receipt(finish, harness.now())
        harness.grant(verification_readbacks=[first, second])

        data = deepcopy(harness.data)
        carrier = data['scheduler']['events'][-1]
        same_time = {**first, 'at': reader.guard.timestamp(first['at']).astimezone(timezone.utc).isoformat(),
                     'source': 'copied receipt in UTC'}
        for readbacks, expected in (([first, second], None), ([second, first, second], None),
                                    ([first, same_time], 3)):
            with self.subTest(readbacks=readbacks):
                carrier['verification_readbacks'] = readbacks
                row = next(e for e in reader.process_view(data)['events'] if e['kind'] == 'finish')
                self.assertEqual(row['outcome'], 'passed')
                self.assertEqual(row['timing']['seconds']['end_to_finish'], expected)

    def test_file_is_read_only_and_changed_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'run.md'; raw = raw_document(history()); p.write_bytes(raw)
            stat = p.stat()
            view = reader.read_view(p)
            self.assertEqual(p.read_bytes(), raw)
            self.assertEqual(p.stat().st_mtime_ns, stat.st_mtime_ns)
            self.assertEqual(view['source']['sha256'], reader.guard.digest(raw))
            with patch.object(Path, 'read_bytes', side_effect=[raw, raw+b'changed']):
                with self.assertRaisesRegex(ValueError, 'changed while reading'):
                    reader.read_view(p)

    def test_cli_isolated_package_rejects_invalid_or_old_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); package = root / 'cadra'
            shutil.copytree(SCRIPT.parents[1], package)
            p = root / 'run.md'; p.write_bytes(raw_document(history()))
            command = [sys.executable, '-I', '-B', str(package/'scripts/process_view.py'), '--run', str(p)]
            ok = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertEqual(len(json.loads(ok.stdout)['tasks'][0]['calls']), 7)
            for raw in (b'broken', raw_document({'protocol': '0.11'})):
                p.write_bytes(raw)
                fail = subprocess.run(command, capture_output=True, text=True)
                self.assertNotEqual(fail.returncode, 0)
                self.assertEqual(fail.stdout, '')

    def test_compact_candidates_omit_input_manifests(self):
        data = history()
        data['tasks'][0]['result']['candidate'] = dict(snapshot='fixed.json', inputs={'large': 'x'*100000})
        row = reader.process_view(data)['tasks'][0]
        self.assertNotIn('inputs', row['result']['candidate'])
        self.assertEqual(row['result']['candidate']['snapshot'], 'fixed.json')

    def test_interrupted_run_retains_recovery_provenance_and_pending_call(self):
        data = example(); pending(data); data['tasks'][0]['agents'] = [binding()]
        data['status'] = 'interrupted'
        previous = deepcopy(data['executor'])
        data['ownership_history'] = [dict(previous=previous, source='synthetic stopped owner handoff', at=LATER)]
        data['executor'].update(instance_id='next', generation=2, claimed_at=LATER,
                                progress={'at': LATER, 'event': 'takeover'})
        view = reader.process_view(data)
        self.assertEqual(view['status'], 'interrupted')
        self.assertEqual(view['ownership_history'], data['ownership_history'])
        self.assertEqual(view['tasks'][0]['calls'][0]['status'], 'pending')

    def test_corrupt_contract_fields_are_rejected_before_projection(self):
        bad_fields = [
            ('status', 'ready'),
            ('candidate', 'not-a-mapping'), ('candidate', None),
            ('candidate', {'snapshot': None}),
            ('candidate', {'commit': False, 'snapshot': None}),
            ('findings', []), ('findings', {'blocking': 0}),
            ('findings', {'blocking': -1, 'non_blocking': 0}),
            ('findings', {'blocking': True, 'non_blocking': 0}),
            ('findings', {'blocking': 0, 'non_blocking': 'zero'}),
            ('findings', {'blocking': 0, 'non_blocking': 0, 'unresolved': -1}),
            ('acceptance', []), ('acceptance', {}),
            ('acceptance', {'status': 'approved'}),
            ('next', None), ('next', {'allowed': False, 'reason': 'blocked'}),
            ('next', {'stage': None, 'allowed': 'false', 'reason': 'blocked'}),
            ('next', {'stage': 'launch', 'allowed': True, 'reason': 'stage_completed'}),
            ('next', {'stage': None, 'allowed': False, 'reason': 'go'}),
            ('blocked', []), ('blocked', {'value': False}),
            ('blocked', {'value': 'true', 'reason': 'missing_permission'}),
            ('blocked', {'value': False, 'reason': 'missing_permission'}),
            ('blocked', {'value': True, 'reason': None}),
        ]
        for field, value in bad_fields:
            with self.subTest(field=field, value=value):
                data = history()
                data['tasks'][0]['calls'][-1]['result']['contract'][field] = value
                with self.assertRaisesRegex(ValueError, 'camera call 7:'):
                    reader.process_view(data)
        for field in ('status', 'execution_mode', 'candidate', 'next', 'blocked'):
            with self.subTest(missing=field):
                data = history()
                del data['tasks'][0]['calls'][-1]['result']['contract'][field]
                with self.assertRaises(ValueError):
                    reader.process_view(data)

    def test_claimed_incomplete_contract_is_not_missing_evidence(self):
        for result in ({'contract': None}, {'contract': []}, {'contract': {}}, {'contract': '0.8'}):
            with self.subTest(result=result):
                call = history()['tasks'][0]['calls'][-1]
                call['result'] = result
                with self.assertRaises(ValueError):
                    reader.call_view(call, 'camera')

    def test_cli_rejects_corrupt_snapshots_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'run.md'
            for field, value in [('acceptance', {'status': 'approved'}),
                                 ('acceptance', {'status': 'passed'}),
                                 ('findings', {'blocking': -1, 'non_blocking': 'zero'}),
                                 ('candidate', 'not-a-mapping'),
                                 ('next', {'stage': 'launch', 'allowed': 'yes', 'reason': 'go'})]:
                with self.subTest(field=field):
                    data = history()
                    data['tasks'][0]['calls'][-1]['result']['contract'][field] = value
                    raw = raw_document(data); path.write_bytes(raw); before = path.stat().st_mtime_ns
                    result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), '--run', str(path)],
                                            capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, '')
                    self.assertIn('camera call 7:', result.stderr)
                    self.assertEqual(path.read_bytes(), raw)
                    self.assertEqual(path.stat().st_mtime_ns, before)

    def test_optional_contract_fields_preserve_missing_and_null(self):
        for mode in ('missing', 'null', 'unknown_unresolved'):
            with self.subTest(mode=mode):
                data = history(); contract_ = data['tasks'][0]['calls'][-1]['result']['contract']
                if mode == 'missing':
                    contract_.pop('findings', None); contract_.pop('acceptance', None)
                elif mode == 'null':
                    contract_.update(findings=None, acceptance=None)
                else:
                    contract_['findings'] = dict(blocking=0, non_blocking=0, unresolved=None)
                call = reader.process_view(data)['tasks'][0]['calls'][-1]
                self.assertEqual(call['status'], 'recorded')
                if mode == 'unknown_unresolved':
                    self.assertIsNone(call['findings']['unresolved'])
                else:
                    self.assertIsNone(call['findings'])
                    self.assertIsNone(call['acceptance'])

    def test_validate_passed_rejects_inconsistent_completion_fields(self):
        call = history()['tasks'][0]['calls'][-1]
        valid = deepcopy(call['result']['contract'])
        valid.update(status='completed', acceptance={'status': 'passed'},
                     next=dict(stage=None, allowed=False, reason='task_completed'),
                     blocked=dict(value=False, reason=None))
        valid['stage_result']['status'] = 'completed'
        for field, value in [
            ('stage_result', dict(stage='validate', status='blocked', round=1)),
            ('stage_result', dict(stage='validate', status='failed', round=1)),
            ('status', 'in_progress'),
            ('next', dict(stage=None, allowed=False, reason='blocked')),
            ('next', dict(stage='review', allowed=True, reason='stage_completed')),
        ]:
            with self.subTest(field=field, value=value):
                invalid = deepcopy(valid); invalid[field] = value
                call['result']['contract'] = invalid
                with self.assertRaisesRegex(ValueError, 'validate completion state'):
                    reader.call_view(call, 'camera')

    def test_validate_completion_and_retained_prior_acceptance_remain_valid(self):
        call = history()['tasks'][0]['calls'][-1]
        valid = deepcopy(call['result']['contract'])
        valid.update(status='completed', acceptance={'status': 'passed'},
                     next=dict(stage=None, allowed=False, reason='task_completed'),
                     blocked=dict(value=False, reason=None))
        valid['stage_result']['status'] = 'completed'
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped):
                call['result'] = dict(contract=valid, index_sync=True) if wrapped else valid
                row = reader.call_view(call, 'camera')
                self.assertEqual(row['status'], 'recorded')
                self.assertEqual(row['acceptance']['status'], 'passed')
        # Prior acceptance may be retained on another stage; do not apply the
        # current-validate completion constraint to that historical field.
        code = history()['tasks'][0]['calls'][0]
        code['result']['contract']['acceptance'] = {'status': 'passed'}
        self.assertEqual(reader.call_view(code, 'camera')['status'], 'recorded')
