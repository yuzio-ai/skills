import sys
sys.dont_write_bytecode = True
sys.path.insert(0, '/Users/zhubowen/Documents/yuzio-ai/skills/tests')
from copy import deepcopy
import json
import itertools
import unittest
import cadra_v06_model as m
import test_cadra

def contract(stage='code', next_stage='review', reason='stage_completed'):
    return dict(contract='0.8', task='a', execution_mode='unattended', status='in_progress',
                stage_result=dict(stage=stage, status='completed', round=1),
                candidate=dict(commit=None, snapshot=None),
                next=dict(stage=next_stage, allowed=True, reason=reason),
                blocked=dict(value=False, reason=None))

def terminal():
    s = contract('validate')
    s.update(status='completed', acceptance=dict(status='passed'))
    s['next'] = dict(stage=None, allowed=False, reason='task_completed')
    return s

out = {}
def flatten(suite):
    for x in suite:
        if isinstance(x, unittest.TestSuite): yield from flatten(x)
        else: yield x
suite = unittest.TestSuite(t for t in flatten(unittest.defaultTestLoader.loadTestsFromModule(test_cadra))
                          if not t.id().endswith('test_pre_call_blocked_revision_keeps_requirement_change'))
with open('/private/tmp/cadra-four-fix-model-review/baseline.log', 'w') as log:
    r = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
out['baseline'] = dict(ran=r.testsRun, failures=len(r.failures), errors=len(r.errors),
                       excluded='test_pre_call_blocked_revision_keeps_requirement_change reads prior report fixture')

# Ordinary calls become provenance after interrupted delivery reconciliation;
# special authorization must remain false throughout ordinary execution.
item = m.new_item()
assert m.prepare(item, contract(), 'small-change') == 'prepared'
assert not item['authorization_consumed']
persisted = json.loads(json.dumps(item))
assert m.recover_call(persisted, contract('review', 'validate'), 'complete') == 'closed'
assert m.prepare(persisted, persisted['calls'][-1]['result'], 'small-change') == 'prepared'
assert m.recover_call(persisted, terminal(), 'complete') == 'closed'
assert m.prepare(persisted, persisted['calls'][-1]['result'], 'small-change') == 'completed'
persisted.update(slug='a', revision=1, previous_run=None, definition=dict(requirement='old'),
                 state='completed', result=dict(state='completed', last_delivery=terminal()))
run = dict(protocol='0.6', run_id='ordinary-1', status='completed', tasks=[persisted])
task = dict(protocol='0.6', slug='a', revision=2, preparation='ready',
            definition=dict(requirement='old'), changed_fields=['execution_policy'])
assert m.revision_action(task, [run]) == 'verify_only'
task['changed_fields'] = ['requirement']
assert m.revision_action(task, [run]) == 'start'
out['ordinary_recovery_revision'] = dict(calls=len(persisted['calls']), authorization_consumed=persisted['authorization_consumed'],
                                         policy_only='verify_only', requirement='start')

# All tail permutations and duplicate tails preserve semantic flow outcomes.
n = 0
for preset, stages in m.PRESETS.items():
    for tail in itertools.permutations(stages[1:]):
        candidate = [stages[0], *tail, *tail]
        assert m.flow(candidate) == m.flow(preset)
        for stage in m.STAGES:
            for nxt in m.STAGES:
                for reason in ('stage_completed', 'blocking_findings', 'stage_failed', 'acceptance_failed'):
                    state = contract(stage, nxt, reason)
                    assert m.decision(state, candidate) == m.decision(state, preset)
                    n += 1
out['flow_equivalence_checks'] = n

# The unstarted selector preserves action and leaves evidence untouched.
for stage in ('need', 'fix', None):
    entry = m.new_item(); entry['start_action'] = dict(stage=stage, source='fresh external admission')
    before = deepcopy(entry)
    assert m.resume_unstarted(entry, True, 'not_dispatched_no_delivery') == entry['start_action']
    assert entry == before
    assert m.resume_unstarted(entry, False, 'not_dispatched_no_delivery') is None
    assert m.resume_unstarted(entry, True, 'unknown') is None
out['unstarted_selector'] = '3 actions preserve evidence; rejected Gate and unknown dispatch return None'

# Composition boundary: model has no operation that consumes a selected start.
entry = m.new_item(); entry['start_action'] = dict(stage='code', source='requirement revision')
old = terminal()
selected = m.resume_unstarted(entry, True, 'not_dispatched_no_delivery')
out['unstarted_start_composition'] = dict(selected=selected, prepare_from_old=m.prepare(entry, old, 'small-change', authorization=True),
                                         calls=entry['calls'], authorization_consumed=entry['authorization_consumed'])

# Illegal enum/type mutations independent of existing test fixtures.
rejected, accepted = [], []
base = terminal()
mutations = [(['candidate'], ['commit', 'snapshot']),
             (['candidate','commit'], 12), (['candidate','snapshot'], {'path':'handoff.md'}),
             (['findings'], 'invalid'), (['findings'], {'blocking':True,'non_blocking':'zero'}),
             (['stage_result','round'], True), (['stage_result','stage'], 'deploy'),
             (['next','allowed'], 1), (['next','reason'], []),
             (['blocked','reason'], 'unavailable'), (['acceptance','status'], {})]
for path, value in mutations:
    state = deepcopy(base); obj = state
    for key in path[:-1]: obj = obj[key]
    obj[path[-1]] = value
    record = dict(path=path, value=value, valid=m.result_valid(state), decision=m.decision(state,'full'))
    (accepted if record['valid'] else rejected).append(record)
out['invalid_contract_rejected'] = rejected
out['invalid_contract_accepted'] = accepted

entry = m.new_item()
m.prepare(entry, contract('review','validate'), 'full')
invalid_live = terminal(); invalid_live['candidate'] = ['commit','snapshot']
out['invalid_candidate_recovery_composition'] = dict(
    recovery=m.recover_call(entry, invalid_live, 'complete'),
    terminal_decision=m.prepare(entry, invalid_live, 'full'),
    closed=entry['calls'][0]['closed'])

with open('/private/tmp/cadra-four-fix-model-review/results.json','w') as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False,indent=2))
