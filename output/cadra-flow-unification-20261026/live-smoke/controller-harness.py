import pathlib,json,subprocess,datetime,hashlib,sys
P=pathlib.Path('/private/tmp/cadra-live-fa274994d4');RUN=P/'.yuzio/cadra/runs/run-20261026-01.md';OUT=pathlib.Path('/Users/zhubowen/Documents/yuzio-ai/skills/output/cadra-flow-unification-20261026/live-smoke');GUARD='/Users/zhubowen/Documents/yuzio-ai/skills/cadra/scripts/run_guard.py'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(path):return json.loads(path.read_text().split('---',2)[1])
def publish(data,old,op='update'):
 raw=RUN.read_bytes(); body=raw.decode().split('---',2)[2]; proposal=RUN.parent/'scratch'/('proposal-'+now().replace(':','-')+'.md');proposal.write_text('---\n'+json.dumps(data,ensure_ascii=False,indent=2)+'\n---'+body)
 cmd=['python3','-B',GUARD,op,'--run',str(RUN),'--proposal',str(proposal),'--expected-sha256',hashlib.sha256(raw).hexdigest()]
 if op=='update':cmd+=['--instance',old['executor']['instance_id'],'--generation',str(old['executor']['generation'])]
 res=subprocess.run(cmd,text=True,capture_output=True);(OUT/'guard-publications.jsonl').open('a').write(json.dumps({'at':now(),'op':op,'command':cmd,'stdout':res.stdout,'stderr':res.stderr,'exit':res.returncode})+'\n');print(res.stdout,res.stderr);res.check_returncode();assert read(RUN)==data
if __name__=='__main__':
 op=sys.argv[1];d=read(RUN);old=json.loads(json.dumps(d));t=next((x for x in d['tasks'] if x['slug']==sys.argv[2]),None) if len(sys.argv)>2 else None
 if op=='bind':
  role,aid=sys.argv[3:5];t['agents'].append({'id':role+'-1','role':role,'agent_id':aid,'host_id':None,'created_at':now(),'source':'collaboration.spawn_agent '+aid+' actual returned canonical identity; child initialization confirmed available before dispatch','supersedes':None,'stop_observation':None})
 elif op=='prepare':
  taskpath=P/'.yuzio/cadra/tasks'/(t['slug']+'.md');assert read(taskpath)==t['definition'], 'frozen Task definition drift'
  assert not t['definition']['dependencies'], 'fixture declares no dependencies'
  for check in d['preflight']:
   if check['status']=='passed' and (check['scope']=='project' or (check.get('slug')==t['slug'] and not t['calls'])):
    for path,sha in check['inputs'].items():assert hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()==sha, 'preflight current input drift: '+path
  stage=sys.argv[3];role='reviewer' if stage=='review' else 'worker';id=len(t['calls'])+1;index=P/t['definition']['cohestra_task']/'README.md';before=read(index) if index.exists() else None;rem=int(bool(stage=='fix' and before and before['next']['reason']=='blocking_findings'));retry=stage if before and (before['stage_result']['status']=='failed' or before['next']['reason']=='stage_failed') else None
  c={'id':id,'reason':'first_start' if before is None else before['next']['reason'],'stage':stage,'execution_mode':'unattended','agent_ref':role+'-1','dispatch_evidence':None,'before':before,'dispatch':'prepared','closed':False,'result':None,'charged':{'calls':1,'remediation':rem,'retry_stage':retry},'prepared_at':now()};t['calls'].append(c);t['budget']['calls']+=1;t['budget']['remediation']+=rem
  if retry:t['budget']['retries'][retry]=t['budget']['retries'].get(retry,0)+1
  t['state']='running';t['checkpoint']['pending_call']=id
 elif op=='dispatch':
  c=t['calls'][-1];b=next(x for x in t['agents'] if x['id']==c['agent_ref']);c['dispatch']='dispatched';c['dispatch_evidence']={'agent_id':b['agent_id'],'source':'collaboration.followup_task '+b['agent_id']+' phase '+c['stage']+' call '+str(c['id'])+' accepted by tool','at':now()};d['executor']['progress']={'at':now(),'event':t['slug']+' '+c['stage']+' dispatched'}
 elif op=='close':
  c=t['calls'][-1];index=P/t['definition']['cohestra_task']/'README.md';contract=read(index);handoff=index.parent/(c['stage']+'-'+str(contract['stage_result']['round']).zfill(2)+'.md');assert handoff.exists();assert contract['contract']=='0.8' and contract['task']==t['slug'] and contract['execution_mode']=='unattended' and contract['stage_result']['stage']==c['stage'];assert not c['before'] or c['before']['stage_result']['stage']!=c['stage'] or contract['stage_result']['round']>c['before']['stage_result']['round'];assert contract['candidate']['snapshot'] or contract['candidate']['commit'];assert not(contract['next']['allowed'] and not contract['next']['stage']);assert all(k in contract for k in ['status','next','blocked']);c['closed']=True;c['result']={'contract':contract,'handoff':str(handoff),'index':str(index),'index_sha256':hashlib.sha256(index.read_bytes()).hexdigest(),'at':now(),'sync_evidence':sys.argv[3] if len(sys.argv)>3 else 'Child final reports index sync succeeded; controller reread actual index, handoff and candidate. Child completed with tools stopped.'};t['checkpoint']={'pending_call':None,'last_delivery':{'stage':c['stage'],'round':contract['stage_result']['round'],'status':contract['stage_result']['status'],'source':str(handoff)}};d['executor']['progress']={'at':now(),'event':t['slug']+' '+c['stage']+' delivery verified'}
  print(json.dumps(contract,indent=2))
 elif op=='terminal':
  state=sys.argv[3];c=t['calls'][-1];ct=c['result']['contract'];t['state']=state;t['result']={'state':state,'last_delivery':t['checkpoint']['last_delivery'],'candidate':ct['candidate'],'findings':ct.get('findings'),'acceptance':ct.get('acceptance',{'status':'unknown'}),'next':ct['next'],'human_intervention':[] if state=='completed' and ct.get('acceptance',{}).get('status')=='passed' else [sys.argv[4] if len(sys.argv)>4 else 'Flow stops before necessary fix; explicit implementation authorization/flow required.'],'source':c['result']['handoff'],'at':now()};d['executor']['progress']={'at':now(),'event':t['slug']+' '+state}
 elif op=='finish':
  assert all(t['state'] in ['completed','blocked','failed','skipped'] for t in d['tasks']);d['status']='completed';d['executor']['progress']={'at':now(),'event':'run_closed'}
 elif op=='inspect':
  print(json.dumps(d,indent=2));sys.exit()
 elif op=='report':
  d['reports'].append(sys.argv[2]);publish(d,old,'report');sys.exit()
 else:raise ValueError(op)
 publish(d,old)
