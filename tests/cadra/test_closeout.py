"""0.12 closeout scenarios using shipped reducers, real files, CAS and CLI.

Agent/host observations and Cohestra deliveries are synthetic. They verify
control behavior and filesystem evidence, not a real agent's review quality.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from .test_run_guard import guard, example, raw_document, binding, AT, LATER
from .closeout_fixture import definition, deliver, finalize, complete
from .test_append_agents import appended


class Harness:
    def __init__(self, root, flow='code'):
        self.root = root
        self.path = root / '.yuzio/cadra/runs/run-20261025-01.md'
        self.path.parent.mkdir(parents=True)
        self.task_dir = self.path.parent.parent / 'tasks'
        self.task_dir.mkdir()
        for name, content in [('app.py', 'def current(): return 1\n'),
                              ('README.md', 'Use current()\n'), ('old.py', '# compatibility entry\n')]:
            (root / name).write_text(content)
        self.data = example(flow=flow)
        task = self.data['tasks'][0]
        task['definition'].update(title='Feature', dependencies=[], priority='medium', origin=None,
                cohestra_task='.yuzio/cohestra/handoffs/camera/', execution_policy=dict(stop_queue_on_failure=False))
        task['definition']['ready_scope']['scope'] = dict(mode='parallel', files=['app.py','README.md','old.py'], dirs=[])
        task['definition']['ready_scope']['inputs'] = self.inputs()
        self.data['scheduler'] = guard.scheduler.initial()
        self.sha = guard.publish(self.path, raw_document(self.data), None, 'first', 1, 'create')
        self.write_task(task['definition'])
        self.group()

    def inputs(self):
        return {name: hashlib.sha256((self.root/name).read_bytes()).hexdigest() if (self.root/name).exists() else None
                for name in ('app.py','README.md','old.py')}

    def candidate(self, extra=None):
        inputs = {**self.inputs(), **(extra or {})}
        raw = json.dumps(inputs, sort_keys=True).encode()
        sha = hashlib.sha256(raw).hexdigest()
        folder = self.root / '.yuzio/synthetic-candidates'; folder.mkdir(exist_ok=True)
        path = folder / (sha+'.json')
        if not path.exists(): path.write_bytes(raw)
        return dict(snapshot=str(path.relative_to(self.root)), sha256=sha, inputs=inputs)

    def write_task(self, d):
        doc = deepcopy(d); requirement = doc.pop('requirement', '')
        (self.task_dir/(doc['slug']+'.md')).write_bytes(raw_document(doc)+f'\n## Requirement\n\n{requirement}\n'.encode())

    def save(self, data, mode='update', *, who=None):
        owner = data['executor']
        self.sha = guard.publish(self.path, raw_document(data), self.sha,
                                who or owner['instance_id'], owner['generation'], mode)
        self.data = deepcopy(data)
        if mode == 'closeout': self.write_task(data['tasks'][-1]['definition'])

    def when(self):
        return max([self.data['executor']['progress']['at']] + [e['at'] for e in self.data['scheduler']['events']] + [e['at'] for e in self.data['append_history']], key=guard.timestamp)

    def group(self):
        members = guard.scheduler.select_group(self.data)
        d = guard.scheduler.append_event(self.data, 'group', self.when(),
                  members=members, before={s:self.inputs() for s in members}, before_refs={s:'synthetic fixed before' for s in members})
        self.save(d)

    def business_done(self, slug=None, *, state='completed'):
        slug = slug or guard.scheduler.replay(self.data)['group']['members'][0]
        d = guard.scheduler.append_event(self.data, 'wait', self.when(), slug=slug,
                call_id=None, resource='finalization', candidate=self.candidate(), scope=guard.scheduler.replay(self.data)['scope'][slug],
                stop=dict(agent_id=None,host_id=None,tools_stopped=True,observed_at=AT,source='synthetic adopted candidate'))
        self.save(d)
        d = guard.scheduler.append_event(self.data, 'close', self.when(), candidate=self.candidate(), residuals={slug:'synthetic safe residual check'})
        self.save(d)
        task = next(t for t in d['tasks'] if t['slug']==slug)
        task.update(state=state, result=dict(state=state, candidate=self.candidate()))
        self.save(d)

    def proposal(self, candidate=None):
        candidate = candidate or self.candidate()
        return guard.closeout.prepare(self.data, definition(self.data,candidate), candidate,
                    self.when(), 'synthetic actual Gate and preflight', guard.scheduler, guard.normalize_flow)

    def register(self, candidate=None):
        self.save(self.proposal(candidate), 'closeout')
        self.group()

    def finish(self, *, finding=None, repair=None):
        initial = self.candidate()
        if not self.data['tasks'][-1]['definition'].get('origin'): self.register(initial)
        if finding:
            self.save(deliver(self.data, 'review', initial, self.save, next_stage='fix', blocking=1, findings=[finding]))
            if repair: repair()
            final = self.candidate()
            self.save(deliver(self.data, 'fix', final, self.save, next_stage='review', findings=[finding]))
            self.save(deliver(self.data, 'review', final, self.save, next_stage='validate', findings=[finding]))
            self.save(deliver(self.data, 'validate', final, self.save))
        else:
            final = initial
            readonly = self.data['tasks'][-1]['definition']['flow']==['review']
            self.save(deliver(self.data, 'review', final, self.save, next_stage=None if readonly else 'validate'))
            if not readonly: self.save(deliver(self.data, 'validate', final, self.save))
        self.save(finalize(self.data, final, self.save))

    def close(self):
        d=deepcopy(self.data); d['status']='completed'; self.save(d)

    def take_over(self):
        old=self.data['executor']; d=deepcopy(self.data)
        obs=dict(instance_id=old['instance_id'],generation=old['generation'],host_id=old['host_id'],
                 thread_id=old['thread_id'],turn_id=old['turn_id'],source_kind='host',state='stopped',
                 tools_stopped=True,source='synthetic stopped host',observed_at=LATER,
                 children=[dict(agent_id=b['agent_id'],host_id=b['host_id'],state='stopped',tools_stopped=True,
                                source='synthetic stopped child',observed_at=LATER) for t in self.data['tasks'] for b in t['agents']])
        d['ownership_history'].append(dict(previous=deepcopy(old),observation=obs))
        d['executor'].update(instance_id='second',generation=2,claimed_at=LATER,progress=dict(at=LATER,event='takeover'))
        self.sha=guard.publish(self.path,raw_document(d),self.sha,'second',2,'takeover',obs); self.data=d


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.h=Harness(self.root)

    def reject(self, proposal, mode='update', match=None, who=None):
        before=self.h.path.read_bytes()
        with self.assertRaisesRegex(ValueError, match or '.'):
            self.h.save(proposal, mode, who=who)
        self.assertEqual(self.h.path.read_bytes(),before)

    def test_missing_closeout_cannot_close_normally_but_user_stop_can(self):
        h=self.h;h.business_done()
        d=deepcopy(h.data);d['status']='completed';self.reject(d,match='requires current passed closeout')
        d['status']='stopped';h.save(d)
        self.assertEqual(guard.closeout.summary(h.data)['status'],'not_started')
        self.assertFalse(guard.unfinished(h.data))
        with self.assertRaisesRegex(ValueError,'running Run'):h.proposal()

    def test_clean_closeout_uses_review_validate_and_preserves_business_result(self):
        h=self.h;h.business_done();original=deepcopy(h.data['tasks'][0]);h.finish();h.close()
        self.assertEqual(h.data['tasks'][0],original)
        self.assertEqual([c['stage'] for c in h.data['tasks'][-1]['calls']],['review','validate'])
        self.assertEqual(guard.closeout.summary(h.data)['status'],'passed')

    def test_document_sync_finding_is_fixed_rereviewed_and_verified(self):
        h=self.h;(h.root/'README.md').write_text('Use removed_entry()\n');h.business_done()
        original=deepcopy(h.data['tasks'][0])
        finding=dict(id='DOC-1',path='README.md',reason='removed_entry no longer exists')
        h.finish(finding=finding,repair=lambda:(h.root/'README.md').write_text('Use current()\n'));h.close()
        audit=h.data['tasks'][-1]
        self.assertEqual([c['stage'] for c in audit['calls']],['review','fix','review','validate'])
        self.assertEqual(audit['budget'],dict(calls=4,remediation=1,retries={}))
        self.assertEqual(h.data['tasks'][0],original)
        self.assertEqual(audit['calls'][2]['result']['findings'][0]['id'],'DOC-1')

    def test_replaced_code_cleanup_records_absence_without_rewriting_history(self):
        h=self.h;h.business_done(state='failed');original=deepcopy(h.data['tasks'][0])
        h.finish(finding=dict(id='CODE-1',path='old.py',reason='verified obsolete entry'),repair=lambda:(h.root/'old.py').unlink())
        h.close()
        self.assertIsNone(h.data['tasks'][-1]['result']['candidate']['inputs']['old.py'])
        self.assertEqual(h.data['tasks'][0],original)
        self.assertEqual(original['state'],'failed')

    def test_read_only_run_has_no_worker_or_fix_permission(self):
        other=self.root/'readonly';other.mkdir();h=Harness(other,['review']);h.business_done();h.finish();h.close()
        audit=h.data['tasks'][-1]
        self.assertEqual(audit['definition']['flow'],['review'])
        self.assertEqual([b['role'] for b in audit['agents']],['reviewer'])
        self.assertEqual(audit['budget']['calls'],1)
        self.assertTrue(guard.closeout.summary(h.data)['read_only'])

    def test_mixed_run_does_not_inherit_readonly_task_write_scope(self):
        h=self.h;h.business_done()
        d=appended(h.data,('readonly',));t=d['tasks'][-1]
        t['definition'].update(flow=['review'],ready_scope=dict(revision=1,scope=dict(mode='exclusive',files=['secret.md'],dirs=[]),inputs={'secret.md':None}))
        t['start_action']['stage']='review'
        h.save(d,'append');h.group();h.business_done('readonly')
        # Include explicitly absent input without granting write permission.
        candidate=h.candidate({'secret.md':None});p=h.proposal(candidate)
        self.assertNotIn('secret.md',p['tasks'][-1]['definition']['ready_scope']['scope']['files'])
        p['tasks'][-1]['definition']['ready_scope']['scope']['files'].append('secret.md')
        self.reject(p,'closeout',match='inherited implementation permission')

    def test_registration_is_owner_only_atomic_and_ordinary_append_cannot_register(self):
        h=self.h;h.business_done();p=h.proposal()
        self.reject(p,'closeout',who='foreign',match='does not own')
        self.reject(p,'append')
        original=deepcopy(h.data);h.save(p,'closeout')
        self.assertEqual(h.data['tasks'][0],original['tasks'][0])
        self.assertEqual(h.data['scheduler'],original['scheduler'])
        self.reject(p,'closeout')
        changed=deepcopy(h.data);changed['closeout'][0]['covered']=[];self.reject(changed)

    def test_gate_preflight_origin_and_candidate_omissions_are_rejected(self):
        h=self.h;h.business_done()
        for fault in ('gate','preflight','origin','candidate','generation','boundary'):
            p=h.proposal()
            if fault=='gate':p['tasks'][-1]['definition']['preparation']='draft'
            if fault=='preflight':p['preflight'].pop()
            if fault=='origin':p['tasks'][-1]['definition']['origin']['run']='run-20261025-99'
            if fault=='candidate':p['closeout'][0]['candidate']['inputs'].pop('old.py')
            if fault=='generation':p['closeout'][0]['generation']=2
            if fault=='boundary':p['closeout'][0]['event_count']-=1
            with self.subTest(fault=fault):self.reject(p,'closeout')

    def test_final_candidate_must_match_review_acceptance_and_all_dependencies(self):
        h=self.h;h.business_done();h.finish()
        for fault in ('snapshot','acceptance','review','source_dependency'):
            d=deepcopy(h.data);t=d['tasks'][-1]
            if fault=='snapshot':t['result']['candidate']['snapshot']='another-candidate'
            if fault=='acceptance':t['calls'][-1]['result']['contract']['acceptance']['status']='pending'
            if fault=='review':t['calls'][0]['result']['contract']['candidate']['snapshot']='different-review'
            if fault=='source_dependency':
                d['closeout'][0]['candidate']['inputs']['additional.md']=None
            with self.subTest(fault=fault),self.assertRaises(ValueError):guard.validate(d)

    def test_live_file_changes_or_missing_deletion_markers_block_final_close(self):
        h=self.h;h.business_done();h.finish()
        (h.root/'README.md').write_text('concurrent stale documentation\n')
        d=deepcopy(h.data);d['status']='completed'
        self.reject(d,match='live inputs invalidate')
        (h.root/'README.md').write_text('Use current()\n');h.close()
        # Historical results remain readable after subsequent independent edits.
        (h.root/'README.md').write_text('later revision\n');guard.current(h.path.read_bytes())

    def test_append_during_closeout_requires_expanded_new_round(self):
        h=self.h;h.business_done();h.register()
        h.save(appended(h.data,('extra',)),'append')
        # Complete the fixed current audit while appended work stays queued.
        fixed=h.candidate();audit=h.data['tasks'][-2]
        # Helpers use the last Task; finish this audit before restoring suffix.
        # Operate directly with a temporary ordered view only in the helper,
        # while publisher keeps the real immutable queue order.
        suffix=deepcopy(h.data['tasks'][-1]);audit_index=len(h.data['tasks'])-2
        def save_audit(proposal,mode):
            proposal=deepcopy(proposal)
            if proposal['tasks'][-1]['slug']==audit['slug']:proposal['tasks'].append(deepcopy(suffix))
            h.save(proposal,mode)
        view=deepcopy(h.data);view['tasks'].pop()
        view=deliver(view,'review',fixed,save_audit,next_stage='validate')
        view=deliver(view,'validate',fixed,save_audit)
        view=finalize(view,fixed,save_audit)
        self.assertEqual(guard.closeout.summary(h.data)['status'],'outdated')
        h.group();h.business_done('extra')
        closing=deepcopy(h.data);closing['status']='completed';self.reject(closing,match='current passed closeout')
        old=deepcopy(h.data['closeout']);h.finish();h.close()
        self.assertEqual(h.data['closeout'][:1],old)
        self.assertEqual(len(h.data['closeout']),2)
        self.assertEqual(len(h.data['closeout'][-1]['covered']),3)

    def test_new_closeout_cannot_reset_budget_or_repeat_unchanged_coverage(self):
        h=self.h;h.business_done();h.finish()
        p=h.proposal();self.reject(p,'closeout',match='unchanged coverage')
        d=deepcopy(h.data);t=d['tasks'][-1]
        t['budget']['calls']=17;self.reject(d,match='budget mismatch')
        with self.assertRaisesRegex(ValueError,'history is immutable'):
            changed=deepcopy(h.data);changed['tasks'][-1]['budget']['calls']=0
            guard.validate_update(h.data,changed)

    def test_prepared_task_and_registered_task_resume_without_duplicate(self):
        h=self.h;h.business_done();p=h.proposal();h.write_task(p['tasks'][-1]['definition'])
        h.take_over()
        # An unregistered prepared Task is reused only after caller rechecks Gate.
        p=h.proposal();h.save(p,'closeout');self.assertEqual(len(h.data['closeout']),1)
        actual,_=guard.current(h.path.read_bytes())
        self.assertEqual(actual['tasks'][-1]['state'],'queued')
        with self.assertRaisesRegex(ValueError,'drain queue'):h.proposal()
        h.group();h.finish();h.close()
        self.assertEqual(len(h.data['closeout']),1)

    def test_registered_call_identity_and_budget_survive_takeover(self):
        h=self.h;h.business_done();h.register()
        h.save(deliver(h.data,'review',h.candidate(),h.save,next_stage='validate'))
        before=deepcopy(h.data['tasks'][-1]);h.take_over()
        self.assertEqual(h.data['tasks'][-1],before)
        h.save(deliver(h.data,'validate',h.candidate(),h.save));h.save(finalize(h.data,h.candidate(),h.save));h.close()
        self.assertEqual(h.data['tasks'][-1]['budget']['calls'],2)

    def test_author_cannot_become_closeout_reviewer(self):
        h=self.h;d=deepcopy(h.data);d['tasks'][0]['agents']=[binding()];h.save(d);h.business_done();h.register()
        d=deepcopy(h.data);d['tasks'][-1]['agents']=[binding('reviewer')]
        self.reject(d,match='agent cannot be reused|authored covered')

    def test_closeout_runtime_scope_cannot_expand(self):
        h=self.h;h.business_done();h.register()
        t=h.data['tasks'][-1];scope=deepcopy(t['definition']['ready_scope']['scope']);scope['files'].append('outside.py')
        with self.assertRaisesRegex(ValueError,'cannot expand inherited'):
            guard.scheduler.append_event(h.data,'wait',AT,slug=t['slug'],call_id=None,resource='agent',stage='review',
                scope=scope,candidate=h.candidate(),stop=dict(agent_id=None,host_id=None,tools_stopped=True,observed_at=AT,source='synthetic'))

    def test_user_stop_preserves_unstarted_closeout_and_never_passes_it(self):
        h=self.h;h.business_done();p=h.proposal();h.save(p,'closeout')
        d=deepcopy(h.data);t=d['tasks'][-1];t.update(state='skipped',result=dict(state='skipped',last_delivery=None));d['status']='stopped'
        h.save(d)
        self.assertEqual(guard.closeout.summary(h.data)['status'],'skipped')
        self.assertFalse(guard.unfinished(h.data))

    def test_isolated_current_query_displays_closeout_without_mutation(self):
        h=self.h;h.business_done();h.finish();h.close()
        installed=h.root/'installation/cadra';shutil.copytree(Path(guard.__file__).parents[1],installed)
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in h.path.parent.parent.rglob('*') if p.is_file()}
        proc=subprocess.run([sys.executable,'-B',str(installed/'scripts/list_summary.py'),'--project',str(h.root),'--run',h.data['run_id']],capture_output=True,text=True,check=True)
        result=json.loads(proc.stdout)
        self.assertEqual(result['issues'],[])
        self.assertEqual(result['runs'][0]['closeout']['status'],'passed')
        self.assertEqual(result['protocol'],'0.12')
        self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in h.path.parent.parent.rglob('*') if p.is_file()})

    def test_legacy_011_remains_native_read_only_and_writer_rejects_it(self):
        h=self.h;h.business_done()
        legacy=deepcopy(h.data);legacy['protocol']='0.11';legacy.pop('closeout');legacy['status']='completed'
        legacy['tasks'][0]['definition']['protocol']='0.11'
        h.path.write_bytes(raw_document(legacy))
        d=deepcopy(legacy['tasks'][0]['definition']);h.write_task(d)
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in h.path.parent.parent.rglob('*') if p.is_file()}
        proc=subprocess.run([sys.executable,'-B',str(Path(guard.__file__).with_name('list_summary.py')),'--project',str(h.root),'--history'],capture_output=True,text=True,check=True)
        result=json.loads(proc.stdout)
        self.assertEqual(result['issues'],[]);self.assertEqual(result['counts'],{'completed':1})
        self.assertTrue(result['legacy_read_only']);self.assertIn('scheduling',result['runs'][0]);self.assertNotIn('closeout',result['runs'][0])
        self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in h.path.parent.parent.rglob('*') if p.is_file()})
        with self.assertRaisesRegex(ValueError,'unsupported Cadra protocol'):guard.current(h.path.read_bytes())

    def test_same_candidate_additional_dependency_cannot_disappear_at_finalization(self):
        h=self.h;h.business_done();h.register(h.candidate({'additional.md':None}))
        final=h.candidate()
        h.save(deliver(h.data,'review',final,h.save,next_stage='validate'))
        h.save(deliver(h.data,'validate',final,h.save))
        with self.assertRaisesRegex(ValueError,'omits covered inputs'):
            finalize(h.data,final,h.save)
        actual,_=guard.current(h.path.read_bytes())
        self.assertNotEqual(actual['tasks'][-1]['state'],'completed')

    def test_unsynchronized_handoff_or_missing_rereview_cannot_pass(self):
        h=self.h;h.business_done();h.finish(finding=dict(id='DOC-2',path='README.md'))
        for fault in ('index_sync','handoff','rereview'):
            d=deepcopy(h.data);t=d['tasks'][-1]
            if fault=='index_sync':t['calls'][-1]['result']['index_sync']=False
            if fault=='handoff':t['calls'][-1]['result']['handoff']=''
            if fault=='rereview':
                t['calls'][2]['result']['contract']['candidate']['snapshot']='before-fix'
                t['calls'][3]['before']=deepcopy(t['calls'][2]['result']['contract'])
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'matching independent review'):
                guard.validate(d)

    def test_exhausted_closeout_cannot_start_new_round_or_reset_budget(self):
        h=self.h;h.business_done();h.register()
        for index in range(16):
            stage='review' if index%2==0 else 'validate'
            next_stage='validate' if stage=='review' else 'review'
            h.save(deliver(h.data,stage,h.candidate(),h.save,next_stage=next_stage))
        with self.assertRaisesRegex(ValueError,'budget limit exceeded'):
            deliver(h.data,'review',h.candidate(),h.save,next_stage='validate')
        # The rejected seventeenth intent did not reach disk.
        h.data,_=guard.current(h.path.read_bytes());self.assertEqual(h.data['tasks'][-1]['budget']['calls'],16)
        task=h.data['tasks'][-1];call=task['calls'][-1]
        role=next(b for b in task['agents'] if b['id']==call['agent_ref'])
        d=guard.scheduler.append_event(h.data,'abort',AT,slug=task['slug'],call_id=call['id'],state='blocked',
                reason='call budget exhausted',source='synthetic budget observation',
                stop=dict(agent_id=role['agent_id'],host_id=role['host_id'],tools_stopped=True,observed_at=AT,source='synthetic stopped role'))
        h.save(d)
        d=guard.scheduler.append_event(h.data,'close',AT,candidate=h.candidate(),residuals={task['slug']:'synthetic safe residual evidence'})
        h.save(d)
        with self.assertRaisesRegex(ValueError,'stopped policy'):h.proposal()
        d=deepcopy(h.data);d['status']='stopped';h.save(d)
        self.assertEqual(guard.closeout.summary(h.data)['status'],'blocked')

    def test_prepared_or_dispatched_call_resumes_same_identity_without_new_charge(self):
        for pause_after_dispatch in (False,True):
            folder=self.root/('dispatched' if pause_after_dispatch else 'prepared');folder.mkdir()
            h=Harness(folder);h.business_done();h.register()
            class Paused(Exception):pass
            def pause(proposal,mode):
                h.save(proposal,mode)
                calls=h.data['tasks'][-1]['calls']
                if calls and not calls[-1]['closed'] and (calls[-1]['dispatch']=='dispatched')==pause_after_dispatch:
                    raise Paused()
            with self.assertRaises(Paused):deliver(h.data,'review',h.candidate(),pause,next_stage='validate')
            h.take_over();d=deepcopy(h.data);task=d['tasks'][-1];call=task['calls'][-1]
            if call['dispatch']=='prepared':
                call.update(dispatch='dispatched',dispatch_evidence=dict(agent_id=task['slug']+'-reviewer',source='synthetic original role continuation',at=LATER))
                h.save(d)
            from .test_cadra import contract
            sr=contract('review','validate','stage_completed')
            sr.update(task=task['slug'],candidate=dict(commit=None,snapshot=h.candidate()['snapshot']),findings=dict(blocking=0,non_blocking=0))
            delivery=dict(contract=sr,handoff='review-01.md',index_sync=True)
            call.update(closed=True,result=delivery);task['checkpoint'].update(pending_call=None,last_delivery=delivery);h.save(d)
            h.save(deliver(h.data,'validate',h.candidate(),h.save));h.save(finalize(h.data,h.candidate(),h.save));h.close()
            self.assertEqual([c['id'] for c in h.data['tasks'][-1]['calls']],[1,2])
            self.assertEqual(h.data['tasks'][-1]['budget']['calls'],2)

    def test_input_drift_preserves_result_and_can_resume_via_authorized_normal_task(self):
        h=self.h;h.business_done();h.finish();old=deepcopy(h.data['tasks'][-1])
        (h.root/'README.md').write_text('explicit subsequent change\n')
        d=deepcopy(h.data);d['status']='completed';self.reject(d,match='live inputs invalidate')
        d=deepcopy(h.data);d['status']='interrupted';h.save(d)
        self.assertEqual(h.data['tasks'][-1],old)
        d=deepcopy(h.data);d['status']='running';h.save(d)
        # This represents an explicitly authorized add/ready/append decision,
        # not an automatic retry of the immutable old audit.
        d=appended(h.data,('reconcile',));h.save(d,'append');h.group();h.business_done('reconcile')
        h.finish();h.close();self.assertEqual(h.data['tasks'][1],old)

    def test_append_and_close_processes_have_one_atomic_winner(self):
        h=self.h;h.business_done();h.finish()
        closing=deepcopy(h.data);closing['status']='completed'
        extension=appended(h.data,('concurrent',))
        processes=[]
        for name,mode,proposal in [('closing','update',closing),('extension','append',extension)]:
            path=h.root/(name+'.md');path.write_bytes(raw_document(proposal))
            cmd=[sys.executable,'-B',str(Path(guard.__file__)) ,mode,'--run',str(h.path),'--proposal',str(path),'--expected-sha256',h.sha]
            if mode=='update':cmd+=['--instance','first','--generation','1']
            processes.append(subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE))
        for proc in processes:proc.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes),[0,1])
        actual,_=guard.current(h.path.read_bytes())
        self.assertIn((actual['status'],len(actual['tasks'])),[('completed',2),('running',3)])
        self.assertEqual(actual['tasks'][:2],h.data['tasks'])

    def test_failed_partial_delivery_is_reported_without_crashing_or_passing(self):
        h=self.h;h.business_done();h.register()
        class Paused(Exception):pass
        def pause(proposal,mode):
            h.save(proposal,mode)
            calls=h.data['tasks'][-1]['calls']
            if calls and calls[-1]['dispatch']=='dispatched' and not calls[-1]['closed']:raise Paused()
        with self.assertRaises(Paused):deliver(h.data,'review',h.candidate(),pause,next_stage='validate')
        d=deepcopy(h.data);t=d['tasks'][-1];t['calls'][-1]['result']={'contract':'unconfirmed partial delivery'};h.save(d)
        b=t['agents'][0]
        d=guard.scheduler.append_event(h.data,'abort',AT,slug=t['slug'],call_id=1,state='failed',
            reason='unconfirmed delivery',source='synthetic stopped role',
            stop=dict(agent_id=b['agent_id'],host_id=b['host_id'],tools_stopped=True,observed_at=AT,source='synthetic'))
        h.save(d)
        d=guard.scheduler.append_event(h.data,'close',AT,candidate=h.candidate(),residuals={t['slug']:'synthetic safe residual check'});h.save(d)
        d=deepcopy(h.data);d['status']='stopped';h.save(d)
        result=guard.closeout.summary(h.data)
        self.assertEqual(result['status'],'failed');self.assertEqual(result['findings'],{})
        self.assertEqual(result['acceptance'],'unknown')
        proc=subprocess.run([sys.executable,'-B',str(Path(guard.__file__).with_name('list_summary.py')),'--project',str(h.root),'--history'],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(proc.stdout)['runs'][0]['closeout']['status'],'failed')

    def extension(self, *, granted):
        h=self.h
        scope=deepcopy(guard.scheduler.replay(h.data)['scope']['camera'])
        scope['files'].append('runtime.md')
        candidate=h.candidate({'runtime.md':None,'dependency.md':None})
        stop=dict(agent_id=None,host_id=None,tools_stopped=True,observed_at=AT,source='synthetic stopped task')
        d=guard.scheduler.append_event(h.data,'wait',AT,slug='camera',call_id=None,resource='files',
                    scope=scope,candidate=candidate,stop=stop)
        h.save(d)
        if granted:
            d=guard.scheduler.append_event(h.data,'grant',AT,seq=1,
                    before={**candidate['inputs'],'grant-dependency.md':None},before_ref='synthetic granted before')
            h.save(d)
            (h.root/'runtime.md').write_text('Authorized new documentation\n')
            h.business_done()
        else:
            d=guard.scheduler.append_event(h.data,'abort',AT,slug='camera',call_id=None,state='blocked',
                    reason='scope extension not authorized',source='synthetic refused grant',stop=stop)
            h.save(d)
            d=guard.scheduler.append_event(h.data,'close',AT,candidate=h.candidate(),
                    residuals={'camera':'synthetic safe residual check; no extra write performed'})
            h.save(d)
        return h

    def test_ungranted_extension_is_review_input_and_never_inherited_write_permission(self):
        h=self.extension(granted=False)
        candidate=h.candidate({'runtime.md':None,'dependency.md':None})
        proposal=h.proposal(candidate)
        self.assertNotIn('runtime.md',proposal['tasks'][-1]['definition']['ready_scope']['scope']['files'])
        self.assertIn('runtime.md',proposal['closeout'][-1]['candidate']['inputs'])
        h.save(proposal,'closeout')
        self.assertEqual([(r['kind'],r['status']) for r in guard.scheduler.replay(h.data)['requests']], [('files','aborted')])

    def test_granted_runtime_files_and_observed_dependencies_cannot_be_omitted(self):
        h=self.extension(granted=True)
        digest=hashlib.sha256((h.root/'runtime.md').read_bytes()).hexdigest()
        candidate=h.candidate({'runtime.md':digest,'dependency.md':None,'grant-dependency.md':None})
        for path in ('runtime.md','dependency.md','grant-dependency.md'):
            incomplete=deepcopy(candidate);incomplete['inputs'].pop(path)
            with self.subTest(path=path):self.reject(h.proposal(incomplete),'closeout',match='omits covered inputs')
        h.register(candidate)
        self.assertIn('runtime.md',h.data['tasks'][-1]['definition']['ready_scope']['scope']['files'])
        self.assertNotIn('dependency.md',h.data['tasks'][-1]['definition']['ready_scope']['scope']['files'])
        h.save(deliver(h.data,'review',candidate,h.save,next_stage='validate'))
        h.save(deliver(h.data,'validate',candidate,h.save));h.save(finalize(h.data,candidate,h.save));h.close()

    def test_actual_first_closeout_call_cannot_be_fix_or_validate(self):
        h=self.h;h.business_done();h.register()
        for stage in ('fix','validate'):
            with self.subTest(stage=stage),self.assertRaisesRegex(ValueError,'first call must be review'):
                deliver(h.data,stage,h.candidate(),h.save,next_stage='review')
            actual,_=guard.current(h.path.read_bytes())
            self.assertEqual(actual['tasks'][-1]['calls'],[])
            self.assertEqual(actual['tasks'][-1]['budget']['remediation'],0)

    def test_closeout_cannot_skip_verified_next_to_avoid_remediation_charge(self):
        h=self.h;h.business_done();h.register()
        h.save(deliver(h.data,'review',h.candidate(),h.save,next_stage='validate'))
        with self.assertRaisesRegex(ValueError,'follow verified next'):
            deliver(h.data,'fix',h.candidate(),h.save,next_stage='review')
        actual,_=guard.current(h.path.read_bytes())
        self.assertEqual([c['stage'] for c in actual['tasks'][-1]['calls']],['review'])
        self.assertEqual(actual['tasks'][-1]['budget']['calls'],1)

    def test_readonly_closeout_rejects_failed_acceptance_and_retains_other_boundaries(self):
        folder=self.root/'readonly-acceptance';folder.mkdir();h=Harness(folder,['review'])
        h.business_done();h.finish()
        for status in ('failed','pending','blocked','passed',None):
            d=deepcopy(h.data);t=d['tasks'][-1]
            if status is not None:
                t['calls'][-1]['result']['contract']['acceptance']={'status':status}
                t['result']['acceptance']={'status':status}
            d['status']='completed'
            with self.subTest(acceptance=status):
                if status=='failed':
                    with self.assertRaisesRegex(ValueError,'matching independent review'):guard.validate(d)
                else:
                    guard.validate(d)
                    self.assertEqual(guard.closeout.summary(d)['acceptance'],status or 'unknown')



if __name__=='__main__':unittest.main()
