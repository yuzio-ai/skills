"""Exercise the shipped preparation CLI and both sides of Run admission."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from .test_run_guard import example, guard, raw_document
from .test_append_agents import appended

PACKAGE = Path(__file__).resolve().parents[2] / 'cadra'
SCRIPT = PACKAGE / 'scripts' / 'prepare.py'


class PrepareTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name).resolve()
        self.container = self.project / '.yuzio/cadra'
        self.tasks = self.container / 'tasks'
        self.runs = self.container / 'runs'
        self.tasks.mkdir(parents=True)
        self.runs.mkdir()
        (self.container / 'README.md').write_bytes((PACKAGE / 'assets/project/README.md').read_bytes())
        (self.project / '.gitignore').write_text('/.yuzio/\n')
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.task = self.tasks / 'camera.md'
        self.run = self.runs / 'run-20261025-01.md'
        self.header = dict(protocol='0.12', slug='camera', title='Share preview', revision=1,
                           preparation='draft', ready_scope=None, origin=None, priority='medium',
                           dependencies=[], flow='code', execution_policy=dict(stop_queue_on_failure=False),
                           cohestra_task='.yuzio/cohestra/handoffs/camera/', revision_base=None, changed_fields=[])
        self.body = ('\n\n# Share preview\n\n## Requirement\n\nAdd a share preview.\n\n'
                     '## Ready Gate\n\n')
        self.inputs = {'src/layout.css': 'preview layout'}
        (self.project / 'src').mkdir()
        (self.project / 'src/layout.css').write_text('layout')
        (self.project / 'src/unrelated.txt').write_text('unrelated')

    def call(self, action, *args, error=None):
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT), action, *map(str, args)],
                              capture_output=True, text=True)
        if error is not None:
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertIn(error, proc.stderr)
            return None
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def dump(self, name, data):
        file = self.project / name
        file.write_text(json.dumps(data))
        return file

    def inspect(self, entry='add', **kwargs):
        return self.call('inspect', '--project', self.project, '--slug', 'camera', '--entry', entry, **kwargs)

    def check(self, inspection, inputs=None, attachments=None, error=None):
        return self.call('check', '--inspection', self.dump('inspection.json', inspection),
                         '--inputs', self.dump('inputs.json', inputs or {}),
                         '--attachments', self.dump('attachments.json', attachments or {}), error=error)

    def task_document(self, header, gate='- 未检查'):
        return ('---\n' + json.dumps(header, ensure_ascii=False) + '\n---' + self.body + gate + '\n').encode()

    def save(self, checked, header=None, *, error=None):
        proposal = self.project / 'proposal.md'
        proposal.write_bytes(self.task_document(header or self.header))
        return self.call('publish', '--checked', self.dump('checked.json', checked), '--proposal', proposal,
                         error=error)

    def ready(self, checked):
        return dict(self.header, preparation='ready', ready_scope=dict(
            revision=1, scope=dict(mode='exclusive', files=[], dirs=['src']), inputs=checked['business']))

    def draft(self):
        self.assertEqual(self.save(self.check(self.inspect()))['preparation'], 'draft')
        return self.task.read_bytes()

    def retained_files(self):
        paths = {}
        for name, content in [('layout.png', b'fixture image bytes'), ('prototype.html', b'<main>Preview</main>')]:
            file = self.tasks / 'camera/inputs/batch' / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
            paths[str(file.relative_to(self.project))] = guard.digest(content)
        return paths

    def proposal(self, task_header):
        run = example()
        run['tasks'][0]['definition'] = dict(task_header, requirement='Add a share preview.')
        return run

    def publish_run(self, run, mode='create', expected=None):
        return guard.publish(self.run, raw_document(run), expected, 'first', 1, mode)

    def test_add_then_ready_with_two_attachments_and_explicit_inputs_only(self):
        inspection = self.inspect()
        attachments = self.retained_files()
        self.assertEqual(self.save(self.check(inspection, attachments=attachments))['preparation'], 'draft')
        checked = self.check(self.inspect('ready'), self.inputs, attachments)
        self.assertEqual(set(checked['business']), set(self.inputs))
        self.assertEqual(checked['captured'], attachments)
        (self.project / 'src/unrelated.txt').write_text('unrelated file changed')
        result = self.save(checked, self.ready(checked))
        self.assertEqual(result['preparation'], 'ready')
        self.assertEqual(result['sha256'], guard.digest(self.task.read_bytes()))

    def test_old_protocol_is_rejected_before_save(self):
        self.task.write_bytes(self.task_document(dict(self.header, protocol='0.11')))
        self.inspect(error='unsupported Cadra protocol')
        self.assertIn(b'0.11', self.task.read_bytes())
        self.task.unlink()
        self.run.write_text("---\nprotocol: '0.11'\n---\n")
        self.inspect(error=self.run.name)

    def test_changing_attachment_or_input_rejects_without_replacing_task(self):
        before = self.draft()
        attachments = self.retained_files()
        inspected = self.inspect('ready')
        checked = self.check(inspected, self.inputs, attachments)
        path = self.project / next(iter(attachments))
        path.write_bytes(b'changed')
        self.save(checked, self.ready(checked), error='design attachments changed')
        self.assertEqual(self.task.read_bytes(), before)
        checked = self.check(inspected, self.inputs, attachments)
        self.save(checked, self.ready(checked), error='changed or missing attachment')
        self.assertEqual(self.task.read_bytes(), before)
        checked = self.check(inspected, self.inputs)
        (self.project / 'src/layout.css').write_text('new layout')
        self.save(checked, self.ready(checked), error='business inputs changed: src/layout.css')
        self.assertEqual(self.task.read_bytes(), before)

    def test_check_rejects_directories_and_unexplained_inputs(self):
        self.draft()
        inspected = self.inspect('ready')
        self.check(inspected, {'src': 'source directory'}, error='must match actual path kind')
        self.check(inspected, {'src/layout.css': ''}, error='non-empty reason')

    def test_stale_edit_does_not_replace_a_newer_task(self):
        self.draft()
        checked = self.check(self.inspect())
        newer = dict(self.header, title='New title')
        self.save(checked, newer)
        self.save(checked, dict(self.header, priority='high'), error='camera task changed')
        self.assertEqual(self.task.read_bytes(), self.task_document(newer))

    def test_task_publication_uses_the_run_writer_lock(self):
        before = self.draft()
        checked = self.check(self.inspect())
        with guard.writer_lock(self.runs):
            self.save(checked, dict(self.header, priority='high'), error='another Run writer is active')
        self.assertEqual(self.task.read_bytes(), before)

    def test_create_before_task_edit_blocks_preparation(self):
        self.draft()
        checked = self.check(self.inspect('ready'), self.inputs)
        ready = self.ready(checked)
        self.save(checked, ready)
        checked = self.check(self.inspect())
        self.publish_run(self.proposal(ready))
        self.save(checked, dict(ready, priority='high'), error='belongs to unfinished Run')
        self.inspect('ready', error='belongs to unfinished Run')
        self.assertEqual(self.task.read_bytes(), self.task_document(ready))

    def test_task_edit_before_create_blocks_stale_run(self):
        self.draft()
        checked = self.check(self.inspect('ready'), self.inputs)
        ready = self.ready(checked)
        self.save(checked, ready)
        stale = self.proposal(ready)
        self.save(self.check(self.inspect()), dict(ready, priority='high'))
        with self.assertRaisesRegex(ValueError, 'Task definition changed before admission:.*camera.md'):
            self.publish_run(stale)
        self.assertFalse(self.run.exists())

    def test_append_checks_only_the_new_suffix_and_rejects_stale_definition(self):
        run = example()
        primary = dict(self.header, preparation='ready', ready_scope=run['tasks'][0]['definition']['ready_scope'])
        run['tasks'][0]['definition'] = dict(primary, requirement='Add a share preview.')
        self.task.write_bytes(self.task_document(primary))
        old = self.publish_run(run)
        proposal = appended(run)
        proposed_task = dict(primary, slug='second', cohestra_task='.yuzio/cohestra/handoffs/second/')
        proposal['tasks'][-1]['definition'] = dict(proposed_task, requirement='Add a share preview.')
        target = self.tasks / 'second.md'
        target.write_bytes(self.task_document(dict(proposed_task, priority='high')))
        with self.assertRaisesRegex(ValueError, 'Task definition changed before admission:.*second.md'):
            self.publish_run(proposal, 'append', old)
        self.assertEqual(guard.digest(self.run.read_bytes()), old)
        target.write_bytes(self.task_document(proposed_task))
        self.task.unlink()  # Do not re-admit or reread the already frozen prefix.
        self.publish_run(proposal, 'append', old)
        self.assertEqual(guard.header(self.run.read_bytes())['tasks'], proposal['tasks'])

    def test_ready_cannot_rewrite_requirement(self):
        before = self.draft()
        checked = self.check(self.inspect('ready'), self.inputs)
        ready = self.ready(checked)
        self.body = self.body.replace('Add a share preview.', 'Implement something else.')
        self.save(checked, ready, error='only edit the Ready Gate section')
        self.assertEqual(self.task.read_bytes(), before)
