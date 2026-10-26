"""Offline cutover safety and restoration; no live installations are touched."""
import importlib.util
import json
import fcntl
import os
import re
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .test_run_guard import document

spec = importlib.util.spec_from_file_location('cutover', Path(__file__).resolve().parents[2]/'tools/cutover_cadra_010.py')
cutover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cutover)


class CutoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()/'project'
        self.root = self.project/'.yuzio/cadra'
        self.install = self.project.parent/'installed'
        self.source = self.project.parent/'source'
        for p in (self.root/'tasks', self.root/'runs'): p.mkdir(parents=True)
        (self.root/'README.md').write_text('# Original container\n')
        for base in (self.install, self.source):
            for name in cutover.PACKAGES:
                (base/name).mkdir(parents=True)
                (base/name/'release.json').write_text(json.dumps({'version':'0.10.0', 'protocol_version':'0.10'}))
                (base/name/'SKILL.md').write_text('old' if base == self.install else 'new')
        self.task('done', 'implementation')
        self.task('pending', 'bugfix', ['done'])
        self.task('fresh', 'full')
        self.data = {'protocol':'0.8','run_id':'run-20261026-01','status':'completed','tasks':[
            {'slug':'done','revision':1,'previous_run':None,'state':'completed','result':{'state':'completed'},'calls':[]},
            {'slug':'pending','revision':1,'previous_run':None,'state':'blocked','result':{'state':'blocked'},'calls':[]}]}
        self.run = self.root/'runs/run-20261026-01.md'
        self.run.write_bytes(document(self.data))
        (self.project/'notes.md').write_text('[Run](.yuzio/cadra/runs/run-20261026-01.md)\n[done](.yuzio/cadra/tasks/done.md)\n')

    def task(self, slug, flow, deps=None):
        (self.root/'tasks'/f'{slug}.md').write_bytes(document(dict(protocol='0.8', slug=slug,
            revision=1, preparation='ready', flow=flow, dependencies=deps or [],
            cohestra_task=f'.yuzio/cohestra/handoffs/{slug}/')))

    def plan(self):
        return cutover.inspect(self.project, self.install, self.source)

    def test_unfinished_or_unclosed_calls_refuse_without_backup_or_edits(self):
        for variant in ('running','interrupted','call'):
            d = json.loads(json.dumps(self.data))
            if variant == 'call': d['tasks'][1]['calls'] = [{'closed':False}]
            else: d['status'] = variant
            self.run.write_bytes(document(d))
            before = cutover.files(self.root)
            with self.assertRaises(ValueError): self.plan()
            self.assertEqual(cutover.files(self.root), before)
            self.assertFalse((self.project/'.yuzio/cadra-archive').exists())

    def test_archive_originals_gate_invalidation_links_and_installation(self):
        before = cutover.files(self.root)
        plan = self.plan()
        archive = cutover.apply(plan, plan['sha256'])
        self.assertEqual(cutover.files(archive/'original/container'), before)
        self.assertFalse(list((self.root/'runs').glob('*.md')))
        self.assertEqual({p.stem for p in (self.root/'tasks').glob('*.md')}, {'pending','fresh'})
        pending, body = cutover.load((self.root/'tasks/pending.md').read_bytes())
        self.assertEqual((pending['protocol'], pending['flow'],pending['revision'],pending['preparation']),('0.10','fix',2,'draft'))
        self.assertEqual(pending['dependencies'], [])
        self.assertIsNone(pending['revision_base'])
        self.assertIn('原结果 blocked',body)
        self.assertIn('已完成前置输入',body)
        fresh,_ = cutover.load((self.root/'tasks/fresh.md').read_bytes())
        self.assertEqual((fresh['flow'],fresh['revision'],fresh['preparation']),('code',1,'draft'))
        self.assertIn('cadra-archive', (self.project/'notes.md').read_text())
        for name in cutover.PACKAGES:
            self.assertEqual(cutover.files(self.install/name),cutover.files(self.source/name))
        cutover.rollback(archive)
        self.assertEqual(cutover.files(self.root),before)
        self.assertEqual((self.install/'cadra/SKILL.md').read_text(),'old')
        self.assertNotIn('cadra-archive', (self.project/'notes.md').read_text())

    def test_snapshot_change_refuses_before_replacement(self):
        plan = self.plan()
        (self.root/'README.md').write_text('# Concurrent update\n')
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            cutover.apply(plan, plan['sha256'])
        self.assertEqual((self.install/'cadra/SKILL.md').read_text(),'old')
        self.assertTrue(self.run.exists())

    def test_rollback_refuses_new_work(self):
        plan=self.plan();archive=cutover.apply(plan,plan['sha256'])
        (self.root/'README.md').write_text('# New work\n')
        with self.assertRaisesRegex(ValueError, 'new work'):
            cutover.rollback(archive)

    def test_partial_switch_has_restorable_journal(self):
        before=cutover.files(self.root);plan=self.plan();real=cutover.replace_tree
        def fail_install(target, source, **kwargs):
            if target == self.install/'cadra': raise OSError('injected installation failure')
            return real(target,source,**kwargs)
        with patch.object(cutover,'replace_tree',side_effect=fail_install):
            with self.assertRaises(OSError):cutover.apply(plan,plan['sha256'])
        archive=next((self.project/'.yuzio/cadra-archive').iterdir())
        cutover.rollback(archive)
        self.assertEqual(cutover.files(self.root),before)

    def test_old_flow_mapping_and_invalid_lists(self):
        for old,new in (('implementation','code'),('bugfix','fix'),('review-only',['review']),('full','code')):
            self.assertEqual(cutover.old_flow(old),new)
        self.assertEqual(cutover.old_flow(['review','fix']),['review','fix'])
        for flow in ([],['need','code'],'unknown'):
            with self.assertRaises(ValueError):cutover.old_flow(flow)

    def test_duplicate_yaml_keys_fail_conservatively(self):
        with self.assertRaises(ValueError):cutover.load(b'---\nprotocol: "0.8"\nprotocol: "0.9"\n---\n')

    def test_run_writer_lock_remains_exclusive_through_container_swap(self):
        plan=self.plan();real=cutover.replace_tree;observed=[]
        def inspect_lock(target,source,**kwargs):
            real(target,source,**kwargs)
            if target == self.root:
                fd=os.open(self.root/'runs/.writer.lock', os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    observed.append(True)
                finally:os.close(fd)
        with patch.object(cutover,'replace_tree',side_effect=inspect_lock):
            cutover.apply(plan,plan['sha256'])
        self.assertEqual(observed,[True])

    def test_rollback_obeys_current_run_writer_lock(self):
        plan=self.plan();archive=cutover.apply(plan,plan['sha256'])
        before=cutover.files(self.root)
        with cutover.file_lock(self.root/'runs/.writer.lock'):
            with self.assertRaisesRegex(ValueError,'writer is active'):cutover.rollback(archive)
        self.assertEqual(cutover.files(self.root),before)

    def test_rollback_recovers_both_rename_crash_windows(self):
        for has_target in (False,True):
            with self.subTest(has_target=has_target):
                self.setUp()
                plan=self.plan();archive=cutover.apply(plan,plan['sha256'])
                displaced=self.root.with_name(self.root.name+'.cutover-old')
                shutil.copytree(archive/'original/container',displaced)
                if not has_target:shutil.rmtree(self.root)
                cutover.rollback(archive)
                self.assertEqual(cutover.files(self.root),plan['container'])
                self.assertFalse(displaced.exists())

    def test_reference_replace_failure_preserves_old_bytes_and_can_rollback(self):
        plan=self.plan();real=cutover.os.replace;notes=self.project/'notes.md';before=notes.read_bytes()
        def fail_reference(src,dst):
            if dst == notes:raise OSError('injected reference replace failure')
            return real(src,dst)
        with patch.object(cutover.os,'replace',side_effect=fail_reference):
            with self.assertRaises(OSError):cutover.apply(plan,plan['sha256'])
        self.assertEqual(notes.read_bytes(),before)
        archive=next((self.project/'.yuzio/cadra-archive').iterdir())
        self.assertEqual(json.loads((archive/'manifest.json').read_text())['state'],'prepared')
        cutover.rollback(archive)
        self.assertEqual(cutover.files(self.root),plan['container'])

    def test_repeat_cutover_and_tampered_backup_are_rejected(self):
        plan=self.plan();archive=cutover.apply(plan,plan['sha256'])
        with self.assertRaisesRegex(ValueError,'already completed'):self.plan()
        (archive/'original/container/README.md').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'backup changed'):cutover.rollback(archive)

    def test_nested_run_evidence_and_directory_links_move_to_archive(self):
        evidence=self.root/'runs/scratch/batch/evidence.json'
        evidence.parent.mkdir(parents=True);evidence.write_text('{}')
        (self.project/'notes.md').write_text('[evidence](.yuzio/cadra/runs/scratch/batch/evidence.json)\n目录：.yuzio/cadra/runs/scratch/batch/\n')
        plan=self.plan();archive=cutover.apply(plan,plan['sha256'])
        text=(self.project/'notes.md').read_text()
        self.assertIn(str((archive/'original/container/runs/scratch/batch').relative_to(self.project)),text)
        self.assertNotIn('.yuzio/cadra/runs/scratch',text)
        self.assertEqual((archive/'original/container/runs/scratch/batch/evidence.json').read_text(),'{}')

    def test_rollback_does_not_overwrite_reference_changed_after_validation(self):
        plan=self.plan();archive=cutover.apply(plan,plan['sha256']);real=cutover.restore_tree
        notes=self.project/'notes.md'
        def concurrent_edit(*args):
            real(*args)
            if args[0] == self.root:notes.write_text('concurrent user change')
        with patch.object(cutover,'restore_tree',side_effect=concurrent_edit):
            with self.assertRaisesRegex(ValueError,'file changed'):
                cutover.rollback(archive)
        self.assertEqual(notes.read_text(),'concurrent user change')

    def test_empty_pending_container_cannot_repeat_cutover(self):
        (self.root/'tasks/fresh.md').unlink()
        self.data['tasks'][1].update(state='completed',result={'state':'completed'})
        self.run.write_bytes(document(self.data))
        plan=self.plan();self.assertFalse(plan['pending'])
        cutover.apply(plan,plan['sha256'])
        self.assertFalse(list((self.root/'tasks').glob('*.md')))
        with self.assertRaisesRegex(ValueError,'already completed'):self.plan()

    def test_archived_views_resolve_directory_links_to_archived_originals(self):
        (self.root/'README.md').write_text('[tasks](tasks/) [runs](runs/)\n')
        plan=self.plan();archive=cutover.apply(plan,plan['sha256'])
        view=archive/'views/README.md';text=view.read_text()
        for target in re.findall(r'\]\(([^)]+)\)',text):
            resolved=(view.parent/target).resolve()
            self.assertTrue(resolved.is_dir())
            self.assertTrue(resolved.is_relative_to(archive/'original/container'))


if __name__ == '__main__':unittest.main()
