import sys, json, copy, subprocess
from pathlib import Path
sys.path.insert(0, '/Users/zhubowen/Documents/yuzio-ai/skills/tests')
from cadra_v06_model import *
from test_cadra import task, run, contract
cases=[]
def check(name, inputs, fn, expected):
    try:
        actual=fn()
        if isinstance(actual,set): actual=sorted(actual)
    except Exception as e: actual={'exception':type(e).__name__, 'message':str(e)}
    cases.append({'name':name,'input':copy.deepcopy(inputs),'expected':expected,'actual':actual,'matches':actual==expected})

records=[run()]
for rev, state, field in [(2,'blocked','requirement'),(3,'failed','flow'),(4,'skipped','dependencies')]:
    r=run('r'+str(rev),'r'+str(rev-1),rev,state)
    r['tasks'][0].update(calls=[],authorization_consumed=False)
    r['tasks'][0]['definition']['changed_fields']=[field]
    records.append(r)
t=task(5);t['changed_fields']=['execution_policy']
for resolved in [True,False]:
    check('continuous_unconsumed_revisions_'+str(resolved), {'task':t,'runs':records,'cause_resolved':resolved}, lambda: {'fields':sorted(revision_fields(t,records)),'action':revision_action(t,records,resolved)}, {'fields':['dependencies','execution_policy','flow','requirement'],'action':'start' if resolved else 'reject'})
first=run(state='blocked');first['tasks'][0].update(calls=[],authorization_consumed=False)
check('first_pre_call_blocked', {'runs':[first]}, lambda: execution_basis('a',[first]),None)
prepared=run(revision=2,state='failed');prepared['tasks'][0]['calls'][0]['dispatch']='prepared'
t=task(3);t['changed_fields']=['execution_policy']
check('prepared_not_skipped', {'runs':[prepared],'task':t}, lambda: {'basis':execution_basis('a',[prepared])['revision'],'action':revision_action(t,[prepared])}, {'basis':2,'action':'check_recovery'})
no_call=run('r2','r1',2);no_call['tasks'][0].update(calls=[]);no_call['tasks'][0]['result']['last_delivery']={'source':'validate-01.md'}
no_call['tasks'][0]['definition'].update(requirement='R1',changed_fields=['execution_policy'])
t=task(3);t['definition']['requirement']='R1';t['changed_fields']=['dependencies']
check('legitimate_no_call_closeout',{'runs':[run(),no_call],'task':t},lambda:{'basis':execution_basis('a',[run(),no_call])['revision'],'action':revision_action(t,[run(),no_call])},{'basis':2,'action':'verify_only'})
for mutation in ['missing_predecessor','fork','cycle']:
    rs={'missing_predecessor':[run(previous='missing')],'fork':[run(),run('r2','r1'),run('r3','r1')],'cycle':[run('r1','r2'),run('r2','r1')]}[mutation]
    check(mutation,rs,lambda:chain('a',rs),{'exception':'ValueError','message':{'missing_predecessor':'missing predecessor','fork':'fork','cycle':'disconnected or cyclic chain'}[mutation]})
for evidence,live,synced,expected in [('not_dispatched_no_delivery',None,True,'dispatch_same_id'),('unknown',contract('fix'),True,'failed'),('partial',contract('fix'),True,'failed'),('complete',contract('fix'),False,'failed'),('complete',contract('fix'),True,'closed')]:
    item=new_item();prepare(item,contract(),'full',authorization=True)
    inputs={'item':copy.deepcopy(item),'live':live,'evidence':evidence,'synced':synced}
    check('recovery_'+evidence+'_'+str(synced),inputs,lambda:{'result':recover_call(item,live,evidence,synced),'calls':item['budget']['calls'],'call_id':item['calls'][0]['id'],'authorization_consumed':item['authorization_consumed']},{'result':expected,'calls':1,'call_id':1,'authorization_consumed':True})
# Contract-model discrepancies: these are test-only validation gaps, not runtime defects.
s=contract('review','validate','NOT_A_VALID_REASON')
check('invalid_next_reason_is_accepted',{'state':s,'flow':'review-only'},lambda:{'valid':result_valid(s),'decision':decision(s,'review-only')},{'valid':False,'decision':'failed'})
s=contract('review','validate','stage_completed');s['status']='completed';s['acceptance']={'status':'NOT_A_VALID_ACCEPTANCE'}
check('invalid_acceptance_is_accepted',{'state':s,'flow':'review-only'},lambda:{'valid':result_valid(s),'decision':decision(s,'review-only')},{'valid':False,'decision':'failed'})
s=contract();s['status']='blocked';s['next']['allowed']=False;s['next']['reason']='blocked';s['blocked']={'value':True,'reason':'missing_input'}
check('legal_blocked_retaining_next_stage_is_rejected',{'state':s,'flow':'full'},lambda:{'valid':result_valid(s),'decision':decision(s,'full')},{'valid':True,'decision':'blocked'})
proc=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_cadra.py','-v'],cwd='/Users/zhubowen/Documents/yuzio-ai/skills',capture_output=True,text=True)
result={'scope':'Test-only executable model; not Cadra runtime or end-to-end agent behavior','existing_tests':{'command':'python3 -B -m unittest discover -s tests -p test_cadra.py -v','exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr},'cases':cases}
Path('/private/tmp/cadra-model-audit-02.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'test_return_code':proc.returncode,'case_count':len(cases),'mismatches':[{'name':c['name'],'expected':c['expected'],'actual':c['actual']} for c in cases if not c['matches']]},ensure_ascii=False,indent=2))
